"""Design system -- Daangn Ad Reporter brand theme.

Provides inject_theme() which adds the full CSS design system to the current page.
Call once per page (idempotent via JS guard).
"""
from nicegui import ui
from app.theme_css import BRAND_CSS  # noqa: F401


def inject_theme() -> None:
    """Inject the brand CSS into the current page.

    Quasar 컴포넌트(업로더 헤더, 기본 버튼, 탭, 스위치 등)가 쓰는
    primary 색을 당근 오렌지로 바꿔 기본 파란색이 새는 것을 막는다.
    """
    ui.colors(
        primary="#FF6F0F",
        secondary="#52483C",
        accent="#FF8A30",
        positive="#00A84D",
        negative="#E5484D",
        info="#2196F3",
        warning="#F78C0C",
    )
    ui.add_css(BRAND_CSS)


def section_header(icon: str, title: str, subtitle: str = "") -> None:
    """Render a styled section header with icon badge."""
    with ui.row().classes("items-center gap-3 mb-4"):
        with ui.element("div").classes("dg-section-icon"):
            ui.icon(icon, size="20px")
        with ui.column().classes("gap-0"):
            ui.label(title).classes("dg-section-title")
            if subtitle:
                ui.label(subtitle).classes("dg-section-subtitle")
