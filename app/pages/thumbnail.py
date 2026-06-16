"""Screen 4 -- 썸네일 이미지 생성 (Gemini Image Generation)."""
import asyncio
import base64
from datetime import datetime

from nicegui import ui, app as nicegui_app

from app.common import create_nav, next_step_bar
from app.theme import section_header
from app.export_manager import ExportManager
from app.paths import THUMBNAILS_DIR, sanitize_filename
from app.database import save_thumbnail
from app.logger import get_logger

_log = get_logger("thumbnail")


@ui.page("/thumbnail")
def thumbnail_page() -> None:
    create_nav("/thumbnail")

    page_state: dict = {
        "ref_bytes": None,
        "ref_mime": "image/png",
        "result_bytes": None,
        "result_mime": "image/png",
        "history": [],
    }
    _MAX_HISTORY = 10

    with ui.column().classes("dg-page-content w-full gap-5"):
        next_step_bar("/thumbnail")  # CSS order로 본문 맨 아래에 '다음 단계' 흐름 버튼

        # Page header
        ui.label("썸네일 제작").classes("dg-page-title")
        ui.label("AI로 당근 광고용 썸네일 이미지를 만들어요.").classes("dg-page-subtitle")

        # -- Guide banner --
        with ui.element("div").classes("dg-banner dg-banner-info w-full"):
            ui.icon("lightbulb", size="20px")
            ui.label(
                "당근 피드에선 '광고 같은' 이미지보다 동네 사장님이 직접 찍은 듯한 "
                "자연스러운 실사 사진이 더 잘 눌려요. 그래서 만들어지는 이미지는 "
                "디자인·문구 없는 깨끗한 실사로 나와요. 상품·장면·분위기를 구체적으로 "
                "적어 주세요. (가격/문구는 생성 후 따로 얹는 걸 권장해요.)"
            )

        # -- Reference image --
        with ui.card().classes("dg-card w-full"):
            section_header("add_photo_alternate", "참고 이미지", "스타일 참고용 이미지를 올리면 비슷한 분위기로 만들어 드려요.")

            ref_preview = ui.column().classes("w-full hidden")

            with ui.row().classes("gap-3 items-center"):
                ref_upload = ui.upload(
                    label="이미지 선택",
                    auto_upload=True,
                    on_upload=lambda e: _handle_ref_upload(e),
                ).classes("max-w-xs dg-upload").props('accept="image/*"')

                ref_clear_btn = ui.button(
                    "제거", icon="close",
                    on_click=lambda: _clear_ref(),
                ).classes("dg-btn-secondary dg-btn-sm hidden")

        # -- Prompt input --
        with ui.card().classes("dg-card w-full"):
            section_header("text_fields", "프롬프트 입력")
            prompt_input = ui.textarea(
                placeholder=(
                    "예: 동네 과일가게 진열대에 제철 딸기를 담은 바구니를 가까이서 찍은 사진, "
                    "자연광, 사장님이 직접 폰으로 찍은 듯 투박하고 따뜻한 느낌"
                ),
            ).classes("w-full dg-input").props("rows=4 outlined")

            name_input = ui.input(
                label="파일명 (선택)",
                placeholder="예: 과일할인_썸네일",
            ).classes("w-72 mt-3 dg-input").props("dense outlined")

        # -- Action buttons --
        with ui.row().classes("gap-3 items-center"):
            gen_btn = ui.button(
                "썸네일 생성",
                on_click=lambda: _generate(),
                icon="auto_awesome",
            ).classes("dg-btn-primary")

            save_btn = ui.button(
                "기본 폴더에 저장",
                on_click=lambda: _save_result(),
                icon="save",
            ).classes("dg-btn-success hidden")

            spinner = ui.spinner(size="32px").classes("hidden")
            status_label = ui.label("").classes("dg-progress-text hidden")

        # -- Result preview --
        result_card = ui.card().classes("dg-card w-full hidden")
        result_container = ui.column().classes("w-full items-center gap-3")

        with result_card:
            section_header("image", "생성 결과")
            result_container

        # -- History strip --
        thumb_history_label = ui.label("").classes("dg-label-sm mt-3 hidden")
        thumb_history_strip = ui.row().classes(
            "w-full overflow-x-auto gap-2 mt-1 hidden"
        ).style("max-height: 120px")

    # -- History helpers --

    def _refresh_history() -> None:
        history = page_state["history"]
        if not history:
            thumb_history_strip.classes("hidden")
            thumb_history_label.classes("hidden")
            return
        thumb_history_label.set_text(f"이전에 만든 썸네일 ({len(history)}장)")
        thumb_history_label.classes(remove="hidden")
        thumb_history_strip.clear()
        thumb_history_strip.classes(remove="hidden")
        with thumb_history_strip:
            for idx, (img_bytes, mime, snippet) in enumerate(history):
                b64 = base64.b64encode(img_bytes).decode()
                with ui.column().classes("items-center cursor-pointer shrink-0"):
                    ui.image(f"data:{mime};base64,{b64}").classes(
                        "w-20 h-20 object-cover rounded-lg dg-history-item"
                    ).on("click", lambda _, i=idx: _restore_history(i))
                    ui.label(snippet[:12]).classes("dg-label-sm truncate max-w-20")

    def _restore_history(idx: int) -> None:
        history = page_state["history"]
        if idx < 0 or idx >= len(history):
            return
        img_bytes, mime, snippet = history[idx]
        page_state["result_bytes"] = img_bytes
        page_state["result_mime"] = mime
        b64 = base64.b64encode(img_bytes).decode()
        result_container.clear()
        with result_container:
            ui.image(f"data:{mime};base64,{b64}").classes("max-w-lg dg-image-preview")
            ui.label(f"{len(img_bytes):,} bytes | 복원: {snippet[:20]}").classes("dg-label-sm")
        result_card.classes(remove="hidden")
        save_btn.classes(remove="hidden")
        ui.notify(f"이전 썸네일을 다시 불러왔어요: {snippet[:20]}", type="info", timeout=2000)

    # -- Handlers --

    async def _handle_ref_upload(e) -> None:
        try:
            data = await e.file.read()
            mime = e.file.content_type or "image/png"
            page_state["ref_bytes"] = data
            page_state["ref_mime"] = mime

            b64 = base64.b64encode(data).decode()
            ref_preview.clear()
            ref_preview.classes(remove="hidden")
            with ref_preview:
                ui.image(f"data:{mime};base64,{b64}").classes("max-w-sm dg-image-preview")
                ui.label(f"{len(data):,} bytes").classes("dg-label-sm")

            ref_clear_btn.classes(remove="hidden")
            _log.info("참고 이미지 업로드: %s (%d bytes)", mime, len(data))
        except Exception as exc:
            ui.notify(f"이미지를 읽지 못했어요. 파일을 확인하고 다시 올려 주세요. ({exc})", type="negative")

    def _clear_ref() -> None:
        page_state["ref_bytes"] = None
        page_state["ref_mime"] = "image/png"
        ref_preview.clear()
        ref_preview.classes("hidden")
        ref_clear_btn.classes("hidden")
        ref_upload.reset()
        _log.info("참고 이미지 제거됨")

    async def _generate() -> None:
        prompt_text = prompt_input.value.strip()
        if not prompt_text:
            ui.notify("만들고 싶은 썸네일을 먼저 적어 주세요.", type="warning")
            return

        gen_btn.props("disabled loading")
        spinner.classes(remove="hidden")
        status_label.classes(remove="hidden")
        status_label.set_text("썸네일을 만들고 있어요...")

        try:
            from app.ai.image_provider import get_image_provider
            from app.ai.thumbnail_style import build_natural_thumbnail_prompt

            provider = get_image_provider()
            loop = asyncio.get_running_loop()
            ref = page_state["ref_bytes"]
            ref_mime = page_state["ref_mime"]

            # 당근 피드용 자연 실사로 강제 — 광고 티가 나면 스크롤로 넘어간다.
            final_prompt = build_natural_thumbnail_prompt(
                prompt_text, has_reference=ref is not None
            )

            if ref is not None:
                img_bytes, mime = await loop.run_in_executor(
                    None,
                    lambda: provider.generate_image(
                        final_prompt,
                        reference_image=ref,
                        reference_mime=ref_mime,
                    ),
                )
            else:
                img_bytes, mime = await loop.run_in_executor(
                    None,
                    lambda: provider.generate_image(final_prompt),
                )

            page_state["result_bytes"] = img_bytes
            page_state["result_mime"] = mime

            snippet = prompt_text[:20]
            page_state["history"].append((img_bytes, mime, snippet))
            if len(page_state["history"]) > _MAX_HISTORY:
                page_state["history"] = page_state["history"][-_MAX_HISTORY:]

            b64 = base64.b64encode(img_bytes).decode()
            result_container.clear()
            with result_container:
                ui.image(f"data:{mime};base64,{b64}").classes("max-w-lg dg-image-preview")
                ui.label(f"{len(img_bytes):,} bytes | {mime}").classes("dg-label-sm")
            result_card.classes(remove="hidden")
            save_btn.classes(remove="hidden")

            status_label.set_text("썸네일이 완성됐어요!")
            _refresh_history()
            ui.notify("썸네일이 완성됐어요!", type="positive", timeout=5000)

        except ValueError as ve:
            status_label.set_text("썸네일을 만들지 못했어요")
            ui.notify(str(ve), type="negative", timeout=8000)
            from app.ai.image_provider import get_image_failure_guide
            ui.notify(get_image_failure_guide(str(ve)), type="info", timeout=15000, close_button="확인")
        except Exception as exc:
            status_label.set_text("썸네일을 만들지 못했어요")
            ui.notify(f"썸네일을 만들지 못했어요. 잠시 후 다시 시도해 주세요. ({exc})", type="negative", timeout=8000)
            from app.ai.image_provider import get_image_failure_guide
            ui.notify(get_image_failure_guide(str(exc)), type="info", timeout=15000, close_button="확인")
        finally:
            gen_btn.props(remove="disabled loading")
            spinner.classes("hidden")

    def _save_result() -> None:
        img_bytes = page_state.get("result_bytes")
        if not img_bytes:
            ui.notify("저장할 썸네일이 아직 없어요. 먼저 썸네일을 만들어 주세요.", type="warning")
            return

        mime = page_state.get("result_mime", "image/png")
        ext = ".png" if "png" in mime else ".jpeg" if "jpeg" in mime else ".png"

        raw_name = name_input.value.strip()
        base_name = sanitize_filename(raw_name) if raw_name else "thumbnail"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{base_name}_{timestamp}{ext}"

        ExportManager.save_default(img_bytes, filename, dest_dir=THUMBNAILS_DIR)

        # 현재 프로젝트가 선택돼 있으면 그 캠페인 기록에 썸네일을 묶어 저장
        pid = nicegui_app.storage.user.get("current_project_id")
        if pid:
            try:
                link_path = THUMBNAILS_DIR / f"proj{pid}_{timestamp}{ext}"
                link_path.write_bytes(img_bytes)
                save_thumbnail(
                    int(pid), str(link_path),
                    title=raw_name, prompt=(prompt_input.value or "").strip(),
                )
                ui.notify("선택한 프로젝트 기록에 썸네일을 저장했어요.", type="positive")
            except Exception as exc:
                _log.warning("썸네일 DB 기록 실패(파일은 저장됨): %s", exc)
