"""Screen 2 – 광고 기획 + 콘텐츠 생성."""
import asyncio
import json
import re
from pathlib import Path

from nicegui import ui, app as nicegui_app

from app.common import create_nav, no_project_notice, create_log_panel, create_path_info_panel
from app.export_manager import ExportManager
from app.database import (
    get_project,
    get_projects,
    get_latest_content,
    save_generated_content,
)
from app.ai_engine import build_planning_prompt, SYSTEM_GUIDE_PLANNING, CATEGORIES
from app.ai.news_post_guard import validate_news_post, build_news_post_repair_prompt, _split_blocks
from app.content.news_post_rules import (
    validate_news_post as validate_news_post_bc,
    build_news_repair_prompt as build_news_repair_bc,
)
from app.ai.providers import get_provider, ClaudeProvider, GeminiProvider
from app.reporting.docx_report import build_planning_docx


def _parse_planning_sections(content: str) -> dict:
    """소식글 콘텐츠를 섹션별로 파싱.

    Returns dict with keys: version_1, version_2, summary, ad_copies, raw
    """
    blocks = _split_blocks(content)

    v1_text = ""
    v2_text = ""
    if "의심해소" in blocks:
        v1_text = "【소식글 1 | 의심해소형】\n" + blocks["의심해소"]
    if "가성비" in blocks:
        v2_text = "【소식글 2 | 가성비형】\n" + blocks["가성비"]

    # ## 헤더 기준으로 기획요약/카피 분리
    summary = ""
    ad_copies = ""
    parts = re.split(r"(?m)^(## .+)", content)
    for i, part in enumerate(parts):
        if not part.startswith("## "):
            continue
        if "기획" in part and "요약" in part:
            summary = parts[i + 1] if i + 1 < len(parts) else ""
        elif "카피" in part or "광고" in part:
            ad_copies = parts[i + 1] if i + 1 < len(parts) else ""

    return {
        "version_1": v1_text,
        "version_2": v2_text,
        "summary": summary,
        "ad_copies": ad_copies,
        "raw": content,
    }


@ui.page("/planning")
def planning_page() -> None:
    create_nav("/planning")

    with ui.column().classes("w-full p-6 gap-4"):

        # ── Project selector bar ───────────────────────────────────────────
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center gap-4"):
                ui.label("프로젝트").classes("font-bold text-gray-600 w-20")
                projects = get_projects()
                options = {p["id"]: f"{p['name']} ({p.get('region','')})" for p in projects}
                saved_pid = nicegui_app.storage.user.get("current_project_id")
                project_sel = ui.select(
                    options,
                    label="프로젝트 선택",
                    value=saved_pid if saved_pid in options else None,
                ).classes("flex-1")

                def on_project_change(e) -> None:
                    nicegui_app.storage.user["current_project_id"] = e.value
                    _refresh_project_info()

                project_sel.on("update:model-value", on_project_change)

        # ── Project info banner ────────────────────────────────────────────
        project_banner = ui.card().classes("w-full bg-orange-50 hidden")
        banner_label = ui.label("").classes("text-sm text-gray-600")

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
            banner_label

        _refresh_project_info()

        # ── Top-level tabs ────────────────────────────────────────────
        with ui.tabs().classes("w-full") as top_tabs:
            tab_news = ui.tab("소식글 기획")
            tab_proposal = ui.tab("운영 제안서")
        with ui.tab_panels(top_tabs, value=tab_news).classes("w-full"):
            with ui.tab_panel(tab_news):
                # ── Options row ────────────────────────────────────────────────────
                with ui.card().classes("w-full"):
                    ui.label("생성 옵션").classes("font-bold text-gray-700 mb-2")
                    with ui.row().classes("items-start gap-8 flex-wrap"):
                        with ui.column().classes("gap-1"):
                            ui.label("AI 엔진").classes("text-sm font-medium text-gray-500")
                            engine_radio = ui.radio(
                                {"claude": "Claude", "gemini": "Gemini", "both": "둘 다 (비교)"},
                                value="claude",
                            ).props("inline")

                        with ui.column().classes("gap-1"):
                            ui.label("프롬프트 카테고리").classes("text-sm font-medium text-gray-500")
                            cat_options = {cid: cat["label"] for cid, cat in CATEGORIES.items()}
                            category_sel = ui.select(
                                cat_options,
                                label="카테고리 선택",
                                value="default",
                            ).classes("w-72")

                            # 전략 선택 (restaurant일 때만 표시)
                            strategy_options = {"A": "A: 진정성/스토리", "B": "B: 긴급성/한정", "C": "C: 가성비/구성"}
                            strategy_sel = ui.select(
                                strategy_options,
                                label="전략 선택",
                                value="A",
                            ).classes("w-72")
                            strategy_sel.set_visibility(False)

                            def _on_category_change(e) -> None:
                                strategy_sel.set_visibility(e.value == "restaurant")

                            category_sel.on("update:model-value", _on_category_change)

                        with ui.column().classes("flex-1 gap-1"):
                            ui.label("추가 요청 사항 (선택)").classes(
                                "text-sm font-medium text-gray-500"
                            )
                            extra_input = ui.textarea(
                                placeholder="예: 20~30대 직장인 타겟 강조, 쿠폰 위주 카피 등"
                            ).classes("w-full").props("rows=2 outlined")

                # ── Action buttons ─────────────────────────────────────────────────
                _plan_state: dict = {"cancelled": False}

                with ui.row().classes("gap-3 items-center"):
                    gen_btn = ui.button("✨ 기획 콘텐츠 생성", on_click=lambda: asyncio.ensure_future(_generate())).classes(
                        "bg-orange-500 text-white text-base px-6"
                    )
                    export_default_btn = ui.button(
                        "기본 폴더에 저장 (권장)",
                        on_click=lambda: asyncio.ensure_future(_export_default()),
                    ).classes("bg-green-600 text-white text-base px-6")
                    export_saveas_btn = ui.button(
                        "다른 위치로 저장...",
                        on_click=lambda: asyncio.ensure_future(_export_saveas()),
                    ).classes("bg-green-700 text-white text-base px-6").props("outline")
                    cancel_btn = ui.button(
                        "중단",
                        on_click=lambda: _plan_state.__setitem__("cancelled", True),
                    ).classes("bg-red-500 text-white text-sm px-4 hidden")
                    spinner = ui.spinner(size="32px").classes("hidden")
                    step_label = ui.label("").classes("text-sm text-gray-500 hidden")
                    download_status = ui.label("").classes("text-sm text-green-600 font-medium hidden")

                def _set_step(text: str) -> None:
                    step_label.classes(remove="hidden")
                    step_label.set_text(text)

                # ── Result area (탭 UI) ──────────────────────────────────────────
                result_card = ui.card().classes("w-full hidden")
                with result_card:
                    validation_banner = ui.label("").classes(
                        "w-full text-sm font-medium px-3 py-2 rounded mb-2 hidden"
                    )
                    retry_repair_btn = ui.button(
                        "재보정 시도",
                        icon="refresh",
                        on_click=lambda: asyncio.ensure_future(_retry_repair()),
                    ).classes("text-sm bg-orange-500 text-white hidden")
                    with ui.tabs().classes("w-full") as result_tabs:
                        tab_all = ui.tab("전체 보기")
                        tab_v1 = ui.tab("소식글 1 (의심해소)")
                        tab_v2 = ui.tab("소식글 2 (가성비)")

                    with ui.tab_panels(result_tabs, value=tab_all).classes("w-full"):
                        with ui.tab_panel(tab_all):
                            result_md_all = ui.markdown("").classes("w-full prose max-w-none")
                        with ui.tab_panel(tab_v1):
                            with ui.row().classes("w-full justify-end mb-1"):
                                ui.button("복사", icon="content_copy",
                                          on_click=lambda: _copy_section("version_1"),
                                          ).classes("text-xs bg-gray-100")
                            result_md_v1 = ui.markdown("").classes("w-full prose max-w-none")
                        with ui.tab_panel(tab_v2):
                            with ui.row().classes("w-full justify-end mb-1"):
                                ui.button("복사", icon="content_copy",
                                          on_click=lambda: _copy_section("version_2"),
                                          ).classes("text-xs bg-gray-100")
                            result_md_v2 = ui.markdown("").classes("w-full prose max-w-none")

                # ── stored content ref ─────────────────────────────────────────────
                _state: dict = {"content": "", "engine": "claude"}

                def _copy_section(key: str) -> None:
                    sections = _parse_planning_sections(_state.get("content", ""))
                    text = sections.get(key, "")
                    if not text:
                        ui.notify("복사할 내용이 없습니다.", type="warning")
                        return
                    escaped = json.dumps(text)
                    ui.run_javascript(f'navigator.clipboard.writeText({escaped})')
                    ui.notify("클립보드에 복사되었습니다!", type="positive", timeout=2000)

                def _update_result_display(
                    content: str,
                    validation_ok: bool | None = None,
                    error_count: int = 0,
                ) -> None:
                    """결과 영역을 업데이트. validation_ok=None이면 배너 숨김."""
                    sections = _parse_planning_sections(content)
                    result_md_all.set_content(content)
                    result_md_v1.set_content(
                        sections["version_1"] or "*의심해소형 블록을 찾을 수 없습니다.*"
                    )
                    result_md_v2.set_content(
                        sections["version_2"] or "*가성비형 블록을 찾을 수 없습니다.*"
                    )
                    result_card.classes(remove="hidden")
                    if validation_ok is True:
                        validation_banner.classes(remove="hidden")
                        validation_banner.classes(
                            "bg-green-100 text-green-800",
                            remove="bg-red-100 text-red-800",
                        )
                        validation_banner.set_text("✓ 소식글 검증 통과")
                        retry_repair_btn.classes("hidden")
                    elif validation_ok is False:
                        validation_banner.classes(remove="hidden")
                        validation_banner.classes(
                            "bg-red-100 text-red-800",
                            remove="bg-green-100 text-green-800",
                        )
                        validation_banner.set_text(
                            f"✗ 검증 미달 {error_count}건 — 내보내기 비활성화"
                        )
                        retry_repair_btn.classes(remove="hidden")
                    else:
                        validation_banner.classes("hidden")
                        retry_repair_btn.classes("hidden")

                async def _retry_repair() -> None:
                    """검증 미달 시 추가 보정 1회 시도."""
                    content = _state.get("content", "")
                    if not content:
                        ui.notify("보정할 콘텐츠가 없습니다.", type="warning")
                        return
                    pid = nicegui_app.storage.user.get("current_project_id")
                    project = get_project(pid) if pid else {}
                    engine = _state.get("engine", "claude")
                    extra = extra_input.value
                    cat = category_sel.value or "default"
                    from app.ai_engine import _get_planning_guide
                    guide = _get_planning_guide(engine) if cat == "default" else CATEGORIES.get(cat, CATEGORIES["default"])["system_guide"]
                    loop = asyncio.get_running_loop()

                    retry_repair_btn.props("disabled loading")
                    try:
                        if cat == "restaurant" or re.search(r"\[소식글\s*Type\s*[BC]", content, re.IGNORECASE):
                            bc_errors = validate_news_post_bc(content)
                            if not bc_errors:
                                _update_result_display(content, validation_ok=True, error_count=0)
                                export_default_btn.props(remove="disabled")
                                export_saveas_btn.props(remove="disabled")
                                ui.notify("검증 통과!", type="positive")
                                return
                            ctx = {
                                "name": project.get("name", ""),
                                "industry": project.get("industry", ""),
                                "region": project.get("region", ""),
                                "benefits": project.get("benefits", ""),
                                "goal": project.get("goal", ""),
                                "period": project.get("period", ""),
                                "extra": extra,
                            }
                            repair_prompt = build_news_repair_bc(content, bc_errors, ctx)
                        else:
                            ok, errors = validate_news_post(content)
                            if ok:
                                _update_result_display(content, validation_ok=True, error_count=0)
                                export_default_btn.props(remove="disabled")
                                export_saveas_btn.props(remove="disabled")
                                ui.notify("검증 통과!", type="positive")
                                return
                            repair_prompt = build_news_post_repair_prompt(
                                errors=errors, project=project, extra=extra,
                            )

                        provider = get_provider(engine)
                        repaired = await loop.run_in_executor(
                            None, lambda: provider.generate_text(repair_prompt, system_prompt=guide),
                        )
                        _state["content"] = repaired
                        save_generated_content(pid, engine, repaired)

                        # Re-validate
                        if cat == "restaurant" or re.search(r"\[소식글\s*Type\s*[BC]", repaired, re.IGNORECASE):
                            final_errors = validate_news_post_bc(repaired)
                            final_ok = len(final_errors) == 0
                            final_count = len(final_errors)
                        else:
                            final_ok, final_errs = validate_news_post(repaired)
                            final_count = len(final_errs) if not final_ok else 0

                        _update_result_display(repaired, validation_ok=final_ok, error_count=final_count)
                        if final_ok:
                            export_default_btn.props(remove="disabled")
                            export_saveas_btn.props(remove="disabled")
                            ui.notify("재보정 성공! 검증 통과.", type="positive")
                        else:
                            ui.notify(f"재보정 후에도 미달 {final_count}건.", type="warning", timeout=8000)
                    except Exception as exc:
                        ui.notify(f"재보정 실패: {exc}", type="negative", timeout=8000)
                    finally:
                        retry_repair_btn.props(remove="disabled loading")

                # Load latest saved content if available
                pid0 = nicegui_app.storage.user.get("current_project_id")
                if pid0:
                    saved = get_latest_content(pid0)
                    if saved:
                        _state["content"] = saved["content"]
                        _state["engine"] = saved.get("engine", "claude")
                        # Detect format: Type B/C headers → restaurant, else default
                        _saved_text = saved["content"] or ""
                        if re.search(r"\[소식글\s*Type\s*[BC]", _saved_text, re.IGNORECASE):
                            _saved_bc_errors = validate_news_post_bc(_saved_text)
                            saved_ok = len(_saved_bc_errors) == 0
                            saved_error_count = len(_saved_bc_errors)
                        else:
                            saved_ok, saved_errors = validate_news_post(_saved_text)
                            saved_error_count = len(saved_errors) if not saved_ok else 0
                        _update_result_display(
                            saved["content"],
                            validation_ok=saved_ok,
                            error_count=saved_error_count,
                        )
                        if not saved_ok:
                            export_default_btn.props("disabled")
                            export_saveas_btn.props("disabled")

                # ── Handlers ───────────────────────────────────────────────────────

                async def _generate() -> None:
                    pid = nicegui_app.storage.user.get("current_project_id")
                    if not pid:
                        ui.notify("프로젝트를 먼저 선택해주세요.", type="warning")
                        return
                    project = get_project(pid)
                    if not project:
                        ui.notify("프로젝트를 찾을 수 없습니다.", type="negative")
                        return

                    engine = engine_radio.value
                    extra = extra_input.value
                    cat = category_sel.value or "default"
                    strat = strategy_sel.value or "A"

                    _plan_state["cancelled"] = False
                    spinner.classes(remove="hidden")
                    gen_btn.props("disabled")
                    cancel_btn.classes(remove="hidden")

                    try:
                        _set_step("1/3 프롬프트 생성 중...")
                        guide, prompt = build_planning_prompt(
                            project, extra, category=cat, strategy=strat,
                            engine=engine if engine != "both" else "",
                        )
                        loop = asyncio.get_running_loop()

                        if _plan_state["cancelled"]:
                            ui.notify("생성이 중단되었습니다.", type="warning")
                            return

                        if engine == "both":
                            _set_step("2/3 Claude + Gemini 동시 호출 중...")
                            claude_guide, _ = build_planning_prompt(
                                project, extra, category=cat, strategy=strat, engine="claude",
                            )
                            gemini_guide, _ = build_planning_prompt(
                                project, extra, category=cat, strategy=strat, engine="gemini",
                            )
                            claude_p = ClaudeProvider()
                            gemini_p = GeminiProvider()
                            c_text, g_text = await asyncio.gather(
                                loop.run_in_executor(None, lambda: claude_p.generate_text(prompt, system_prompt=claude_guide)),
                                loop.run_in_executor(None, lambda: gemini_p.generate_text(prompt, system_prompt=gemini_guide)),
                            )
                            if _plan_state["cancelled"]:
                                ui.notify("생성이 중단되었습니다.", type="warning")
                                return
                            content = (
                                f"## [Claude 결과]\n\n{c_text}\n\n"
                                f"---\n\n## [Gemini 결과]\n\n{g_text}"
                            )
                        else:
                            _set_step(f"2/3 {engine.capitalize()} 호출 중...")
                            provider = get_provider(engine)
                            content = await loop.run_in_executor(None, lambda: provider.generate_text(prompt, system_prompt=guide))
                            if _plan_state["cancelled"]:
                                ui.notify("생성이 중단되었습니다.", type="warning")
                                return

                        # ── 소식글 검증 + 자동 보정 (both 제외, 최대 2회 retry) ──
                        _validation_ok = True
                        _final_error_count = 0
                        _has_validation = cat in ("default", "restaurant") and engine != "both"

                        if cat == "default" and engine != "both":
                            for _attempt in range(1, 3):  # 최대 2회 repair
                                ok, validation_errors = validate_news_post(content)
                                if ok:
                                    break
                                _set_step(f"검증 실패 — 자동 보정 {_attempt}/2 회차...")
                                repair_prompt = build_news_post_repair_prompt(
                                    errors=validation_errors,
                                    project=project,
                                    extra=extra,
                                )
                                try:
                                    repair_provider = get_provider(engine)
                                    repaired = await loop.run_in_executor(
                                        None, lambda: repair_provider.generate_text(repair_prompt, system_prompt=guide),
                                    )
                                    content = repaired
                                except Exception as repair_exc:
                                    ui.notify(f"자동 보정 {_attempt}회차 실패: {repair_exc}", type="warning", timeout=6000)
                                    break

                            final_ok, final_errors = validate_news_post(content)
                            if not final_ok:
                                _validation_ok = False
                                _final_error_count = len(final_errors)
                                error_text = "\n".join(f"  {e}" for e in final_errors)
                                ui.notify(
                                    f"2회 보정 후에도 미달 {len(final_errors)}건.\n{error_text}",
                                    type="negative", timeout=12000, close_button="확인",
                                )
                                export_default_btn.props("disabled")
                                export_saveas_btn.props("disabled")

                        elif cat == "restaurant" and engine != "both":
                            # Type B(긴급성) / Type C(가성비) 검증
                            for _attempt in range(1, 3):
                                bc_errors = validate_news_post_bc(content)
                                if not bc_errors:
                                    break
                                _set_step(f"검증 실패 — 자동 보정 {_attempt}/2 회차...")
                                ctx = {
                                    "name": project.get("name", ""),
                                    "industry": project.get("industry", ""),
                                    "region": project.get("region", ""),
                                    "benefits": project.get("benefits", ""),
                                    "goal": project.get("goal", ""),
                                    "period": project.get("period", ""),
                                    "extra": extra,
                                }
                                repair_prompt = build_news_repair_bc(content, bc_errors, ctx)
                                try:
                                    repair_provider = get_provider(engine)
                                    repaired = await loop.run_in_executor(
                                        None, lambda: repair_provider.generate_text(repair_prompt, system_prompt=guide),
                                    )
                                    content = repaired
                                except Exception as repair_exc:
                                    ui.notify(f"자동 보정 {_attempt}회차 실패: {repair_exc}", type="warning", timeout=6000)
                                    break

                            final_bc_errors = validate_news_post_bc(content)
                            if final_bc_errors:
                                _validation_ok = False
                                _final_error_count = len(final_bc_errors)
                                error_text = "\n".join(f"  {e}" for e in final_bc_errors)
                                ui.notify(
                                    f"2회 보정 후에도 미달 {len(final_bc_errors)}건.\n{error_text}",
                                    type="negative", timeout=12000, close_button="확인",
                                )
                                export_default_btn.props("disabled")
                                export_saveas_btn.props("disabled")

                        _set_step("3/3 결과 저장 중...")
                        _state["content"] = content
                        _state["engine"] = engine
                        save_generated_content(pid, engine, content)

                        _show_validation = _has_validation
                        _update_result_display(
                            content,
                            validation_ok=_validation_ok if _show_validation else None,
                            error_count=_final_error_count,
                        )

                        if _validation_ok:
                            export_default_btn.props(remove="disabled")
                            export_saveas_btn.props(remove="disabled")
                            ui.notify("기획 콘텐츠 생성 완료!", type="positive")
                        else:
                            ui.notify("콘텐츠가 생성되었지만 검증 미달입니다. 내보내기가 비활성화되었습니다.", type="warning", timeout=10000)
                    except Exception as exc:
                        ui.notify(f"오류: {exc}", type="negative", timeout=8000)
                    finally:
                        spinner.classes("hidden")
                        cancel_btn.classes("hidden")
                        step_label.classes("hidden")
                        gen_btn.props(remove="disabled")

                def _build_docx_bytes() -> tuple[bytes, str]:
                    """Build planning DOCX bytes + filename. Raises on error."""
                    import tempfile

                    content = _state.get("content", "")
                    if not content:
                        raise ValueError("먼저 콘텐츠를 생성해주세요.")
                    pid = nicegui_app.storage.user.get("current_project_id")
                    project = get_project(pid) if pid else None
                    if not project:
                        raise ValueError("프로젝트를 선택해주세요.")

                    name = project.get("name", "unknown")
                    project_meta = {
                        k: project.get(k, "")
                        for k in ("name", "period", "goal", "industry", "region", "budget")
                    }
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        tmp_path = Path(tmp_dir) / f"기획서_{name}.docx"
                        build_planning_docx(project_meta, content, tmp_path)
                        return tmp_path.read_bytes(), f"기획서_{name}.docx"

                async def _export_default() -> None:
                    export_default_btn.props("disabled loading")
                    download_status.classes(remove="hidden")
                    download_status.set_text("DOCX 파일 준비 중...")
                    try:
                        loop = asyncio.get_running_loop()
                        docx_bytes, fname = await loop.run_in_executor(None, _build_docx_bytes)
                        ExportManager.save_default(docx_bytes, fname)
                        download_status.set_text(f"✅ {fname} 저장 완료")
                        ui.notify(f"📥 {fname}", type="positive", timeout=8000, close_button="확인")
                    except ValueError as ve:
                        ui.notify(str(ve), type="warning")
                    except Exception as exc:
                        download_status.set_text("⚠️ 내보내기 오류")
                        ui.notify(f"내보내기 오류: {exc}", type="negative")
                    finally:
                        export_default_btn.props(remove="disabled loading")

                async def _export_saveas() -> None:
                    export_saveas_btn.props("disabled loading")
                    download_status.classes(remove="hidden")
                    download_status.set_text("DOCX 파일 준비 중...")
                    try:
                        loop = asyncio.get_running_loop()
                        docx_bytes, fname = await loop.run_in_executor(None, _build_docx_bytes)
                        ok = await ExportManager.save_as(docx_bytes, fname)
                        if ok:
                            download_status.set_text(f"✅ {fname} 저장 완료")
                        else:
                            download_status.set_text("저장 취소됨")
                    except ValueError as ve:
                        ui.notify(str(ve), type="warning")
                    except Exception as exc:
                        download_status.set_text("⚠️ 내보내기 오류")
                        ui.notify(f"내보내기 오류: {exc}", type="negative")
                    finally:
                        export_saveas_btn.props(remove="disabled loading")

                # ── 썸네일 생성 패널 ──────────────────────────────────────────────
                _thumb_state: dict = {
                    "ref_images": [],  # list of (bytes, mime_type)
                    "result_bytes": None,
                    "history": [],  # list of (bytes, prompt_snippet) — max 10
                }
                _MAX_THUMB_HISTORY = 10

                with ui.expansion("썸네일 생성", icon="palette").classes(
                    "w-full bg-purple-50 mt-4"
                ):
                    ui.label(
                        "기획 결과를 바탕으로 광고 썸네일 이미지를 생성합니다."
                    ).classes("text-xs text-gray-400 mb-3")

                    # 레퍼런스 이미지 업로드 (0~3장)
                    with ui.row().classes("items-start gap-4 flex-wrap"):
                        with ui.column().classes("gap-1"):
                            ui.label("레퍼런스 이미지 (0~3장)").classes("text-sm font-medium text-gray-600")
                            thumb_ref_upload = ui.upload(
                                label="이미지 선택",
                                auto_upload=True,
                                on_upload=lambda e: asyncio.ensure_future(_thumb_handle_ref(e)),
                                max_files=3,
                            ).classes("max-w-xs").props('accept="image/*" multiple')
                            thumb_ref_preview = ui.row().classes("gap-2 flex-wrap")
                            ui.button(
                                "레퍼런스 초기화",
                                on_click=lambda: _thumb_clear_refs(),
                            ).classes("text-xs bg-gray-200 text-gray-600")

                    # 비율 + 모드 선택
                    with ui.row().classes("items-start gap-8 flex-wrap mt-3"):
                        with ui.column().classes("gap-1"):
                            ui.label("비율").classes("text-sm font-medium text-gray-600")
                            thumb_ratio_sel = ui.select(
                                {"1:1": "1:1 (정사각형)", "4:5": "4:5 (인스타)", "9:16": "9:16 (스토리)"},
                                value=["1:1"],
                                label="비율 선택 (복수 가능)",
                                multiple=True,
                            ).classes("w-48")

                        with ui.column().classes("gap-1"):
                            ui.label("생성 모드").classes("text-sm font-medium text-gray-600")
                            thumb_mode_sel = ui.select(
                                {"style_fusion": "Style Fusion (스타일 합성)", "image_mapping": "Image Mapping (상품 매핑)"},
                                value="style_fusion",
                                label="모드 선택",
                            ).classes("w-64")

                    # 텍스트 입력
                    with ui.row().classes("items-start gap-4 flex-wrap mt-3 w-full"):
                        thumb_main_input = ui.input(
                            label="메인 카피",
                            placeholder="예: 매일 아침 직접 반죽하는 빵",
                        ).classes("flex-1").props("outlined dense")
                        thumb_sub_input = ui.input(
                            label="서브 카피",
                            placeholder="예: 동네 빵집의 정성",
                        ).classes("flex-1").props("outlined dense")
                        thumb_cta_input = ui.input(
                            label="CTA",
                            placeholder="예: 지금 방문하기",
                            value="자세히 보기",
                        ).classes("w-40").props("outlined dense")

                    thumb_visual_input = ui.textarea(
                        placeholder="비주얼 가이드: 따뜻한 오렌지톤, 밝은 자연광, 음식 클로즈업 등",
                        label="비주얼 가이드 (선택)",
                    ).classes("w-full mt-2").props("rows=2 outlined dense")

                    # 자동 추출 버튼
                    ui.button(
                        "기획 결과에서 카피 자동 추출",
                        on_click=lambda: _thumb_auto_extract(),
                    ).classes("text-xs bg-orange-100 text-orange-700 mt-1")

                    # PIL 텍스트 오버레이 옵션
                    thumb_overlay_check = ui.checkbox(
                        "PIL 텍스트 오버레이 (카피를 이미지 위에 합성)",
                        value=False,
                    ).classes("text-sm mt-2")

                    # 생성 버튼 + 결과
                    with ui.row().classes("gap-3 items-center mt-3"):
                        thumb_gen_btn = ui.button(
                            "썸네일 생성",
                            on_click=lambda: asyncio.ensure_future(_thumb_generate()),
                            icon="palette",
                        ).classes("bg-purple-600 text-white px-6")
                        thumb_save_btn = ui.button(
                            "PNG 저장",
                            on_click=lambda: _thumb_save(),
                            icon="save",
                        ).classes("bg-green-600 text-white px-4 hidden")
                        thumb_spinner = ui.spinner(size="28px").classes("hidden")
                        thumb_status = ui.label("").classes("text-sm text-gray-500 hidden")

                    thumb_result_container = ui.column().classes("w-full items-center mt-3")

                    # ── 이미지 히스토리 ──
                    thumb_history_label = ui.label("").classes("text-xs text-gray-400 mt-2 hidden")
                    thumb_history_strip = ui.row().classes(
                        "w-full overflow-x-auto gap-2 mt-1 hidden"
                    ).style("max-height: 120px")

                def _refresh_thumb_history() -> None:
                    """히스토리 스트립 UI 갱신."""
                    import base64
                    history = _thumb_state["history"]
                    if not history:
                        thumb_history_strip.classes("hidden")
                        thumb_history_label.classes("hidden")
                        return
                    thumb_history_label.set_text(f"이전 생성 ({len(history)}장)")
                    thumb_history_label.classes(remove="hidden")
                    thumb_history_strip.clear()
                    thumb_history_strip.classes(remove="hidden")
                    with thumb_history_strip:
                        for idx, (img_bytes, snippet) in enumerate(history):
                            b64 = base64.b64encode(img_bytes).decode()
                            with ui.column().classes("items-center cursor-pointer shrink-0"):
                                ui.image(f"data:image/png;base64,{b64}").classes(
                                    "w-20 h-20 object-cover rounded border"
                                ).on("click", lambda _, i=idx: _restore_from_history(i))
                                ui.label(snippet[:12]).classes("text-xs text-gray-400 truncate max-w-20")

                def _restore_from_history(idx: int) -> None:
                    """히스토리에서 이미지를 복원."""
                    import base64
                    history = _thumb_state["history"]
                    if idx < 0 or idx >= len(history):
                        return
                    img_bytes, snippet = history[idx]
                    _thumb_state["result_bytes"] = img_bytes
                    b64 = base64.b64encode(img_bytes).decode()
                    thumb_result_container.clear()
                    with thumb_result_container:
                        ui.image(f"data:image/png;base64,{b64}").classes(
                            "max-w-lg rounded shadow"
                        )
                        ui.label(f"{len(img_bytes):,} bytes | 복원: {snippet[:20]}").classes(
                            "text-xs text-gray-400"
                        )
                    thumb_save_btn.classes(remove="hidden")
                    ui.notify(f"이미지 복원됨: {snippet[:20]}", type="info", timeout=2000)

                # ── 썸네일 핸들러 ─────────────────────────────────────────────────

                async def _thumb_handle_ref(e) -> None:
                    import base64
                    try:
                        data = await e.file.read()
                        mime = e.file.content_type or "image/png"
                        if len(_thumb_state["ref_images"]) >= 3:
                            ui.notify("레퍼런스 이미지는 최대 3장까지 가능합니다.", type="warning")
                            return
                        _thumb_state["ref_images"].append((data, mime))
                        b64 = base64.b64encode(data).decode()
                        with thumb_ref_preview:
                            ui.image(f"data:{mime};base64,{b64}").classes(
                                "w-20 h-20 object-cover rounded shadow"
                            )
                    except Exception as exc:
                        ui.notify(f"이미지 읽기 오류: {exc}", type="negative")

                def _thumb_clear_refs() -> None:
                    _thumb_state["ref_images"].clear()
                    thumb_ref_preview.clear()
                    thumb_ref_upload.reset()

                def _thumb_auto_extract() -> None:
                    """기획 결과에서 메인 카피, 서브 카피, CTA를 자동 추출."""
                    import re
                    content = _state.get("content", "")
                    if not content:
                        ui.notify("먼저 기획 콘텐츠를 생성해주세요.", type="warning")
                        return

                    # [제목] 패턴에서 메인 카피 추출
                    title_match = re.search(r"\[제목\]\s*(.+)", content)
                    if title_match:
                        thumb_main_input.set_value(title_match.group(1).strip()[:50])

                    # 광고 카피에서 첫 번째 항목을 서브 카피로
                    copy_match = re.search(r"(?:^|\n)\s*1[.)]\s*(.+)", content)
                    if copy_match:
                        thumb_sub_input.set_value(copy_match.group(1).strip()[:50])

                    ui.notify("카피 자동 추출 완료", type="positive", timeout=3000)

                def _calc_canvas(ratio: str) -> tuple[int, int]:
                    """비율 문자열 → (width, height) 픽셀."""
                    ratio_map = {
                        "1:1": (1024, 1024),
                        "4:5": (1024, 1280),
                        "9:16": (720, 1280),
                    }
                    return ratio_map.get(ratio, (1024, 1024))

                async def _thumb_generate() -> None:
                    main_copy = thumb_main_input.value.strip()
                    if not main_copy:
                        ui.notify("메인 카피를 입력해주세요.", type="warning")
                        return

                    thumb_gen_btn.props("disabled loading")
                    thumb_spinner.classes(remove="hidden")
                    thumb_status.classes(remove="hidden")

                    try:
                        from app.ai.image_provider import GeminiImageProvider
                        from app.ai.nanobanana_prompt import compose_style_fusion_prompt, compose_image_mapping_prompt
                        import io
                        import base64

                        ratios = thumb_ratio_sel.value or ["1:1"]
                        if isinstance(ratios, str):
                            ratios = [ratios]
                        mode = thumb_mode_sel.value or "style_fusion"
                        sub_copy = thumb_sub_input.value.strip() or ""
                        cta_copy = thumb_cta_input.value.strip() or "자세히 보기"
                        visual = thumb_visual_input.value.strip() or "clean, modern, bright"
                        provider = GeminiImageProvider()
                        images = _thumb_state["ref_images"] if _thumb_state["ref_images"] else None
                        loop = asyncio.get_running_loop()

                        thumb_status.set_text(f"Gemini 이미지 생성 중... ({len(ratios)}개 비율)")

                        async def _gen_one(ratio: str):
                            w, h = _calc_canvas(ratio)
                            if mode == "style_fusion":
                                prompt = compose_style_fusion_prompt(w, h, ratio, visual, main_copy, sub_copy, cta_copy)
                            else:
                                prompt = compose_image_mapping_prompt(
                                    w, h, ratio,
                                    product_desc=main_copy,
                                    benchmark_desc=visual,
                                    visual_guide=visual,
                                    main=main_copy,
                                    sub=sub_copy,
                                    cta=cta_copy,
                                )
                            pil_img = await loop.run_in_executor(
                                None,
                                lambda: provider.generate_image(prompt, images, aspect_ratio=ratio),
                            )
                            if thumb_overlay_check.value:
                                from app.ai.text_overlay import render_text_overlay
                                pil_img = render_text_overlay(pil_img, main=main_copy, sub=sub_copy, cta=cta_copy)
                            buf = io.BytesIO()
                            pil_img.save(buf, format="PNG")
                            return ratio, w, h, buf.getvalue()

                        # Generate all ratios (sequential to avoid rate limits)
                        results = []
                        for i, ratio in enumerate(ratios):
                            thumb_status.set_text(f"생성 중... {i + 1}/{len(ratios)} ({ratio})")
                            results.append(await _gen_one(ratio))

                        # Display results
                        thumb_result_container.clear()
                        with thumb_result_container:
                            with ui.row().classes("gap-4 flex-wrap justify-center"):
                                for ratio, w, h, img_bytes in results:
                                    b64 = base64.b64encode(img_bytes).decode()
                                    with ui.column().classes("items-center"):
                                        ui.image(f"data:image/png;base64,{b64}").classes(
                                            "max-w-xs rounded shadow"
                                        )
                                        ui.label(f"{ratio} | {w}x{h} | {len(img_bytes):,}B").classes(
                                            "text-xs text-gray-400"
                                        )

                        # Save first result as primary + all to history
                        snippet = main_copy[:20]
                        _thumb_state["result_bytes"] = results[0][3]  # first ratio bytes
                        for ratio, w, h, img_bytes in results:
                            _thumb_state["history"].append((img_bytes, f"{snippet} ({ratio})"))
                        if len(_thumb_state["history"]) > _MAX_THUMB_HISTORY:
                            _thumb_state["history"] = _thumb_state["history"][-_MAX_THUMB_HISTORY:]

                        thumb_save_btn.classes(remove="hidden")
                        thumb_status.set_text(f"생성 완료! ({len(results)}개)")
                        _refresh_thumb_history()
                        ui.notify(f"썸네일 {len(results)}개 생성 완료!", type="positive", timeout=5000)

                    except Exception as exc:
                        thumb_status.set_text("생성 실패")
                        ui.notify(f"썸네일 생성 오류: {exc}", type="negative", timeout=8000)
                        from app.ai.image_provider import get_image_failure_guide
                        guide_text = get_image_failure_guide(str(exc))
                        ui.notify(guide_text, type="info", timeout=15000, close_button="확인")
                    finally:
                        thumb_gen_btn.props(remove="disabled loading")
                        thumb_spinner.classes("hidden")

                def _thumb_save() -> None:
                    from datetime import datetime
                    img_bytes = _thumb_state.get("result_bytes")
                    if not img_bytes:
                        ui.notify("먼저 썸네일을 생성해주세요.", type="warning")
                        return
                    from app.paths import THUMBNAILS_DIR, sanitize_filename
                    pid = nicegui_app.storage.user.get("current_project_id")
                    project = get_project(pid) if pid else None
                    base = sanitize_filename(project.get("name", "thumbnail")) if project else "thumbnail"
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{base}_{ts}.png"
                    ExportManager.save_default(img_bytes, filename, dest_dir=THUMBNAILS_DIR)


            with ui.tab_panel(tab_proposal):
                from app.pages.proposal_tab import build_proposal_tab
                build_proposal_tab()

        # ── Diagnostic panels ─────────────────────────────────────────────
        create_log_panel()
        create_path_info_panel()
