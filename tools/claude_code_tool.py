"""
Claude Code Tool — Hermes Gateway 연동

!cc <메시지> 명령으로 Claude Code CLI subprocess를 호출합니다.
- 세션 유지: 채널별 session_id 저장 (cc_sessions.json)
- 컨텍스트 전달: hot.md(볼트 상태) + 최근 Hermes 대화 → --append-system-prompt
- 세션 만료 자동 복구: session_id 무효 시 새 세션으로 재시도
"""

import json
import logging
import re
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# --- 경로 설정 ---
_SESSIONS_FILE = Path.home() / ".hermes" / "data" / "cc_sessions.json"
_HOT_CACHE_PATH = Path("/Users/shlee/leesh/mynotes/06_Metadata/hot.md")
_VAULT_DIR = "/Users/shlee/leesh/mynotes"
_SUBPROCESS_TIMEOUT = 300  # 5분

_lock = threading.Lock()


# ---------------------------------------------------------------------------
# 세션 관리
# ---------------------------------------------------------------------------

def _load_sessions() -> dict:
    if _SESSIONS_FILE.exists():
        try:
            return json.loads(_SESSIONS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_sessions(sessions: dict) -> None:
    _SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SESSIONS_FILE.write_text(
        json.dumps(sessions, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def reset_session(session_key: str) -> None:
    """채널 세션 초기화."""
    with _lock:
        sessions = _load_sessions()
        sessions.pop(session_key, None)
        _save_sessions(sessions)


# ---------------------------------------------------------------------------
# Hot Cache 연동
# ---------------------------------------------------------------------------

def _load_hot_cache() -> str:
    """hot.md 본문 반환 (frontmatter 제외)."""
    if not _HOT_CACHE_PATH.exists():
        return ""
    text = _HOT_CACHE_PATH.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    return parts[2].strip() if len(parts) >= 3 else text.strip()


def _update_hot_cache_hermes_section(recent_msgs: list) -> None:
    """hot.md의 '다음 세션 컨텍스트' 섹션 내용을 최신 Hermes 대화로 교체합니다."""
    if not _HOT_CACHE_PATH.exists() or not recent_msgs:
        return
    try:
        content = _HOT_CACHE_PATH.read_text(encoding="utf-8")
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        summary_lines = "\n".join(f"- {m}" for m in recent_msgs[-5:])
        new_section_body = f"[Hermes Slack 대화 - {now}]\n{summary_lines}\n"

        target = "## 다음 세션 컨텍스트"
        if target not in content:
            content += f"\n{target}\n{new_section_body}"
        else:
            idx = content.index(target)
            # 다음 ## 섹션 또는 파일 끝까지를 섹션 범위로 확정
            next_sec = content.find("\n## ", idx + len(target))
            before = content[:idx]
            after = content[next_sec:] if next_sec != -1 else ""
            # 섹션 전체를 새 내용으로 교체 (누적 없음)
            content = before + target + "\n\n" + new_section_body + after

        _HOT_CACHE_PATH.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.debug("hot.md Hermes 섹션 업데이트 실패: %s", e)


# ---------------------------------------------------------------------------
# 메인 실행
# ---------------------------------------------------------------------------

def run(
    session_key: str,
    prompt: str,
    recent_msgs: Optional[list] = None,
) -> tuple:
    """Claude Code subprocess 실행. (response_text, session_id) 반환."""

    # 1. hot.md에 Hermes 컨텍스트 기록
    if recent_msgs:
        _update_hot_cache_hermes_section(recent_msgs)

    # 2. hot.md 읽어 시스템 컨텍스트 구성
    hot_cache = _load_hot_cache()
    system_ctx = (
        f"[Obsidian 볼트 컨텍스트 - 최근 세션 정보]\n{hot_cache}"
        if hot_cache
        else ""
    )

    # 3. 저장된 세션 ID 조회
    with _lock:
        sessions = _load_sessions()
    session_id = sessions.get(session_key)

    # 4. subprocess 실행 (세션 resume 또는 신규)
    response, new_session_id = _execute(prompt, session_id, system_ctx)

    # session_id 만료 시 새 세션으로 재시도
    if new_session_id is None and session_id:
        logger.info("!cc: session_id 만료 — 새 세션으로 재시도")
        response, new_session_id = _execute(prompt, None, system_ctx)

    # 5. 세션 ID 저장
    if new_session_id:
        with _lock:
            sessions = _load_sessions()
            sessions[session_key] = new_session_id
            _save_sessions(sessions)

    return response, new_session_id


def _execute(
    prompt: str,
    session_id: Optional[str],
    system_ctx: str,
) -> tuple:
    """실제 subprocess 호출. (response_text, session_id | None) 반환."""
    cmd = ["claude"]
    if session_id:
        cmd += ["--resume", session_id]
    cmd += [
        "-p", prompt,
        "--output-format", "json",
        "--permission-mode", "acceptEdits",
    ]
    if system_ctx:
        cmd += ["--append-system-prompt", system_ctx]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
            cwd=_VAULT_DIR,
        )
    except subprocess.TimeoutExpired:
        return "⏰ Claude Code 응답 시간 초과 (5분)", None

    if result.returncode != 0:
        # session_id 만료 신호
        return None, None

    try:
        data = json.loads(result.stdout)
        new_id = data.get("session_id") or session_id
        text = data.get("result") or "응답 없음"
        return text, new_id
    except json.JSONDecodeError:
        # 파싱 실패 시 raw stdout 반환
        return (result.stdout[:2000] or "응답 없음"), session_id
