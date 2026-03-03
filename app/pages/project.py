"""Screen 1 – 프로젝트 생성 / 선택."""
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
)


@ui.page("/")
def project_page() -> None:
    create_nav("/")

    # ── page-level state ──────────────────────────────────────────────────────
    state: dict = {"current_id": None}

    # ── layout ────────────────────────────────────────────────────────────────
    with ui.row().classes("w-full gap-6 p-6 items-start"):

        # ── LEFT: project list ────────────────────────────────────────────────
        with ui.card().classes("w-64 shrink-0"):
            ui.label("저장된 프로젝트").classes("text-base font-bold text-orange-600 mb-2")
            project_list = ui.column().classes("w-full gap-1")

            with ui.row().classes("w-full mt-2 gap-1"):
                ui.button(
                    "+ 새 프로젝트",
                    on_click=lambda: load_form(None),
                ).classes("flex-1 bg-orange-500 text-white text-sm")

        # ── RIGHT: form ───────────────────────────────────────────────────────
        with ui.card().classes("flex-1"):
            form_title = ui.label("새 프로젝트 만들기").classes(
                "text-lg font-bold text-gray-700 mb-4"
            )

            with ui.grid(columns=2).classes("w-full gap-3"):
                name_in = ui.input("광고주명 *").classes("col-span-1")
                industry_in = ui.input("업종 (예: 카페, 헬스장)").classes("col-span-1")
                region_in = ui.input("지역 (예: 서울 마포구 상수동)").classes("col-span-1")
                goal_in = ui.input("광고 목표 (예: 신규 방문 유도)").classes("col-span-1")
                budget_in = ui.input("예산 (예: 300,000원)").classes("col-span-1")
                period_in = ui.input("집행 기간 (예: 2024.06.01~06.30)").classes(
                    "col-span-1"
                )

            benefits_in = ui.textarea(
                "주요 혜택·특징 (3~5가지, 줄바꿈 구분)"
            ).classes("w-full mt-1").props("rows=4")

            reference_in = ui.input("참고 링크 (선택, URL)").classes("w-full mt-1")

            with ui.row().classes("mt-5 gap-2"):
                save_btn = ui.button("저장", on_click=lambda: _save()).classes(
                    "bg-orange-500 text-white"
                )
                to_plan_btn = ui.button(
                    "광고 기획 시작 →",
                    on_click=lambda: ui.navigate.to("/planning"),
                ).classes("bg-green-600 text-white")
                delete_btn = ui.button(
                    "삭제",
                    on_click=lambda: _delete(),
                ).classes("bg-red-400 text-white").bind_visibility_from(
                    state, "current_id", lambda v: v is not None
                )

    # ── helpers ───────────────────────────────────────────────────────────────

    def refresh_list() -> None:
        project_list.clear()
        projects = get_projects()
        with project_list:
            if not projects:
                ui.label("(없음)").classes("text-gray-400 text-sm")
            for p in projects:
                pid = p["id"]
                is_active = state["current_id"] == pid
                ui.button(
                    f"{'▶ ' if is_active else ''}{p['name']}",
                    on_click=lambda _pid=pid: load_form(_pid),
                ).classes(
                    "w-full text-left text-sm py-1 "
                    + ("bg-orange-100 font-bold" if is_active else "")
                ).props("flat")

    def load_form(pid: int | None) -> None:
        state["current_id"] = pid
        if pid is None:
            form_title.set_text("새 프로젝트 만들기")
            for inp in (name_in, industry_in, region_in, goal_in, budget_in, period_in, reference_in):
                inp.value = ""
            benefits_in.value = ""
        else:
            p = get_project(pid)
            if not p:
                return
            form_title.set_text(f"프로젝트 수정: {p['name']}")
            name_in.value = p.get("name", "")
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

        async def confirm_delete() -> None:
            with ui.dialog() as dlg, ui.card():
                ui.label("이 프로젝트를 삭제하시겠습니까?").classes("text-base font-semibold")
                ui.label("관련된 생성 내역, 성과 데이터도 함께 삭제됩니다.").classes(
                    "text-sm text-gray-500"
                )
                with ui.row().classes("mt-4 gap-2"):
                    ui.button(
                        "삭제",
                        on_click=lambda: (
                            delete_project(pid),
                            dlg.close(),
                            load_form(None),
                            ui.notify("삭제되었습니다."),
                        ),
                    ).classes("bg-red-500 text-white")
                    ui.button("취소", on_click=dlg.close).props("flat")
            dlg.open()

        import asyncio
        asyncio.ensure_future(confirm_delete())

    # ── Data management (backup / export) ─────────────────────────────────
    with ui.row().classes("w-full px-6 pb-6 gap-6 items-start"):
        with ui.card().classes("w-full"):
            ui.label("데이터 관리").classes("text-base font-bold text-gray-700 mb-2")
            with ui.row().classes("gap-3 flex-wrap"):
                ui.button(
                    "📋 프로젝트 CSV 내보내기",
                    on_click=lambda: safe_download(export_projects_csv(), "프로젝트_목록.csv"),
                ).classes("bg-blue-500 text-white text-sm")
                ui.button(
                    "📊 성과데이터 CSV 내보내기",
                    on_click=lambda: safe_download(export_performance_csv(), "성과데이터_전체.csv"),
                ).classes("bg-blue-500 text-white text-sm")
                ui.button(
                    "💾 DB 백업",
                    on_click=lambda: _do_backup(),
                ).classes("bg-gray-600 text-white text-sm")

    def _do_backup() -> None:
        try:
            path = backup_db()
            ui.notify(f"백업 완료: {path.name}", type="positive")
        except Exception as exc:
            ui.notify(f"백업 실패: {exc}", type="negative")

    # initial render
    refresh_list()
