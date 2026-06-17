"""전문 지식 베이스 — 광고 실전 교재(당근·메타 퍼포먼스, 윤익 세팅/쿠폰)를 정제해 주입.

LLM Wiki 3계층: raw(app/knowledge/raw/*.txt 원문) → distilled(app/knowledge/distilled_*.md 정제)
→ 주입(system 프롬프트). 매장 위키(이 매장 실측)와 합쳐져 '교재 + 실측'으로 기획한다.
정제 절차는 교재 원문을 Claude로 압축한 것이며, 출처에 충실하게 원칙·체크리스트·벤치마크만 담았다.
"""
from pathlib import Path

_DIR = Path(__file__).parent / "knowledge"


def _load(name: str) -> str:
    try:
        return (_DIR / f"distilled_{name}.md").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


# 모듈 로드 시 1회 읽어 캐시 (system 프롬프트 = 캐시 친화)
_DAANGN = _load("daangn")    # 당근 본질·비즈프로필·소식 3유형·쿠폰
_META = _load("meta")        # 메타 퍼포먼스 → 당근 이식 원리(콘텐츠 발굴·확장, 공헌이익)
_SETTING = _load("setting")  # 윤익 광고 세팅(연령 분리, 자동/수동)
_COUPON = _load("coupon")    # 윤익 쿠폰 다운율
_PERF = _load("performance")  # 실제 성과 패턴(심곡 벤치마크·터지는 콘텐츠 — 후크·골격·트리거)

_HEADER = (
    "━━ 광고 실전 교재 (정제 지식 — 이 원칙·체크리스트·수치 벤치마크를 반드시 따른다. "
    "매장 위키의 실측과 충돌하면 매장 위키를 우선) ━━\n"
)
_FOOTER = "\n━━ (교재 지식 끝) ━━\n"

# 환각·사실 왜곡 차단 — 모든 생성에 공통 적용(가짜 숫자가 가장 큰 품질 킬러).
_FACT_LOCK = (
    "\n\n━━ [사실관계 락 — 위반 시 출력 무효] ━━\n"
    "- 입력 자료(매장 정보·행사·성과 데이터)에 있는 숫자·가격·기간·조건·상품명은 그대로 인용한다. "
    "추정·반올림·재해석·창작 금지. 입력에 없는 가격/수치를 새로 지어내지 않는다.\n"
    "- 입력에 없는 일별·소재별·캠페인별 수치(예: 특정 날짜 CTR)는 절대 생성·인용하지 않는다. "
    "필요하면 '[매장 확인 필요]'로 표기한다.\n"
    "- 매장 위키·데이터에 없는 추정치(객단가·마진·MAX CPA 등)는 반드시 '[가정]' 라벨 + 근거를 붙이고 사장님 확인을 권한다.\n"
    "- 비교 기준치는 입력 벤치마크 또는 '광역시 표준'이라 명시한 값만 쓴다. 출처 없는 단정 수치 금지.\n"
    "- 시즌·시점은 입력된 집행 기간/이벤트를 따른다. 다른 월·시즌을 임의 추정하지 않는다.\n"
    "- '소재 N개 운영' 식으로 선언했으면 실제 산출물(카피 문구 등)을 N개 전량 제출한다. 골격·구조 설명만 하고 실물을 빼면 무효.\n"
)


def domain_knowledge(scope: str = "full") -> str:
    """주입용 전문 지식 블록. scope로 필요한 부분만 골라 토큰 절약."""
    # _PERF(실제 성과 패턴)을 맨 앞에 — '이게 실제로 클릭·전환을 냈다'가 최우선 기준.
    if scope == "setting":
        parts = [_PERF, _SETTING, _DAANGN, _META, _COUPON]
    elif scope == "report":
        parts = [_PERF, _DAANGN, _META]
    elif scope == "content":
        parts = [_PERF, _DAANGN, _COUPON, _META]
    else:  # full / strategy
        parts = [_PERF, _DAANGN, _META, _SETTING, _COUPON]
    body = "\n\n".join(p for p in parts if p)
    return f"\n\n{_HEADER}{body}{_FOOTER}{_FACT_LOCK}" if body else _FACT_LOCK
