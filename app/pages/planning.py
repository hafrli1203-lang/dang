"""Screen 2 -- 광고 기획 + 콘텐츠 생성."""
import json
import os
import re
import traceback
from pathlib import Path

from nicegui import ui, app as nicegui_app

from app.common import create_nav, no_project_notice
from app.logger import get_logger
from app.theme import section_header

_log = get_logger("planning")
from app.export_manager import ExportManager
from app.database import (
    get_project,
    get_projects,
    get_latest_content,
    save_generated_content,
    get_setting,
    save_setting,
    delete_setting,
)
from app.ai_engine import build_planning_prompt, SYSTEM_GUIDE_PLANNING, CATEGORIES
from app.ai.news_post_guard import validate_news_post, build_news_post_repair_prompt, _split_blocks
from app.content.news_post_rules import (
    validate_news_post as validate_news_post_bc,
    build_news_repair_prompt as build_news_repair_bc,
)
from app.ai.providers import get_provider, ClaudeProvider, OpenAIProvider
from app.reporting.docx_report import build_planning_docx


def _parse_planning_sections(content: str) -> dict:
    """기획 콘텐츠를 7개 섹션별로 파싱."""
    blocks = _split_blocks(content)

    v1_text = ""
    v2_text = ""
    if "의심해소" in blocks:
        v1_text = "【소식글 1 | 의심해소형】\n" + blocks["의심해소"]
    if "가성비" in blocks:
        v2_text = "【소식글 2 | 가성비형】\n" + blocks["가성비"]

    summary = ""
    ad_copies = ""
    campaign_groups = ""
    thumbnail_guide = ""
    coupon_spec = ""
    naming_convention = ""

    # Collect all ## sections with their headers and bodies
    parts = re.split(r"(?m)^(## .+)", content)
    header_body_pairs = []
    for i, part in enumerate(parts):
        if not part.startswith("## "):
            continue
        body = parts[i + 1] if i + 1 < len(parts) else ""
        header_body_pairs.append((part, body))

    for header, body in header_body_pairs:
        h = header
        # summary: 기획+요약 OR 요약 alone
        if ("기획" in h and "요약" in h) or ("요약" in h and not summary):
            summary = body
        # ad_copies: 카피 OR 제목 OR (광고 with digit or standalone)
        elif "카피" in h or "제목" in h or ("광고" in h and (re.search(r"\d", h) or "카피" not in h)):
            if not ad_copies:
                ad_copies = body
        # campaign_groups: 캠페인+그룹/구성 OR 타겟 OR 그룹 OR 연령 OR 나이
        elif ("캠페인" in h and ("그룹" in h or "구성" in h)) or "타겟" in h or "그룹" in h or "연령" in h or "나이" in h:
            if not campaign_groups:
                campaign_groups = body
        # thumbnail_guide: 썸네일 OR 이미지 OR 촬영 OR 사진
        elif "썸네일" in h or "이미지" in h or "촬영" in h or "사진" in h:
            if not thumbnail_guide:
                thumbnail_guide = body
        # coupon_spec: 쿠폰 OR 혜택 OR 할인
        elif "쿠폰" in h or "혜택" in h or "할인" in h:
            if not coupon_spec:
                coupon_spec = body
        # naming_convention: 네이밍 OR 캠페인명 OR 명명 OR 이름
        elif "네이밍" in h or "캠페인명" in h or "명명" in h or "이름" in h:
            if not naming_convention:
                naming_convention = body

    # Position-based fallback: assign remaining unmatched ## sections in order
    _fallback_keys = ["summary", "ad_copies", "campaign_groups", "thumbnail_guide", "coupon_spec", "naming_convention"]
    _fallback_values = [summary, ad_copies, campaign_groups, thumbnail_guide, coupon_spec, naming_convention]
    matched_headers = set()

    for header, body in header_body_pairs:
        h = header
        if ("기획" in h and "요약" in h) or ("요약" in h):
            matched_headers.add(header)
        elif "카피" in h or "제목" in h or ("광고" in h and (re.search(r"\d", h) or "카피" not in h)):
            matched_headers.add(header)
        elif ("캠페인" in h and ("그룹" in h or "구성" in h)) or "타겟" in h or "그룹" in h or "연령" in h or "나이" in h:
            matched_headers.add(header)
        elif "썸네일" in h or "이미지" in h or "촬영" in h or "사진" in h:
            matched_headers.add(header)
        elif "쿠폰" in h or "혜택" in h or "할인" in h:
            matched_headers.add(header)
        elif "네이밍" in h or "캠페인명" in h or "명명" in h or "이름" in h:
            matched_headers.add(header)

    unmatched = [(h, b) for h, b in header_body_pairs if h not in matched_headers]

    empty_slots = [k for k, v in zip(_fallback_keys, _fallback_values) if not v]
    for slot_key, (uh, ub) in zip(empty_slots, unmatched):
        if slot_key == "summary":
            summary = ub
        elif slot_key == "ad_copies":
            ad_copies = ub
        elif slot_key == "campaign_groups":
            campaign_groups = ub
        elif slot_key == "thumbnail_guide":
            thumbnail_guide = ub
        elif slot_key == "coupon_spec":
            coupon_spec = ub
        elif slot_key == "naming_convention":
            naming_convention = ub

    return {
        "version_1": v1_text,
        "version_2": v2_text,
        "summary": summary,
        "ad_copies": ad_copies,
        "campaign_groups": campaign_groups,
        "thumbnail_guide": thumbnail_guide,
        "coupon_spec": coupon_spec,
        "naming_convention": naming_convention,
        "raw": content,
    }


@ui.page("/planning")
def planning_page() -> None:
    create_nav("/planning")

    with ui.column().classes("dg-page-content w-full gap-5"):

        # Page header
        ui.label("광고 기획").classes("dg-page-title")
        ui.label("AI가 소식글 콘텐츠부터 운영 제안서까지 만들어 드려요.").classes("dg-page-subtitle")

        # -- Project selector --
        with ui.card().classes("dg-card w-full"):
            with ui.row().classes("items-center gap-4"):
                ui.icon("business", size="20px").style("color: var(--dg-primary)")
                ui.label("프로젝트").style("font-weight: 600; color: var(--dg-text-primary)")
                projects = get_projects()
                def _project_label(p: dict) -> str:
                    name = p.get("name", "")
                    campaign = p.get("campaign_name", "")
                    region = p.get("region", "")
                    parts = [name]
                    if campaign:
                        parts.append(campaign)
                    if region:
                        parts.append(region)
                    return " | ".join(parts)
                options = {p["id"]: _project_label(p) for p in projects}
                saved_pid = nicegui_app.storage.user.get("current_project_id")
                project_sel = ui.select(
                    options, label="프로젝트 선택",
                    value=saved_pid if saved_pid in options else None,
                ).classes("flex-1 dg-select")

                # Wizard reset ref (filled after wizard is built)
                _wizard_reset_ref: dict = {"fn": None}

                def on_project_change(e) -> None:
                    nicegui_app.storage.user["current_project_id"] = e.value
                    _refresh_project_info()
                    # Reset wizard on project change
                    if _wizard_reset_ref["fn"]:
                        _wizard_reset_ref["fn"]()

                # GenericEventArguments에는 e.value가 없어 on_value_change를 써야 한다.
                project_sel.on_value_change(on_project_change)

        # -- Project info banner --
        project_banner = ui.element("div").classes("dg-banner dg-banner-info w-full hidden")
        banner_label = ui.label("").style("font-size: 13px")

        def _refresh_project_info() -> None:
            pid = nicegui_app.storage.user.get("current_project_id")
            if not pid:
                project_banner.classes("hidden", remove=False)
                return
            p = get_project(pid)
            if not p:
                return
            project_banner.classes(remove="hidden")
            banner_label.set_text(
                f"[{p.get('name','')}] {p.get('industry','')} · {p.get('region','')} · "
                f"예산 {p.get('budget','')} · 기간 {p.get('period','')}"
            )

        with project_banner:
            ui.icon("info", size="18px")
            banner_label

        _refresh_project_info()

        # -- Options --
        with ui.card().classes("dg-card w-full"):
            section_header("tune", "생성 옵션")
            with ui.row().classes("items-start gap-8 flex-wrap"):
                with ui.column().classes("gap-1"):
                    ui.label("AI 엔진").classes("dg-label-sm")
                    engine_radio = ui.radio(
                        {"claude": "Claude", "gpt": "GPT", "coordinate": "Claude+GPT 조율"},
                        value="claude",
                    ).props("inline").classes("dg-radio")

                with ui.column().classes("gap-1"):
                    ui.label("프롬프트 카테고리").classes("dg-label-sm")
                    cat_options = {cid: cat["label"] for cid, cat in CATEGORIES.items()}
                    category_sel = ui.select(
                        cat_options, label="카테고리 선택", value="default",
                    ).classes("w-72 dg-select")

                    strategy_options = {"A": "A: 진정성/스토리", "B": "B: 긴급성/한정", "C": "C: 가성비/구성"}
                    strategy_sel = ui.select(
                        strategy_options, label="전략 선택", value="A",
                    ).classes("w-72 dg-select")
                    strategy_sel.set_visibility(False)

                    def _on_category_change(e) -> None:
                        strategy_sel.set_visibility(e.value == "restaurant")

                    category_sel.on_value_change(_on_category_change)

                with ui.column().classes("flex-1 gap-1"):
                    ui.label("추가 요청 사항 (선택)").classes("dg-label-sm")
                    extra_input = ui.textarea(
                        placeholder="예: 20~30대 직장인 타겟 강조, 쿠폰 위주 카피 등"
                    ).classes("w-full dg-input").props("rows=2 outlined")

        # -- System prompt editor --
        with ui.expansion("시스템 프롬프트 편집", icon="edit_note").classes(
            "dg-expansion w-full"
        ).props("dense"):
            with ui.column().classes("w-full gap-3"):
                with ui.element("div").classes("dg-banner dg-banner-info w-full"):
                    ui.icon("info", size="18px")
                    ui.label(
                        "AI에게 전달되는 시스템 지침을 직접 고칠 수 있어요. "
                        "'저장'을 누르면 다음 생성부터 적용돼요."
                    )
                _custom_prompt = get_setting("custom_system_prompt")
                prompt_editor = ui.textarea(
                    value=_custom_prompt or SYSTEM_GUIDE_PLANNING,
                ).classes("w-full dg-input").props("rows=12 outlined")

                _prompt_modified = ui.label("").classes("dg-label-sm hidden")

                with ui.row().classes("gap-2"):
                    def _save_prompt() -> None:
                        val = prompt_editor.value.strip()
                        if val:
                            save_setting("custom_system_prompt", val)
                            _prompt_modified.set_text("저장했어요!")
                            _prompt_modified.classes(remove="hidden")
                            ui.notify("시스템 프롬프트를 저장했어요. 다음 생성부터 적용돼요.", type="positive")

                    def _reset_prompt() -> None:
                        delete_setting("custom_system_prompt")
                        prompt_editor.set_value(SYSTEM_GUIDE_PLANNING)
                        _prompt_modified.set_text("기본값으로 되돌렸어요")
                        _prompt_modified.classes(remove="hidden")
                        ui.notify("기본 시스템 프롬프트로 되돌렸어요.", type="info")

                    ui.button("저장", icon="save", on_click=_save_prompt).classes("dg-btn-primary dg-btn-sm")
                    ui.button("기본값으로 초기화", icon="restart_alt", on_click=_reset_prompt).classes("dg-btn-secondary dg-btn-sm")
                _prompt_modified

        # -- Wizard UI --
        from app.pages.planning_wizard import build_wizard_ui
        wizard_reset_fn = build_wizard_ui(
            engine_radio=engine_radio,
            category_sel=category_sel,
            strategy_sel=strategy_sel,
            extra_input=extra_input,
            prompt_editor=prompt_editor,
        )
        _wizard_reset_ref["fn"] = wizard_reset_fn

