"""DOCX/이미지 내보내기 통합 관리자.

모든 저장 로직을 한 곳에서 관리한다.
- native 모드: 파일 저장 + 다이얼로그
- browser 모드: 파일 저장 + ui.download()
"""
from pathlib import Path

from nicegui import ui

from app.paths import EXPORTS_DIR
from app.native_dialogs import open_folder, ask_save_path, is_native_available
from app.logger import get_logger

_log = get_logger("export_manager")


class ExportManager:
    """DOCX/이미지 내보내기 통합 관리자."""

    @staticmethod
    def save_default(data: bytes, filename: str, *, dest_dir: "Path | None" = None) -> None:
        """기본 폴더 저장. native→파일+다이얼로그, browser→파일+ui.download()."""
        target_dir = dest_dir if dest_dir is not None else EXPORTS_DIR
        saved = target_dir / filename
        try:
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(data)
            _log.info("기본 폴더 저장: %s (%d bytes)", saved, len(data))
        except OSError as exc:
            _log.error("파일 저장 실패: %s — %s", saved, exc)
            ui.notify(f"파일 저장 실패: {exc}", type="negative", timeout=8000)
            if not is_native_available():
                ui.download(data, filename=filename)
            return

        with ui.dialog() as dlg, ui.card().classes("items-center p-6 gap-3"):
            ui.label(f"저장 완료: {saved.name}").classes("font-bold")
            ui.label(str(saved)).classes("text-xs text-gray-500 break-all")
            with ui.row().classes("gap-3 mt-2"):
                ui.button(
                    "폴더 열기",
                    on_click=lambda: (open_folder(saved), dlg.close()),
                ).classes("bg-orange-500 text-white")
                ui.button("닫기", on_click=dlg.close).classes("bg-gray-100")
        dlg.open()

        # browser 모드에서는 추가로 브라우저 다운로드 제공
        if not is_native_available():
            ui.download(data, filename=filename)

    @staticmethod
    async def save_as(data: bytes, filename: str) -> bool:
        """Save As 다이얼로그. native→SAVE_DIALOG, browser→ui.download(). 성공 시 True."""
        path = await ask_save_path(filename)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            _log.info("Save As 저장: %s (%d bytes)", path, len(data))
            ui.notify(f"저장 완료: {path}", type="positive", timeout=6000, close_button="확인")
            return True

        # browser mode or native cancel → fall back to browser download
        if not is_native_available():
            _log.info("브라우저 다운로드 (Save As fallback): %s (%d bytes)", filename, len(data))
            ui.download(data, filename=filename)
            return True

        # native cancel
        _log.info("Save As 취소됨: %s", filename)
        return False

    @staticmethod
    async def save_as_multi(pairs: list[tuple[bytes, str]]) -> bool:
        """복수 파일 Save As."""
        if len(pairs) == 1:
            return await ExportManager.save_as(pairs[0][0], pairs[0][1])

        # native: 각 파일에 대해 Save As
        if is_native_available():
            saved_any = False
            for data, filename in pairs:
                path = await ask_save_path(filename)
                if path is not None:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                    _log.info("Save As (multi): %s (%d bytes)", path, len(data))
                    saved_any = True
            if saved_any:
                ui.notify("저장 완료", type="positive", timeout=6000, close_button="확인")
            return saved_any

        # browser: ui.download 각각
        for data, filename in pairs:
            ui.download(data, filename=filename)
        return True
