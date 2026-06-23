# -*- coding: utf-8 -*-
"""저장된 커뮤니티 리서치 인사이트를 기획 프롬프트로 잇는 다리.

/research에서 만든 인사이트를 매장(프로젝트)별로 DB에 저장(content_type="research")하고,
전략·소식글 빌더가 그걸 '실제 고객의 목소리' 레퍼런스로 주입한다.
리서치를 '먼저' 하면 기획이 그 결과를 자동으로 반영한다(선행 → 연결).
경쟁 광고 주입(competitor.py)과 같은 best-effort 패턴: 없거나 실패해도 기획은 그대로 진행.
"""
from __future__ import annotations

import re
from types import SimpleNamespace

from app.database import (
    save_generated_content, get_latest_content,
    save_ad_observations as _db_save_ads, get_ad_observations as _db_get_ads,
)
from app.research.insight import format_research_insight
from app.logger import get_logger

_log = get_logger("research_saved")

# 혜택/판촉 단어 — 리서치 키워드로는 노이즈라 제거(예: "변색렌즈 0원" → "변색렌즈").
_OFFER_WORDS = ("원", "%", "％", "할인", "무료", "증정", "이벤트", "특가", "세일",
                "쿠폰", "사은품", "첫", "선착순", "한정", "혜택", "행사", "오픈")
_TOKEN_SPLIT = re.compile(r"[\s,/·|\n\t]+")
_NUM_ONLY = re.compile(r"^[\d.,]+%?원?$")


def suggest_keywords(project) -> list[str]:
    """프로젝트 소재(혜택·광고제목·업종)에서 리서치 키워드 후보를 뽑는다(중첩용).

    근거(실측): 업종("안경원")·지역("공주")은 커뮤니티에서 무관한 글만 잡힘 → 제외.
    상품/소재 명사("변색렌즈")가 적합. 숫자·금액·판촉어는 검색을 망치므로 제거.
    사용자가 화면에서 보고 수정하는 '출발점'이다(완벽할 필요 없음).
    """
    if not isinstance(project, dict):
        return []
    region_tokens = {t for t in str(project.get("region", "") or "").split() if t}
    kws: list[str] = []
    # 혜택 → 광고 소재 제목 순으로 소재 명사 수집.
    for field in ("benefits", "ad_titles", "goal"):
        for tok in _TOKEN_SPLIT.split(str(project.get(field, "") or "")):
            t = tok.strip()
            if len(t) < 2 or t in region_tokens or t in kws:
                continue
            if _NUM_ONLY.match(t) or any(w in t for w in _OFFER_WORDS):
                continue
            kws.append(t)
            if len(kws) >= 6:
                break
        if len(kws) >= 6:
            break
    # 아무것도 못 뽑으면 업종이라도(약하지만 빈손보단 나음 — 사용자가 고치게).
    if not kws:
        ind = str(project.get("industry", "") or "").strip()
        if ind:
            kws.append(ind)
    return kws


def save_research_insight(project_id: int, insight: dict, keyword: str = "") -> bool:
    """리서치 인사이트를 매장별로 저장. 빈 결과면 저장하지 않고 False."""
    if not project_id or not isinstance(insight, dict):
        return False
    summary = format_research_insight(insight, keyword)
    if not summary.strip():
        return False
    try:
        save_generated_content(project_id, "research", summary, content_type="research")
        return True
    except Exception:
        _log.exception("리서치 인사이트 저장 실패")
        return False


def save_observations(project_id: int, observations) -> bool:
    """경쟁 광고 관측(AdObservation 리스트)을 매장별 최신 스냅샷으로 저장."""
    if not project_id or not observations:
        return False
    rows = [{
        "engine": getattr(o, "engine", "") or "",
        "keyword": getattr(o, "keyword", "") or "",
        "headline": getattr(o, "headline", "") or "",
        "description": getattr(o, "description", "") or "",
        "display_url": getattr(o, "display_url", "") or "",
        "landing_url": getattr(o, "landing_url", "") or "",
        "position": int(getattr(o, "position", 0) or 0),
        "heuristic_score": float(getattr(o, "heuristic_score", 0) or 0),
        "ad_type": getattr(o, "ad_type", "") or "",
    } for o in observations]
    try:
        _db_save_ads(project_id, rows)
        return True
    except Exception:
        _log.exception("경쟁 광고 관측 저장 실패")
        return False


def get_saved_observations(project_id: int) -> list:
    """저장된 관측을 화면 렌더용 객체(속성 접근)로 복원. 없으면 []."""
    if not project_id:
        return []
    try:
        rows = _db_get_ads(project_id)
    except Exception:
        _log.exception("저장된 광고 관측 로드 실패")
        return []
    return [SimpleNamespace(**r) for r in rows]


def get_saved_research(project_id: int):
    """저장된 리서치 원본 행(content=요약 마크다운 + created_at). 없으면 None.

    화면 표시용 — 기획에 어떤 커뮤니티 리서치가 반영됐는지 사용자가 눈으로 확인한다.
    """
    if not project_id:
        return None
    try:
        row = get_latest_content(project_id, content_type="research")
    except Exception:
        _log.exception("저장된 리서치 로드 실패")
        return None
    if not row or not str(row.get("content") or "").strip():
        return None
    return row


def research_context(project_id: int) -> str:
    """저장된 최신 리서치 인사이트를 전략/소식글 프롬프트 주입 블록으로. 없으면 ''."""
    if not project_id:
        return ""
    try:
        row = get_latest_content(project_id, content_type="research")
    except Exception:
        _log.exception("리서치 인사이트 로드 실패")
        return ""
    summary = ((row.get("content") if row else "") or "").strip()
    if not summary:
        return ""
    return (
        "\n\n[커뮤니티 리서치 — 실제 고객의 목소리(이 기획보다 먼저 수집됨). "
        "아래 고충·욕구·실제 표현·앵글을 소식글/카피의 근거로 삼아라. "
        "매끈한 광고말 대신 커뮤니티 날것의 표현을 우선 반영하고, 진부한 반복은 금지]\n"
        f"{summary}\n"
    )
