"""Shared UI components for all pages."""
import sys
from pathlib import Path

from nicegui import ui

from app.export_manager import ExportManager


# ── Backward-compat wrappers (delegate to ExportManager) ──────────────────


def safe_download(data: bytes, filename: str, *, dest_dir: "Path | None" = None) -> None:
    """기본 폴더 저장. ExportManager.save_default() delegate."""
    ExportManager.save_default(data, filename, dest_dir=dest_dir)


async def save_as_download(data: bytes, filename: str) -> bool:
    """Save As 다이얼로그. ExportManager.save_as() delegate."""
    return await ExportManager.save_as(data, filename)


async def save_as_download_multi(pairs: list[tuple[bytes, str]]) -> bool:
    """복수 파일 Save As. ExportManager.save_as_multi() delegate."""
    return await ExportManager.save_as_multi(pairs)


NAV_PAGES = [
    ("프로젝트 관리", "/"),
    ("광고 기획", "/planning"),
    ("성과 보고서", "/report"),
    ("썸네일 제작", "/thumbnail"),
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
    from app.paths import DATA_DIR, DB_PATH, EXPORTS_DIR, CHARTS_DIR, THUMBNAILS_DIR, LOG_PATH, APP_DIR, IS_FROZEN

    with ui.expansion("경로 정보", icon="folder_open").classes("w-full bg-blue-50 mt-2"):
        for label, path in [
            ("데이터 폴더", DATA_DIR),
            ("DB", DB_PATH),
            ("내보내기", EXPORTS_DIR),
            ("차트", CHARTS_DIR),
            ("썸네일", THUMBNAILS_DIR),
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
