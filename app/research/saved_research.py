# -*- coding: utf-8 -*-
"""저장된 커뮤니티 리서치 인사이트를 기획 프롬프트로 잇는 다리.

/research에서 만든 인사이트를 매장(프로젝트)별로 DB에 저장(content_type="research")하고,
전략·소식글 빌더가 그걸 '실제 고객의 목소리' 레퍼런스로 주입한다.
리서치를 '먼저' 하면 기획이 그 결과를 자동으로 반영한다(선행 → 연결).
경쟁 광고 주입(competitor.py)과 같은 best-effort 패턴: 없거나 실패해도 기획은 그대로 진행.
"""
from __future__ import annotations

from app.database import save_generated_content, get_latest_content
from app.research.insight import format_research_insight
from app.logger import get_logger

_log = get_logger("research_saved")


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
