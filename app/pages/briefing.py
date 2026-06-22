# -*- coding: utf-8 -*-
"""Screen: /briefing — AI 상담/브리핑.

행사·캠페인 내용을 붙여넣거나 파일(.txt/.docx, pypdf 있으면 .pdf)로 올리면
Claude Opus가 읽고 대화·분석한다. '이 내용으로 리서치/광고관측' 버튼으로
소재 키워드를 AI가 뽑아 /research(커뮤니티 리서치 + 경쟁광고 관측)로 연결한다.
"""
import asyncio

from nicegui import ui, app as nicegui_app

from app.common import create_nav, next_step_bar
from app.theme import section_header
from app.logger import get_logger
from app.ai.providers import get_provider
from app.research.briefing import (
    extract_text, build_chat_prompt, extract_keywords,
    SYSTEM_GUIDE_BRIEFING, BriefingUnsupported,
)

_log = get_logger("briefing")


@ui.page("/briefing")
def briefing_page() -> None:
    create_nav("/briefing")

    state: dict = {"messages": []}  # [(role, text)] role: 'user' | 'ai'

    with ui.column().classes("dg-page-content w-full gap-5"):
        next_step_bar("/briefing")
        ui.label("AI 상담 / 브리핑").classes("dg-page-title")
        ui.label(
            "행사·캠페인 내용을 붙여넣거나 파일로 올리면 Claude가 읽고 같이 정리해요. "
            "정리되면 '이 내용으로 리서치'로 실제 고객 반응·경쟁 광고까지 이어가요."
        ).classes("dg-page-subtitle")

        # ── 입력: 파일 업로드 + 붙여넣기 ──
        with ui.card().classes("dg-card w-full"):
            section_header("description", "행사/캠페인 내용", "붙여넣거나 파일(.txt·.docx)을 올려 주세요.")

            brief_input = ui.textarea(
                label="내용", placeholder="여기에 행사 내용을 붙여넣거나, 아래에서 파일을 올리면 자동으로 채워져요.",
            ).classes("w-full dg-input").props("outlined autogrow")

            async def _on_upload(e) -> None:
                name = e.name
                data = e.content.read()
                ui.notify(f"'{name}' 읽는 중...", type="info")
                try:
                    loop = asyncio.get_running_loop()
                    # docx/pdf/이미지(비전 API)는 느릴 수 있어 executor에서.
                    text = await loop.run_in_executor(None, lambda: extract_text(name, data))
                except BriefingUnsupported as ex:
                    ui.notify(str(ex), type="warning", timeout=8000)
                    return
                except Exception:  # noqa: BLE001
                    _log.exception("파일 읽기 실패")
                    ui.notify("파일을 읽지 못했어요. 내용을 붙여넣어 주세요.", type="negative")
                    return
                if not text.strip():
                    ui.notify("파일에서 글자를 못 찾았어요. 내용을 붙여넣어 주세요.", type="warning")
                    return
                # 기존 내용에 이어 붙임(여러 파일/붙여넣기 혼용 대비).
                brief_input.value = (brief_input.value + "\n\n" + text).strip() if brief_input.value else text
                ui.notify(f"'{name}'에서 {len(text):,}자 불러왔어요.", type="positive")

            ui.upload(on_upload=_on_upload, auto_upload=True, max_files=1).props(
                'accept=".txt,.md,.csv,.docx,.pdf,.png,.jpg,.jpeg,.webp" flat'
            ).classes("w-full dg-uploader")
            ui.label(
                ".txt·.docx·PDF·이미지(포스터/전단) 지원. 이미지는 Claude가 글자를 읽어와요(몇 초 걸려요)."
            ).classes("dg-label-sm")

        # ── 대화 ──
        with ui.card().classes("dg-card w-full"):
            section_header("forum", "AI와 정리하기", "내용을 읽은 Claude와 대화하며 광고 방향을 잡아요.")
            chat_col = ui.column().classes("w-full gap-2")
            with chat_col:
                _empty = ui.label("내용을 넣고 아래에 물어보세요. 예: '이 행사 광고로 어떻게 풀지?'").classes("dg-label-sm")

            progress_row = ui.row().classes("items-center gap-2 hidden")
            with progress_row:
                ui.spinner("dots", size="sm")
                ui.label("Claude가 읽고 답하는 중...").classes("dg-progress-text")

            with ui.row().classes("w-full gap-2 items-end no-wrap"):
                msg_input = ui.textarea(
                    placeholder="질문하거나 '광고 관점에서 정리해줘'라고 해보세요.",
                ).classes("flex-1 dg-input").props("outlined autogrow")
                send_btn = ui.button("보내기", icon="send").classes("dg-btn-primary")

        # ── 다음으로: 리서치/광고관측 (여기서 바로 보거나 리서치 화면으로) ──
        with ui.card().classes("dg-card w-full"):
            section_header("travel_explore", "이 내용으로 리서치 + 경쟁광고 관측",
                           "AI가 소재 키워드를 뽑아 실제 고객 반응·경쟁 광고를 분석해요.")
            with ui.row().classes("gap-2 flex-wrap"):
                analyze_btn = ui.button("여기서 바로 분석 (리서치+광고관측)", icon="insights").classes("dg-btn-primary")
                to_research_btn = ui.button("리서치 화면에서 보기", icon="open_in_new").classes("dg-btn-secondary")
            ui.label("커뮤니티 검색 + 3엔진 광고관측이라 1~3분 걸려요. 결과는 현재 매장 리서치로도 저장돼요.").classes("dg-label-sm")
            analyze_progress = ui.row().classes("items-center gap-2 hidden")
            with analyze_progress:
                ui.spinner("dots", size="sm")
                analyze_label = ui.label("분석 중...").classes("dg-progress-text")
            analyze_results = ui.column().classes("w-full gap-3")

        # ───────── handlers ─────────

        def _add_msg(role: str, text: str) -> None:
            state["messages"].append((role, text))
            _empty.set_visibility(False)
            with chat_col:
                me = role == "user"
                with ui.element("div").classes("w-full").style(
                    "display:flex; justify-content:" + ("flex-end" if me else "flex-start")
                ):
                    bubble = ui.element("div").style(
                        "max-width:80%; padding:10px 14px; border-radius:12px; white-space:pre-wrap; "
                        "line-height:1.6; font-size:14px; "
                        + ("background:var(--dg-primary); color:#fff;"
                           if me else "background:var(--dg-surface-2,#f1f3f7); color:var(--dg-text-primary);")
                    )
                    with bubble:
                        ui.markdown(text) if not me else ui.label(text)

        async def _send() -> None:
            user_msg = (msg_input.value or "").strip()
            brief = (brief_input.value or "").strip()
            if not user_msg and not brief:
                ui.notify("내용을 넣거나 질문을 입력해 주세요.", type="warning")
                return
            if not user_msg:
                user_msg = "이 내용을 광고 관점에서 정리해 줘."
            _add_msg("user", user_msg)
            msg_input.value = ""
            history = state["messages"][:-1]  # 방금 추가한 user 제외
            send_btn.props("disabled loading")
            progress_row.classes(remove="hidden")
            try:
                prompt = build_chat_prompt(brief, history, user_msg)
                loop = asyncio.get_running_loop()
                reply = await loop.run_in_executor(
                    None,
                    lambda: get_provider("claude").generate_text(prompt, system_prompt=SYSTEM_GUIDE_BRIEFING),
                )
                _add_msg("ai", (reply or "").strip() or "(응답이 비었어요. 다시 시도해 주세요.)")
            except Exception:  # noqa: BLE001
                _log.exception("briefing chat failed")
                ui.notify("답변 생성 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.", type="negative", timeout=8000)
            finally:
                progress_row.classes("hidden")
                send_btn.props(remove="disabled loading")

        async def _to_research() -> None:
            brief = (brief_input.value or "").strip()
            if not brief:
                ui.notify("먼저 행사 내용을 넣어 주세요.", type="warning")
                return
            to_research_btn.props("disabled loading")
            try:
                loop = asyncio.get_running_loop()
                kws = await loop.run_in_executor(
                    None,
                    lambda: extract_keywords(
                        brief, lambda p, system_prompt=None: get_provider("claude").generate_text(p, system_prompt=system_prompt)
                    ),
                )
                if not kws:
                    ui.notify("키워드를 못 뽑았어요. 내용을 더 구체적으로 넣거나 /research에서 직접 입력해 주세요.",
                              type="warning", timeout=8000)
                    return
                # /research가 프리필로 쓰도록 저장 후 이동(뒤로 안 가게 바로 앞으로).
                nicegui_app.storage.user["briefing_keywords"] = kws
                ui.notify("키워드: " + " / ".join(kws) + " — 리서치 화면으로 가요.", type="positive")
                ui.navigate.to("/research")
            except Exception:  # noqa: BLE001
                _log.exception("keyword extraction failed")
                ui.notify("키워드 추출 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.", type="negative", timeout=8000)
            finally:
                to_research_btn.props(remove="disabled loading")

        def _render_analysis(kws: list, run, ads: list) -> None:
            from app.research.insight import format_research_insight
            analyze_results.clear()
            with analyze_results:
                ui.label("뽑은 키워드: " + " / ".join(kws)).classes("dg-label-sm")
                # 커뮤니티 리서치
                with ui.card().classes("w-full").style("border-left:4px solid var(--dg-primary)"):
                    ui.label(f"커뮤니티 리서치 — 발견 {run.discovered} · 분석 {run.fetched}건").style(
                        "font-weight:700; font-size:14px")
                    summary = format_research_insight(getattr(run, "insight", {}) or {}, run.keyword)
                    if summary:
                        ui.markdown(summary).classes("w-full dg-prose")
                    else:
                        ui.label("수집된 고객 반응이 없어요. 키워드를 바꿔 보세요.").classes("dg-label-sm")
                # 경쟁 광고
                by = {"GOOGLE": 0, "NAVER": 0, "META": 0}
                for o in ads:
                    by[o.engine] = by.get(o.engine, 0) + 1
                with ui.card().classes("w-full").style("border-left:4px solid #03C75A"):
                    ui.label(
                        f"경쟁 광고 {len(ads)}건 — 네이버 {by['NAVER']} · 메타 {by['META']} · 구글 {by['GOOGLE']}"
                        + ("  (구글 0=봇차단, 정상)" if by["GOOGLE"] == 0 else "")
                    ).style("font-weight:700; font-size:14px")
                    for o in sorted(ads, key=lambda x: x.heuristic_score, reverse=True)[:15]:
                        with ui.row().classes("items-start gap-2 w-full no-wrap"):
                            ui.label({"GOOGLE": "구글", "NAVER": "네이버", "META": "메타"}.get(o.engine, o.engine)).style(
                                "font-size:11px; font-weight:700; color:var(--dg-primary); min-width:34px")
                            ui.label(o.headline).style("font-size:13px; line-height:1.5")

        async def _analyze_here() -> None:
            brief = (brief_input.value or "").strip()
            if not brief:
                ui.notify("먼저 행사 내용을 넣어 주세요.", type="warning")
                return
            analyze_btn.props("disabled loading")
            analyze_progress.classes(remove="hidden")
            analyze_results.clear()
            try:
                loop = asyncio.get_running_loop()

                def gen(p, system_prompt=None):
                    return get_provider("claude").generate_text(p, system_prompt=system_prompt)

                analyze_label.set_text("소재 키워드 뽑는 중...")
                kws = await loop.run_in_executor(None, lambda: extract_keywords(brief, gen))
                if not kws:
                    ui.notify("키워드를 못 뽑았어요. 내용을 더 구체적으로 넣어 주세요.", type="warning", timeout=8000)
                    return
                from app.research.pipeline import run_research, observe_ads
                from app.research.sources import DEFAULT_SOURCE_IDS
                run = await loop.run_in_executor(
                    None,
                    lambda: run_research(kws, list(DEFAULT_SOURCE_IDS), gen,
                                         period_months=3, max_docs=12,
                                         progress=lambda m: analyze_label.set_text(m)),
                )
                analyze_label.set_text("경쟁 광고 관측 중... (1~2분)")
                ads = await loop.run_in_executor(
                    None,
                    lambda: observe_ads(kws[:5], progress=lambda m: analyze_label.set_text(m)),
                )
                _render_analysis(kws, run, ads)
                # 현재 매장에 리서치 저장 → 기획이 자동 반영.
                pid = nicegui_app.storage.user.get("current_project_id")
                if pid and getattr(run, "insight", None):
                    from app.research.saved_research import save_research_insight
                    save_research_insight(pid, run.insight, run.keyword)
                ui.notify("분석 완료!", type="positive")
            except Exception:  # noqa: BLE001
                _log.exception("inline analyze failed")
                ui.notify("분석 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.", type="negative", timeout=8000)
            finally:
                analyze_btn.props(remove="disabled loading")
                analyze_progress.classes("hidden")

        send_btn.on_click(_send)
        to_research_btn.on_click(_to_research)
        analyze_btn.on_click(_analyze_here)
