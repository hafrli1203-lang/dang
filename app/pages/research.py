# -*- coding: utf-8 -*-
"""Screen: /research — 커뮤니티 리서치.

검색 키워드 → 네이버/커뮤니티에서 실제 글·댓글 수집 → AI가 고충·욕구·실제 표현·
콘텐츠 앵글·후크를 뽑아 소식글/광고 콘텐츠를 다양화할 재료로 보여준다.
검색 프로젝트(C:/project/search) 풀 포팅의 UI 레이어.
"""
import asyncio

from nicegui import ui, app as nicegui_app

from app.common import create_nav, next_step_bar
from app.theme import section_header
from app.database import get_project
from app.logger import get_logger
from app.ai.providers import get_provider
from app.research.sources import SOURCE_POLICIES, DEFAULT_SOURCE_IDS
from app.research.connectors import naver_credentials, google_cse_credentials
from app.research.pipeline import run_research

_log = get_logger("research")


@ui.page("/research")
def research_page() -> None:
    create_nav("/research")

    state: dict = {"selected": set(DEFAULT_SOURCE_IDS), "run": None}

    with ui.column().classes("dg-page-content w-full gap-5"):
        next_step_bar("/research")  # CSS order로 본문 맨 아래에 '다음 단계' 흐름 버튼
        ui.label("커뮤니티 리서치").classes("dg-page-title")
        ui.label(
            "네이버·커뮤니티에서 실제 고객의 글과 댓글을 모아, 광고 콘텐츠를 다양화할 재료를 찾아 드려요."
        ).classes("dg-page-subtitle")

        # 키 상태 안내 (없으면 솔직히)
        nid, nsec = naver_credentials()
        gkey, gcx = google_cse_credentials()
        if not (nid and nsec):
            with ui.element("div").classes("dg-banner dg-banner-warning w-full"):
                ui.icon("vpn_key", size="18px")
                ui.label(
                    "네이버 검색 키(NAVER_CLIENT_ID/SECRET)가 .env에 없어 네이버 소스는 건너뛰어요. "
                    "developers.naver.com에서 검색 API 키를 발급해 .env에 넣어 주세요."
                )
        if not (gkey and gcx):
            with ui.element("div").classes("dg-banner dg-banner-info w-full"):
                ui.icon("info", size="18px")
                ui.label(
                    "Google CSE 키(GOOGLE_CSE_API_KEY/CX)가 없어 커뮤니티(더쿠·디시 등) 소스는 건너뛰어요. "
                    "네이버 키만으로도 블로그·카페·지식인 리서치는 충분히 돼요."
                )

        # -- 입력 --
        with ui.card().classes("dg-card w-full"):
            section_header("search", "검색 키워드", "업종·상품·지역을 조합하면 더 구체적인 반응을 찾아요.")

            # 프로젝트에서 업종/지역 프리필
            pid = nicegui_app.storage.user.get("current_project_id")
            project = get_project(pid) if pid else None
            prefill = ""
            if project:
                parts = [project.get("industry", ""), project.get("region", "")]
                prefill = " ".join(p for p in parts if p).strip()

            keyword_input = ui.input(
                label="키워드", value=prefill,
                placeholder="예: 변색렌즈 후기 / 밀양 안경원 / 동네 마라탕",
            ).classes("w-full dg-input").props("outlined")

            with ui.row().classes("gap-4 items-center mt-2 flex-wrap"):
                depth_select = ui.select(
                    {6: "빠르게 (소스당 6건)", 10: "보통 (10건)", 16: "깊게 (16건)"},
                    value=10, label="검색 깊이",
                ).classes("w-48 dg-select").props("outlined")
                maxdocs_select = ui.select(
                    {8: "본문 8개", 12: "본문 12개", 20: "본문 20개"},
                    value=12, label="본문 분석 수",
                ).classes("w-44 dg-select").props("outlined")

            # 소스 선택 (칩 토글)
            ui.label("검색할 소스").classes("dg-label-sm mt-3")
            source_chips: dict[str, ui.chip] = {}
            with ui.row().classes("gap-2 flex-wrap"):
                for sp in SOURCE_POLICIES:
                    chip = ui.chip(
                        sp.label, selectable=True,
                        selected=sp.id in state["selected"],
                    ).props("outline").classes("dg-chip")

                    def _toggle(sid=sp.id, c=None):
                        c = source_chips[sid]
                        if c.selected:
                            state["selected"].add(sid)
                        else:
                            state["selected"].discard(sid)

                    chip.on("update:selected", lambda e, sid=sp.id: _toggle(sid))
                    source_chips[sp.id] = chip

            with ui.row().classes("gap-2 mt-3 items-center flex-wrap"):
                run_btn = ui.button("리서치 시작", icon="travel_explore").classes("dg-btn-primary")
                ads_btn = ui.button("경쟁 광고 관측", icon="ads_click").classes("dg-btn-secondary")
            ui.label(
                "경쟁 광고 관측: 네이버 파워링크·브랜드검색 + 메타(페이스북·인스타) 광고 라이브러리에서 "
                "이 키워드로 집행 중인 광고를 긁어 와요. 브라우저 자동화(Playwright)가 필요하고 20~40초 걸려요. "
                "구글은 자동화 차단(CAPTCHA)이 강해 결과가 없을 수 있어요."
            ).classes("dg-label-sm")

        # -- 진행 --
        progress_row = ui.row().classes("w-full items-center gap-2 hidden")
        with progress_row:
            ui.spinner("dots", size="sm")
            progress_label = ui.label("준비 중...").classes("dg-progress-text")

        # -- 결과 --
        results_card = ui.card().classes("dg-card w-full hidden")
        with results_card:
            section_header("insights", "리서치 결과", "실제 고객 반응에서 뽑은 콘텐츠 재료예요.")
            results_body = ui.column().classes("w-full gap-4")

        # -- 경쟁 광고 관측 결과 --
        ads_card = ui.card().classes("dg-card w-full hidden")
        with ads_card:
            section_header("ads_click", "경쟁 광고 관측", "지금 집행 중인 경쟁 광고예요. 카피·구도를 참고하세요.")
            ads_body = ui.column().classes("w-full gap-3")

        # ───────── handlers ─────────

        def _chip_list(title: str, items: list[str], icon: str, copyable: bool = True) -> None:
            if not items:
                return
            with ui.card().classes("w-full").style("border-left:4px solid var(--dg-primary)"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon(icon, size="18px").style("color: var(--dg-primary)")
                    ui.label(title).style("font-size:14px; font-weight:700")
                for it in items:
                    with ui.row().classes("items-start gap-2 w-full"):
                        ui.icon("chevron_right", size="16px").style("color: var(--dg-text-tertiary); margin-top:3px")
                        ui.label(it).style("font-size:13px; line-height:1.6; flex:1")
                if copyable:
                    def _copy(text="\n".join(f"- {i}" for i in items)):
                        ui.clipboard.write(text)
                        ui.notify("복사했어요.", type="positive", timeout=1500)
                    ui.button("복사", icon="content_copy", on_click=_copy).classes("dg-btn-secondary dg-btn-sm mt-1")

        def _render(run) -> None:
            results_body.clear()
            with results_body:
                # 수집 요약
                with ui.element("div").classes("dg-banner dg-banner-success w-full"):
                    ui.icon("check_circle", size="18px")
                    ui.label(
                        f"검색 {run.discovered}건 → 본문·댓글 {run.fetched}개 분석"
                        + (f" (수집 실패 {run.failed})" if run.failed else "")
                    )
                if run.key_missing:
                    with ui.element("div").classes("dg-banner dg-banner-info w-full"):
                        ui.icon("info", size="16px")
                        ui.label("키가 없어 건너뛴 소스: " + ", ".join(sorted(set(run.key_missing))))

                if not run.documents:
                    with ui.element("div").classes("dg-banner dg-banner-warning w-full"):
                        ui.icon("warning", size="18px")
                        ui.label(
                            "본문을 수집하지 못했어요. 키워드를 바꾸거나 소스를 늘려 보세요. "
                            "(커뮤니티 일부는 로그인·차단으로 본문이 막힐 수 있어요.)"
                        )
                    return

                ins = run.insight or {}
                if ins.get("verdict"):
                    with ui.card().classes("w-full").style(
                        "background: var(--dg-primary-light); border-left:5px solid var(--dg-primary)"
                    ):
                        ui.label("한 줄 종합").style("font-size:12px; font-weight:600; color: var(--dg-primary)")
                        ui.label(ins["verdict"]).style("font-size:15px; font-weight:600; margin-top:4px")

                _chip_list("고객 고충 (pain points)", ins.get("pain_points", []), "sentiment_dissatisfied")
                _chip_list("고객이 원하는 것 (desires)", ins.get("desires", []), "favorite")
                _chip_list("실제 쓰는 표현 — 그대로 카피에", ins.get("real_expressions", []), "format_quote")
                _chip_list("콘텐츠 앵글 — 소식글 다양화", ins.get("content_angles", []), "diversity_3")
                _chip_list("후크 아이디어 — 썸네일·제목", ins.get("hook_ideas", []), "bolt")
                _chip_list("혜택·가격 반응 신호", ins.get("offer_signals", []), "sell")
                _chip_list("다음 액션", ins.get("next_actions", []), "checklist")

                comps = ins.get("competitors", [])
                if comps:
                    with ui.card().classes("w-full"):
                        ui.label("언급된 경쟁 매장·브랜드").style("font-size:14px; font-weight:700")
                        ui.table(
                            columns=[
                                {"name": "name", "label": "이름", "field": "name", "align": "left"},
                                {"name": "mention", "label": "언급", "field": "mention", "align": "right"},
                                {"name": "sentiment", "label": "여론", "field": "sentiment", "align": "center"},
                            ],
                            rows=[{"name": c["name"], "mention": c["mention_count"],
                                   "sentiment": {"positive": "긍정", "negative": "부정"}.get(c["sentiment"], "중립")}
                                  for c in comps],
                        ).classes("w-full dg-table").props("dense flat bordered")

                # 출처
                with ui.expansion("수집한 글 출처 보기", icon="link").classes("w-full"):
                    for d in run.documents:
                        with ui.row().classes("items-center gap-2 w-full"):
                            ui.label(f"[{d['source_label']}]").style(
                                "font-size:11px; color: var(--dg-primary); font-weight:600")
                            ui.link(d["title"][:60] or d["url"], d["url"], new_tab=True).style(
                                "font-size:12px")
                            if d.get("comment_count"):
                                ui.label(f"댓글 {d['comment_count']}").style(
                                    "font-size:11px; color: var(--dg-text-tertiary)")

        async def _run() -> None:
            keyword = (keyword_input.value or "").strip()
            if not keyword:
                ui.notify("키워드를 입력해 주세요.", type="warning")
                return
            if not state["selected"]:
                ui.notify("소스를 하나 이상 선택해 주세요.", type="warning")
                return

            run_btn.props("disabled")
            progress_row.classes(remove="hidden")
            results_card.classes("hidden")

            def _progress(msg: str) -> None:
                progress_label.set_text(msg)

            try:
                provider = get_provider("claude")

                def _gen(prompt, system_prompt=None):
                    return provider.generate_text(prompt, system_prompt=system_prompt)

                loop = asyncio.get_running_loop()
                run = await loop.run_in_executor(
                    None,
                    lambda: run_research(
                        keyword, list(state["selected"]), _gen,
                        limit_per_source=int(depth_select.value),
                        max_docs=int(maxdocs_select.value),
                        progress=_progress,
                    ),
                )
                state["run"] = run
                _render(run)
                results_card.classes(remove="hidden")
                if run.documents:
                    ui.notify("리서치 완료!", type="positive")
                    # 선택된 매장이 있으면 인사이트를 저장 → 기획(전략·소식글)이 자동 반영
                    pid = nicegui_app.storage.user.get("current_project_id")
                    if pid and getattr(run, "insight", None):
                        from app.research.saved_research import save_research_insight
                        if save_research_insight(pid, run.insight, run.keyword):
                            ui.notify("이 리서치를 기획에 자동 반영할게요.", type="info")
                else:
                    ui.notify("수집된 본문이 없어요. 소스나 키워드를 바꿔 보세요.", type="warning")
            except Exception:  # noqa: BLE001
                _log.exception("Research failed")
                ui.notify("리서치 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.",
                          type="negative", timeout=8000)
            finally:
                progress_row.classes("hidden")
                run_btn.props(remove="disabled")

        def _render_ads(observations: list) -> None:
            ads_body.clear()
            engine_labels = {"GOOGLE": "구글 검색광고", "NAVER": "네이버", "META": "메타"}
            engine_colors = {"GOOGLE": "#4285F4", "NAVER": "#03C75A", "META": "#0866FF"}
            with ads_body:
                if not observations:
                    with ui.element("div").classes("dg-banner dg-banner-warning w-full"):
                        ui.icon("warning", size="18px")
                        ui.label(
                            "관측된 광고가 없어요. 키워드에 광고가 안 붙었거나, 페이지 구조가 "
                            "바뀌었거나, 봇 차단일 수 있어요. 키워드를 바꿔 보세요."
                        )
                    return
                with ui.element("div").classes("dg-banner dg-banner-success w-full"):
                    ui.icon("check_circle", size="18px")
                    ui.label(f"경쟁 광고 {len(observations)}건 관측 — 점수 높은 순으로 정렬했어요.")
                ordered = sorted(observations, key=lambda o: o.heuristic_score, reverse=True)
                for ob in ordered:
                    color = engine_colors.get(ob.engine, "#888")
                    with ui.card().classes("w-full").style(f"border-left:4px solid {color}"):
                        with ui.row().classes("items-center gap-2 w-full"):
                            ui.label(engine_labels.get(ob.engine, ob.engine)).style(
                                f"font-size:11px; font-weight:700; color:{color}; "
                                f"background:{color}1a; padding:1px 8px; border-radius:10px")
                            if ob.ad_type:
                                ui.label({"powerlink": "파워링크", "brand_search": "브랜드검색"}.get(
                                    ob.ad_type, ob.ad_type)).style(
                                    "font-size:10px; color: var(--dg-text-tertiary)")
                            ui.space()
                            ui.label(f"점수 {ob.heuristic_score:.0f}").style(
                                "font-size:11px; color: var(--dg-text-tertiary)")
                        ui.label(ob.headline).style("font-size:14px; font-weight:600")
                        if ob.description:
                            ui.label(ob.description).style(
                                "font-size:12px; color: var(--dg-text-secondary); line-height:1.5")
                        link = ob.landing_url or ob.display_url
                        if link:
                            ui.link(link[:80], link, new_tab=True).style(
                                "font-size:11px; color:" + color)

        async def _run_ads() -> None:
            keyword = (keyword_input.value or "").strip()
            if not keyword:
                ui.notify("키워드를 입력해 주세요.", type="warning")
                return
            from app.research.stealth import playwright_available
            if not playwright_available():
                ui.notify(
                    "경쟁 광고 관측엔 Playwright가 필요해요. 터미널에서 "
                    "'pip install playwright && playwright install chromium' 실행 후 다시 시도해 주세요.",
                    type="warning", timeout=10000)
                return

            ads_btn.props("disabled")
            progress_row.classes(remove="hidden")
            ads_card.classes("hidden")
            try:
                from app.research.pipeline import observe_ads
                loop = asyncio.get_running_loop()
                obs = await loop.run_in_executor(
                    None, lambda: observe_ads(keyword, progress=lambda m: progress_label.set_text(m)),
                )
                _render_ads(obs)
                ads_card.classes(remove="hidden")
                ui.notify(f"광고 관측 완료 — {len(obs)}건", type="positive")
            except Exception:  # noqa: BLE001
                _log.exception("Ad observation failed")
                ui.notify("광고 관측 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.",
                          type="negative", timeout=8000)
            finally:
                progress_row.classes("hidden")
                ads_btn.props(remove="disabled")

        run_btn.on_click(_run)
        ads_btn.on_click(_run_ads)
