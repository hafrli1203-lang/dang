"""원클릭 통합 기획 — 자료(매장+위키+교재)로 전략→소식글→세팅→제안서를 한 번에 생성.

'단계가 너무 많다'를 해소: 사용자는 버튼 1번. 각 단계 결과는 단계별 content_type으로
DB 저장되어 개별 페이지(/plan/*)가 그대로 이어받고 편집할 수 있다. 앞 단계 결과를
뒷 단계 컨텍스트로 흘려 일관성을 유지한다.
"""
import asyncio
from typing import Callable, Dict, Optional

from app.ai_engine import (
    build_strategy_prompt,
    build_planning_prompt,
    build_ad_settings_prompt,
    build_wizard_proposal_prompt,
)
from app.ai.providers import get_provider
from app.ai.output_validator import repair_output, get_schema
from app.database import save_generated_content, get_project
from app import store_wiki
from app.logger import get_logger

_log = get_logger("pipeline")


def _resolve_engine(engine: str) -> str:
    """통합 생성은 단일 엔진으로(조율은 4단계×3호출이라 과비용). coordinate/both → claude."""
    return "claude" if engine in ("coordinate", "both", "") else engine


async def generate_full_plan(
    project_id: int,
    engine: str = "claude",
    on_progress: Optional[Callable[[str], None]] = None,
) -> Dict[str, str]:
    """전략→소식글→세팅→제안서를 순차 생성·저장하고 결과 dict 반환.

    각 단계는 위키·교재가 주입된 프롬프트 빌더를 그대로 쓴다(개별 페이지와 동일 품질).
    """
    project = get_project(project_id)
    if not project:
        raise ValueError("프로젝트를 찾을 수 없어요. 먼저 매장을 선택해 주세요.")

    eng = _resolve_engine(engine)
    wiki = store_wiki.wiki_context(project_id, project)
    loop = asyncio.get_running_loop()

    def _emit(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    def _gen(guide: str, prompt: str, schema_key: Optional[str] = None) -> str:
        out = get_provider(eng).generate_text(prompt, system_prompt=guide)
        if schema_key:
            try:
                out = repair_output(out, get_schema(schema_key), engine=eng)
            except Exception:  # 보정 실패는 비치명적 — 원본 유지
                _log.exception("repair_output 실패 (%s)", schema_key)
        return out

    # 1) 전략 분석
    _emit("1/4 전략 분석을 만들고 있어요...")
    g, p = build_strategy_prompt(project, wiki=wiki)
    strategy = await loop.run_in_executor(None, lambda: _gen(g, p, "strategy"))
    save_generated_content(project_id, eng, strategy, content_type="strategy")

    # 2) 소식글·제목·쿠폰
    _emit("2/4 소식글·제목·쿠폰을 만들고 있어요...")
    g, p = build_planning_prompt(
        project, category="default", engine=eng, strategy_context=strategy, wiki=wiki,
    )
    content = await loop.run_in_executor(None, lambda: _gen(g, p))
    save_generated_content(project_id, eng, content, content_type="content")

    # 3) 광고 세팅 가이드
    _emit("3/4 광고 세팅 가이드를 만들고 있어요...")
    g, p = build_ad_settings_prompt(
        project, strategy_context=strategy, content_context=content, wiki=wiki,
    )
    adset = await loop.run_in_executor(None, lambda: _gen(g, p, "ad_settings"))
    save_generated_content(project_id, eng, adset, content_type="ad_settings")

    # 4) 운영 제안서
    _emit("4/4 운영 제안서를 만들고 있어요...")
    g, p = build_wizard_proposal_prompt(
        project, strategy_context=strategy, content_context=content, ad_settings_context=adset,
    )
    proposal = await loop.run_in_executor(None, lambda: _gen(g, p, "wizard_proposal"))
    save_generated_content(project_id, eng, proposal, content_type="wizard_proposal")

    _emit("완료")
    return {
        "strategy": strategy,
        "content": content,
        "ad_settings": adset,
        "proposal": proposal,
    }
