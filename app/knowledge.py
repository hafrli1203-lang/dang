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

_HEADER = (
    "━━ 광고 실전 교재 (정제 지식 — 이 원칙·체크리스트·수치 벤치마크를 반드시 따른다. "
    "매장 위키의 실측과 충돌하면 매장 위키를 우선) ━━\n"
)
_FOOTER = "\n━━ (교재 지식 끝) ━━\n"


def domain_knowledge(scope: str = "full") -> str:
    """주입용 전문 지식 블록. scope로 필요한 부분만 골라 토큰 절약."""
    if scope == "setting":
        parts = [_SETTING, _DAANGN, _META, _COUPON]
    elif scope == "report":
        parts = [_DAANGN, _META]
    elif scope == "content":
        parts = [_DAANGN, _COUPON, _META]
    else:  # full / strategy
        parts = [_DAANGN, _META, _SETTING, _COUPON]
    body = "\n\n".join(p for p in parts if p)
    return f"\n\n{_HEADER}{body}{_FOOTER}" if body else ""
