"""Shared UI components for all pages."""
from pathlib import Path

from nicegui import ui

from app.export_manager import ExportManager
from app.theme import inject_theme, section_header  # noqa: F401


def _get_version() -> str:
    """Read __version__ from main module without circular import."""
    try:
        import main
        return getattr(main, "__version__", "1.1.0")
    except Exception:
        return "1.1.0"


# -- Backward-compat wrappers (delegate to ExportManager) --

def safe_download(data: bytes, filename: str, *, dest_dir: "Path | None" = None) -> None:
    ExportManager.save_default(data, filename, dest_dir=dest_dir)


async def save_as_download(data: bytes, filename: str) -> bool:
    return await ExportManager.save_as(data, filename)


async def save_as_download_multi(pairs: list[tuple[bytes, str]]) -> bool:
    return await ExportManager.save_as_multi(pairs)


NAV_PAGES = [
    ("folder_open", "프로젝트 관리", "/"),
    ("edit_note", "광고 기획", "/planning"),
    ("assessment", "성과 보고서", "/report"),
    ("insights", "고급 분석", "/analysis"),
]


def create_nav(current: str) -> None:
    inject_theme()

    # -- Header --
    with ui.header().classes("dg-header"):
        with ui.row().classes("w-full items-center px-4 h-full"):
            ui.button(
                icon="menu",
                on_click=lambda: drawer.toggle(),
            ).props("flat round dense").style("color: var(--dg-text-secondary)")
            ui.label("당근 광고 도우미").classes("dg-logo ml-2")
            ui.space()
            ui.label(f"v{_get_version()}").classes("dg-header-version")

    # -- Sidebar --
    drawer = ui.left_drawer(value=True, fixed=True, bordered=False).classes("dg-sidebar")
    with drawer:
        # Logo block
        with ui.column().classes("px-5 pt-2 pb-4"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("storefront", size="28px").style("color: var(--dg-primary)")
                with ui.column().classes("gap-0"):
                    ui.label("당근 광고").style(
                        "font-size: 15px; font-weight: 700; color: var(--dg-text-primary)"
                    )
                    ui.label("기획 도우미").style(
                        "font-size: 12px; color: var(--dg-text-caption)"
                    )
        ui.separator().style("border-color: var(--dg-border-light); margin: 0 16px")

        # Section label
        ui.label("메뉴").classes("dg-nav-section-label")

        # Nav items
        for icon, name, path in NAV_PAGES:
            active = current == path
            ui.button(
                name,
                icon=icon,
                on_click=lambda p=path: ui.navigate.to(p),
            ).classes(
                "dg-nav-item" + (" active" if active else "")
            ).props("flat no-caps align=left")

        # Spacer + footer
        ui.space()
        ui.separator().style("border-color: var(--dg-border-light); margin: 0 16px")
        with ui.row().classes("px-5 py-3 items-center gap-2"):
            ui.icon("info_outline", size="16px").style("color: var(--dg-text-caption)")
            ui.label(f"당근 광고 도우미 v{_get_version()}").style(
                "font-size: 11px; color: var(--dg-text-caption)"
            )


def project_selector(label: str = "프로젝트 선택") -> ui.select:
    from app.database import get_projects
    projects = get_projects()
    options = {p["id"]: f"{p['name']} ({p.get('region','')})" for p in projects}
    return ui.select(options, label=label).classes("w-72 dg-select")


def create_log_panel() -> None:
    from app.logger import get_recent_logs
    with ui.expansion(
        "실시간 로그", icon="terminal",
        on_value_change=lambda e: _refresh() if e.value else None,
    ).classes("w-full mt-4 dg-expansion"):
        log_area = ui.textarea().classes("w-full dg-mono").props(
            "readonly outlined rows=10"
        )

        def _refresh() -> None:
            entries = get_recent_logs(50)
            log_area.value = "\n".join(entries) if entries else "(로그 없음 -- AI 생성을 실행하면 로그가 표시됩니다)"

        with ui.row().classes("gap-2 items-center mt-1"):
            ui.button("새로고침", icon="refresh", on_click=_refresh).classes("dg-btn-secondary dg-btn-sm")
        _refresh()


def create_path_info_panel() -> None:
    from app.paths import EXPORTS_DIR, THUMBNAILS_DIR, IS_FROZEN

    with ui.expansion("저장 위치", icon="folder_open").classes("w-full mt-2 dg-expansion"):
        for label, path in [
            ("내보내기 폴더", EXPORTS_DIR),
            ("썸네일 폴더", THUMBNAILS_DIR),
        ]:
            with ui.row().classes("items-center gap-2 py-1"):
                ui.label(label).style(
                    "font-size: 12px; font-weight: 500; color: var(--dg-text-tertiary); width: 120px"
                )
                ui.label(str(path)).classes("dg-mono").style("color: var(--dg-text-secondary)")
                ok = path.exists()
                ui.icon(
                    "check_circle" if ok else "error", size="16px"
                ).style(f"color: {'var(--dg-success)' if ok else 'var(--dg-error)'}")
        with ui.row().classes("items-center gap-2 py-1"):
            ui.label("실행 모드").style(
                "font-size: 12px; font-weight: 500; color: var(--dg-text-tertiary); width: 120px"
            )
            ui.label("PyInstaller" if IS_FROZEN else "개발 모드").classes("dg-mono")


def no_project_notice() -> None:
    with ui.card().classes("dg-card w-full"):
        with ui.column().classes("dg-empty w-full"):
            ui.icon("folder_open").classes("dg-empty-icon")
            ui.label("먼저 프로젝트를 선택해주세요.").classes("dg-empty-text")
            ui.button(
                "프로젝트 관리로 이동",
                icon="arrow_forward",
                on_click=lambda: ui.navigate.to("/"),
            ).classes("dg-btn-primary mt-4")
