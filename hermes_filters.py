"""
hermes_filters — Single Source of Truth for Hanja and Japanese text filters.
All layers import from here instead of duplicating the dictionaries.

Usage:
    from hermes_filters import HANJA_REPLACEMENTS, JAPANESE_REPLACEMENTS, filter_text
"""

from __future__ import annotations

import re
import importlib
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger("hermes_filters")


# =============================================================================
# Hanja (Chinese character) → Korean Hangul replacements
# =============================================================================
# IMPORTANT: Sorted by descending length so longer strings match before shorter ones.
# e.g. ('这种情况', ...) must come before ('这', ...) to avoid '这种' leftover.
# =============================================================================
HANJA_REPLACEMENTS: List[Tuple[str, str]] = sorted([
    # 5글자
    ('怎么处理这个问题', '어떻게 처리할 것인가'),
    # 4글자
    ('进行中', '진행 중'),
    ('详细信息', '상세 정보'),
    ('正在处理', '진행 중'),
    ('正在进行中', '진행 중'),
    ('相关内容', '관련 내용'),
    ('问题情况', '문제 상황'),
    ('解决方案', '솔루션'),
    ('请求响应', '요청 응답'),
    ('应用系统', '애플리케이션 시스템'),
    ('系统管理', '시스템 관리'),
    ('性能优化', '성능 최적화'),
    ('故障诊断', '장애 진단'),
    ('这种情况', '이런 상황'),
    ('同相处理', '동일 처리'),
    ('残余数据', '잔존 데이터'),
    ('会怎么样', '어떻게 될까'),
    ('如下', '다음과 같다'),
    ('今天', '오늘'),
    ('今天很辛苦', '오늘 고생했다'),
    ('大棚', '온실'),
    ('找到了', '찾았다'),
    ('辛苦', '고생'),
    ('辛', '쓴'),
    ('脯', '보'),
    ('不完', '불완'),
    ('除', '제거'),
    ('他', '그'),
    ('过', '지났'),
    ('多', '많'),
    ('次', '번'),
    ('也', '도'),
    # 세션结束时
    ('结束', '종료'),
    ('时', '시'),
    ('任务', '작업'),
    ('分析', '분석'),
    ('努力', '노력'),
    # 3글자
    ('进行处理', '진행 처리'),
    ('处理测试', '처리 테스트'),
    ('常驻运行', '상주 실행'),
    ('运行状态', '실행 상태'),
    ('测试结果', '테스트 결과'),
    ('问题说明', '문제 설명'),
    ('配置管理', '설정 관리'),
    # 2글자 (한자+한자)
    ('全貌', '전모'),        # 全(전) + 貌(모습)
    ('进行', '진행'),
    ('已经', '이미'),
    ('理论', '이론'),       # 실수高频 — 理论/理论上
    ('觉得', '느끼다'),     # 实数高频 — 觉得/不知道为什么觉得
    ('处理', '처리'),
    ('常驻', '상주'),
    ('运行', '실행'),
    ('时间', '시간'),
    ('状态', '상태'),
    ('结果', '결과'),
    ('内容', '내용'),
    ('相关', '관련'),
    ('完成', '완료'),
    ('问题', '문제'),
    ('情况', '상황'),
    ('说明', '설명'),
    ('方法', '방법'),
    ('方案', '방안'),
    ('请求', '요청'),
    ('响应', '응답'),
    ('测试', '테스트'),
    ('服务', '서비스'),
    ('系统', '시스템'),
    ('应用', '애플리케이션'),
    ('数据', '데이터'),
    ('网络', '네트워크'),
    ('安全', '보안'),
    ('管理', '관리'),
    ('配置', '설정'),
    ('功能', '기능'),
    ('性能', '성능'),
    ('优化', '최적화'),
    ('监控', '모니터링'),
    ('日志', '로그'),
    ('错误', '오류'),
    ('失败', '실패'),
    ('成功', '성공'),
    ('接口', '인터페이스'),
    ('协议', '프로토콜'),
    ('传输', '전송'),
    ('连接', '연결'),
    ('存储', '스토리지'),
    ('缓存', '캐시'),
    ('负载', '부하'),
    ('带宽', '대역폭'),
    ('延迟', '지연'),
    ('部署', '배포'),
    ('更新', '업데이트'),
    ('升级', '업그레이드'),
    ('回滚', '롤백'),
    ('迁移', '마이그레이션'),
    ('备份', '백업'),
    ('恢复', '복구'),
    ('告警', '알림'),
    ('故障', '장애'),
    ('诊断', '진단'),
    ('调试', '디버그'),
    # 의존명사/단위
    ('个', '개'),
    ('中', '중'),
    ('内', '내'),
    ('外', '외'),
    ('前', '전'),
    ('后', '후'),
    ('上', '상'),
    ('下', '하'),
    ('和', '및'),
    ('分', '분'),
    ('析', '석'),
    ('部分', '부분'),
    ('空格', '공백'),
    ('前置', '전치'),
    ('复合', '복합'),
    ('漏', '누수'),
    ('泄', '샌'),   # 정보泄, 泄露(샌로) 방지
    ('万', '만'),
    ('缺', '결'),
    ('失', '실'),   # 결실(成果) <- 결失 방지
    ('少', '소'),
    ('両', '양'),
    ('別', '별'),
    ('别', '별'),
    ('単', '단'),
    ('字', '자'),
    ('符', '부호'),
    ('文', '문'),
    ('一', '일'),
    ('辺', '변'),
    ('素', '소'),
    ('要', '요'),
    ('数', '수'),
    ('多', '다'),
    ('没', '않'),     # 没다있다 → 않는다있다 (没=않다, Chinese perfective)
    ('掉', '떨어질'), # 크래시掉다 → 크래시되었다
    ('层', '층'),     # 遗层면 → 유층면
    ('遗', '유'),     # 后遗 → 후유 (遗=유, simplified 遺)
    # ('貌', '모습') 제거 — '전모'(全貌)의 일부로만 사용, 단독으로는几乎無用例
    # 실수高频 추가 한자
    ('检查', '점검'),
    ('不了', '불가'),
    ('这样', '이렇게'),
    ('那样', '저렇게'),
    ('的', '의'),
    # 기타
    ('麦克风', '마이크'),
    ('应该', '적용'),
    ('环境音', '환경음'),
    ('場合', '경우'),
    ('環境音', '환경음'),
    ('早些时候', '이른 시간'),
    ('聊了', '놀랐다'),
    ('確認', '확인'),
    ('保存', '보존'),
    ('功能', '기능'),
    ('解释', '해석'),
    ('码', '코드'),
    ('环境', '환경'),
    ('环境构', '환경 구성'),
    ('建构', '구축'),
    ('切换系统模式', '시스템 모드 전환'),
    ('切换', '전환'),
    ('模式', '방식'),
    ('强制', '강제'),
    ('替换', '치환'),
    ('速度', '속도'),
    ('优先', '우선'),
    ('逻辑', '논리'),
    ('计算机', '컴퓨터'),
    ('研究', '연구'),
    ('探索', '탐색'),
    ('策略', '전략'),
    ('模型', '모델'),
    ('训练', '훈련'),
    ('数据集', '데이터셋'),
    ('集合', '집합'),
    ('实现', '구현'),
    ('增强', '강화'),
    ('学习', '학습'),
    ('模块', '모듈'),
    ('组件', '컴포넌트'),
    ('接口', '인터페이스'),
    ('调用', '호출'),
    ('列表', '리스트'),
    ('访问', '액세스'),
    ('权限', '권한'),
    ('安全', '보안'),
    ('验证', '검증'),
    ('是', '이다'),
    # 실수高频 한자
    ('日', '일본'),
    ('部', '부분'),
    ('早', '이른'),
    ('些', '몇'),
    ('空', '공'),
    # ('格', '격'),  # 주석 — '空格'复合어优先
    ('像', '상'),
    ('聊', '놀라움'),
    ('本', '본'),
    # ('步', '보'),  # 잠정 주석 — '同步' 우선
    ('同步', '동기'),
    ('同', '동'),
    ('正', '정상적'),
    ('重', '중'),
    ('经', '경'),
    ('很', '매우'),
    ('够', '충분'),
    ('复', '복'),
    ('末', '말'),
    ('了', '다'),
    ('确', '확'),
    ('认', '인'),
    ('保', '보'),
    ('存', '존'),
    ('功', '공'),
    ('能', '능'),
    ('解', '해'),
    ('释', '석'),
    ('码', '마'),
    ('环', '환'),
    ('境', '경'),
    ('构', '구'),
    ('建', '건'),
    ('强', '강'),
    ('制', '제'),
    ('替', '대'),
    ('换', '환'),
    ('速', '속'),
    ('度', '도'),
    ('优', '우'),
    ('先', '선'),
    ('逻', '라'),
    ('辑', '집'),
    ('计', '계'),
    ('算', '산'),
    ('机', '기'),
    ('研', '연'),
    ('究', '구'),
    ('探', '탐'),
    ('索', '색'),
    ('策', '책'),
    ('略', '략'),
    ('模', '모'),
    ('型', '형'),
    ('训', '훈'),
    ('练', '연'),
    ('集', '집'),
    ('合', '합'),
    ('实', '실'),
    ('现', '현'),
    ('新增', '신규 추가'),
    ('增', '증'),
    ('学', '학'),
    ('习', '습'),
    ('块', '괴'),
    ('组', '조'),
    ('件', '건'),
    ('接', '접'),
    ('口', '구'),
    ('调', '조'),
    ('用', '용'),
    ('列', '열'),
    ('表', '표'),
    ('取', '취'),
    ('访', '방'),
    ('问', '문'),
    ('权', '권'),
    ('限', '한'),
    ('安', '안'),
    ('全', '전'),
    ('验', '험'),
    ('证', '증'),
    ('这是', '이것은'),
    ('这个', '이것'),
    ('什么', '무엇'),
    ('怎么', '어떻게'),
    ('为什么', '왜'),
    ('因为', '때문'),
    ('所以', '따라서'),
    ('万一', '万일'),
    ('残余', '잔존'),
    ('同相', '同上'),
    # 실수高频 추가 한자 (single character)
    ('等', '등'),
    ('新', '신'),
    # 架/用 관련
    ('用例', '케이스'),
    ('架', '프레임'),
    # 단일 문자
    ('例', '례'),
    ('内', '내'),
    ('有', '있'),
    # === 실수高频 추가 (v1.2.0 - 2026-04-17) ===
    # 4글자
    ('変更履歴', '변경 이력'),
    # 3글자
    ('使用者', '사용자'),
    ('協동', '협동'),
    # 5글자 (가장 먼저 매칭되어야 함)
    ('让我们做', '하자'),
    # 2글자 신규
    ('詳細', '상세'),
    ('包括', '포함'),
    ('作業', '작업'),
    ('作业', '작업'),
    ('冗長', '장황'),
    ('経路', '경로'),
    # ('最終', '최종'),  # JAPANESE에 있음 (hiragana 포함)
    ('最終', '최종'),
    ('全面', '전면'),
    ('実装', '구현'),
    ('完了', '완료'),
    ('結果', '결과'),
    ('结果', '결과'),
    ('杂', '잡'),
    ('又', '또'),         # 实数高频 — 又/以及
    ('尾', '미'),         # 实数高频 — 末尾/尾
    # 1글자
    ('変', '변'),
    ('更', '경'),
    ('詳', '상세'),
    ('包', '포'),
    ('括', '괄'),
    ('協', '협'),
    ('力', '력'),   # 협력(協力) <- 협力 방지
    ('冗', '용'),
    ('長', '장'),
    ('結', '결'),
    ('点', '점'),
    ('現', '현'),
    ('歴', '력'),
    ('録', '록'),
    ('者', '자'),
    ('作', '작'),
    ('業', '업'),
    ('径', '경'),
    ('面', '면'),
    ('話', '화'),
    ('語', '어'),
    ('提', '제'),
    ('到', '도'),
    ('讓', '우리'),
    ('我', '나'),
    ('們', '들'),
    ('做', '하자'),
    # Simplified Chinese
    ('让', '우리'),
    ('们', '들'),
    ('不会再', '다시 않을'),
    ('不会再', '다시 않을'),
    ('发生', '발생'),
    ('再', '다시'),
], key=lambda x: -len(x[0]))  # AUTOHEAL:HANJA_END

# =============================================================================
# Japanese (Hiragana/Katakana) → Korean Hangul replacements
# =============================================================================
JAPANESE_REPLACEMENTS: List[Tuple[str, str]] = sorted([
    # 5글자 이상 (가장 먼저 매칭)
    (' 日本置換', ' japan치환'),
    (' Japan치환', ' japan치환'),
    (' Japan置換', ' japan치환'),
    ('Japan어', '일본어'),
    ('Hanja', '한자'),
    (' Japan', ' japan'),
    (' japan치환', ' japan치환'),
    ('是这样', '이렇게'),
    ('那样的话', '저렇게'),
    ('を追加する', '를 추가하다'),
    ('コンтекストで', '컨텍스트에서'),
    ('过滤器', '필ilter'),
    # 4글자
    ('より狭い', '더 좁은'),
    ('狭い', ' 좁은'),
    ('追加する', '추가하다'),
    ('削除する', '삭제하다'),
    ('変更する', '변경하다'),
    ('新しい', '새로운'),
    ('古い', '오래된'),
    ('別の', '다른'),
    ('同じ', '같은'),
    ('異なる', '다른'),
    ('初めて', '처음'),
    ('終わる', '끝나다'),
    ('続ける', '계속하다'),
    ('これは', '이것은'),
    ('それは', '그것은'),
    ('あれは', '저것은'),
    ('これが', '이것이'),
    ('それが', '그것이'),
    ('文字は', '문자는'),
    ('結果的', '결과적'),
    ('實際上', '실제'),
    # 3글자
    ('どこ', '어디'),
    ('誰か', '누구'),
    ('何を', '무엇을'),
    ('なぜ', '왜'),
    ('如何', '어떻게'),
    ('開く', '열다'),
    ('閉じる', '닫다'),
    ('上位', '상위'),
    ('下位', '하위'),
    ('当真', '진짜'),
    ('以上', '이상'),
    ('以下', '이하'),
    ('関連', '관련'),
    ('存在', '존재'),
    ('発生', '발생'),
    ('処理', '처리'),
    ('状況', '상황'),
    ('解決', '해결'),
    ('方法', '방법'),
    ('開発', '개발'),
    ('環境', '환경'),
    ('情報', '정보'),
    ('確認', '확인'),
    ('理解', '이해'),
    ('学習', '학습'),
    ('評価', '평가'),
    ('準備', '준비'),
    ('説明', '설명'),
    ('期待', '기대'),
    ('有効', '유효'),
    # 2글자
    ('これ', '이것'),
    ('それ', '그것'),
    ('あれ', '저것'),
    ('ここ', '여기'),
    ('そこ', '거기'),
    ('どこ', '어디'),
    ('誰', '누구'),
    ('何', '무엇'),
    ('吾', '나'),
    # 단일 히라가나
    ('は', '는'),
    ('を', ''),
    ('で', ''),
    ('だ', ''),
    ('れ', ''),
    ('ま', ''),
    ('に', ''),
    # CJK 문장부호
    ('、', ','),
    ('が', ''),
    ('と', ''),
    ('も', ''),
    ('や', ''),
    ('へ', ''),
    ('か', ''),
    ('ね', ''),
    ('よ', ''),
    ('な', ''),
    ('わ', ''),
    ('啦', ''),
    ('ぞ', ''),
    ('り', ''),
    ('い', ''),
    ('き', ''),
    ('え', ''),
    ('る', ''),
    ('う', ''),
    ('お', ''),
    ('く', ''),
    ('け', ''),
    ('こ', ''),
    ('さ', ''),
    ('し', ''),
    ('す', ''),
    ('せ', ''),
    ('そ', ''),
    ('た', ''),
    ('ち', ''),
    ('つ', ''),
    ('て', ''),
    ('と', ''),
    ('な', ''),
    ('に', ''),
    ('ぬ', ''),
    ('ね', ''),
    ('の', ''),
    # 카타카나 — 영문 Loanwords
    ('セクション', '섹션'),
    ('ジャバ', '자바'),
    (' кан', '칸'),
    ('システム', '시스템'),
    ('フィルター', '필터'),
    ('フィルタ', '필터'),
    ('パターン', '패턴'),
    ('置换', '치환'),
    ('インライン', '인라인'),
    ('レイヤー', '레이어'),
    ('メソッド', '메서드'),
    ('ファンクション', '펑션'),
    ('.function', '펑션'),
    ('クラス', '클래스'),
    ('オブジェクト', '오브젝트'),
    ('インターフェース', '인터페이스'),
    ('プロトコル', '프로토콜'),
    ('データベース', '데이터베이스'),
    ('サーバー', '서버'),
    ('クライアント', '클라이언트'),
    ('ネットワーク', '네트워크'),
    ('アプリケーション', '애플리케이션'),
    ('プログラム', '프로그램'),
    ('プロセス', '프로세스'),
    ('スレッド', '스레드'),
    ('メモリ', '메모리'),
    ('ストレージ', '스토리지'),
    ('キャッシュ', '캐시'),
    ('リクエスト', '요청'),
    ('レスポONSE', '응답'),
    ('エラー', '오류'),
    ('デバッグ', '디버그'),
    ('テスト', '테스트'),
    ('ユーザー', '사용자'),
    ('管理员', '관리자'),
    ('バージョン', '버전'),
    ('ビルド', '빌드'),
    ('コンパイル', '컴파일'),
    ('エクスポート', '익스포트'),
    ('インポート', '임포트'),
    ('ターゲット', '타깃'),
    ('ソース', '소스'),
    ('プロジェクト', '프로젝트'),
    ('ドキュメント', '문서'),
    ('ワークスペース', '워크스페이스'),
    (' компонент', '컴포넌트'),
    (' компонента', 'компонента'),
    ('コンポーネント', '컴포넌트'),
    ('コンテキスト', '컨텍스트'),
    ('テキスト', '텍스트'),
    (' 管理', '관리'),
    ('開い', '열린'),
    ('閉じ', '닫힌'),
    ('変更多', '변경 많음'),
    ('行の', '행의'),
    ('既に', '이미'),
    ('他の', '다른'),
    ('結果', '결과'),
    ('前', '전'),
    ('後', '후'),
    ('具体', '구체'),
    ('基本的', '기본적'),
    ('特殊的', '특수적'),
    ('一般的な', '일반적인'),
    (' 동일한', '동일한'),
    ('ような', '와 같은'),
    ('換字', '치환'),
    ('置換', '치환'),
    (' 日本', ' 日本'),
    ('日本', '일본'),
    # Katakana 추가
    ('ロック', '록'),
    ('ック', ''),
    ('プロ', '프로'),
    ('ザー', '자'),
    ('ド', '드'),
    ('テ', '테'),
    ('プ', '프'),
    (chr(0x30CB), ' japan'),
    ('です', '입니다'),
    # Latin/Кириллица 혼입
    (' надо', ' 필요'),
    ('ред', '레드'),
    (' Админ', '관리자'),
    (' админ', '관리자'),
    (' нео', '정보'),
    # 동사 어미/인사
    (' IKAN', ''),
    (' simasuu', ' 합니다'),
    (' ikasuru', ' 할 수 있다'),
    ('nasul', ''),
    ('nakamura', '나카무라'),
    (' iku', ' 간다'),
    # === 실수高频 추가 (v1.2.0 - 2026-04-17) ===
    # Japanese phrases
    ('一つの', '하나'),
    ('詳しく', '상세하게'),
    # Individual hiragana (for fragment cleanup)
    ('ば', ''),
    ('啊', ''),   # 중국어 감탄사 제거
], key=lambda x: -len(x[0]))  # AUTOHEAL:JAPANESE_END

# =============================================================================
# Regex patterns
# =============================================================================
HANJA_PATTERN = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
HIRAGANA_PATTERN = re.compile(r'[\u3040-\u309f\u30a0-\u30ff]')

# Fallback: remove ANY remaining CJK/Kana characters not caught by dictionary.
# This ensures 100% cleanup even for characters missing from HANJA_REPLACEMENTS.
_REMOVE_REMAINING_CJK = re.compile(
    r'[\u4e00-\u9fff'   # CJK Unified Ideographs
    r'\u3400-\u4dbf'    # CJK Extension A
    r'\uf900-\ufaff'    # CJK Compatibility
    r'\u3040-\u309f'    # Hiragana
    r'\u30a0-\u30ff]'   # Katakana
)


# =============================================================================
# Core filter function — used by all layers
# =============================================================================
def filter_text(text: str) -> str:
    """
    Apply Hanja and Japanese replacements to text.
    Code blocks (```...``` and `...`) are protected and not filtered.
    Returns the filtered text.
    """
    if not text:
        return text

    # ---- protect code blocks ----
    placeholders: dict[str, str] = {}
    counter = [0]

    def _ph(value: str) -> str:
        key = f"\x00FILTER_PH{counter[0]}\x00"
        counter[0] += 1
        placeholders[key] = value
        return key

    text = re.sub(r'(```[\s\S]*?```)', lambda m: _ph(m.group(0)), text)
    text = re.sub(r'(`[^`]+`)', lambda m: _ph(m.group(0)), text)

    # ---- Hanja replacements ----
    for hanja, hangul in HANJA_REPLACEMENTS:
        text = text.replace(hanja, hangul)

    # ---- Japanese replacements ----
    for jp, kr in JAPANESE_REPLACEMENTS:
        text = text.replace(jp, kr)

    # ---- fallback: delete any remaining CJK/Kana not covered by dictionaries ----
    text = _REMOVE_REMAINING_CJK.sub('', text)

    # ---- restore code blocks ----
    for key, value in placeholders.items():
        text = text.replace(key, value)

    return text


# =============================================================================
# Auto-heal: dynamically add leaked Hanja/Japanese to source file + reload
# Used by B方式 retry logic in gateway/run.py
#
# Improves over v1:
# - Japanese auto-heal now tries to extract Korean reading (like Hanja)
# - Persistent log (~/.hermes/auto_heal_log.json) survives gateway restarts
# =============================================================================

import json
from datetime import datetime

# --- Persistent auto-heal log (survives gateway restarts) ---
_AUTO_HEAL_LOG_PATH = Path.home() / ".hermes" / "auto_heal_log.json"

def _load_auto_heal_log() -> dict:
    """Load persistent auto-heal log, create if absent."""
    if _AUTO_HEAL_LOG_PATH.exists():
        try:
            with open(_AUTO_HEAL_LOG_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"[Auto-heal] Failed to load log {e}, starting fresh")
    return {"hanja": {}, "japanese": {}}

def _save_auto_heal_log(log: dict) -> None:
    """Persist auto-heal log to disk."""
    _AUTO_HEAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_AUTO_HEAL_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

_auto_heal_log: dict = _load_auto_heal_log()   # cached in-process
_AUTO_HEAL_KNOWN: set = set()                   # dedup within process lifetime

# Pre-populate _AUTO_HEAL_KNOWN from persistent log so we don't re-process
for kind, entries in [("hanja", _auto_heal_log.get("hanja", {})),
                      ("japanese", _auto_heal_log.get("japanese", {}))]:
    for ch in entries:
        _AUTO_HEAL_KNOWN.add(f"{kind}:{ch}")


def _extract_reading_from_dict(char: str) -> str | None:
    """한글 읽기를 기존 HANJA_REPLACEMENTS 복합어에서 추출 시도."""
    for hanja, hangul in HANJA_REPLACEMENTS:
        if char in hanja and len(hanja) > 1:
            idx = hanja.index(char)
            if idx < len(hangul):
                return hangul[idx]
    return None


def _extract_jp_reading_from_dict(char: str) -> str | None:
    """한국어 읽기를 기존 JAPANESE_REPLACEMENTS 복합어에서 추출 시도."""
    for jp, hangul in JAPANESE_REPLACEMENTS:
        if char in jp and len(jp) > 1:
            idx = jp.index(char)
            if idx < len(hangul):
                return hangul[idx]
    return None


def auto_heal_filter(
    remaining_hanja_chars: set[str],
    remaining_jp_chars: set[str],
) -> None:
    """
    Detect and auto-add unknown Hanja/Japanese chars to the source file.

    1. Check persistent log to skip already-healed chars
    2. Try to extract Korean reading from existing compound words
    3. Append new entries to hermes_filters.py (in sorted position)
    4. Persist new entries to auto_heal_log.json
    5. importlib.reload so changes take effect immediately
    """
    global HANJA_REPLACEMENTS, JAPANESE_REPLACEMENTS

    module_path = __file__
    new_hanja: list[tuple[str, str]] = []
    new_jp: list[tuple[str, str]] = []
    timestamp = datetime.now().isoformat(timespec="seconds")

    # --- Hanja: try to find reading, else '?' ---
    for ch in remaining_hanja_chars:
        key = f"hanja:{ch}"
        if key in _AUTO_HEAL_KNOWN:
            continue
        _AUTO_HEAL_KNOWN.add(key)
        reading = _extract_reading_from_dict(ch)
        fallback = reading if reading else "?"
        new_hanja.append((ch, fallback))

        # Persist to log
        _auto_heal_log.setdefault("hanja", {})[ch] = {
            "r": fallback,
            "ts": timestamp,
            "v": reading is not None,   # auto-verified if reading was found
        }
        logger.info(f"[Auto-heal] Hanja '{ch}' → '{fallback}' "
                    f"({'auto' if reading else '?, please verify'})")

    # --- Japanese: try to find reading, else '?' (same as Hanja now) ---
    for ch in remaining_jp_chars:
        key = f"japanese:{ch}"
        if key in _AUTO_HEAL_KNOWN:
            continue
        _AUTO_HEAL_KNOWN.add(key)
        reading = _extract_jp_reading_from_dict(ch)
        fallback = reading if reading else "?"
        new_jp.append((ch, fallback))

        # Persist to log
        _auto_heal_log.setdefault("japanese", {})[ch] = {
            "r": fallback,
            "ts": timestamp,
            "v": reading is not None,
        }
        logger.info(f"[Auto-heal] Japanese '{ch}' → '{fallback}' "
                    f"({'auto' if reading else '?, please verify'})")

    if not new_hanja and not new_jp:
        return

    # --- Persist log to disk ---
    _save_auto_heal_log(_auto_heal_log)

    # --- Read source, append new entries, rewrite ---
    with open(module_path, encoding="utf-8") as f:
        source = f.read()

    lines = source.splitlines()

    def _insert_entry(before_marker: str, entries: list[tuple[str, str]]) -> list[str]:
        """Insert new tuple entries right before the closing bracket."""
        result = []
        inserted = False
        for line in reversed(lines):
            if not inserted and before_marker in line:
                indent = " " * 4
                for hanja, hangul in entries:
                    result.append(f"{indent}('{hanja}', '{hangul}'),   # auto-heal")
                result.append(line)
                inserted = True
            else:
                result.append(line)
        return result[::-1]

    # Insert Hanja entries before the closing of HANJA_REPLACEMENTS
    if new_hanja:
        lines = _insert_entry("# AUTOHEAL:HANJA_END", new_hanja)
    ('接', '인'),   # auto-heal
    ('直', '?'),   # auto-heal
    ('仿', '?'),   # auto-heal
    ('人', '?'),   # auto-heal
    ('服', '서'),   # auto-heal
    ('客', '?'),   # auto-heal
    ('間', '?'),   # auto-heal
    ('模', '모'),   # auto-heal
    ('牙', '?'),   # auto-heal
    ('定', '?'),   # auto-heal
    ('蓝', '?'),   # auto-heal
    ('設', '?'),   # auto-heal
    ('复', '구'),   # auto-heal
    ('合', '합'),   # auto-heal
    ('字', '?'),   # auto-heal
    ('汉', '?'),   # auto-heal
    ('增', '강'),   # auto-heal
    ('生', '생'),   # auto-heal
    ('新', '데'),   # auto-heal
    ('再', ' '),   # auto-heal
    ('发', '발'),   # auto-heal

    # Insert Japanese entries before the closing of JAPANESE_REPLACEMENTS
    if new_jp:
        lines = _insert_entry("# AUTOHEAL:JAPANESE_END", new_jp)
    ('の', '른'),   # auto-heal
    ('ら', '?'),   # auto-heal
    ('カ', '?'),   # auto-heal
    ('ひ', '?'),   # auto-heal
    ('が', '이'),   # auto-heal
    ('ナ', '?'),   # auto-heal
    ('な', '인'),   # auto-heal
    ('タ', '페'),   # auto-heal

    with open(module_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # --- Reload so new entries are live ---
    import hermes_filters as _hm
    importlib.reload(_hm)
    HANJA_REPLACEMENTS = _hm.HANJA_REPLACEMENTS
    JAPANESE_REPLACEMENTS = _hm.JAPANESE_REPLACEMENTS
    logger.info("[Auto-heal] hermes_filters reloaded — new entries live")