"""경쟁 광고 주입 — 실제로 돌아가는 경쟁 광고를 긁어 기획 프롬프트 컨텍스트로.

채팅에서 잘 나오는 이유 = 실제 잘된 광고를 보여주고 "이렇게 써"라고 하기 때문.
그걸 자동화한다: 키워드로 네이버·메타 광고를 관측 → 상위 광고의 실제 카피를
'경쟁 광고 레퍼런스'로 만들어 전략·소식글 프롬프트에 주입한다.

Playwright/네트워크 의존이라 best-effort: 실패하거나 0건이면 빈 문자열을 돌려
본 생성은 그대로 진행한다(절대 차단하지 않음).
"""
from __future__ import annotations

import re
from typing import Callable, List, Optional

from app.logger import get_logger

_log = get_logger("competitor")

# 구글은 CAPTCHA로 헤드리스 차단 → 네이버·메타만.
_DEFAULT_ENGINES = ("NAVER", "META")
_STOP = ("이벤트", "할인", "무료", "최저가", "당근", "광고")


def derive_keyword(project: dict) -> str:
    """매장 혜택/업종에서 경쟁 광고 검색 키워드를 뽑는다(예: '변색렌즈 0원' → '변색렌즈')."""
    benefits = (project.get("benefits") or "").strip()
    # 첫 명사구: 숫자·기호·불용어 제거 전 첫 토큰 묶음
    first = re.split(r"[,/·\n(]", benefits)[0].strip() if benefits else ""
    words = [w for w in re.split(r"\s+", first) if w and not any(s in w for s in _STOP)
             and not re.fullmatch(r"[\d%원~+-]+", w)]
    kw = " ".join(words[:2]).strip()
    if kw:
        return kw
    return (project.get("industry") or "").strip()


def fetch_competitor_ads(keyword: str, *, limit: int = 8,
                         progress: Optional[Callable[[str], None]] = None) -> List:
    """키워드로 경쟁 광고 관측(best-effort). 실패 시 []."""
    if not keyword:
        return []
    try:
        from app.research.pipeline import observe_ads
        ads = observe_ads(keyword, engines=_DEFAULT_ENGINES, progress=progress)
    except Exception as exc:  # Playwright 미설치/네트워크/차단 등 전부 격리
        _log.warning("경쟁 광고 관측 실패(%s): %s", keyword, exc)
        return []
    ads = [a for a in ads if getattr(a, "headline", "").strip()]
    ads.sort(key=lambda a: getattr(a, "heuristic_score", 0), reverse=True)
    return ads[:limit]


def format_competitor_block(ads: List, keyword: str = "") -> str:
    """관측한 광고를 프롬프트 주입용 레퍼런스 블록으로. 비면 ''."""
    if not ads:
        return ""
    lines: List[str] = []
    for a in ads:
        head = (getattr(a, "headline", "") or "").strip()
        desc = (getattr(a, "description", "") or "").strip()
        eng = getattr(a, "engine", "")
        if not head:
            continue
        lines.append(f"- [{eng}] {head}" + (f" — {desc}" if desc else ""))
    if not lines:
        return ""
    body = "\n".join(lines)
    return (
        f"\n\n[실제 경쟁 광고 — '{keyword}' 검색 시 지금 돌아가는 광고들. "
        "이들이 쓰는 후크·표현·소구를 분석해 '더 나은' 카피를 만들되, 베끼지 말고 "
        "성과 패턴(의심 인용·숫자갭·결핍 직격)으로 한 단계 높여라. 진부하게 같은 말 반복 금지]\n"
        f"{body}\n"
    )


def competitor_context(project: dict, *, progress: Optional[Callable[[str], None]] = None) -> str:
    """매장 → 키워드 → 경쟁 광고 관측 → 주입 블록. 한 번에. 실패해도 ''."""
    kw = derive_keyword(project)
    if not kw:
        return ""
    ads = fetch_competitor_ads(kw, progress=progress)
    return format_competitor_block(ads, kw)
