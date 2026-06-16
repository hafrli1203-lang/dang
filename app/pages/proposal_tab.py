"""제안서 탭 UI -- /planning 페이지의 '운영 제안서' 탭 내용.

스트리밍 지원: queue.Queue + ui.timer(0.2) 브릿지 패턴.
"""
import asyncio
import logging
import queue
from datetime import datetime
from pathlib import Path

from nicegui import ui, app as nicegui_app

from app.theme import section_header
from app.ai_engine import (
    build_proposal_prompt,
    build_proposal_section_prompt,
    parse_proposal_sections,
    calc_kpi,
    SYSTEM_GUIDE_PROPOSAL,
    _PROPOSAL_SECTION_NAMES,
    _PROPOSAL_SECTION_KEYS,
)
from app.ai.providers import get_provider, ClaudeProvider, OpenAIProvider
from app.ai.news_post_guard import _split_blocks
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

    # -- State --
    _state: dict = {
        "csv_rows": None,
        "csv_warnings": [],
        "sections": {},
        "raw_content": "",
        "kpi": None,
        "generating": False,
    }

    with ui.column().classes("w-full gap-4"):
        # Wizard Step 4 notice
        with ui.card().classes("dg-card w-full").style(
            "background: var(--dg-primary-light); border: 1px solid var(--dg-primary)"
        ):
            with ui.row().classes("items-center gap-3"):
                ui.icon("info", size="24px").style("color: var(--dg-primary)")
                with ui.column().classes("gap-1"):
                    ui.label("소식글 기획 탭의 Step 4에서 통합 운영 제안서를 만들 수 있어요.").style(
                        "font-weight: 600; font-size: 14px; color: var(--dg-text-primary)"
                    )
                    ui.label(
                        "4단계 위자드(전략 분석 > 콘텐츠 생성 > 광고 세팅 > 운영 제안서)를 거치면 "
                        "더 종합적인 제안서를 받아볼 수 있어요."
                    ).classes("dg-label-sm")

        section_header("description", "광고 운영 제안서 생성기 (독립 모드)",
                       "AI가 7개 섹션으로 구성된 광고 운영 제안서를 만들어 드려요.")

        # -- Input form --
        with ui.card().classes("dg-card w-full"):
            section_header("store", "점포 정보")
            with ui.row().classes("w-full gap-4 flex-wrap"):
                shop_name_input = ui.input("점포명", placeholder="예: 행복안경").classes("flex-1 min-w-48 dg-input").props("outlined dense")
                industry_input = ui.input("업종", placeholder="예: 안경점").classes("flex-1 min-w-48 dg-input").props("outlined dense")
                location_input = ui.input("위치", placeholder="예: 부천시 심곡동").classes("flex-1 min-w-48 dg-input").props("outlined dense")

            pid = nicegui_app.storage.user.get("current_project_id")
            if pid:
                proj = get_project(pid)
                if proj:
                    shop_name_input.set_value(proj.get("name", ""))
                    industry_input.set_value(proj.get("industry", ""))
                    location_input.set_value(proj.get("region", ""))

        with ui.card().classes("dg-card w-full"):
            section_header("campaign", "프로모션 & 타겟")
            promo_input = ui.textarea(
                "프로모션/상품 정보",
                placeholder="예: 누진렌즈 0원 프로모션, 45-65세 타겟, 3월 한정",
            ).classes("w-full dg-input").props("rows=3 outlined")
            age_select = ui.select(
                {
                    "전연령": "전연령", "10대-20대": "10대-20대",
                    "20대-30대": "20대-30대", "30대-40대": "30대-40대",
                    "40대-50대": "40대-50대", "50대-60대": "50대-60대",
                    "60대 이상": "60대 이상",
                },
                label="타겟 연령대", value="전연령",
            ).classes("w-48 dg-select")

        with ui.card().classes("dg-card w-full"):
            section_header("analytics", "이전 캠페인 성과", "CSV 파일을 올리면 KPI를 자동으로 계산해 드려요.")

            csv_status = ui.label("").classes("dg-text-sm")

            async def _on_csv_upload(e) -> None:
                if not e.content:
                    return
                data = e.content.read()
                rows, warnings = parse_daangn_csv(data)
                _state["csv_rows"] = rows
                _state["csv_warnings"] = warnings
                if rows:
                    _state["kpi"] = calc_kpi(rows)
                    csv_status.set_text(f"CSV를 읽었어요: {len(rows)}행 (경고 {len(warnings)}건)")
                    csv_status.style("color: var(--dg-success)")
                    manual_summary.set_visibility(False)
                else:
                    csv_status.set_text(f"CSV를 읽지 못했어요. 파일 양식을 확인해 주세요. ({'; '.join(warnings)})")
                    csv_status.style("color: var(--dg-error)")

            ui.upload(
                label="CSV 파일 업로드",
                on_upload=_on_csv_upload,
                auto_upload=True,
            ).props('accept=".csv" flat bordered').classes("w-full max-w-md dg-upload")

            manual_summary = ui.textarea(
                "이전 캠페인 요약 (CSV 없을 때)",
                placeholder="예: CTR 1.5%, CPC 300원, 월 문의 15건, 총 비용 30만원",
            ).classes("w-full dg-input").props("rows=2 outlined")

        # -- AI engine selector --
        with ui.card().classes("dg-card w-full"):
            with ui.row().classes("items-center gap-4"):
                ui.icon("smart_toy", size="20px").style("color: var(--dg-primary)")
                ui.label("AI 엔진").style("font-weight: 600; color: var(--dg-text-primary)")
                engine_radio = ui.radio(
                    {"claude": "Claude", "gpt": "GPT", "coordinate": "Claude+GPT 조율"},
                    value="claude",
                ).props("inline").classes("dg-radio")

        # -- Generate button --
        with ui.row().classes("gap-4 items-center"):
            gen_btn = ui.button(
                "제안서 생성", icon="auto_awesome",
                on_click=lambda: _generate(),
            ).classes("dg-btn-primary")
            spinner = ui.spinner("dots", size="lg").classes("hidden")
            progress_label = ui.label("").classes("dg-progress-text")

        # -- Result area --
        result_container = ui.column().classes("w-full gap-2 hidden")

        with result_container:
            with ui.tabs().classes("w-full dg-tabs") as result_tabs:
                tab_full = ui.tab("전체 보기")
                tab_sections = ui.tab("섹션별 보기")

            with ui.tab_panels(result_tabs, value=tab_sections).classes("w-full"):
                with ui.tab_panel(tab_full):
                    result_md_full = ui.markdown("").classes("w-full dg-prose")

                with ui.tab_panel(tab_sections):
                    sections_container = ui.column().classes("w-full gap-2")

        # -- Export buttons --
        export_row = ui.row().classes("gap-4 hidden")
        with export_row:
            export_default_btn = ui.button(
                "기본 폴더에 저장", icon="save",
            ).classes("dg-btn-success")
            export_saveas_btn = ui.button(
                "다른 위치로 저장", icon="save_as",
            ).classes("dg-btn-secondary")

        # -- Section rendering --

        def _render_sections_now() -> None:
            _render_sections(sections_container, _state, result_md_full, gen_btn, progress_label, regen_fn=_regen_section)
            result_container.classes(remove="hidden")
            export_row.classes(remove="hidden")

        # -- Generate handler --

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
                ui.notify("점포명을 입력해 주세요.", type="warning")
                _state["generating"] = False
                return

            engine = engine_radio.value
            spinner.classes(remove="hidden")
            gen_btn.props("disabled")
            progress_label.set_text("제안서 작성을 준비하고 있어요...")

            try:
                news_post = ""
                pid = nicegui_app.storage.user.get("current_project_id")
                if pid:
                    planning_content = get_latest_content(pid, content_type="content") or get_latest_content(pid, content_type="planning")
                    if planning_content:
                        blocks = _split_blocks(planning_content["content"])
                        parts = []
                        if "의심해소" in blocks:
                            parts.append("【소식글 1 | 의심해소형】\n" + blocks["의심해소"])
                        if "가성비" in blocks:
                            parts.append("【소식글 2 | 가성비형】\n" + blocks["가성비"])
                        news_post = "\n\n".join(parts)

                guide, prompt = build_proposal_prompt(
                    shop_info=shop_info,
                    promo_text=promo_input.value or "",
                    target_age=age_select.value or "전연령",
                    prev_csv_rows=_state["csv_rows"],
                    prev_summary=manual_summary.value or "",
                    news_post_content=news_post,
                )
                loop = asyncio.get_running_loop()
                content = ""

                if engine == "coordinate":
                    from app.ai.coordination import synthesize
                    progress_label.set_text("Claude와 GPT가 각자 초안을 쓰고 있어요...")
                    claude_p = get_provider("claude")
                    gpt_p = get_provider("gpt")
                    c_text, g_text = await asyncio.gather(
                        loop.run_in_executor(
                            None, lambda: claude_p.generate_text(prompt, system_prompt=guide)
                        ),
                        loop.run_in_executor(
                            None, lambda: gpt_p.generate_text(prompt, system_prompt=guide)
                        ),
                    )
                    progress_label.set_text("Claude가 두 초안을 종합하고 있어요...")
                    content = await loop.run_in_executor(
                        None, lambda: synthesize(c_text, g_text, "운영 제안서")
                    )
                else:
                    engine_name = "GPT" if engine == "gpt" else "Claude"
                    progress_label.set_text(f"{engine_name}가 제안서를 작성하고 있어요...")
                    provider = get_provider(engine)
                    chunk_queue: queue.Queue[str | None] = queue.Queue()
                    accumulated = ""
                    section_count = 0

                    result_container.classes(remove="hidden")
                    stream_md = ui.markdown("").classes("w-full dg-prose")

                    def _stream_worker():
                        try:
                            for chunk in provider.generate_text_stream(prompt, system_prompt=guide):
                                chunk_queue.put(chunk)
                        except Exception as exc:
                            chunk_queue.put(exc)
                        finally:
                            chunk_queue.put(None)

                    future = loop.run_in_executor(None, _stream_worker)

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
                                    progress_label.set_text(f"섹션 {min(section_count, 7)}/7을 작성하고 있어요...")
                                stream_md.set_content(accumulated)
                        except Exception as poll_exc:
                            _log.warning("스트리밍 폴링 오류: %s", poll_exc)

                    timer = ui.timer(0.2, _poll_chunks)
                    await stream_done.wait()
                    content = accumulated

                    stream_md.delete()

                progress_label.set_text("섹션을 정리하고 있어요...")
                _state["raw_content"] = content
                _state["sections"] = parse_proposal_sections(content)

                pid = nicegui_app.storage.user.get("current_project_id")
                if pid:
                    save_generated_content(pid, engine, content, content_type="proposal")

                _render_sections_now()
                progress_label.set_text("제안서가 완성됐어요!")
                ui.notify("제안서를 만들었어요. 아래에서 내용을 확인해 보세요.", type="positive")

            except Exception as exc:
                _log.exception("제안서 생성 실패")
                ui.notify(f"제안서를 만들지 못했어요. 잠시 후 다시 시도해 주세요. ({exc})", type="negative", timeout=8000)
                progress_label.set_text("제안서를 만들지 못했어요. 다시 시도해 주세요.")
            finally:
                spinner.classes("hidden", remove=False)
                gen_btn.props(remove="disabled")
                _state["generating"] = False

        # -- Section re-generation handler --

        async def _regen_section(section_key: str, feedback: str = "") -> None:
            engine = engine_radio.value
            if engine == "coordinate":
                engine = "claude"

            shop_info = {
                "shop_name": shop_name_input.value or "",
                "industry": industry_input.value or "",
                "location": location_input.value or "",
            }

            progress_label.set_text(f"'{_PROPOSAL_SECTION_NAMES[section_key]}' 섹션을 다시 쓰고 있어요...")
            spinner.classes(remove="hidden")

            try:
                news_post = ""
                if section_key == "creative":
                    pid = nicegui_app.storage.user.get("current_project_id")
                    cur_engine = engine
                    if pid:
                        planning_content = get_latest_content(pid, content_type="content") or get_latest_content(pid, content_type="planning")
                        if planning_content:
                            blocks = _split_blocks(planning_content["content"])
                            parts = []
                            if "의심해소" in blocks:
                                parts.append("【소식글 1 | 의심해소형】\n" + blocks["의심해소"])
                            if "가성비" in blocks:
                                parts.append("【소식글 2 | 가성비형】\n" + blocks["가성비"])
                            news_post = "\n\n".join(parts)

                guide, prompt = build_proposal_section_prompt(
                    section_key=section_key,
                    current_content=_state["raw_content"],
                    shop_info=shop_info,
                    feedback=feedback,
                    news_post_content=news_post,
                )
                loop = asyncio.get_running_loop()
                provider = get_provider(engine)
                new_text = await loop.run_in_executor(
                    None, lambda: provider.generate_text(prompt, system_prompt=guide)
                )
                _state["sections"][section_key] = new_text.strip()

                parts = []
                for idx, key in enumerate(_PROPOSAL_SECTION_KEYS):
                    name = _PROPOSAL_SECTION_NAMES[key]
                    body = _state["sections"].get(key, "")
                    parts.append(f"## {idx + 1}. {name}\n{body}")
                _state["raw_content"] = "\n\n".join(parts)

                pid = nicegui_app.storage.user.get("current_project_id")
                if pid:
                    save_generated_content(pid, engine, _state["raw_content"], content_type="proposal")

                _render_sections_now()
                progress_label.set_text("다시 만들었어요!")
                ui.notify(f"'{_PROPOSAL_SECTION_NAMES[section_key]}' 섹션을 다시 만들었어요.", type="positive")

            except Exception as exc:
                _log.exception("섹션 재생성 실패")
                ui.notify(f"섹션을 다시 만들지 못했어요. 잠시 후 다시 시도해 주세요. ({exc})", type="negative", timeout=8000)
                progress_label.set_text("섹션을 다시 만들지 못했어요. 다시 시도해 주세요.")
            finally:
                spinner.classes("hidden", remove=False)

        # -- Export handlers --

        async def _export_default() -> None:
            if not _state["raw_content"]:
                ui.notify("저장할 제안서가 아직 없어요. 먼저 제안서를 만들어 주세요.", type="warning")
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
                ui.notify(f"저장했어요: {filename}", type="positive")
            except Exception as exc:
                ui.notify(f"저장하지 못했어요. 잠시 후 다시 시도해 주세요. ({exc})", type="negative")

        async def _export_saveas() -> None:
            if not _state["raw_content"]:
                ui.notify("저장할 제안서가 아직 없어요. 먼저 제안서를 만들어 주세요.", type="warning")
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
                ui.notify(f"저장하지 못했어요. 잠시 후 다시 시도해 주세요. ({exc})", type="negative")

        export_default_btn.on_click(_export_default)
        export_saveas_btn.on_click(_export_saveas)

        # -- Load saved content --
        pid = nicegui_app.storage.user.get("current_project_id")
        if pid:
            saved = get_latest_content(pid, content_type="proposal")
            if saved:
                _state["raw_content"] = saved["content"]
                _state["sections"] = parse_proposal_sections(saved["content"])
                _render_sections_now()


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
            body = state["sections"].get(key, "(아직 내용이 없어요)")

            with ui.expansion(
                f"{section_num}. {section_name}",
                icon="article",
                value=True,
            ).classes("w-full dg-expansion"):
                md_widget = ui.markdown(body).classes("w-full dg-prose")
                edit_area = ui.textarea(value=body).classes("w-full hidden dg-input").props("rows=10 outlined")

                with ui.row().classes("gap-2 mt-2"):
                    edit_btn = ui.button("편집", icon="edit").classes("dg-btn-ghost dg-btn-sm")
                    save_btn = ui.button("편집 완료", icon="check").classes("dg-btn-success dg-btn-sm hidden")
                    regen_btn = ui.button("재생성", icon="refresh").classes("dg-btn-ghost dg-btn-sm")

                    def _toggle_edit(
                        _e, _md=md_widget, _ea=edit_area, _eb=edit_btn, _sb=save_btn, _key=key,
                    ) -> None:
                        _md.classes("hidden", remove=False)
                        _ea.classes(remove="hidden")
                        _eb.classes("hidden", remove=False)
                        _sb.classes(remove="hidden")

                    def _save_edit(
                        _e, _md=md_widget, _ea=edit_area, _eb=edit_btn, _sb=save_btn,
                        _key=key, _full_md=full_md,
                    ) -> None:
                        new_text = _ea.value
                        state["sections"][_key] = new_text
                        _md.set_content(new_text)
                        _md.classes(remove="hidden")
                        _ea.classes("hidden", remove=False)
                        _sb.classes("hidden", remove=False)
                        _eb.classes(remove="hidden")
                        parts = []
                        for i, k in enumerate(_PROPOSAL_SECTION_KEYS):
                            n = _PROPOSAL_SECTION_NAMES[k]
                            b = state["sections"].get(k, "")
                            parts.append(f"## {i + 1}. {n}\n{b}")
                        state["raw_content"] = "\n\n".join(parts)
                        _full_md.set_content(state["raw_content"])
                        p_id = nicegui_app.storage.user.get("current_project_id")
                        if p_id:
                            save_generated_content(p_id, "edited", state["raw_content"], content_type="proposal")
                        ui.notify("수정한 내용을 저장했어요.", type="positive")

                    edit_btn.on_click(_toggle_edit)
                    save_btn.on_click(_save_edit)
                    if regen_fn is not None:
                        regen_btn.on_click(
                            lambda _e, _key=key: regen_fn(_key)
                        )
