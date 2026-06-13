"""Screen 1 -- 프로젝트 관리 (카드 그리드 + 다이얼로그 편집).

배치 원칙:
- 프로젝트는 카드 그리드로 한눈에 (세로 목록 금지)
- 생성/편집 폼은 다이얼로그로 — 평소 화면을 차지하지 않는다
- 상단 한 줄: 제목/개수 + 검색 + 데이터 관리 + 새 프로젝트
"""
from nicegui import ui, app as nicegui_app

from app.common import create_nav, safe_download
from app.database import (
    get_projects,
    get_project,
    save_project,
    update_project,
    delete_project,
    export_projects_csv,
    export_performance_csv,
    backup_db,
    get_latest_content,
    get_latest_report,
    get_setting,
    save_setting,
)
from app.onboarding import (
    compute_onboarding_steps,
    is_onboarding_complete,
    onboarding_progress,
)


@ui.page("/")
def project_page() -> None:
    create_nav("/")

    # -- page-level state --
    state: dict = {"current_id": None, "query": ""}

    # ══════════════════ 생성/편집 다이얼로그 ══════════════════
    with ui.dialog() as form_dlg, ui.card().classes("dg-card").style(
        "width: 680px; max-width: 95vw"
    ):
        form_title = ui.label("새 프로젝트").classes("dg-section-title")
        with ui.grid(columns=2).classes("w-full gap-3 mt-3"):
            name_in = ui.input("광고주명 *").classes("dg-input").props("outlined dense")
            campaign_name_in = ui.input("캠페인명 (예: 6월_신규방문)").classes("dg-input").props("outlined dense")
            industry_in = ui.input("업종 (예: 카페, 헬스장)").classes("dg-input").props("outlined dense")
            region_in = ui.input("지역 (예: 서울 마포구 상수동)").classes("dg-input").props("outlined dense")
            goal_in = ui.input("광고 목표 (예: 신규 방문 유도)").classes("dg-input").props("outlined dense")
            budget_in = ui.input("예산 (예: 300,000원)").classes("dg-input").props("outlined dense")
            period_in = ui.input("집행 기간 (예: 2024.06.01~06.30)").classes("dg-input").props("outlined dense")
            reference_in = ui.input("참고 링크 (선택, URL)").classes("dg-input").props("outlined dense")
        benefits_in = ui.textarea(
            "주요 혜택/특징 (3~5가지, 줄바꿈 구분)"
        ).classes("w-full mt-2 dg-input").props("outlined dense rows=4")

        with ui.row().classes("mt-4 gap-2 w-full items-center"):
            delete_btn = ui.button(
                "삭제", icon="delete_outline", on_click=lambda: _confirm_delete(),
            ).classes("dg-btn-danger dg-btn-sm")
            ui.space()
            ui.button("취소", on_click=form_dlg.close).classes("dg-btn-secondary")
            ui.button("저장", icon="save", on_click=lambda: _save()).classes("dg-btn-primary")

    # ══════════════════ 삭제 확인 다이얼로그 ══════════════════
    with ui.dialog() as del_dlg, ui.card().classes("dg-card"):
        ui.label("이 프로젝트를 삭제할까요?").classes("dg-section-title")
        ui.label("생성 내역과 성과 데이터도 함께 사라지고, 되돌릴 수 없어요.").classes("dg-text-sm mt-1")
        with ui.row().classes("mt-5 gap-3"):
            ui.button("삭제", icon="delete", on_click=lambda: _delete()).classes("dg-btn-danger")
            ui.button("취소", on_click=del_dlg.close).classes("dg-btn-secondary")

    # ══════════════════ 페이지 레이아웃 ══════════════════
    with ui.column().classes("dg-page-content w-full gap-4"):

        # 헤더 한 줄: 제목 + 검색 + 데이터 관리 + 새 프로젝트
        with ui.row().classes("w-full items-end gap-3 flex-wrap"):
            with ui.column().classes("gap-0"):
                ui.label("프로젝트").classes("dg-page-title").style("margin-bottom: 0 !important")
                count_label = ui.label("").classes("dg-text-sm")
            ui.space()
            search_in = ui.input(placeholder="이름·캠페인·지역 검색").props(
                "outlined dense clearable"
            ).classes("w-64 dg-input")
            with ui.button(icon="settings").props("flat round").style(
                "color: var(--dg-text-tertiary)"
            ):
                with ui.menu().classes("dg-card"):
                    ui.menu_item(
                        "프로젝트 CSV 내보내기",
                        lambda: safe_download(export_projects_csv(), "프로젝트_목록.csv"),
                    )
                    ui.menu_item(
                        "성과데이터 CSV 내보내기",
                        lambda: safe_download(export_performance_csv(), "성과데이터_전체.csv"),
                    )
                    ui.menu_item("DB 백업", lambda: _do_backup())
            ui.button(
                "새 프로젝트", icon="add", on_click=lambda: _open_create(),
            ).classes("dg-btn-primary")

        # 온보딩 체크리스트 (첫 사용자 안내 — 전부 끝내거나 닫으면 사라짐)
        onboarding_box = ui.element("div").classes("w-full")

        # 카드 그리드
        grid = ui.element("div").classes("dg-project-grid")

    # ══════════════════ 동작 ══════════════════

    def _initial(name: str) -> str:
        return (name or "?").strip()[:1].upper()

    def _matches(p: dict, q: str) -> bool:
        hay = " ".join([
            p.get("name", ""), p.get("campaign_name", "") or "",
            p.get("region", "") or "", p.get("industry", "") or "",
        ]).lower()
        return q in hay

    def refresh_grid() -> None:
        grid.clear()
        projects = get_projects()
        q = (state["query"] or "").strip().lower()
        filtered = [p for p in projects if _matches(p, q)] if q else projects
        count_label.set_text(f"광고주 프로젝트 {len(projects)}개")
        selected = nicegui_app.storage.user.get("current_project_id")
        _render_onboarding()

        with grid:
            if not projects:
                with ui.column().classes("dg-empty w-full items-center").style("grid-column: 1/-1"):
                    ui.icon("storefront", size="56px").classes("dg-empty-icon")
                    ui.label("아직 프로젝트가 없어요. '새 프로젝트'로 시작해 보세요.").classes("dg-empty-text")
                return
            if not filtered:
                with ui.column().classes("dg-empty w-full items-center").style("grid-column: 1/-1"):
                    ui.icon("search_off", size="56px").classes("dg-empty-icon")
                    ui.label(f"'{state['query']}' 검색 결과가 없어요.").classes("dg-empty-text")
                return

            for p in filtered:
                pid = p["id"]
                is_active = selected == pid
                card = ui.element("div").classes(
                    "dg-project-card" + (" active" if is_active else "")
                )
                with card:
                    # 상단: 아바타 + 이름/캠페인 + 편집
                    with ui.row().classes("items-center gap-3 w-full no-wrap"):
                        with ui.element("div").classes("dg-avatar"):
                            ui.label(_initial(p.get("name", "")))
                        with ui.column().classes("gap-0").style("flex: 1; min-width: 0"):
                            ui.label(p.get("name", "")).classes("dg-project-card-title w-full")
                            ui.label(
                                p.get("campaign_name") or "캠페인명 미입력"
                            ).classes("dg-project-card-sub w-full")
                        ui.button(
                            icon="edit",
                            color=None,
                            on_click=lambda _, _pid=pid: _open_edit(_pid),
                        ).props("flat round dense").style("color: var(--dg-text-caption)")

                    # 메타 칩: 업종 / 지역
                    with ui.row().classes("gap-2 flex-wrap"):
                        if p.get("industry"):
                            ui.label(p["industry"]).classes("dg-meta-chip")
                        if p.get("region"):
                            ui.label(p["region"]).classes("dg-meta-chip")
                        if p.get("budget"):
                            ui.label(f"예산 {p['budget']}").classes("dg-meta-chip")

                    # 하단: 바로가기
                    with ui.row().classes("gap-1 w-full items-center"):
                        ui.button(
                            "기획 시작", icon="edit_note", color=None,
                            on_click=lambda _, _pid=pid: _go(_pid, "/planning"),
                        ).props("flat dense no-caps").classes("dg-quick-link")
                        ui.button(
                            "성과 보고서", icon="assessment", color=None,
                            on_click=lambda _, _pid=pid: _go(_pid, "/report"),
                        ).props("flat dense no-caps").classes("dg-quick-link")
                        ui.space()
                        if is_active:
                            ui.label("선택됨").classes("dg-badge dg-badge-success")
                # 카드 클릭 = 현재 프로젝트로 선택
                card.on("click", lambda _, _pid=pid: _select(_pid))

    def _dismiss_onboarding() -> None:
        save_setting("onboarding_dismissed", "1")
        onboarding_box.clear()

    def _onboarding_click(step) -> None:
        if step.key == "project" and not step.done:
            _open_create()
            return
        ui.navigate.to(step.route)

    def _render_onboarding() -> None:
        onboarding_box.clear()
        if get_setting("onboarding_dismissed") == "1":
            return
        projects = get_projects()
        flags = {
            "has_project": bool(projects),
            "has_strategy": any(get_latest_content(p["id"], "strategy") for p in projects),
            "has_planning": any(get_latest_content(p["id"], "planning") for p in projects),
            "has_ad_settings": any(get_latest_content(p["id"], "ad_settings") for p in projects),
            "has_proposal": any(get_latest_content(p["id"], "wizard_proposal") for p in projects),
            "has_report": any(get_latest_report(p["id"]) for p in projects),
        }
        steps = compute_onboarding_steps(flags)
        if is_onboarding_complete(steps):
            return  # 전부 끝나면 자동으로 사라짐
        done, total = onboarding_progress(steps)

        with onboarding_box:
            with ui.card().classes("w-full").style("border:1px solid var(--dg-border)"):
                with ui.row().classes("w-full items-center gap-2"):
                    ui.icon("rocket_launch", size="20px").style("color: var(--dg-primary)")
                    ui.label(f"시작 가이드 · {done}/{total} 완료").style(
                        "font-weight:700; color: var(--dg-text-primary)"
                    )
                    ui.space()
                    ui.button(
                        "다시 보지 않기", on_click=_dismiss_onboarding, color=None,
                    ).props("flat dense no-caps").style(
                        "font-size:11px; color: var(--dg-text-tertiary)"
                    )
                # 진행 바
                with ui.element("div").style(
                    "width:100%; height:6px; background: var(--dg-surface); "
                    "border-radius:999px; overflow:hidden; margin:8px 0"
                ):
                    ui.element("div").style(
                        f"width:{int(done / total * 100)}%; height:100%; "
                        "background: var(--dg-primary); border-radius:999px"
                    )
                # 단계 칩
                with ui.row().classes("w-full gap-2 flex-wrap"):
                    for s in steps:
                        icon = "check_circle" if s.done else "radio_button_unchecked"
                        color = "var(--dg-primary)" if s.done else "var(--dg-text-tertiary)"
                        opacity = "0.6" if s.done else "1"
                        chip = ui.element("div").style(
                            "display:flex; align-items:center; gap:6px; padding:8px 12px; "
                            "border:1px solid var(--dg-border); border-radius:10px; "
                            f"cursor:pointer; opacity:{opacity}"
                        )
                        with chip:
                            ui.icon(icon, size="18px").style(f"color:{color}")
                            with ui.column().classes("gap-0"):
                                ui.label(s.label).style(
                                    "font-size:12px; font-weight:600; color: var(--dg-text-primary)"
                                )
                                ui.label(s.desc).style(
                                    "font-size:10px; color: var(--dg-text-tertiary)"
                                )
                        chip.on("click", lambda _, _s=s: _onboarding_click(_s))

    def _select(pid: int) -> None:
        nicegui_app.storage.user["current_project_id"] = pid
        state["current_id"] = pid
        refresh_grid()

    def _go(pid: int, path: str) -> None:
        nicegui_app.storage.user["current_project_id"] = pid
        ui.navigate.to(path)

    def _fill_form(p: dict | None) -> None:
        values = p or {}
        name_in.value = values.get("name", "")
        campaign_name_in.value = values.get("campaign_name", "") or ""
        industry_in.value = values.get("industry", "") or ""
        region_in.value = values.get("region", "") or ""
        goal_in.value = values.get("goal", "") or ""
        budget_in.value = values.get("budget", "") or ""
        period_in.value = values.get("period", "") or ""
        benefits_in.value = values.get("benefits", "") or ""
        reference_in.value = values.get("reference_url", "") or ""

    def _open_create() -> None:
        state["current_id"] = None
        form_title.set_text("새 프로젝트")
        _fill_form(None)
        delete_btn.set_visibility(False)
        form_dlg.open()

    def _open_edit(pid: int) -> None:
        p = get_project(pid)
        if not p:
            ui.notify("프로젝트를 찾을 수 없어요. 새로고침 후 다시 시도해 주세요.", type="negative")
            return
        state["current_id"] = pid
        form_title.set_text(f"프로젝트 수정 — {p.get('name', '')}")
        _fill_form(p)
        delete_btn.set_visibility(True)
        form_dlg.open()

    def _collect() -> dict:
        return {
            "name": name_in.value.strip(),
            "campaign_name": campaign_name_in.value.strip(),
            "industry": industry_in.value.strip(),
            "region": region_in.value.strip(),
            "goal": goal_in.value.strip(),
            "budget": budget_in.value.strip(),
            "period": period_in.value.strip(),
            "benefits": benefits_in.value.strip(),
            "reference_url": reference_in.value.strip(),
        }

    def _save() -> None:
        data = _collect()
        if not data["name"]:
            ui.notify("광고주명을 입력해 주세요.", type="negative")
            return
        if state["current_id"]:
            update_project(state["current_id"], data)
            ui.notify("수정한 내용을 저장했어요.", type="positive")
        else:
            new_id = save_project(data)
            state["current_id"] = new_id
            nicegui_app.storage.user["current_project_id"] = new_id
            ui.notify("새 프로젝트를 저장했어요.", type="positive")
        form_dlg.close()
        refresh_grid()

    def _confirm_delete() -> None:
        if state["current_id"]:
            del_dlg.open()

    def _delete() -> None:
        pid = state["current_id"]
        if not pid:
            return
        delete_project(pid)
        if nicegui_app.storage.user.get("current_project_id") == pid:
            nicegui_app.storage.user["current_project_id"] = None
        state["current_id"] = None
        del_dlg.close()
        form_dlg.close()
        ui.notify("프로젝트를 삭제했어요.")
        refresh_grid()

    def _do_backup() -> None:
        try:
            path = backup_db()
            ui.notify(f"백업을 완료했어요: {path.name}", type="positive")
        except Exception as exc:
            ui.notify(f"백업하지 못했어요. 잠시 후 다시 시도해 주세요. ({exc})", type="negative")

    def _on_search(e) -> None:
        state["query"] = e.value or ""
        refresh_grid()

    search_in.on_value_change(_on_search)

    # initial render
    refresh_grid()
