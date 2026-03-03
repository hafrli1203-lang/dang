"""Shared UI components for all pages."""
import os
import platform
import subprocess
import sys
from pathlib import Path

from nicegui import ui

from app.paths import EXPORTS_DIR
from app.logger import get_logger

_log = get_logger("common")


def _open_path(path: Path) -> None:
    """Open a file or folder with the OS default handler."""
    try:
        if platform.system() == "Windows":
            os.startfile(str(path))
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def safe_download(data: bytes, filename: str) -> None:
    """기본 폴더 저장: EXPORTS_DIR에 자동 저장 + 열기 버튼 알림.  Browser 모드: ui.download()."""
    if getattr(sys, '_nicegui_native', False):
        saved = EXPORTS_DIR / filename
        saved.write_bytes(data)
        _log.info("기본 폴더 저장: %s (%d bytes)", saved, len(data))
        with ui.dialog() as dlg, ui.card().classes("items-center p-6 gap-3"):
            ui.label(f"저장 완료: {saved.name}").classes("font-bold")
            ui.label(str(saved)).classes("text-xs text-gray-500 break-all")
            with ui.row().classes("gap-3 mt-2"):
                ui.button("파일 열기", on_click=lambda: (_open_path(saved), dlg.close())).classes(
                    "bg-orange-500 text-white"
                )
                ui.button("폴더 열기", on_click=lambda: (_open_path(EXPORTS_DIR), dlg.close())).classes(
                    "bg-gray-200 text-gray-700"
                )
                ui.button("닫기", on_click=dlg.close).classes("bg-gray-100")
        dlg.open()
        return
    _log.info("브라우저 다운로드: %s (%d bytes)", filename, len(data))
    ui.download(data, filename=filename)


async def save_as_download(data: bytes, filename: str) -> bool:
    """다른 위치로 저장: native면 Save As 다이얼로그, browser면 ui.download(). 성공 시 True."""
    from app.exporting import choose_save_path_docx

    path = await choose_save_path_docx(filename)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        _log.info("Save As 저장: %s (%d bytes)", path, len(data))
        ui.notify(f"저장 완료: {path}", type="positive", timeout=6000, close_button="확인")
        return True

    # browser mode or native cancel → fall back to browser download
    if not getattr(sys, "_nicegui_native", False):
        _log.info("브라우저 다운로드 (Save As fallback): %s (%d bytes)", filename, len(data))
        ui.download(data, filename=filename)
        return True

    # native cancel
    _log.info("Save As 취소됨: %s", filename)
    return False

async def save_as_download_multi(pairs: list[tuple[bytes, str]]) -> bool:
    """여러 파일: 폴더 다이얼로그 1회. 단일 파일: 기존 Save As. browser: ui.download()."""
    if len(pairs) == 1:
        return await save_as_download(pairs[0][0], pairs[0][1])

    from app.exporting import choose_save_folder

    folder = await choose_save_folder()
    if folder is not None:
        folder.mkdir(parents=True, exist_ok=True)
        for data, filename in pairs:
            (folder / filename).write_bytes(data)
            _log.info("Save As (폴더): %s/%s (%d bytes)", folder, filename, len(data))
        ui.notify(f"저장 완료: {folder}", type="positive", timeout=8000, close_button="확인")
        return True

    if not getattr(sys, "_nicegui_native", False):
        for data, filename in pairs:
            ui.download(data, filename=filename)
        return True

    return False  # native cancel


NAV_PAGES = [
    ("프로젝트 관리", "/"),
    ("광고 기획", "/planning"),
    ("성과 보고서", "/report"),
]


def create_nav(current: str) -> None:
    with ui.header().classes("bg-orange-500 text-white"):
        with ui.row().classes("w-full items-center px-6 py-2 gap-6"):
            ui.label("🥕 당근 광고 기획 도우미").classes(
                "text-xl font-bold tracking-tight"
            )
            ui.space()
            for name, path in NAV_PAGES:
                active = current == path
                ui.button(
                    name,
                    on_click=lambda p=path: ui.navigate.to(p),
                ).classes(
                    "text-white font-medium px-4 py-1 rounded "
                    + ("bg-orange-800" if active else "bg-orange-400 hover:bg-orange-600")
                ).props("flat")


def project_selector(label: str = "프로젝트 선택") -> ui.select:
    from app.database import get_projects

    projects = get_projects()
    options = {p["id"]: f"{p['name']} ({p.get('region','')})" for p in projects}
    return ui.select(options, label=label).classes("w-72")


def create_log_panel() -> None:
    """Expandable diagnostic log panel at the bottom of the page."""
    from app.logger import get_recent_logs

    with ui.expansion("최근 로그 보기", icon="terminal").classes(
        "w-full bg-gray-50 mt-4"
    ):
        log_area = ui.textarea().classes("w-full font-mono text-xs").props(
            "readonly outlined rows=10"
        )

        def _refresh() -> None:
            lines = get_recent_logs(50)
            log_area.value = "\n".join(lines) if lines else "(로그 없음)"

        ui.button("새로고침", on_click=_refresh).classes("text-sm mt-1")
        _refresh()


def create_path_info_panel() -> None:
    """Expandable panel showing resolved paths and run mode."""
    from app.paths import DATA_DIR, DB_PATH, EXPORTS_DIR, CHARTS_DIR, LOG_PATH, APP_DIR, IS_FROZEN

    with ui.expansion("경로 정보", icon="folder_open").classes("w-full bg-blue-50 mt-2"):
        for label, path in [
            ("데이터 폴더", DATA_DIR),
            ("DB", DB_PATH),
            ("내보내기", EXPORTS_DIR),
            ("차트", CHARTS_DIR),
            ("로그", LOG_PATH),
            ("앱 디렉토리", APP_DIR),
        ]:
            with ui.row().classes("items-center gap-2 py-1"):
                ui.label(label).classes("text-xs font-medium text-gray-600 w-40")
                ui.label(str(path)).classes("text-xs text-gray-500 font-mono break-all")
                ok = path.exists()
                ui.icon("check_circle" if ok else "error", size="16px").classes(
                    "text-green-500" if ok else "text-red-400"
                )
        with ui.row().classes("items-center gap-2 py-1"):
            ui.label("실행 모드").classes("text-xs font-medium text-gray-600 w-40")
            ui.label("PyInstaller" if IS_FROZEN else "개발 모드").classes("text-xs font-mono")


def no_project_notice() -> None:
    with ui.card().classes("w-full items-center py-12 text-center"):
        ui.icon("folder_open", size="64px").classes("text-orange-300")
        ui.label("먼저 프로젝트를 선택해주세요.").classes("text-gray-500 text-lg mt-2")
        ui.button(
            "프로젝트 관리로 이동",
            on_click=lambda: ui.navigate.to("/"),
        ).classes("mt-4 bg-orange-500 text-white")
