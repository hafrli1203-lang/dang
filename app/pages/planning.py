"""Screen 2 – 광고 기획 + 콘텐츠 생성."""
import asyncio
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
from app.ai_engine import build_planning_prompt, SYSTEM_GUIDE_PLANNING, CATEGORIES, validate_planning_output, build_repair_prompt
from app.ai.providers import get_provider, ClaudeProvider, GeminiProvider
from app.reporting.docx_report import build_planning_docx


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

        # ── Result area ────────────────────────────────────────────────────
        result_card = ui.card().classes("w-full hidden")
        result_md = ui.markdown("").classes("w-full prose max-w-none")

        with result_card:
            result_md

        # ── stored content ref ─────────────────────────────────────────────
        _state: dict = {"content": "", "engine": "claude"}

        # Load latest saved content if available
        pid0 = nicegui_app.storage.user.get("current_project_id")
        if pid0:
            saved = get_latest_content(pid0)
            if saved:
                _state["content"] = saved["content"]
                _state["engine"] = saved.get("engine", "claude")
                result_md.set_content(saved["content"])
                result_card.classes(remove="hidden")

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
                )
                loop = asyncio.get_event_loop()

                if _plan_state["cancelled"]:
                    ui.notify("생성이 중단되었습니다.", type="warning")
                    return

                if engine == "both":
                    _set_step("2/3 Claude + Gemini 동시 호출 중...")
                    claude_p = ClaudeProvider()
                    gemini_p = GeminiProvider()
                    c_text, g_text = await asyncio.gather(
                        loop.run_in_executor(None, lambda: claude_p.generate_text(prompt, system_prompt=guide)),
                        loop.run_in_executor(None, lambda: gemini_p.generate_text(prompt, system_prompt=guide)),
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

                # ── 소식글 검증 + 자동 보정 (default 카테고리만) ──
                if cat == "default":
                    validation_missing = validate_planning_output(content)
                    if validation_missing:
                        _set_step("검증 실패 — 자동 보정 중...")
                        repair_prompt = build_repair_prompt(content, validation_missing)
                        try:
                            if engine == "both":
                                # both인 경우 Claude 결과만 보정
                                repaired = await loop.run_in_executor(
                                    None, lambda: ClaudeProvider().generate_text(repair_prompt, system_prompt=guide),
                                )
                            else:
                                repair_provider = get_provider(engine)
                                repaired = await loop.run_in_executor(
                                    None, lambda: repair_provider.generate_text(repair_prompt, system_prompt=guide),
                                )
                            # 2차 검증
                            second_check = validate_planning_output(repaired)
                            if not second_check:
                                content = repaired
                            else:
                                # 2회째도 실패 — 원본 유지 + 경고
                                ui.notify(
                                    f"자동 보정 후에도 미달 항목 {len(second_check)}건. 원본 사용.",
                                    type="warning", timeout=8000,
                                )
                        except Exception as repair_exc:
                            ui.notify(f"자동 보정 실패: {repair_exc}", type="warning", timeout=6000)

                _set_step("3/3 결과 저장 중...")
                _state["content"] = content
                _state["engine"] = engine
                save_generated_content(pid, engine, content)

                result_md.set_content(content)
                result_card.classes(remove="hidden")
                ui.notify("기획 콘텐츠 생성 완료!", type="positive")
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
                loop = asyncio.get_event_loop()
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
                loop = asyncio.get_event_loop()
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

        # ── Diagnostic panels ─────────────────────────────────────────────
        create_log_panel()
        create_path_info_panel()
