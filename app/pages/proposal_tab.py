"""제안서 탭 UI — /planning 페이지의 '운영 제안서' 탭 내용.

스트리밍 지원: queue.Queue + ui.timer(0.2) 브릿지 패턴.
"""
import asyncio
import logging
import queue
from datetime import datetime
from pathlib import Path

from nicegui import ui, app as nicegui_app

from app.ai_engine import (
    build_proposal_prompt,
    build_proposal_section_prompt,
    parse_proposal_sections,
    calc_kpi,
    SYSTEM_GUIDE_PROPOSAL,
    _PROPOSAL_SECTION_NAMES,
    _PROPOSAL_SECTION_KEYS,
)
from app.ai.providers import get_provider, ClaudeProvider, GeminiProvider
from app.database import (
    get_project,
    get_latest_content,
    save_generated_content,
)
from app.export_manager import ExportManager
from app.reporting.docx_report import build_proposal_docx
from app.reporting.parsers import parse_daangn_csv

_log = logging.getLogger("daangn.proposal_tab")


def build_proposal_tab() -> None:  # noqa: C901
    """Render the proposal tab content inside the planning page."""

    # ── State ─────────────────────────────────────────────────────────────
    _state: dict = {
        "csv_rows": None,
        "csv_warnings": [],
        "sections": {},
        "raw_content": "",
        "kpi": None,
        "generating": False,
    }

    with ui.column().classes("w-full gap-4"):
        ui.label("광고 운영 제안서 생성기").classes("text-xl font-bold text-gray-700")
        ui.label(
            "7섹션 구조의 전문 광고 운영 제안서를 AI로 자동 생성합니다."
        ).classes("text-sm text-gray-500")

        # ── Input form ────────────────────────────────────────────────────
        with ui.card().classes("w-full"):
            ui.label("점포 정보").classes("font-bold text-gray-700 mb-2")
            with ui.row().classes("w-full gap-4 flex-wrap"):
                shop_name_input = ui.input("점포명", placeholder="예: 행복안경").classes("flex-1 min-w-48")
                industry_input = ui.input("업종", placeholder="예: 안경점").classes("flex-1 min-w-48")
                location_input = ui.input("위치", placeholder="예: 부천시 심곡동").classes("flex-1 min-w-48")

            # Pre-fill from selected project
            pid = nicegui_app.storage.user.get("current_project_id")
            if pid:
                proj = get_project(pid)
                if proj:
                    shop_name_input.set_value(proj.get("name", ""))
                    industry_input.set_value(proj.get("industry", ""))
                    location_input.set_value(proj.get("region", ""))

        with ui.card().classes("w-full"):
            ui.label("프로모션 & 타겟").classes("font-bold text-gray-700 mb-2")
            promo_input = ui.textarea(
                "프로모션/상품 정보",
                placeholder="예: 누진렌즈 0원 프로모션, 45-65세 타겟, 3월 한정",
            ).classes("w-full").props("rows=3")
            age_select = ui.select(
                {
                    "전연령": "전연령",
                    "10대-20대": "10대-20대",
                    "20대-30대": "20대-30대",
                    "30대-40대": "30대-40대",
                    "40대-50대": "40대-50대",
                    "50대-60대": "50대-60대",
                    "60대 이상": "60대 이상",
                },
                label="타겟 연령대",
                value="전연령",
            ).classes("w-48")

        with ui.card().classes("w-full"):
            ui.label("이전 캠페인 성과 (선택)").classes("font-bold text-gray-700 mb-2")
            ui.label(
                "CSV 파일을 업로드하면 자동으로 KPI를 계산합니다. 없으면 아래에 직접 입력하세요."
            ).classes("text-xs text-gray-400 mb-2")

            csv_status = ui.label("").classes("text-sm text-gray-500")

            async def _on_csv_upload(e) -> None:
                if not e.content:
                    return
                data = e.content.read()
                rows, warnings = parse_daangn_csv(data)
                _state["csv_rows"] = rows
                _state["csv_warnings"] = warnings
                if rows:
                    _state["kpi"] = calc_kpi(rows)
                    csv_status.set_text(f"CSV 파싱 완료: {len(rows)}행 ({len(warnings)}건 경고)")
                    csv_status.classes("text-green-600", remove="text-gray-500 text-red-500")
                    manual_summary.set_visibility(False)
                else:
                    csv_status.set_text(f"CSV 파싱 실패: {'; '.join(warnings)}")
                    csv_status.classes("text-red-500", remove="text-gray-500 text-green-600")

            ui.upload(
                label="CSV 파일 업로드",
                on_upload=_on_csv_upload,
                auto_upload=True,
            ).props('accept=".csv" flat bordered').classes("w-full max-w-md")

            manual_summary = ui.textarea(
                "이전 캠페인 요약 (CSV 없을 때)",
                placeholder="예: CTR 1.5%, CPC 300원, 월 문의 15건, 총 비용 30만원",
            ).classes("w-full").props("rows=2")

        # ── AI engine selector ────────────────────────────────────────────
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center gap-4"):
                ui.label("AI 엔진").classes("font-bold text-gray-700")
                engine_radio = ui.radio(
                    {"claude": "Claude", "gemini": "Gemini", "both": "둘 다 (비교)"},
                    value="claude",
                ).props("inline")

        # ── Generate button ───────────────────────────────────────────────
        with ui.row().classes("gap-4 items-center"):
            gen_btn = ui.button(
                "제안서 생성",
                on_click=lambda: _generate(),
                icon="auto_awesome",
            ).classes("bg-orange-500 text-white")
            spinner = ui.spinner("dots", size="lg").classes("hidden")
            progress_label = ui.label("").classes("text-sm text-gray-500")

        # ── Result area ───────────────────────────────────────────────────
        result_container = ui.column().classes("w-full gap-2 hidden")

        with result_container:
            with ui.tabs().classes("w-full") as result_tabs:
                tab_full = ui.tab("전체 보기")
                tab_sections = ui.tab("섹션별 보기")

            with ui.tab_panels(result_tabs, value=tab_sections).classes("w-full"):
                with ui.tab_panel(tab_full):
                    result_md_full = ui.markdown("").classes("w-full")

                with ui.tab_panel(tab_sections):
                    sections_container = ui.column().classes("w-full gap-2")

        # ── Export buttons ────────────────────────────────────────────────
        export_row = ui.row().classes("gap-4 hidden")
        with export_row:
            export_default_btn = ui.button(
                "기본 폴더에 저장",
                icon="save",
            ).classes("bg-blue-500 text-white")
            export_saveas_btn = ui.button(
                "다른 위치로 저장",
                icon="save_as",
            ).classes("bg-green-600 text-white")

        # ── Section rendering ─────────────────────────────────────────────

        def _render_sections_now() -> None:
            _render_sections(sections_container, _state, result_md_full, gen_btn, progress_label, regen_fn=_regen_section)
            result_container.classes(remove="hidden")
            export_row.classes(remove="hidden")

        # ── Generate handler ──────────────────────────────────────────────

        async def _generate() -> None:
            if _state["generating"]:
                return
            _state["generating"] = True

            shop_info = {
                "shop_name": shop_name_input.value or "",
                "industry": industry_input.value or "",
                "location": location_input.value or "",
            }

            if not shop_info["shop_name"]:
                ui.notify("점포명을 입력해주세요.", type="warning")
                _state["generating"] = False
                return

            engine = engine_radio.value
            spinner.classes(remove="hidden")
            gen_btn.props("disabled")
            progress_label.set_text("프롬프트 생성 중...")

            try:
                guide, prompt = build_proposal_prompt(
                    shop_info=shop_info,
                    promo_text=promo_input.value or "",
                    target_age=age_select.value or "전연령",
                    prev_csv_rows=_state["csv_rows"],
                    prev_summary=manual_summary.value or "",
                )
                loop = asyncio.get_running_loop()
                content = ""

                if engine == "both":
                    # "both" mode: sync calls for two providers (no streaming)
                    progress_label.set_text("Claude + Gemini 동시 호출 중...")
                    claude_p = ClaudeProvider()
                    gemini_p = GeminiProvider()
                    c_text, g_text = await asyncio.gather(
                        loop.run_in_executor(
                            None, lambda: claude_p.generate_text(prompt, system_prompt=guide)
                        ),
                        loop.run_in_executor(
                            None, lambda: gemini_p.generate_text(prompt, system_prompt=guide)
                        ),
                    )
                    content = (
                        f"## [Claude 결과]\n\n{c_text}\n\n"
                        f"---\n\n## [Gemini 결과]\n\n{g_text}"
                    )
                else:
                    # Single engine: streaming with queue.Queue + ui.timer bridge
                    progress_label.set_text(f"{engine.capitalize()} 스트리밍 중...")
                    provider = get_provider(engine)
                    chunk_queue: queue.Queue[str | None] = queue.Queue()
                    accumulated = ""
                    section_count = 0

                    # Show streaming preview
                    result_container.classes(remove="hidden")
                    stream_md = ui.markdown("").classes("w-full")

                    def _stream_worker():
                        try:
                            for chunk in provider.generate_text_stream(prompt, system_prompt=guide):
                                chunk_queue.put(chunk)
                        except Exception as exc:
                            chunk_queue.put(exc)
                        finally:
                            chunk_queue.put(None)  # sentinel

                    future = loop.run_in_executor(None, _stream_worker)

                    # Poll queue with ui.timer
                    stream_done = asyncio.Event()

                    def _poll_chunks():
                        nonlocal accumulated, section_count, content
                        try:
                            while not chunk_queue.empty():
                                item = chunk_queue.get_nowait()
                                if item is None:
                                    timer.deactivate()
                                    stream_done.set()
                                    return
                                if isinstance(item, Exception):
                                    timer.deactivate()
                                    stream_done.set()
                                    raise item
                                accumulated += item
                                new_count = accumulated.count("\n## ")
                                if new_count > section_count:
                                    section_count = new_count
                                    progress_label.set_text(f"섹션 {min(section_count, 7)}/7 생성 중...")
                                stream_md.set_content(accumulated)
                        except Exception as poll_exc:
                            _log.warning("스트리밍 폴링 오류: %s", poll_exc)

                    timer = ui.timer(0.2, _poll_chunks)
                    await stream_done.wait()
                    content = accumulated

                    # Remove streaming preview (will be replaced by section panels)
                    stream_md.delete()

                progress_label.set_text("섹션 파싱 중...")
                _state["raw_content"] = content
                _state["sections"] = parse_proposal_sections(content)

                # Save to DB
                pid = nicegui_app.storage.user.get("current_project_id")
                if pid:
                    save_generated_content(pid, engine, content, content_type="proposal")

                _render_sections_now()
                progress_label.set_text("생성 완료!")
                ui.notify("제안서가 생성되었습니다.", type="positive")

            except Exception as exc:
                _log.exception("제안서 생성 실패")
                ui.notify(f"생성 실패: {exc}", type="negative", timeout=8000)
                progress_label.set_text(f"오류: {exc}")
            finally:
                spinner.classes("hidden", remove=False)
                gen_btn.props(remove="disabled")
                _state["generating"] = False

        # ── Section re-generation handler ─────────────────────────────────

        async def _regen_section(section_key: str, feedback: str = "") -> None:
            engine = engine_radio.value
            if engine == "both":
                engine = "claude"  # default to claude for section regen

            shop_info = {
                "shop_name": shop_name_input.value or "",
                "industry": industry_input.value or "",
                "location": location_input.value or "",
            }

            progress_label.set_text(f"'{_PROPOSAL_SECTION_NAMES[section_key]}' 재생성 중...")
            spinner.classes(remove="hidden")

            try:
                guide, prompt = build_proposal_section_prompt(
                    section_key=section_key,
                    current_content=_state["raw_content"],
                    shop_info=shop_info,
                    feedback=feedback,
                )
                loop = asyncio.get_running_loop()
                provider = get_provider(engine)
                new_text = await loop.run_in_executor(
                    None, lambda: provider.generate_text(prompt, system_prompt=guide)
                )
                _state["sections"][section_key] = new_text.strip()

                # Rebuild raw content from sections
                parts = []
                for idx, key in enumerate(_PROPOSAL_SECTION_KEYS):
                    name = _PROPOSAL_SECTION_NAMES[key]
                    body = _state["sections"].get(key, "")
                    parts.append(f"## {idx + 1}. {name}\n{body}")
                _state["raw_content"] = "\n\n".join(parts)

                # Save updated content
                pid = nicegui_app.storage.user.get("current_project_id")
                if pid:
                    save_generated_content(pid, engine, _state["raw_content"], content_type="proposal")

                _render_sections_now()
                progress_label.set_text("재생성 완료!")
                ui.notify(f"'{_PROPOSAL_SECTION_NAMES[section_key]}' 섹션이 재생성되었습니다.", type="positive")

            except Exception as exc:
                _log.exception("섹션 재생성 실패")
                ui.notify(f"재생성 실패: {exc}", type="negative", timeout=8000)
                progress_label.set_text(f"오류: {exc}")
            finally:
                spinner.classes("hidden", remove=False)

        # ── Export handlers ───────────────────────────────────────────────

        async def _export_default() -> None:
            if not _state["raw_content"]:
                ui.notify("먼저 제안서를 생성해주세요.", type="warning")
                return
            try:
                shop_info = {
                    "shop_name": shop_name_input.value or "광고주",
                    "industry": industry_input.value or "",
                    "location": location_input.value or "",
                }
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"제안서_{shop_info['shop_name']}_{ts}.docx"

                import tempfile
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_path = Path(tmpdir) / filename
                    build_proposal_docx(
                        shop_info=shop_info,
                        sections=_state["sections"],
                        output_path=tmp_path,
                        kpi=_state["kpi"],
                    )
                    docx_bytes = tmp_path.read_bytes()

                ExportManager.save_default(docx_bytes, filename)
                ui.notify(f"'{filename}' 저장 완료", type="positive")
            except Exception as exc:
                ui.notify(f"저장 실패: {exc}", type="negative")

        async def _export_saveas() -> None:
            if not _state["raw_content"]:
                ui.notify("먼저 제안서를 생성해주세요.", type="warning")
                return
            try:
                shop_info = {
                    "shop_name": shop_name_input.value or "광고주",
                    "industry": industry_input.value or "",
                    "location": location_input.value or "",
                }
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"제안서_{shop_info['shop_name']}_{ts}.docx"

                import tempfile
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_path = Path(tmpdir) / filename
                    build_proposal_docx(
                        shop_info=shop_info,
                        sections=_state["sections"],
                        output_path=tmp_path,
                        kpi=_state["kpi"],
                    )
                    docx_bytes = tmp_path.read_bytes()

                await ExportManager.save_as(docx_bytes, filename)
            except Exception as exc:
                ui.notify(f"저장 실패: {exc}", type="negative")

        export_default_btn.on_click(_export_default)
        export_saveas_btn.on_click(_export_saveas)

        # ── Load saved content (after all handlers defined) ──────────────
        pid = nicegui_app.storage.user.get("current_project_id")
        if pid:
            saved = get_latest_content(pid, content_type="proposal")
            if saved:
                _state["raw_content"] = saved["content"]
                _state["sections"] = parse_proposal_sections(saved["content"])
                _render_sections_now()  # uses _regen_section via closure


def _render_sections(
    container: ui.column,
    state: dict,
    full_md: ui.markdown,
    gen_btn: ui.button,
    progress_label: ui.label,
    regen_fn=None,
) -> None:
    """Render parsed sections into expandable panels."""
    container.clear()
    full_md.set_content(state["raw_content"])

    with container:
        for idx, key in enumerate(_PROPOSAL_SECTION_KEYS):
            section_name = _PROPOSAL_SECTION_NAMES[key]
            section_num = idx + 1
            body = state["sections"].get(key, "(내용 없음)")

            with ui.expansion(
                f"{section_num}. {section_name}",
                icon="article",
                value=True,
            ).classes("w-full bg-gray-50"):
                md_widget = ui.markdown(body).classes("w-full")
                edit_area = ui.textarea(value=body).classes("w-full hidden").props("rows=10")

                with ui.row().classes("gap-2 mt-2"):
                    # Toggle edit
                    edit_btn = ui.button("편집", icon="edit", color="grey").props("flat size=sm")
                    save_btn = ui.button("편집 완료", icon="check", color="green").props("flat size=sm").classes("hidden")
                    regen_btn = ui.button("재생성", icon="refresh", color="orange").props("flat size=sm")

                    def _toggle_edit(
                        _e,
                        _md=md_widget,
                        _ea=edit_area,
                        _eb=edit_btn,
                        _sb=save_btn,
                        _key=key,
                    ) -> None:
                        _md.classes("hidden", remove=False)
                        _ea.classes(remove="hidden")
                        _eb.classes("hidden", remove=False)
                        _sb.classes(remove="hidden")

                    def _save_edit(
                        _e,
                        _md=md_widget,
                        _ea=edit_area,
                        _eb=edit_btn,
                        _sb=save_btn,
                        _key=key,
                        _full_md=full_md,
                    ) -> None:
                        new_text = _ea.value
                        state["sections"][_key] = new_text
                        _md.set_content(new_text)
                        _md.classes(remove="hidden")
                        _ea.classes("hidden", remove=False)
                        _sb.classes("hidden", remove=False)
                        _eb.classes(remove="hidden")
                        # Rebuild raw
                        parts = []
                        for i, k in enumerate(_PROPOSAL_SECTION_KEYS):
                            n = _PROPOSAL_SECTION_NAMES[k]
                            b = state["sections"].get(k, "")
                            parts.append(f"## {i + 1}. {n}\n{b}")
                        state["raw_content"] = "\n\n".join(parts)
                        _full_md.set_content(state["raw_content"])
                        # Save to DB
                        p_id = nicegui_app.storage.user.get("current_project_id")
                        if p_id:
                            save_generated_content(p_id, "edited", state["raw_content"], content_type="proposal")
                        ui.notify("편집 저장 완료", type="positive")

                    edit_btn.on_click(_toggle_edit)
                    save_btn.on_click(_save_edit)
                    if regen_fn is not None:
                        regen_btn.on_click(
                            lambda _e, _key=key: asyncio.ensure_future(regen_fn(_key))
                        )
