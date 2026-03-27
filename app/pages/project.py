"""Screen 1 -- 프로젝트 생성 / 선택."""
from nicegui import ui, app as nicegui_app

from app.common import create_nav, safe_download
from app.theme import section_header
from app.database import (
    get_projects,
    get_project,
    save_project,
    update_project,
    delete_project,
    export_projects_csv,
    export_performance_csv,
    backup_db,
)


@ui.page("/")
def project_page() -> None:
    create_nav("/")

    # -- page-level state --
    state: dict = {"current_id": None}

    # -- layout --
    with ui.column().classes("dg-page-content w-full gap-6"):

        # Page header
        ui.label("프로젝트 관리").classes("dg-page-title")
        ui.label("광고주 프로젝트를 생성하고 관리합니다.").classes("dg-page-subtitle")

        with ui.row().classes("w-full gap-6 items-start"):

            # -- LEFT: project list --
            with ui.card().classes("dg-card").style("width: 280px; flex-shrink: 0"):
                section_header("list", "저장된 프로젝트")
                project_list = ui.column().classes("w-full gap-1")

                ui.button(
                    "새 프로젝트",
                    icon="add",
                    on_click=lambda: load_form(None),
                ).classes("dg-btn-primary w-full mt-3")

            # -- RIGHT: form --
            with ui.card().classes("dg-card flex-1"):
                form_title = ui.label("새 프로젝트 만들기").classes("dg-section-title mb-4")

                with ui.grid(columns=2).classes("w-full gap-4"):
                    name_in = ui.input("광고주명 *").classes("dg-input").props("outlined dense")
                    campaign_name_in = ui.input("캠페인명 (예: 6월_신규방문)").classes("dg-input").props("outlined dense")
                    industry_in = ui.input("업종 (예: 카페, 헬스장)").classes("dg-input").props("outlined dense")
                    region_in = ui.input("지역 (예: 서울 마포구 상수동)").classes("dg-input").props("outlined dense")
                    goal_in = ui.input("광고 목표 (예: 신규 방문 유도)").classes("dg-input").props("outlined dense")
                    budget_in = ui.input("예산 (예: 300,000원)").classes("dg-input").props("outlined dense")
                    period_in = ui.input("집행 기간 (예: 2024.06.01~06.30)").classes("dg-input").props("outlined dense")

                benefits_in = ui.textarea(
                    "주요 혜택/특징 (3~5가지, 줄바꿈 구분)"
                ).classes("w-full mt-2 dg-input").props("outlined dense rows=4")

                reference_in = ui.input("참고 링크 (선택, URL)").classes("w-full mt-1 dg-input").props("outlined dense")

                # Action buttons
                with ui.row().classes("mt-6 gap-3"):
                    save_btn = ui.button(
                        "저장", icon="save", on_click=lambda: _save()
                    ).classes("dg-btn-primary")
                    to_plan_btn = ui.button(
                        "광고 기획 시작",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/planning"),
                    ).classes("dg-btn-success")
                    delete_btn = ui.button(
                        "삭제", icon="delete_outline", on_click=lambda: _delete()
                    ).classes("dg-btn-danger").bind_visibility_from(
                        state, "current_id", lambda v: v is not None
                    )

        # -- Data management --
        with ui.card().classes("dg-card w-full"):
            section_header("storage", "데이터 관리", "프로젝트 데이터를 내보내거나 백업합니다.")
            with ui.row().classes("gap-3 flex-wrap"):
                ui.button(
                    "프로젝트 CSV 내보내기",
                    icon="table_chart",
                    on_click=lambda: safe_download(export_projects_csv(), "프로젝트_목록.csv"),
                ).classes("dg-btn-secondary")
                ui.button(
                    "성과데이터 CSV 내보내기",
                    icon="analytics",
                    on_click=lambda: safe_download(export_performance_csv(), "성과데이터_전체.csv"),
                ).classes("dg-btn-secondary")
                ui.button(
                    "DB 백업",
                    icon="backup",
                    on_click=lambda: _do_backup(),
                ).classes("dg-btn-secondary")

    # -- helpers --

    def refresh_list() -> None:
        project_list.clear()
        projects = get_projects()
        with project_list:
            if not projects:
                ui.label("프로젝트가 없습니다").classes("dg-label-sm py-2")
            for p in projects:
                pid = p["id"]
                is_active = state["current_id"] == pid
                btn_label = p["name"]
                if p.get("campaign_name"):
                    btn_label += f" | {p['campaign_name']}"
                ui.button(
                    btn_label,
                    icon="storefront",
                    on_click=lambda _pid=pid: load_form(_pid),
                ).classes(
                    "dg-project-item" + (" active" if is_active else "")
                ).props("flat no-caps align=left")

    def load_form(pid: int | None) -> None:
        state["current_id"] = pid
        if pid is None:
            form_title.set_text("새 프로젝트 만들기")
            for inp in (name_in, campaign_name_in, industry_in, region_in, goal_in, budget_in, period_in, reference_in):
                inp.value = ""
            benefits_in.value = ""
        else:
            p = get_project(pid)
            if not p:
                return
            form_title.set_text(f"프로젝트 수정: {p['name']}")
            name_in.value = p.get("name", "")
            campaign_name_in.value = p.get("campaign_name", "")
            industry_in.value = p.get("industry", "")
            region_in.value = p.get("region", "")
            goal_in.value = p.get("goal", "")
            budget_in.value = p.get("budget", "")
            period_in.value = p.get("period", "")
            benefits_in.value = p.get("benefits", "")
            reference_in.value = p.get("reference_url", "")
            nicegui_app.storage.user["current_project_id"] = pid
        refresh_list()

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
            ui.notify("광고주명을 입력해주세요.", type="negative")
            return
        if state["current_id"]:
            update_project(state["current_id"], data)
            ui.notify("수정되었습니다.", type="positive")
        else:
            new_id = save_project(data)
            state["current_id"] = new_id
            nicegui_app.storage.user["current_project_id"] = new_id
            ui.notify("저장되었습니다.", type="positive")
        refresh_list()

    def _delete() -> None:
        pid = state["current_id"]
        if not pid:
            return

        with ui.dialog() as dlg, ui.card().classes("dg-card"):
            ui.label("이 프로젝트를 삭제하시겠습니까?").classes("dg-section-title")
            ui.label("관련된 생성 내역, 성과 데이터도 함께 삭제됩니다.").classes("dg-text-sm mt-1")
            with ui.row().classes("mt-5 gap-3"):
                ui.button(
                    "삭제",
                    icon="delete",
                    on_click=lambda: (
                        delete_project(pid),
                        dlg.close(),
                        load_form(None),
                        ui.notify("삭제되었습니다."),
                    ),
                ).classes("dg-btn-danger")
                ui.button("취소", on_click=dlg.close).classes("dg-btn-secondary")
        dlg.open()

    def _do_backup() -> None:
        try:
            path = backup_db()
            ui.notify(f"백업 완료: {path.name}", type="positive")
        except Exception as exc:
            ui.notify(f"백업 실패: {exc}", type="negative")

    # initial render
    refresh_list()
