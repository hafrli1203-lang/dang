"""원클릭 통합 기획 — 자료(매장+위키+교재)로 전략→소식글→세팅→제안서(+썸네일)를 한 번에.

'단계가 많다'를 해소: 사용자는 버튼 1번. 각 단계 결과는 단계별 content_type으로 DB 저장되어
개별 페이지(/plan/*)가 이어받고 편집한다. 앞 단계 결과를 뒷 단계 컨텍스트로 흘린다.

엔진 역할 분담(사용자 지정 그대로): 기획·세팅·제안서 = 조율(Claude+GPT 병렬→종합),
소식글·글 = Claude 단독. 원클릭에서도 이 분담을 그대로 지킨다(임의로 단일 엔진 강등 금지).

예산 현실: budget_planner 룰 엔진을 호출해 '예산이 작으면 캠페인을 쪼개지 않는다'를
세팅 프롬프트에 강제 주입한다. (일 1만원이 캠페인 최소치 — 30만원/월이면 단일 캠페인이 정답)
"""
import asyncio
import re
from typing import Callable, Dict, Optional

from app.ai_engine import (
    build_strategy_prompt,
    build_planning_prompt,
    build_ad_settings_prompt,
    build_wizard_proposal_prompt,
)
from app.ai.providers import get_provider
from app.ai.coordination import coordinate_generate
from app.ai.output_validator import repair_output, get_schema
from app.ai.quality_loop import refine_until_good
from app.database import save_generated_content, get_project
from app.engine.budget_planner import recommend_structure, plan_to_prompt_context
from app import store_wiki
from app.logger import get_logger

_log = get_logger("pipeline")

# 글(소식글)은 Claude 단독, 기획/세팅/제안서는 사용자가 고른 엔진(기본 조율).
COPY_ENGINE = "claude"


def _daily_budget(project: dict) -> int:
    """프로젝트에서 일예산(원)을 추정한다. 캠페인 최소치(1만원) 미만이면 1만원으로 본다."""
    raw_daily = project.get("daily_budget")
    if raw_daily:
        digits = re.sub(r"[^\d]", "", str(raw_daily))
        if digits:
            return max(int(digits), 1)
    # 월예산 문자열에서 추정 (예: "30만원" → 300000 → /30일)
    budget = str(project.get("budget", ""))
    m = re.search(r"(\d[\d,]*)\s*만", budget)
    monthly = int(m.group(1).replace(",", "")) * 10_000 if m else 0
    if not monthly:
        m2 = re.search(r"(\d[\d,]{4,})", budget)  # 6자리 이상 = 원 단위
        monthly = int(m2.group(1).replace(",", "")) if m2 else 0
    if monthly:
        return max(monthly // 30, 1)
    return 10_000


def _budget_context(project: dict) -> str:
    """예산 룰 엔진 결과를 세팅 프롬프트용 컨텍스트로. 작은 예산이면 '쪼개지 마라'가 박힌다."""
    try:
        daily = _daily_budget(project)
        region = (project.get("region") or "우리동네").split()[-1]
        gender = (project.get("target_gender") or "여성").strip() or "여성"
        plan = recommend_structure(daily, region=region, gender=gender)
        return plan_to_prompt_context(plan)
    except Exception:
        _log.exception("budget 컨텍스트 계산 실패")
        return ""


async def generate_full_plan(
    project_id: int,
    engine: str = "coordinate",
    on_progress: Optional[Callable[[str], None]] = None,
    with_thumbnail: bool = True,
) -> Dict[str, str]:
    """전략→소식글→세팅→제안서(+썸네일)를 순차 생성·저장하고 결과 dict 반환."""
    project = get_project(project_id)
    if not project:
        raise ValueError("프로젝트를 찾을 수 없어요. 먼저 매장을 선택해 주세요.")

    plan_engine = engine if engine in ("claude", "gpt", "coordinate") else "coordinate"
    wiki = store_wiki.wiki_context(project_id, project)
    budget_ctx = _budget_context(project)
    loop = asyncio.get_running_loop()

    # 실제 경쟁 광고 관측(best-effort) — 전략·소식글에 레퍼런스로 주입
    _emit_pre = on_progress
    if _emit_pre:
        _emit_pre("경쟁 광고를 살펴보는 중...")
    try:
        from app.research.competitor import competitor_context
        competitor_ads = await loop.run_in_executor(None, lambda: competitor_context(project))
    except Exception:
        _log.exception("경쟁 광고 컨텍스트 실패(본 기획은 정상)")
        competitor_ads = ""

    # 커뮤니티 리서치는 /research에서 '소재 키워드로' 명시적으로 선행한다(단일 진입점).
    # 여기선 저장된 결과만 반영(없으면 빈 블록) — 업종 키워드로 몰래 자동 리서치 하지 않는다.
    try:
        from app.research.saved_research import research_context
        research_block = research_context(project_id)
    except Exception:
        _log.exception("리서치 컨텍스트 로드 실패(본 기획은 정상)")
        research_block = ""
    if research_block and _emit_pre:
        _emit_pre("커뮤니티 리서치 인사이트를 기획에 반영하는 중...")
    elif not research_block and _emit_pre:
        _emit_pre("저장된 리서치 없음 — /research에서 먼저 돌리면 반영돼요(이번 기획은 리서치 없이 진행)")

    def _emit(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    async def _run(guide: str, prompt: str, eng: str, label: str, schema_key: Optional[str],
                   quality_type: Optional[str] = None) -> str:
        """eng=='coordinate'면 Claude+GPT 조율, 아니면 단일. 스키마 있으면 1회 보정."""
        if eng == "coordinate":
            out = await coordinate_generate(loop, prompt, guide, label)
        else:
            out = await loop.run_in_executor(
                None, lambda: get_provider(eng).generate_text(prompt, system_prompt=guide)
            )
        if schema_key:
            try:
                out = await loop.run_in_executor(
                    None, lambda: repair_output(out, get_schema(schema_key), engine=(eng if eng != "coordinate" else "claude"))
                )
            except Exception:
                _log.exception("repair_output 실패 (%s)", schema_key)
        if quality_type:
            def _q_gen(prompt: str) -> str:
                return get_provider("claude").generate_text(prompt, system_prompt=guide)
            out = await loop.run_in_executor(
                None,
                lambda: refine_until_good(
                    out, quality_type, generate=_q_gen, guide=guide,
                    target=90, max_iters=1, on_progress=on_progress,
                ),
            )
        return out

    # 1) 전략 분석 — 기획(조율)
    _emit("1/4 전략 분석 (Claude+GPT 조율)" if plan_engine == "coordinate" else "1/4 전략 분석")
    g, p = build_strategy_prompt(project, wiki=wiki, competitor_ads=competitor_ads,
                                 research_block=research_block, budget_plan_context=budget_ctx)
    strategy = await _run(g, p, plan_engine, "전략 분석", "strategy")
    save_generated_content(project_id, plan_engine, strategy, content_type="strategy")

    # 2) 소식글·제목·쿠폰 — 글(Claude 단독)
    _emit("2/4 소식글·제목·쿠폰 (Claude)")
    g, p = build_planning_prompt(
        project, category="default", engine=COPY_ENGINE, strategy_context=strategy, wiki=wiki,
        competitor_ads=competitor_ads, research_block=research_block,
    )
    content = await _run(g, p, COPY_ENGINE, "콘텐츠 생성", None)
    save_generated_content(project_id, COPY_ENGINE, content, content_type="content")

    # 3) 광고 세팅 — 기획(조율) + 예산 룰 엔진 주입
    _emit("3/4 광고 세팅 (예산 현실 반영)")
    g, p = build_ad_settings_prompt(
        project, strategy_context=strategy, content_context=content,
        budget_plan_context=budget_ctx, wiki=wiki,
    )
    adset = await _run(g, p, plan_engine, "광고 세팅", "ad_settings")
    save_generated_content(project_id, plan_engine, adset, content_type="ad_settings")

    # 4) 운영 제안서 — 기획(조율)
    _emit("4/4 운영 제안서")
    g, p = build_wizard_proposal_prompt(
        project, strategy_context=strategy, content_context=content, ad_settings_context=adset,
    )
    proposal = await _run(g, p, plan_engine, "운영 제안서", "wizard_proposal")
    save_generated_content(project_id, plan_engine, proposal, content_type="wizard_proposal")

    result = {"strategy": strategy, "content": content, "ad_settings": adset, "proposal": proposal}

    # 5) 썸네일 — best-effort(이미지 백엔드 없으면 조용히 건너뜀)
    if with_thumbnail:
        _emit("썸네일 이미지 생성 중...")
        try:
            thumb_path = await loop.run_in_executor(None, _make_thumbnail, project, content)
            if thumb_path:
                result["thumbnail"] = thumb_path
        except Exception:
            _log.exception("썸네일 생성 실패(본 기획은 정상)")

    _emit("완료")
    return result


def _make_thumbnail(project: dict, content: str) -> Optional[str]:
    """소식글 맥락으로 자연 실사 썸네일 1장 생성·저장. 실패 시 None."""
    from app.ai.thumbnail_style import build_natural_thumbnail_prompt
    from app.ai.image_provider import get_image_provider
    from app.database import save_thumbnail
    from app.paths import THUMBNAILS_DIR

    benefit = (project.get("benefits") or project.get("goal") or "").strip()
    industry = (project.get("industry") or "").strip()
    scene = f"{industry} 매장에서 '{benefit}' 혜택을 보여주는 자연스러운 동네 가게 사진"
    prompt = build_natural_thumbnail_prompt(scene)
    provider = get_image_provider()
    result = provider.generate_image(prompt, aspect_ratio="1:1")
    # 계약: generate_image → (bytes, mime). api 폴백이 PIL을 줄 수도 있어 둘 다 처리.
    img_bytes = None
    if isinstance(result, tuple) and result and isinstance(result[0], (bytes, bytearray)):
        img_bytes = bytes(result[0])
    elif isinstance(result, (bytes, bytearray)):
        img_bytes = bytes(result)
    if not img_bytes:
        return None
    THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"auto_{project.get('id', 'x')}_{abs(hash(benefit)) % 100000}.png"
    fpath = THUMBNAILS_DIR / fname
    fpath.write_bytes(img_bytes)
    save_thumbnail(project["id"], str(fpath), title=benefit[:40], prompt=prompt)
    return str(fpath)
