"""Screen 4 – 썸네일 이미지 생성 (Gemini Image Generation)."""
import asyncio
import base64
from datetime import datetime

from nicegui import ui

from app.common import create_nav, create_log_panel, create_path_info_panel
from app.export_manager import ExportManager
from app.paths import THUMBNAILS_DIR, sanitize_filename
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
    }

    with ui.column().classes("w-full p-6 gap-4"):

        # ── 안내 카드 ────────────────────────────────────────────
        with ui.card().classes("w-full bg-orange-50"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("image", size="28px").classes("text-orange-500")
                with ui.column().classes("gap-0"):
                    ui.label("썸네일 이미지 생성").classes("font-bold text-gray-700")
                    ui.label(
                        "Gemini AI로 당근 광고용 썸네일 이미지를 생성합니다. "
                        "참고 이미지(선택)와 프롬프트를 입력하세요."
                    ).classes("text-sm text-gray-500")

        # ── 참고 이미지 (선택) ────────────────────────────────────
        with ui.card().classes("w-full"):
            ui.label("참고 이미지 (선택)").classes("font-bold text-gray-700 mb-2")
            ui.label(
                "스타일 참고용 이미지를 업로드하면 비슷한 분위기로 생성합니다."
            ).classes("text-xs text-gray-400 mb-2")

            ref_preview = ui.column().classes("w-full hidden")

            with ui.row().classes("gap-3 items-center"):
                ref_upload = ui.upload(
                    label="이미지 선택",
                    auto_upload=True,
                    on_upload=lambda e: asyncio.ensure_future(_handle_ref_upload(e)),
                ).classes("max-w-xs").props('accept="image/*"')

                ref_clear_btn = ui.button(
                    "제거",
                    on_click=lambda: _clear_ref(),
                ).classes("bg-gray-200 text-gray-700 text-sm hidden")

        # ── 프롬프트 입력 ────────────────────────────────────────
        with ui.card().classes("w-full"):
            ui.label("프롬프트 입력").classes("font-bold text-gray-700 mb-2")
            prompt_input = ui.textarea(
                placeholder=(
                    "예: 당근마켓 스타일의 따뜻한 오렌지톤 썸네일, "
                    "\"신선한 제철 과일 50% 할인\" 문구 포함, "
                    "밝고 친근한 분위기\n\n"
                    "팁: 원하는 분위기(밝은/따뜻한/깔끔한), 색상(오렌지/초록/파랑), "
                    "문구, 이미지 요소(음식/사람/아이콘)를 구체적으로 적을수록 좋습니다."
                ),
            ).classes("w-full").props("rows=5 outlined")

            name_input = ui.input(
                label="파일명 (선택)",
                placeholder="예: 과일할인_썸네일",
            ).classes("w-72 mt-2").props("dense outlined")

        # ── 액션 버튼 ────────────────────────────────────────────
        with ui.row().classes("gap-3 items-center"):
            gen_btn = ui.button(
                "썸네일 생성",
                on_click=lambda: asyncio.ensure_future(_generate()),
                icon="palette",
            ).classes("bg-orange-500 text-white text-base px-6")

            save_btn = ui.button(
                "기본 폴더에 저장",
                on_click=lambda: _save_result(),
                icon="save",
            ).classes("bg-green-600 text-white text-base px-6 hidden")

            spinner = ui.spinner(size="32px").classes("hidden")
            status_label = ui.label("").classes("text-sm text-gray-500 hidden")

        # ── 생성 결과 미리보기 ────────────────────────────────────
        result_card = ui.card().classes("w-full hidden")
        result_container = ui.column().classes("w-full items-center gap-2")

        with result_card:
            ui.label("생성 결과").classes("font-bold text-gray-700 mb-2")
            result_container

        # ── 진단 패널 ────────────────────────────────────────────
        create_log_panel()
        create_path_info_panel()

    # ── 핸들러 ────────────────────────────────────────────────────

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
                ui.image(f"data:{mime};base64,{b64}").classes(
                    "max-w-sm rounded shadow"
                )
                ui.label(f"{len(data):,} bytes").classes("text-xs text-gray-400")

            ref_clear_btn.classes(remove="hidden")
            _log.info("참고 이미지 업로드: %s (%d bytes)", mime, len(data))
        except Exception as exc:
            ui.notify(f"이미지 읽기 오류: {exc}", type="negative")

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
            ui.notify("프롬프트를 입력해주세요.", type="warning")
            return

        gen_btn.props("disabled loading")
        spinner.classes(remove="hidden")
        status_label.classes(remove="hidden")
        status_label.set_text("Gemini 이미지 생성 중...")

        try:
            from app.ai.providers import GeminiProvider

            provider = GeminiProvider()
            loop = asyncio.get_event_loop()
            ref = page_state["ref_bytes"]
            ref_mime = page_state["ref_mime"]

            if ref is not None:
                img_bytes, mime = await loop.run_in_executor(
                    None,
                    lambda: provider.generate_image(
                        prompt_text,
                        reference_image=ref,
                        reference_mime=ref_mime,
                    ),
                )
            else:
                img_bytes, mime = await loop.run_in_executor(
                    None,
                    lambda: provider.generate_image(prompt_text),
                )

            page_state["result_bytes"] = img_bytes
            page_state["result_mime"] = mime

            # 결과 미리보기
            b64 = base64.b64encode(img_bytes).decode()
            result_container.clear()
            with result_container:
                ui.image(f"data:{mime};base64,{b64}").classes(
                    "max-w-lg rounded shadow"
                )
                ui.label(f"{len(img_bytes):,} bytes | {mime}").classes(
                    "text-xs text-gray-400"
                )
            result_card.classes(remove="hidden")
            save_btn.classes(remove="hidden")

            status_label.set_text("생성 완료!")
            ui.notify("썸네일 생성 완료!", type="positive", timeout=5000)

        except ValueError as ve:
            status_label.set_text("생성 실패")
            ui.notify(str(ve), type="negative", timeout=8000)
        except Exception as exc:
            status_label.set_text("오류 발생")
            ui.notify(f"오류: {exc}", type="negative", timeout=8000)
        finally:
            gen_btn.props(remove="disabled loading")
            spinner.classes("hidden")

    def _save_result() -> None:
        img_bytes = page_state.get("result_bytes")
        if not img_bytes:
            ui.notify("먼저 썸네일을 생성해주세요.", type="warning")
            return

        mime = page_state.get("result_mime", "image/png")
        ext = ".png" if "png" in mime else ".jpeg" if "jpeg" in mime else ".png"

        raw_name = name_input.value.strip()
        base_name = sanitize_filename(raw_name) if raw_name else "thumbnail"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{base_name}_{timestamp}{ext}"

        ExportManager.save_default(img_bytes, filename, dest_dir=THUMBNAILS_DIR)
