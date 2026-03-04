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

        # ── 썸네일 생성 패널 ──────────────────────────────────────────────
        _thumb_state: dict = {
            "ref_images": [],  # list of (bytes, mime_type)
            "result_bytes": None,
        }

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
                        value="1:1",
                        label="비율 선택",
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
            thumb_status.set_text("Gemini 이미지 생성 중...")

            try:
                from app.ai.image_provider import GeminiImageProvider
                from app.ai.nanobanana_prompt import compose_style_fusion_prompt, compose_image_mapping_prompt

                ratio = thumb_ratio_sel.value or "1:1"
                mode = thumb_mode_sel.value or "style_fusion"
                w, h = _calc_canvas(ratio)
                sub_copy = thumb_sub_input.value.strip() or ""
                cta_copy = thumb_cta_input.value.strip() or "자세히 보기"
                visual = thumb_visual_input.value.strip() or "clean, modern, bright"

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

                provider = GeminiImageProvider()
                images = _thumb_state["ref_images"] if _thumb_state["ref_images"] else None
                loop = asyncio.get_event_loop()
                pil_img = await loop.run_in_executor(
                    None,
                    lambda: provider.generate_image(prompt, images, aspect_ratio=ratio),
                )

                # PIL → bytes for preview and save
                import io
                import base64
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                img_bytes = buf.getvalue()
                _thumb_state["result_bytes"] = img_bytes

                b64 = base64.b64encode(img_bytes).decode()
                thumb_result_container.clear()
                with thumb_result_container:
                    ui.image(f"data:image/png;base64,{b64}").classes(
                        "max-w-lg rounded shadow"
                    )
                    ui.label(f"{len(img_bytes):,} bytes | {w}x{h}").classes(
                        "text-xs text-gray-400"
                    )

                thumb_save_btn.classes(remove="hidden")
                thumb_status.set_text("생성 완료!")
                ui.notify("썸네일 생성 완료!", type="positive", timeout=5000)

            except Exception as exc:
                thumb_status.set_text("생성 실패")
                ui.notify(f"썸네일 생성 오류: {exc}", type="negative", timeout=8000)
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

        # ── Diagnostic panels ─────────────────────────────────────────────
        create_log_panel()
        create_path_info_panel()
