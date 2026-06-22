"""Shared UI components for all pages."""
from pathlib import Path

from nicegui import ui, app as nicegui_app

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


NAV_SECTIONS = [
    ("기획", [
        ("folder_open", "프로젝트 관리", "/"),
        ("forum", "AI 상담", "/briefing"),
        ("travel_explore", "커뮤니티 리서치", "/research"),
        ("edit_note", "광고 기획", "/plan/strategy"),
        ("image", "썸네일 제작", "/thumbnail"),
    ]),
    ("분석", [
        ("assessment", "성과 분석", "/report"),
    ]),
]

# 하위 호환 (다른 모듈에서 참조할 수 있음)
NAV_PAGES = [item for _, items in NAV_SECTIONS for item in items]

# 워크플로우 단계 — 기능을 '따로 노는 메뉴'가 아니라 하나의 여정으로 잇는다.
# 리서치를 기획 '앞'에 두어 선행 단계임을 명확히 하고(리서치 결과가 기획에 주입됨),
# 기획 4단계(전략·소식글·세팅·제안서)는 '광고 기획' 한 단계로 묶는다(단계 과다 해소).
# 묶인 4단계의 내부 이동은 기획 위자드 자체 네비가 담당한다.
# (아이콘, 단계명, 부제, 경로)
WORKFLOW_STEPS = [
    ("storefront", "매장·캠페인", "작업 대상 선택", "/"),
    ("forum", "AI 상담", "행사 내용 → AI 정리", "/briefing"),
    ("travel_explore", "커뮤니티 리서치", "고객 목소리 (기획 전 선행)", "/research"),
    ("edit_note", "광고 기획", "전략·소식글·세팅·제안서 한 번에", "/plan/strategy"),
    ("image", "썸네일 제작", "광고 이미지", "/thumbnail"),
    ("assessment", "성과 분석", "성과 측정 + 세그먼트 진단", "/report"),
]
# 기획 위자드의 4개 하위 경로는 모두 '광고 기획' 단계로 본다(워크플로우 바 하이라이트·다음단계 유지).
_PLAN_SUBROUTES = ("/plan/strategy", "/plan/content", "/plan/adset", "/plan/proposal")
_STEP_INDEX = {path: i for i, (_ic, _nm, _sub, path) in enumerate(WORKFLOW_STEPS)}
_PLAN_STEP_IDX = _STEP_INDEX.get("/plan/strategy", -1)
for _r in _PLAN_SUBROUTES:
    _STEP_INDEX.setdefault(_r, _PLAN_STEP_IDX)
# 고급분석은 성과분석(/report)에 병합됨 → 같은 단계로 본다(리다이렉트·탭 내부 네비 일관).
_STEP_INDEX.setdefault("/analysis", _STEP_INDEX.get("/report", -1))

# 브레드크럼 제목 — 사이드바에서 묶인 기획 하위 경로까지 포함해 유지.
_PAGE_TITLES = {path: name for _, items in NAV_SECTIONS for _icon, name, path in items}
_PAGE_TITLES.update({
    "/plan/strategy": "전략 분석",
    "/plan/content": "소식글·제목·쿠폰",
    "/plan/adset": "광고 세팅",
    "/plan/proposal": "운영 제안서",
    "/analysis": "성과 분석",
})


def _render_context_switcher() -> None:
    """사이드바 상단 당근식 매장→캠페인 스위처.

    매장/캠페인을 바꾸면 current_project_id를 갱신하고 reload — 어느 페이지에 있든
    그 컨텍스트로 기획/썸네일/보고서가 동작한다. 데이터/스키마 변경 없음.
    """
    from app.database import get_projects

    projects = get_projects()
    with ui.element("div").classes("dg-context-switcher w-full"):
        if not projects:
            ui.label("등록된 매장이 없어요").classes("dg-text-sm")
            ui.button(
                "새 프로젝트", icon="add", color=None,
                on_click=lambda: ui.navigate.to("/"),
            ).props("flat dense no-caps").classes("dg-quick-link")
            return

        cur_pid = nicegui_app.storage.user.get("current_project_id")
        cur = next((p for p in projects if p["id"] == cur_pid), None) or projects[0]
        cur_store = cur["name"]

        # 매장 목록(최초 등장 순) + 현재 매장의 캠페인들
        stores, seen = [], set()
        for p in projects:
            if p["name"] not in seen:
                seen.add(p["name"])
                stores.append(p["name"])
        store_campaigns = [p for p in projects if p["name"] == cur_store]

        def _switch_store(e) -> None:
            if not e.value or e.value == cur_store:
                return
            first = next((p for p in projects if p["name"] == e.value), None)
            if first:
                nicegui_app.storage.user["current_project_id"] = first["id"]
                ui.navigate.reload()

        def _switch_campaign(e) -> None:
            if e.value and e.value != cur["id"]:
                nicegui_app.storage.user["current_project_id"] = e.value
                ui.navigate.reload()

        ui.label("매장").classes("dg-context-caption")
        ui.select(
            stores, value=cur_store, on_change=_switch_store,
        ).props("outlined dense options-dense").classes("w-full dg-context-select")

        camp_opts = {
            p["id"]: (p.get("campaign_name") or "캠페인명 미입력")
            for p in store_campaigns
        }
        ui.label("캠페인").classes("dg-context-caption")
        ui.select(
            camp_opts, value=cur["id"], on_change=_switch_campaign,
        ).props("outlined dense options-dense").classes("w-full dg-context-select")


def _render_workflow_steps(current: str) -> None:
    """한전ON·쿠팡검증식 가로 워크플로우 스텝 바.

    기능을 따로 노는 메뉴가 아니라 ①매장 → ②리서치 → ③기획 → ④썸네일 →
    ⑤성과 → ⑥분석으로 잇는다(리서치가 기획보다 먼저). 현재 단계는 강조,
    지나온 단계는 완료(체크) 표시,
    각 스텝 클릭 시 해당 페이지로 이동. 모든 페이지 상단에 공통으로 표시된다.
    """
    cur_idx = _STEP_INDEX.get(current, -1)
    with ui.element("div").classes("dg-wf"):
        with ui.element("div").classes("dg-wf-track"):
            for i, (icon, name, sub, path) in enumerate(WORKFLOW_STEPS):
                state = "active" if i == cur_idx else ("done" if (cur_idx >= 0 and i < cur_idx) else "todo")
                with ui.element("div").classes(f"dg-wf-step {state}").on(
                    "click", lambda p=path: ui.navigate.to(p)
                ):
                    with ui.element("div").classes("dg-wf-badge"):
                        if state == "done":
                            ui.icon("check", size="15px")
                        else:
                            ui.label(str(i + 1))
                    with ui.element("div").classes("dg-wf-text"):
                        ui.label(name).classes("dg-wf-name")
                        ui.label(sub).classes("dg-wf-sub")
                if i < len(WORKFLOW_STEPS) - 1:
                    ui.element("div").classes("dg-wf-line")


def create_nav(current: str) -> None:
    inject_theme()

    # -- Header (2단: 브랜드 줄 + 워크플로우 스텝 줄) --
    with ui.header().classes("dg-header"):
        with ui.column().classes("w-full gap-0"):
            with ui.row().classes("w-full items-center px-4 gap-1 dg-header-brand"):
                ui.button(
                    icon="menu",
                    on_click=lambda: drawer.toggle(),
                ).props("flat round dense").style("color: var(--dg-text-secondary)")
                ui.label("당근 광고 도우미").classes("dg-logo ml-1")
                if current in _PAGE_TITLES:
                    ui.icon("chevron_right", size="16px").style("color: var(--dg-text-caption)")
                    ui.label(_PAGE_TITLES[current]).style(
                        "font-size: 13px; font-weight: 600; color: var(--dg-text-secondary)"
                    )
                ui.space()
                ui.label(f"v{_get_version()}").classes("dg-header-version")
            # 워크플로우 스텝 바 — 어느 페이지든 현재 위치 + 전체 흐름을 보여준다.
            _render_workflow_steps(current)

    # -- Sidebar --
    drawer = ui.left_drawer(value=True, fixed=True, bordered=False).classes("dg-sidebar")
    with drawer:
        # Workspace header (management 패턴: 로고 칩 + 이름, border-b)
        with ui.element("div").classes("dg-workspace-header w-full"):
            with ui.element("div").style(
                "width: 34px; height: 34px; border-radius: 10px;"
                "background: linear-gradient(135deg, #FF8A30 0%, #FF6F0F 100%);"
                "display: flex; align-items: center; justify-content: center;"
                "box-shadow: 0 2px 6px rgba(255,111,15,0.3); flex-shrink: 0"
            ):
                ui.icon("storefront", size="20px").style("color: white")
            ui.label("당근 광고 도우미").style(
                "font-size: 15px; font-weight: 800; letter-spacing: -0.4px;"
                "color: var(--dg-text-primary)"
            )

        # ── 당근식 컨텍스트 스위처: 매장 → 캠페인 (어느 페이지든 현재 작업 대상 고정·전환) ──
        _render_context_switcher()

        # 페이지 네비게이션은 상단 워크플로우 스텝 바가 전담한다(중복 제거).
        # 사이드바는 '현재 작업 대상(매장·캠페인)'에 집중. 진행 현황만 가볍게 안내.
        ui.element("div").style("height: 6px")
        with ui.element("div").classes("dg-sidebar-hint"):
            ui.icon("alt_route", size="16px")
            ui.label("상단 단계 바에서 다음 작업으로 이동하세요")

        # Spacer + footer
        ui.space()
        ui.separator().style("border-color: var(--dg-border-light); margin: 0 16px")
        with ui.row().classes("px-5 py-3 items-center gap-2"):
            ui.icon("info_outline", size="16px").style("color: var(--dg-text-caption)")
            ui.label(f"당근 광고 도우미 v{_get_version()}").style(
                "font-size: 11px; color: var(--dg-text-caption)"
            )


def next_step_bar(current: str) -> None:
    """페이지 본문 끝에서 호출 — 다음 단계로 이어주는 흐름 버튼(한전·쿠팡검증식).

    현재 단계 기준으로 이전/다음 워크플로우 단계를 좌우에 배치해, 사용자가
    '다음에 뭘 하면 되는지'를 화면이 안내한다(따로 노는 메뉴 → 이어지는 여정).
    마지막 단계면 다음 버튼을 숨긴다.
    """
    idx = _STEP_INDEX.get(current, -1)
    if idx < 0:
        return
    prev_step = WORKFLOW_STEPS[idx - 1] if idx > 0 else None
    next_step = WORKFLOW_STEPS[idx + 1] if idx < len(WORKFLOW_STEPS) - 1 else None
    if not prev_step and not next_step:
        return
    with ui.element("div").classes("dg-nextbar w-full"):
        if prev_step:
            _ic, nm, _sub, path = prev_step
            with ui.element("div").classes("dg-nextbar-btn prev").on(
                "click", lambda p=path: ui.navigate.to(p)
            ):
                ui.icon("arrow_back", size="18px")
                with ui.element("div").classes("dg-nextbar-text"):
                    ui.label("이전 단계").classes("dg-nextbar-label")
                    ui.label(nm).classes("dg-nextbar-name")
        else:
            ui.element("div")  # 좌측 자리 채움(우측 정렬 유지)
        if next_step:
            _ic, nm, _sub, path = next_step
            with ui.element("div").classes("dg-nextbar-btn next").on(
                "click", lambda p=path: ui.navigate.to(p)
            ):
                with ui.element("div").classes("dg-nextbar-text"):
                    ui.label("다음 단계").classes("dg-nextbar-label")
                    ui.label(nm).classes("dg-nextbar-name")
                ui.icon("arrow_forward", size="18px")


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
            log_area.value = "\n".join(entries) if entries else "아직 로그가 없어요. AI 생성을 실행하면 여기에 표시돼요."

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
