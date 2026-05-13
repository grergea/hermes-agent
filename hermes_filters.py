"""
hermes_filters — Single Source of Truth for Hanja and Japanese text filters.
All layers import from here instead of duplicating the dictionaries.

Usage:
    from hermes_filters import HANJA_REPLACEMENTS, JAPANESE_REPLACEMENTS, filter_text

# ─── 복합어 등록 가이드 ────────────────────────────────────────────────────────
#
# [원칙] 긴 것부터 먼저 매칭 (sorted by descending length, 자동 적용)
#   → ('进行中', ...) 를 ('进行', ...) 보다 먼저 등록하지 않아도 됨.
#   → sorted() 가 자동 정렬하므로 순서 신경 쓸 필요 없음.
#
# [어디에 등록하나?]
#   - 순수 한자(CJK U+4E00–U+9FFF) → HANJA_REPLACEMENTS
#   - 순수 가나(U+3040–U+30FF) → JAPANESE_REPLACEMENTS
#   - CJK + 가나 혼합(예: 作り) → HANJA_REPLACEMENTS
#     이유: HANJA 필터가 먼저 실행됨. JAPANESE에 넣으면 CJK 부분이
#     먼저 단독 치환되어 혼합 복합어가 매칭되지 않음.
#
# [공백 처리]
#   앞 단어와 자연스럽게 이어지려면 번역문 앞에 공백 포함:
#     ('要知道', ' 알아야 한다')   ← O  투자자 알아야 한다
#     ('要知道', '알아야 한다')    ← X  투자자알아야 한다
#   단, 복합어 자체로 완성되는 경우(効果 → 효과)는 공백 불필요.
#
# [단일 문자 등록 주의]
#   단일 CJK 1글자는 가급적 등록 금지. 다른 단어의 일부와 충돌 가능.
#   ex) ('中', '중') 등록 시 "中学" → "중학"이 되어야 하지만 잘못 치환될 수 있음.
#   → 2글자 이상 복합어로만 등록하고, 단독 1글자가 남으면 auto_heal에 위임.
#
# [auto_heal 자동 학습]
#   LLM 응답에서 미등록 CJK/가나가 발견되면 auto_heal_filter() 가 자동으로
#   2글자 이상 복합어를 추출해 AUTOHEAL:HANJA_END / AUTOHEAL:JAPANESE_END
#   마커 위에 새 항목을 삽입함. 삽입된 항목은 다음 응답부터 즉시 적용.
#
# [v:false 단독 가나]
#   번역값이 '' (빈 문자열) 인 항목 → 치환이 아닌 삭제.
#   LLM이 한국어 문장 안에 단독으로 가나 1글자를 끼워 넣는 경우
#   (예: "설정ら" → "설정") 의미 없는 잔류 가나를 제거하기 위한 조치.
#
# ──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
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
    # 12글자
    ('请确认一下输出长度是否足够', '출력 길이가 충분한지 확인해 주세요'),
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
    # 한글+한자 혼합 복합어 (공백 삽입으로 이름처럼 읽히는 현상 방지)
    ('이現', '이 현'),       # 이現 → 이현(이름)처럼 읽힘 방지
    ('이现', '이 현'),
    # 2글자 (한자+한자)
    ('全貌', '전모'),        # 全(전) + 貌(모습)
    ('兴趣', '흥미'),        # Chinese simplified — 어떤 분야에흥미이 있으신가요?
    ('興趣', '흥미'),        # Chinese traditional
    ('出现', '출현'),
    ('出現', '출현'),
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
    ('末尾', '끝부분'),    # 파일末尾에 주요 누락 항목들을 추가합니다.
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
    ('大多数', '대부분'),  # auto-heal: 158행 Most →大部分
    ('空的', '비어 있는'),  # auto-heal: 192행 空的 → 저자명 맥락
    ('数', '수'),
    ('多', '다'),
    ('没', '않'),     # 没다있다 → 않는다있다 (没=않다, Chinese perfective)
    ('掉', '떨어질'), # 크래시掉다 → 크래시되었다
    ('层', '층'),     # 遗层면 → 유층면
    ('遗', '유'),     # 后遗 → 후유 (遗=유, simplified 遺)
    ('意譯', '의역'),  # auto-heal: 意譯했으나 → 의역했지만
    ('意', '의'),     # 意譯 → 의역 (의미의 의)
    # ('貌', '모습') 제거 — '전모'(全貌)의 일부로만 사용, 단독으로는几乎無用例
    # 실수高频 추가 한자
    ('检查', '점검'),
    ('不了', '불가'),
    ('这样', '이렇게'),
    ('那样', '저렇게'),
    ('的', '의'),
    # 기타
    ('麦克风', '마이크'),
    ('应该', '해야'),
    ('环境音', '환경음'),
    ('場合', '경우'),
    ('環境音', '환경음'),
    ('早些时候', '이른 시간'),
    ('聊了', '얘기했다'),
    ('確認', '확인'),
    ('保存', '보존'),
    ('解释', '해석'),
    ('码', '코드'),
    ('环境', '환경'),
    ('环境构', '환경 구성'),
    ('建构', '구축'),
    ('切换系统模式', '시스템 모드 전환'),
    ('切换', '전환'),
    ('模式', '방식'),
    ('强制', '강제'),
    ('限制', '제한'),
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
    ('调用', '호출'),
    ('列表', '리스트'),
    ('访问', '액세스'),
    ('权限', '권한'),
    ('验证', '검증'),
    ('是', '이다'),
    # 실수高频 한자
    ('日', '일'),
    ('部', '부분'),
    ('早', '이른'),
    ('些', '몇'),
    ('空', '공'),
    # ('格', '격'),  # 주석 — '空格'复合어优先
    ('像', '상'),
    ('聊', '잡담'),
    ('本', '본'),
    # ('步', '보'),  # 잠정 주석 — '同步' 우선
    ('同步', '동기'),
    ('同一个', '동일한'),   # 同一个条件 → 동일한 조건
    ('条件', '조건'),       # 条件 (Simplified Chinese)
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
    ('万一', '만일'),
    ('残余', '잔존'),
    ('同相', '동일'),
    # 실수高频 추가 한자 (single character)
    # 3글자 신규
    ('직职能', '직능'),         # 직职能 수행 → 직능 수행 (중복 방지)
    ('有效性', '유효성'),       # 등록 전에 피드有效性 확인
    # 3글자 신규 (2026-05-06-blog-log)
    ('联想到', '관련해서'),     # 직접联想到야만 → 직접 관련해서야만
    ('记载', '기록'),           # Process 단계에 Phase 2 두 번 반복記載
    # 2글자 신규 (2026-05-06-blog-log)
    ('政治', '정치'),           # 政治과 경제의 얽힌 관계 / 政治적 발언
    ('语气', '어투'),           # 단정语气 → 단정 어투
    ('根基', '원인'),           # 인플레이션根基 → 인플레이션 원인
    ('計略', '계략'),           # 선거計略 → 선거 계략
    ('困境', '곤경'),           # 금리困境 → 금리 곤경
    # 2글자 신규 (기존 유지)
    ('职能', '직능'),           # 직职能 수행
    ('主席', '의장'),           # 연준主席 물러나지 않겠다
    ('共和党', '공화당'),       # 공화당议员 ETF
    ('民主党', '민주당'),       # 민주당議員 ETF (미국 민주당)
    ('议员', '위원'),           # 미국议员 ETF — 하원/상원 의원
    ('框架', '프레임워크'),     # 법적框架 속에서의 전략적 발언
    ('覆盖', '커버'),           # 필터 사전覆盖率高 → 커버율
    ('困难', '곤란'),           # 프로그래밍적으로 파싱困难
    ('率', '율'),               # 覆盖率 → 커버율
    ('等', '등'),
    ('新', '신'),
    # 架/用 관련
    ('用例', '케이스'),
    ('架', '프레임'),
    # 단일 문자
    ('例', '례'),
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
    ('发生', '발생'),
    ('再', '다시'),
    # === 한자어 자연번역 추가 (2026-04-24) ===
    # 3글자 (가장 먼저 매칭)
    ('候选人', '후보자'),   # 候+选+人
    # 2글자
    ('获取', '얻기'),       # 获取方法 → 얻기 방법
    ('获得', '얻다'),       # 获取(huòdé)과 혼동 방지
    ('候选', '후보'),       # 候+选 → 후보
    # 단독 문자 (복합어 일부로만 사용되지만 안전장치)
    ('候', '헛'),           # 候选의 候
    ('获', '획'),           # 获取/获得的 获
    ('得', '얻'),           # 获取의 得
    ('选', '선'),           # 候选/选择的 选
    # === v:false 복합어 패턴 (2026-04-22) ===
    ('汉字', '한자'),       # Chinese: 漢字
    ('設定', '설정'),       # settings
    ('蓝牙', '블루투스'),    # Bluetooth (Chinese)
    ('直接', '직접'),       # directly
    # 신규 추가 (2026-04-22) — 문제 패턴 대응
    ('包含', '포함'),       # 包含内容 → 포함 내용
    ('條件', '조건'),       # Traditional Chinese: 條件
    ('作成', '작성'),       # 作成完了 → 작성 완료
    # === v:false 단독 문자 (2026-04-22) ===
    ('汉', '한'),   # 汉字의 汉
    ('設', '설'),   # 設定의 設
    ('進行', '진행'),   # 복합어 — 진행
    ('技術', '기술'),   # 복합어 — 기술
    ('問題', '문제'),   # 복합어 — 문제
    ('認識', '인식'),   # 복합어 — 인식
    ('明示', '명시'),   # 복합어 — 명시
    ('生效', '적용'),   # 복합어 — 적용
    ('定', '정'),   # 設定의 定
    ('直', '직'),   # 直接의 直
    ('仿', '방'),   # 模仿의 仿
    ('人', '인'),
    ('間', '간'),
    ('客', '객'),
    # === Taiwan 통신 용어 (2026-04-29) ===
    ('送信', '전송'),       # URL 적용 후 요청送信
    # === 자연번역 개선 (2026-04-29) ===
    ('孤立的', '고립된'),   # 깔끔하게孤立的였습니다 → 깔끔하게 고립된
    ('先を急いで', '급하게'),   # implementations先，急いで → implementations implementations 급하게 (compound 先>
    ('没有问题', '문제없다'),   # 스킬 설정没有问题 → 스킬 설정 문제없다
    ('関連性と', '관련성과'),   # 관련성과 접속 (と→과)
    ('関連性', '관련성'),   # 관련 + 性 (관련보다 먼저 매칭)
    ('接客', '접객'),       # 接+客 (U+5BA2) - customer service
    (' Related性と', '관련성과'),   # 관련성과 접속 ( Related성 already replaced → '관련성' + '과')
    ('中心', '센터'),
    ('其余', '기타'),
    ('不符合', '일치하지 않는'), # Facts不符合 — 정치적 발언 가능성 높다
    ('水准', '수준'),           # 오자 수정: 水槽 → 수준 (Chinese: standard/level)
    # === 금융/시사 복합어 (2026-05-07) ===
    # 3글자
    ('要知道', ' 알아야 한다'),   # 투자자要知道 → 투자자 알아야 한다
    # CJK+가나 혼합 복합어 (HANJA가 먼저 실행되므로 여기에 등록)
    ('作り', ' 조성'),           # 분위기作り → 분위기 조성 (作=U+4F5C, CJK)
    # 2글자
    ('効果', '효과'),           # 정책効果 → 정책효과 (일본식 効)
    ('宣言', '선언'),           # 공동 승리宣言 → 공동 승리선언
    ('防止', '방지'),           # 선반영防止 → 선반영방지
    # 1글자
    ('桌', '테이블'),           # 협상桌 → 협상테이블 (중국어 탁자)
    ('系', '계'),               # 하메네이 系 → 하메네이 계 (계열)
    ('費', '비'),               # 물류費 → 물류비
    ('効', '효'),               # 効果의 効 단독
    ('绰', '수록'),             # 갈绰 → 갈수록 (LLM 오출력 패턴)
    # log ctx 기반 추가 (2026-05-08)
    ('其中どれ感兴趣ですか', '그 중 어느 것에 관심이 있으신가요'),  # 9글자 최우선 — 전체 복합문 처리
    ('感兴趣ですか', '관심이 있으신가요'),   # CJK+kana — HANJA에서 먼저 처리 (7글자)
    ('興味がありませんか', '흥미 없으신가요'),   # 일본어 興味+がありませんか — 부정 의문 (7글자)
    ('感兴趣', '관심이 있는'),              # 感만 남는 문제 해결 (3글자)
    ('文件', '파일'),                       # 중국어 파일 — 첨부싷고 싶은 文件 경로
    # AUTOHEAL:HANJA_END
    ('其中', '그중'),   # 중국어 "그 중에서" — 9글자 복합어가 먼저 매칭, 단독 출현 시 '그중'으로 번역
    ('興味', '흥미'),   # 일본어 興味(興趣와 혼용) — 한국어 '흥미'
    # --- 올바른 단일 문자 매핑 (정리 후 유지) ---
    ('合', '합'),   # 합계, 결합
    ('確', '확'),   # 확인
    ('認', '인'),   # 인식
    ('困', '곤'),   # 곤경
    ('出', '출'),   # 출력
    ('譯', '역'),   # 번역
    ('共', '공'),   # 공통
    ('员', '원'),   # 구성원 (간체자 員)
    ('党', '당'),   # 정당 (간체자 黨)
    ('席', '석'),   # 의석
    ('性', '성'),   # 성질
    ('使', '사'),   # 사용
    ('興', '흥'),   # 흥미, 흥분
    ('趣', '취'),   # 취미, 흥취
    ('繁', '번'),   # 번성, 번영
    ('体', '체'),   # 체력, 단체 (간체자 體)
    ('条', '조'),   # 조건, 조항 (간체자 條)
    ('同', '동'),   # 동일
    ('含', '함'),   # 포함
    ('護', '호'),   # 보호, 호위
    ('條', '조'),   # 조건, 조항 (전통 한자)
    ('思', '사'),   # 의사, 사념
    ('完', '완'),   # 완료
    ('作', '작'),   # 작업
    ('示', '시'),   # 시범, 지시
    ('関', '관'),   # 관계, 관련
    ('題', '제'),   # 문제, 제목
    ('識', '식'),   # 인식, 지식
    ('発', '발'),   # 발생, 발전
    ('浮', '부'),   # 부동, 부력
    ('宙', '주'),   # 우주
    ('連', '연'),   # 연결, 연속
    ('測', '측'),   # 측정, 추측
    ('技', '기'),   # 기술, 기능
    ('術', '술'),   # 기술, 술법
    ('進', '진'),   # 진행, 진출
    ('牙', '아'),   # 상아
    ('を返さない場合です', '반환하지 않는 경우입니다'),  # を 포함 전체 복합어 (5글자, 먼저 매칭)
    ('返さない場合です', '반환하지 않는 경우입니다'),   # Slack API가 정확한 MIME 타입を返さない場合입니다 — 혼합 compound, HANJA에서 먼저 처리
    ('返さない', '반환하지 않는'),  # 단독 출현 처리
    ('重点的に', '집중적으로'),   # 해당 시간대의 로그를重点的に 확인해볼 수 있습니다
    ('回过头来', '돌이켜보면'),   # 중국어 "다시 생각해보면" — ctx: 협상回过头来 → 협상 결렬로
    ('混合', '혼합'),   # 혼합复合어이므로 → 혼합 복합어이므로
    ('复合어', '복합어'),   # 두 건とも复合어優先 원칙에 따라
    ('優先', '우선'),   # 複合어優先 → 복합어 우선 (とも复合어優先 처리)
    ('重点', '중점'),   # 중국어/일본어 "중점, 핵심" — 重点的に의 핵심 단어
    ('激怒', '격노'),   # 중국어/일본어 "격노, 분노" — ctx: 데激怒 → 에 분노한
], key=lambda x: -len(x[0]))

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
    ('过滤器', '필터'),
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
    ('ぬ', ''),
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
    ('コード', '코드'),     # code
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
    ('ですか', '인가요'),  # 의문형 — ですか? → 인가요? (です→입니다 보다 길어 먼저 매칭)
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
    # === 자연번역 개선 (2026-04-29) ===
    ('自動化', '자동화'),    # automation 완성
    ('急いで', '급하게'),   # 단독 uses
    ('バランス取れています', '균형이 잘 맞습니다'),   # 전체 표현
    ('バランス取れ', '균형이 잘 맞'),   # 균형이 잘 맞습니다 (중간)
    ('次回', '다음'),       # 次回 개선 작업 시 → 다음 개선 작업 시
    ('前面的', '앞의'),     # {goal_text}前面的 → {goal_text}앞의
    ('宣称', '선언'),       #宣称前: verification → 선언 전: verification
    ('使用', '사용'),       # 단독使用时만 → 단독 사용시만
    ('模式下', '모드에서'),  # 줄 번호 보기模式下 → 줄 번호 보기 모드에서
    ('预处理', '사전에 처리'), # gateway预处理 → gateway 사전에 처리
    ('非비전', '비전이 아닌'), # 非비전 모델 → 비전이 아닌 모델
    ('参照', '참조'),       # config.yaml参照 → config.yaml 참조
    # ('非', '비'),           # 비 prefix (复合어 처리)
    ('取れ', '유지'),       # 균형取れ → 균형 유지 (fallback)
    # === 금융/시사 일본어 (2026-05-07) ===
    # === v:false 단독 가나 삭제 (2026-04-22) ===
    # 번역값이 '' → 치환이 아닌 삭제. 한국어 문장 안에 단독으로 끼어드는
    # 의미 없는 가나 1글자를 제거. (예: "설정ら" → "설정")
    ('ら', ''),
    ('カ', ''),
    ('ひ', ''),
    ('ナ', ''),
    ('タ', ''),
    # AUTOHEAL:JAPANESE_END
    ('したい', '하고 싶은'),   # 첨부したい 파일
    ('したいファイル', '하고 싶은 파일'),   # 첨부したいファイル 경로
    ('ファイル', '파일'),   # 첨부したいファイル 경로 — 파일로 치환
    ('どれ', '어느'),   # auto-heal:compound
    ('とも', '모두'),   # 두 건とも复合어優先 — Japanese particle "both/all"
    # 이하: AUTOHEAL 이전 ''(삭제)와 충돌하지 않는 가타카나만 유지
    # (う て き い ま を れ す 는 AUTOHEAL 이전 삭제 항목과 충돌 → 제거)
    ('ょ', '요'),   # auto-heal (이전 없음)
    ('ン', '응'),   # auto-heal (이전 없음)
    ('ス', '스'),   # auto-heal (이전 없음)
    ('バ', '바'),   # auto-heal (이전 없음)
    ('ラ', '라'),   # auto-heal (이전 없음)
    ('コ', '코'),   # auto-heal (이전 없음)
    ('ー', ''),     # auto-heal 장음부호 단독 → 삭제 (이전 없음)
    ('ュ', '유'),   # auto-heal 소문자 ュ (이전 없음)
    ('リ', '리'),   # auto-heal (이전 없음)
    ('キ', '키'),   # auto-heal (이전 없음)
    ('メ', '메'),   # auto-heal (이전 없음)
    ('ト', '토'),   # auto-heal (이전 없음)
    ('エ', '에'),   # auto-heal (이전 없음)
    ('ク', '쿠'),   # auto-heal (이전 없음)
    ('クエリ', '쿼리'),   # 복합어 — 쿼리
    ('宙に浮いた', '떠다니는'),   # 관용구 — 떠다니는
    # === 복합어 추가 (2026-05-08) ===
], key=lambda x: -len(x[0]))

# =============================================================================
# Regex patterns
# =============================================================================
HANJA_PATTERN = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
KANA_PATTERN = re.compile(r'[\u3040-\u309f\u30a0-\u30ff]')
CYRILLIC_PATTERN = re.compile(r'[\u0400-\u04ff\u0500-\u052f]')
ARABIC_PATTERN = re.compile(r'[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]')

# Fallback: translate or remove any remaining CJK/Kana characters not caught by dictionary.
# _cjk_to_hangul_fallback (defined below) is used as the sub callback \u2014 it tries the
# single-char reverse index first and only deletes truly unmapped characters.
_REMOVE_REMAINING_CJK = re.compile(
    r'[\u4e00-\u9fff'       # CJK Unified Ideographs
    r'\u3400-\u4dbf'        # CJK Extension A
    r'\uf900-\ufaff'        # CJK Compatibility
    r'\u3040-\u309f'        # Hiragana
    r'\u30a0-\u30ff'        # Katakana
    r'\U00020000-\U0002A6DF' # CJK Extension B (supplementary plane)
    r'\u2f00-\u2fdf'        # Kangxi Radicals
    r'\uff01-\uffef]'        # Fullwidth / Halfwidth forms
)

# Fallback: remove Cyrillic characters (no dictionary mapping — always delete).
_REMOVE_CYRILLIC = re.compile(
    r'[\u0400-\u04ff'   # Cyrillic
    r'\u0500-\u052f]'   # Cyrillic Supplement
)

# Fallback: remove Arabic characters (no dictionary mapping — always delete).
_REMOVE_ARABIC = re.compile(
    r'[\u0600-\u06ff'   # Arabic
    r'\u0750-\u077f'     # Arabic Supplement
    r'\u08a0-\u08ff]'   # Arabic Extended-A
)


# Single-char reverse index: built from HANJA/JAPANESE_REPLACEMENTS at module load time.
# Maps single-char CJK/Kana source → Korean target for _cjk_to_hangul_fallback callback.
# Empty-string targets (deletion entries) are excluded so the fallback never silently deletes.
_SINGLE_CHAR_FALLBACK: dict[str, str] = {}


def _rebuild_single_char_fallback() -> None:
    """Rebuild _SINGLE_CHAR_FALLBACK from _KANA_TABLE + HANJA/JAPANESE_REPLACEMENTS.

    Priority (ascending, last write wins):
      1. _KANA_TABLE  — 히라가나/가타카나 기본 음역 (모든 글자 커버)
      2. HANJA_REPLACEMENTS  — 한자 단독 매핑
      3. JAPANESE_REPLACEMENTS  — 명시적 가나 매핑 (최고 우선순위)

    Called once after _KANA_TABLE is defined, and again after auto_heal_filter
    reloads the module so newly healed single-char entries are immediately live.

    _KANA_TABLE을 포함함으로써 JAPANESE_REPLACEMENTS에 없는 단독 가나 글자가
    fallback 단계에서 삭제되지 않고 한국어 외래어 표기로 처리됩니다.
    """
    global _SINGLE_CHAR_FALLBACK
    table: dict[str, str] = {}
    # 1. KANA_TABLE 기본값 (빈 값 = 촉음·장음부호 → 삭제이므로 제외)
    kana_table = globals().get('_KANA_TABLE', {})
    table.update({k: v for k, v in kana_table.items() if v})
    # 2. HANJA 덮어쓰기
    for src, dst in HANJA_REPLACEMENTS:
        if len(src) == 1 and dst:
            table[src] = dst
    # 3. JAPANESE 덮어쓰기 (최고 우선순위)
    for src, dst in JAPANESE_REPLACEMENTS:
        if len(src) == 1 and dst:
            table[src] = dst
    _SINGLE_CHAR_FALLBACK = table
    logger.debug("[CJK-fallback] single-char table rebuilt: %d entries", len(table))


def _cjk_to_hangul_fallback(match: re.Match) -> str:
    """Callback for _REMOVE_REMAINING_CJK.sub() — translates before deleting.

    Priority:
    1. _SINGLE_CHAR_FALLBACK hit → return Korean translation (natural output)
    2. No hit → return '' (deleted) and log for future auto-heal
    """
    ch = match.group(0)
    result = _SINGLE_CHAR_FALLBACK.get(ch)
    if result is not None:
        return result
    logger.debug("[CJK-fallback] unmapped char deleted: U+%04X %r", ord(ch), ch)
    return ''


# =============================================================================
# Core filter function — used by all layers
# =============================================================================
def filter_text(text: str) -> str:
    """
    Apply Hanja and Japanese replacements to text.

    Code blocks (```...``` and `...`) are intentionally protected and NOT filtered.
    Design decision: filtering code block content would corrupt code literals,
    command examples, and variable names that legitimately contain CJK characters
    (e.g., `grep "進行" file.txt` → `grep "" file.txt`).
    If this behavior ever needs to change, update the placeholder logic below
    AND this docstring together.

    Returns the filtered text.
    """
    if not text:
        return text

    # ---- protect code blocks (intentional — see docstring above) ----
    placeholders: dict[str, str] = {}
    counter = 0

    def _ph(value: str) -> str:
        nonlocal counter
        key = f"\x00FILTER_PH{counter}\x00"
        counter += 1
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

    # ---- fallback: translate (or delete) any remaining CJK/Kana not in dictionaries ----
    text = _REMOVE_REMAINING_CJK.sub(_cjk_to_hangul_fallback, text)

    # ---- remove Cyrillic characters ----
    text = _REMOVE_CYRILLIC.sub('', text)

    # ---- remove Arabic characters ----
    text = _REMOVE_ARABIC.sub('', text)

    # ---- restore code blocks (intentionally unfiltered — see docstring) ----
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


def _init_known_set() -> set:
    known: set = set()
    for kind, entries in [("hanja", _auto_heal_log.get("hanja", {})),
                          ("japanese", _auto_heal_log.get("japanese", {}))]:
        for ch in entries:
            known.add(f"{kind}:{ch}")
    return known


_AUTO_HEAL_KNOWN: set = _init_known_set()   # dedup within process lifetime


def _extract_reading_from_dict(char: str) -> str | None:
    """한글 읽기를 기존 HANJA_REPLACEMENTS 복합어에서 추출 시도."""
    for hanja, hangul in HANJA_REPLACEMENTS:
        if char in hanja and len(hanja) > 1:
            idx = hanja.index(char)
            if idx < len(hangul):
                return hangul[idx]
    return None


# 히라가나/가타카나 → 한국어 외래어 표기 정적 테이블 (결정론적)
_KANA_TABLE: dict[str, str] = {
    # 히라가나 모음
    'あ': '아', 'い': '이', 'う': '우', 'え': '에', 'お': '오',
    # 히라가나 카행
    'か': '카', 'き': '키', 'く': '쿠', 'け': '케', 'こ': '코',
    # 히라가나 사행
    'さ': '사', 'し': '시', 'す': '스', 'せ': '세', 'そ': '소',
    # 히라가나 타행
    'た': '타', 'ち': '치', 'つ': '츠', 'て': '테', 'と': '토',
    # 히라가나 나행
    'な': '나', 'に': '니', 'ぬ': '누', 'ね': '네', 'の': '노',
    # 히라가나 하행
    'は': '하', 'ひ': '히', 'ふ': '후', 'へ': '헤', 'ほ': '호',
    # 히라가나 마행
    'ま': '마', 'み': '미', 'む': '무', 'め': '메', 'も': '모',
    # 히라가나 야행
    'や': '야', 'ゆ': '유', 'よ': '요',
    # 히라가나 라행
    'ら': '라', 'り': '리', 'る': '루', 'れ': '레', 'ろ': '로',
    # 히라가나 와행
    'わ': '와', 'を': '오', 'ん': '응',
    # 히라가나 탁음
    'が': '가', 'ぎ': '기', 'ぐ': '구', 'げ': '게', 'ご': '고',
    'ざ': '자', 'じ': '지', 'ず': '즈', 'ぜ': '제', 'ぞ': '조',
    'だ': '다', 'ぢ': '지', 'づ': '즈', 'で': '데', 'ど': '도',
    'ば': '바', 'び': '비', 'ぶ': '부', 'べ': '베', 'ぼ': '보',
    # 히라가나 반탁음
    'ぱ': '파', 'ぴ': '피', 'ぷ': '푸', 'ぺ': '페', 'ぽ': '포',
    # 히라가나 소문자 (단독 발생 시 근사값)
    'ぁ': '아', 'ぃ': '이', 'ぅ': '우', 'ぇ': '에', 'ぉ': '오',
    'っ': '', 'ゃ': '야', 'ゅ': '유', 'ょ': '요',
    # 가타카나 모음
    'ア': '아', 'イ': '이', 'ウ': '우', 'エ': '에', 'オ': '오',
    # 가타카나 카행
    'カ': '카', 'キ': '키', 'ク': '쿠', 'ケ': '케', 'コ': '코',
    # 가타카나 사행
    'サ': '사', 'シ': '시', 'ス': '스', 'セ': '세', 'ソ': '소',
    # 가타카나 타행
    'タ': '타', 'チ': '치', 'ツ': '츠', 'テ': '테', 'ト': '토',
    # 가타카나 나행
    'ナ': '나', 'ニ': '니', 'ヌ': '누', 'ネ': '네', 'ノ': '노',
    # 가타카나 하행
    'ハ': '하', 'ヒ': '히', 'フ': '후', 'ヘ': '헤', 'ホ': '호',
    # 가타카나 마행
    'マ': '마', 'ミ': '미', 'ム': '무', 'メ': '메', 'モ': '모',
    # 가타카나 야행
    'ヤ': '야', 'ユ': '유', 'ヨ': '요',
    # 가타카나 라행
    'ラ': '라', 'リ': '리', 'ル': '루', 'レ': '레', 'ロ': '로',
    # 가타카나 와행
    'ワ': '와', 'ヲ': '오', 'ン': '응',
    # 가타카나 탁음
    'ガ': '가', 'ギ': '기', 'グ': '구', 'ゲ': '게', 'ゴ': '고',
    'ザ': '자', 'ジ': '지', 'ズ': '즈', 'ゼ': '제', 'ゾ': '조',
    'ダ': '다', 'ヂ': '지', 'ヅ': '즈', 'デ': '데', 'ド': '도',
    'バ': '바', 'ビ': '비', 'ブ': '부', 'ベ': '베', 'ボ': '보',
    # 가타카나 반탁음
    'パ': '파', 'ピ': '피', 'プ': '푸', 'ペ': '페', 'ポ': '포',
    # 가타카나 소문자 (단독 발생 시 근사값)
    'ァ': '아', 'ィ': '이', 'ゥ': '우', 'ェ': '에', 'ォ': '오',
    'ッ': '', 'ャ': '야', 'ュ': '유', 'ョ': '요',
    # 장음 부호 (단독 발생 시 제거)
    'ー': '',
}

# _KANA_TABLE 정의 완료 후 fallback 테이블 빌드 (KANA_TABLE 포함)
_rebuild_single_char_fallback()


def _extract_jp_reading_from_dict(char: str) -> str | None:
    """한국어 읽기를 정적 kana 테이블 → 복합어 순으로 추출 시도."""
    if char in _KANA_TABLE:
        reading = _KANA_TABLE[char]
        return reading  # 빈 문자열('')도 유효한 결과 (촉음·장음부호)
    for jp, hangul in JAPANESE_REPLACEMENTS:
        if char in jp and len(jp) > 1:
            idx = jp.index(char)
            if idx < len(hangul):
                return hangul[idx]
    return None


def _extract_context_snippets(text: str, char: str, window: int = 35, max_n: int = 2) -> list[str]:
    """문자 발생 위치 주변 window자 스니펫 반환 (최대 max_n개)."""
    snippets = []
    for i, c in enumerate(text):
        if c == char:
            start = max(0, i - window)
            end = min(len(text), i + window + 1)
            snippet = text[start:end].replace('\n', ' ').strip()
            snippets.append(snippet)
            if len(snippets) >= max_n:
                break
    return snippets


_CJK_RUN = re.compile(
    r'[一-鿿㐀-䶿豈-﫿぀-ゟ゠-ヿ]+'
)


def _extract_compound_cjk(text: str, chars: set[str]) -> list[str]:
    """text에서 chars 중 하나라도 포함된 연속 CJK 문자열(2자+) 추출. 중복 제거."""
    seen: set[str] = set()
    result: list[str] = []
    for m in _CJK_RUN.finditer(text):
        compound = m.group(0)
        if len(compound) > 1 and any(c in compound for c in chars) and compound not in seen:
            seen.add(compound)
            result.append(compound)
    return result


def _is_already_in_dict(compound: str) -> bool:
    """복합어가 이미 HANJA/JAPANESE_REPLACEMENTS에 있으면 True."""
    for src, _ in HANJA_REPLACEMENTS:
        if src == compound:
            return True
    for src, _ in JAPANESE_REPLACEMENTS:
        if src == compound:
            return True
    return False


def _estimate_compound_translation(compound: str) -> str | None:
    """
    복합어 번역 추정: 각 문자의 한글 읽기를 이어붙임.
    모든 문자의 읽기를 찾을 수 없으면 None 반환 → log만 기록.

    가나(히라가나/가타카나)를 포함한 복합어는 추정하지 않음.
    가나 음역("도레", "시타이" 등)은 의미 없는 한글 발음 일본어이므로,
    올바른 번역(예: "어느", "하고 싶은")은 사람이 직접 사전에 추가해야 함.
    """
    if any('぀' <= c <= 'ヿ' for c in compound):
        return None
    parts: list[str] = []
    for ch in compound:
        reading: str | None = None
        # 한자: 기존 복합어에서 해당 문자 읽기 추출
        for src, dst in HANJA_REPLACEMENTS:
            if ch in src and len(src) > 1:
                idx = src.index(ch)
                if idx < len(dst):
                    reading = dst[idx]
                    break
        # 가나: _KANA_TABLE 참조
        if reading is None and ch in _KANA_TABLE:
            reading = _KANA_TABLE[ch]
        if reading is None:
            return None
        parts.append(reading)
    result = ''.join(parts)
    return result if result else None


def auto_heal_filter(
    remaining_hanja_chars: set[str],
    remaining_jp_chars: set[str],
    context_text: str = "",
) -> None:
    """
    Detect unknown Hanja/Japanese and attempt compound-word auto-heal.

    Strategy (v2 — compound-first):
    - Single characters: log only, do NOT add to dictionary.
      Single-char entries cause garbled output when the char appears in
      non-matching contexts.
    - Compound words (2+ CJK chars from context_text): extract, estimate
      translation from per-char readings, add if translation is found.
    - If no translation can be estimated: log only.
    """
    global HANJA_REPLACEMENTS, JAPANESE_REPLACEMENTS

    module_path = __file__
    all_unknown = remaining_hanja_chars | remaining_jp_chars
    new_hanja: list[tuple[str, str]] = []
    new_jp: list[tuple[str, str]] = []
    timestamp = datetime.now().isoformat(timespec="seconds")

    # --- Phase 1: Log all single unknown chars (no dict entry) ---
    for ch in remaining_hanja_chars:
        key = f"hanja:{ch}"
        if key in _AUTO_HEAL_KNOWN:
            continue
        _AUTO_HEAL_KNOWN.add(key)
        entry: dict = {"r": "", "ts": timestamp, "v": False, "note": "single-char-skipped"}
        if context_text:
            snippets = _extract_context_snippets(context_text, ch)
            if snippets:
                entry["ctx"] = snippets
        _auto_heal_log.setdefault("hanja", {})[ch] = entry
        logger.info("[Auto-heal] Hanja '%s': single-char, log only", ch)

    for ch in remaining_jp_chars:
        key = f"japanese:{ch}"
        if key in _AUTO_HEAL_KNOWN:
            continue
        _AUTO_HEAL_KNOWN.add(key)
        entry = {"r": "", "ts": timestamp, "v": False, "note": "single-char-skipped"}
        if context_text:
            snippets = _extract_context_snippets(context_text, ch)
            if snippets:
                entry["ctx"] = snippets
        _auto_heal_log.setdefault("japanese", {})[ch] = entry
        logger.info("[Auto-heal] Japanese '%s': single-char, log only", ch)

    # --- Phase 2: Extract compound words from context and register ---
    if context_text and all_unknown:
        compounds = _extract_compound_cjk(context_text, all_unknown)
        for compound in compounds:
            if _is_already_in_dict(compound):
                continue
            key = f"compound:{compound}"
            if key in _AUTO_HEAL_KNOWN:
                continue
            _AUTO_HEAL_KNOWN.add(key)

            translation = _estimate_compound_translation(compound)
            entry = {
                "r": translation or "",
                "ts": timestamp,
                "v": translation is not None,
            }
            snippets = _extract_context_snippets(context_text, compound[0])
            if snippets:
                entry["ctx"] = snippets

            if translation:
                is_jp = any('぀' <= c <= 'ヿ' for c in compound)
                if is_jp:
                    new_jp.append((compound, translation))
                    _auto_heal_log.setdefault("japanese", {})[compound] = entry
                else:
                    new_hanja.append((compound, translation))
                    _auto_heal_log.setdefault("hanja", {})[compound] = entry
                logger.info("[Auto-heal] Compound '%s' → '%s' added to dict", compound, translation)
            else:
                _auto_heal_log.setdefault("hanja", {})[compound] = entry
                logger.info("[Auto-heal] Compound '%s': no translation estimate, log only", compound)

    # --- Persist log to disk ---
    _save_auto_heal_log(_auto_heal_log)

    if not new_hanja and not new_jp:
        return

    # --- Read source, append new entries, rewrite ---
    with open(module_path, encoding="utf-8") as f:
        source = f.read()

    lines = source.splitlines()

    def _insert_entry(src: list[str], marker: str, entries: list[tuple[str, str]]) -> list[str]:
        """Insert new tuple entries before the marker line."""
        result = []
        inserted = False
        for line in reversed(src):
            if not inserted and line.rstrip().endswith(marker):
                indent = " " * 4
                for cjk, hangul in entries:
                    result.append(f"{indent}('{cjk}', '{hangul}'),   # auto-heal:compound")
                result.append(line)
                inserted = True
            else:
                result.append(line)
        return result[::-1]

    if new_hanja:
        lines = _insert_entry(lines, "# AUTOHEAL:HANJA_END", new_hanja)

    if new_jp:
        lines = _insert_entry(lines, "# AUTOHEAL:JAPANESE_END", new_jp)

    with open(module_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # --- Reload so new entries are live ---
    import hermes_filters as _hm
    importlib.reload(_hm)
    HANJA_REPLACEMENTS = _hm.HANJA_REPLACEMENTS
    JAPANESE_REPLACEMENTS = _hm.JAPANESE_REPLACEMENTS
    _rebuild_single_char_fallback()
    logger.info("[Auto-heal] hermes_filters reloaded — compound entries live")

def log_cyrillic_chars(chars: set[str], context_text: str = "") -> None:
    """
    Persist detected Cyrillic characters to auto_heal_log.json for future analysis.
    Does NOT modify source code — logging only.
    """
    global _auto_heal_log

    if not chars:
        return

    timestamp = datetime.now().isoformat(timespec="seconds")
    log = _load_auto_heal_log()
    if "cyrillic" not in log:
        log["cyrillic"] = {}

    for ch in chars:
        snippets = _extract_context_snippets(context_text, ch) if context_text else []
        if ch not in log["cyrillic"]:
            log["cyrillic"][ch] = {
                "first_seen": timestamp,
                "count": 1,
                "ctx": snippets,
            }
            logger.info("[Cyrillic-log] new char recorded: %r", ch)
        else:
            log["cyrillic"][ch]["count"] = log["cyrillic"][ch].get("count", 0) + 1
            existing_ctx = log["cyrillic"][ch].get("ctx", [])
            if snippets and len(existing_ctx) < 5:
                existing_ctx.extend(snippets)
                log["cyrillic"][ch]["ctx"] = existing_ctx

    _save_auto_heal_log(log)
    _auto_heal_log = log


def log_arabic_chars(chars: set[str], context_text: str = "") -> None:
    """
    Persist detected Arabic characters to auto_heal_log.json for future analysis.
    Does NOT modify source code — logging only.
    """
    global _auto_heal_log

    if not chars:
        return

    timestamp = datetime.now().isoformat(timespec="seconds")
    log = _load_auto_heal_log()
    if "arabic" not in log:
        log["arabic"] = {}

    for ch in chars:
        snippets = _extract_context_snippets(context_text, ch) if context_text else []
        if ch not in log["arabic"]:
            log["arabic"][ch] = {
                "first_seen": timestamp,
                "count": 1,
                "ctx": snippets,
            }
            logger.info("[Arabic-log] new char recorded: %r", ch)
        else:
            log["arabic"][ch]["count"] = log["arabic"][ch].get("count", 0) + 1
            existing_ctx = log["arabic"][ch].get("ctx", [])
            if snippets and len(existing_ctx) < 5:
                existing_ctx.extend(snippets)
                log["arabic"][ch]["ctx"] = existing_ctx

    _save_auto_heal_log(log)
    _auto_heal_log = log