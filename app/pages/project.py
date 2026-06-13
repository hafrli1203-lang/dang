"""Screen 1 -- 프로젝트 관리 (카드 그리드 + 다이얼로그 편집).

배치 원칙:
- 프로젝트는 카드 그리드로 한눈에 (세로 목록 금지)
- 생성/편집 폼은 다이얼로그로 — 평소 화면을 차지하지 않는다
- 상단 한 줄: 제목/개수 + 검색 + 데이터 관리 + 새 프로젝트
"""
import re
from collections import OrderedDict, defaultdict

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
    get_thumbnail_counts,
    get_setting,
    save_setting,
)
from app.onboarding import (
    compute_onboarding_steps,
    is_onboarding_complete,
    onboarding_progress,
)

_MONTH_RE = re.compile(r"(\d{1,2})\s*월")
# 날짜 형식(2026.05.01 / 2026-05 / 2026/5)에서 월 추출 — period가 'N월'이 아닐 때 폴백.
_DATE_MONTH_RE = re.compile(r"\d{4}[.\-/](\d{1,2})")


def _month_key(p: dict) -> tuple:
    """캠페인의 월 그룹 키 (정렬용 정수, 표시 라벨).

    1) campaign_name→period에서 'N월' 파싱
    2) 없으면 날짜 형식(YYYY.MM.DD)에서 월 추출
    """
    sources = (p.get("campaign_name") or "", p.get("period") or "")
    for rx in (_MONTH_RE, _DATE_MONTH_RE):
        for src in sources:
            m = rx.search(src)
            if m:
                mo = int(m.group(1))
                if 1 <= mo <= 12:
                    return (mo, f"{mo}월")
    return (99, "기타")


def _campaign_label(p: dict, month_label: str) -> str:
    """소재 행 표시명. 월 라벨이 따로 있으면 앞의 'N월'을 떼서 중복 제거."""
    cn = (p.get("campaign_name") or "").strip()
    if not cn:
        return "캠페인명 미입력"
    if month_label != "기타":
        stripped = _MONTH_RE.sub("", cn, count=1).lstrip(" _-·~|").strip()
        return stripped or cn
    return cn


def _fmt_budget(raw: str) -> str:
    """예산 문자열을 짧은 칩용으로 축약 (첫 숫자 기준, 1만 이상이면 '만')."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    m = re.search(r"\d[\d,]*", raw)
    if not m:
        return raw[:10]
    n = int(m.group(0).replace(",", ""))
    if n >= 10000:
        man = n / 10000
        return f"{int(man)}만" if man == int(man) else f"{man:.1f}만"
    return f"{n:,}"


def _targeting_summary(p: dict) -> str:
    """소재 행에 보일 당근 타겟 요약 (기록된 값만). 예: '5km · 여성 · 35~59 · 자동 입찰'."""
    bits = []
    radius = (p.get("target_radius_km") or "").strip()
    if radius:
        bits.append(radius if radius.endswith("km") else f"{radius}km")
    if p.get("target_gender"):
        bits.append(p["target_gender"])
    ages = [a for a in (p.get("target_age") or "").split(",") if a]
    if ages:
        bits.append(ages[0] if len(ages) == 1 else f"{ages[0]}~{ages[-1]}")
    if p.get("bid_type"):
        bits.append(p["bid_type"])
    if p.get("coupon_info"):
        bits.append("쿠폰")
    return " · ".join(bits)


# 당근 연령대 밴드 (광고그룹 타겟과 동일 순서)
_AGE_BANDS = ["15~19", "20~24", "25~29", "30~34", "35~39",
              "40~44", "45~49", "50~54", "55~59", "60이상"]


@ui.page("/")
def project_page() -> None:
    create_nav("/")

    # -- page-level state --
    state: dict = {"current_id": None, "query": ""}

    # 연령대 칩 토글 상태 (당근식 다중 선택)
    selected_ages: set = set()
    age_chip_els: dict = {}

    def _refresh_age_chips() -> None:
        for band, el in age_chip_els.items():
            el.classes(replace="dg-age-chip" + (" active" if band in selected_ages else ""))

    def _toggle_age(band: str) -> None:
        selected_ages.discard(band) if band in selected_ages else selected_ages.add(band)
        _refresh_age_chips()

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

        # ══ 당근 광고 세팅 (기록용) — 당근 '광고그룹 수정' 화면 구조 ══
        ui.label("당근 광고 세팅 (기록용)").classes("dg-section-title").style(
            "margin-top: 18px; font-size: 14px"
        )
        ui.label(
            "당근에서 실제로 설정한 값을 기록해두면 다음 달에 다시 입력하지 않아도 돼요."
        ).classes("dg-text-sm").style("margin-top: 2px")

        # ── 오디언스 타겟 ──
        ui.label("오디언스 타겟").classes("dg-subsection")
        target_radius_km_in = ui.input("지역 반경 (km, 예: 5)").classes(
            "w-full dg-input"
        ).props("outlined dense")
        ui.label("성별").classes("dg-text-sm").style("margin-top: 8px")
        target_gender_in = ui.radio(
            ["모든 성별", "여성", "남성"]
        ).props("inline").classes("dg-radio-inline")
        ui.label("연령").classes("dg-text-sm").style("margin-top: 8px")
        with ui.row().classes("gap-2 flex-wrap"):
            for band in _AGE_BANDS:
                chip = ui.element("div").classes("dg-age-chip")
                with chip:
                    ui.label(band)
                chip.on("click", lambda _, b=band: _toggle_age(b))
                age_chip_els[band] = chip

        # ── 예산 및 입찰 ──
        ui.label("예산 및 입찰").classes("dg-subsection")
        with ui.grid(columns=2).classes("w-full gap-3"):
            daily_budget_in = ui.input("일일 예산 (예: 10,000원)").classes(
                "dg-input"
            ).props("outlined dense")
        ui.label("입찰 방식").classes("dg-text-sm").style("margin-top: 8px")
        bid_type_in = ui.radio(
            ["자동 입찰", "수동 입찰"]
        ).props("inline").classes("dg-radio-inline")

        # ── 소재 & 쿠폰 ──
        ui.label("소재 & 쿠폰").classes("dg-subsection")
        ad_titles_in = ui.textarea(
            "소재(광고) 제목들 — 줄바꿈으로 여러 개"
        ).classes("w-full dg-input").props("outlined dense rows=3")
        coupon_info_in = ui.input(
            "쿠폰 (예: 변색렌즈 0원 / 6월 30일까지)"
        ).classes("w-full mt-2 dg-input").props("outlined dense")

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
        thumb_counts = get_thumbnail_counts()
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

            # 매장(name)별로 묶고, 매장 안에서 월별 소재로 정리
            stores = OrderedDict()
            for p in filtered:
                stores.setdefault(p.get("name", ""), []).append(p)

            for store_name, items in stores.items():
                store_active = any(it["id"] == selected for it in items)
                industry = next((x.get("industry") for x in items if x.get("industry")), "")
                region = next((x.get("region") for x in items if x.get("region")), "")
                meta_bits = [b for b in (industry, region, f"소재 {len(items)}") if b]

                store_card = ui.element("div").classes(
                    "dg-store-card" + (" active" if store_active else "")
                )
                with store_card:
                    # 매장 헤더: 아바타 + 매장명 + 메타 + 소재 추가
                    with ui.row().classes("items-center gap-3 w-full no-wrap"):
                        with ui.element("div").classes("dg-avatar"):
                            ui.label(_initial(store_name))
                        with ui.column().classes("gap-0").style("flex: 1; min-width: 0"):
                            ui.label(store_name or "(이름 없음)").classes("dg-store-name w-full")
                            ui.label(" · ".join(meta_bits)).classes("dg-store-meta w-full")
                        ui.button(
                            icon="add", color=None,
                            on_click=lambda _, n=store_name: _open_create_for(n),
                        ).props("flat round dense").style(
                            "color: var(--dg-text-caption)"
                        ).tooltip("이 매장에 소재 추가")

                    # 월별 소재 그룹
                    by_month = defaultdict(list)
                    for it in items:
                        by_month[_month_key(it)].append(it)
                    for key in sorted(by_month.keys()):
                        _mo, label = key
                        with ui.element("div").classes("dg-month-group"):
                            ui.label(label).classes("dg-month-label")
                            for it in by_month[key]:
                                pid = it["id"]
                                is_active = selected == pid
                                row = ui.element("div").classes(
                                    "dg-campaign-row" + (" active" if is_active else "")
                                )
                                with row:
                                    with ui.row().classes("items-center gap-2 w-full no-wrap"):
                                        ui.label(_campaign_label(it, label)).classes("dg-campaign-name")
                                        if it.get("budget"):
                                            ui.label(_fmt_budget(it["budget"])).classes("dg-campaign-budget")
                                        with ui.row().classes("dg-campaign-actions no-wrap gap-0"):
                                            ui.button(
                                                icon="edit_note", color=None,
                                            ).props("flat round dense").classes("dg-quick-link").on(
                                                "click.stop", lambda _, _pid=pid: _go(_pid, "/planning")
                                            ).tooltip("기획")
                                            ui.button(
                                                icon="assessment", color=None,
                                            ).props("flat round dense").classes("dg-quick-link").on(
                                                "click.stop", lambda _, _pid=pid: _go(_pid, "/report")
                                            ).tooltip("성과")
                                            ui.button(
                                                icon="edit", color=None,
                                            ).props("flat round dense").style(
                                                "color: var(--dg-text-caption)"
                                            ).on(
                                                "click.stop", lambda _, _pid=pid: _open_edit(_pid)
                                            ).tooltip("수정")
                                    summary = _targeting_summary(it)
                                    tcount = thumb_counts.get(pid, 0)
                                    if tcount:
                                        summary = (summary + " · " if summary else "") + f"이미지 {tcount}"
                                    if summary:
                                        ui.label(summary).classes("dg-campaign-target")
                                row.on("click", lambda _, _pid=pid: _select(_pid))

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
        # 광고 기록 (당근 세팅)
        target_radius_km_in.value = values.get("target_radius_km", "") or ""
        daily_budget_in.value = values.get("daily_budget", "") or ""
        target_gender_in.value = values.get("target_gender", "") or None
        bid_type_in.value = values.get("bid_type", "") or None
        selected_ages.clear()
        selected_ages.update(a for a in (values.get("target_age", "") or "").split(",") if a)
        _refresh_age_chips()
        ad_titles_in.value = values.get("ad_titles", "") or ""
        coupon_info_in.value = values.get("coupon_info", "") or ""

    def _open_create() -> None:
        state["current_id"] = None
        form_title.set_text("새 프로젝트")
        _fill_form(None)
        delete_btn.set_visibility(False)
        form_dlg.open()

    def _open_create_for(store_name: str) -> None:
        """매장 카드의 '+'에서 — 새 소재 생성 폼을 열고 매장명을 미리 채운다."""
        _open_create()
        name_in.value = store_name

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
        ordered_ages = [b for b in _AGE_BANDS if b in selected_ages]
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
            # 광고 기록 (당근 세팅)
            "target_radius_km": (target_radius_km_in.value or "").strip(),
            "target_gender": target_gender_in.value or "",
            "target_age": ",".join(ordered_ages),
            "bid_type": bid_type_in.value or "",
            "daily_budget": (daily_budget_in.value or "").strip(),
            "ad_titles": (ad_titles_in.value or "").strip(),
            "coupon_info": (coupon_info_in.value or "").strip(),
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
