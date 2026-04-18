"""Screen 4 — 고급 분석 (연령/성별 찢기 + 캠페인 판정 + 재배분 시뮬).

Based on operator playbook: 당근은 머신러닝이 없어서 연령·성별을 직접 찢어서
효율 낮은 구간을 꺼야 한다. 이 페이지는 xlsx 업로드 → 자동 판정 + 재배분 플랜
+ 실행 우선순위 체크리스트 + 변수 통제/수동자동 매칭 경고까지 한번에 출력한다.
"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from app.common import create_nav
from app.reporting.demographic import (
    AgeGroup,
    CampaignJudgment,
    CampaignPerf,
    Insight,
    PairingGap,
    ReallocationPlan,
    Segment,
    VariableControlWarning,
    analyze_segments,
    build_priority_checklist,
    check_auto_manual_pairing,
    check_variable_control,
    group_ages_by_cpa,
    judge_campaigns,
    parse_demographic_xlsx,
    simulate_reallocation,
)
from app.theme import section_header


_VERDICT_STYLES: dict[str, tuple[str, str]] = {
    "소재정리후유지": ("var(--dg-success)", "var(--dg-success-light)"),
    "유지": ("var(--dg-info)", "var(--dg-info-light)"),
    "소재전면교체": ("var(--dg-warning)", "var(--dg-warning-light)"),
    "캠페인OFF": ("var(--dg-error)", "var(--dg-error-light)"),
    "증액": ("var(--dg-primary)", "var(--dg-primary-light)"),
}


def _fmt_won(value: float | int) -> str:
    return f"{int(round(value)):,}원"


def _empty_state(container: ui.element) -> None:
    container.clear()
    with container:
        with ui.column().classes("w-full items-center gap-2 p-12 text-center"):
            ui.icon("insights", size="48px").style("color: var(--dg-text-caption)")
            ui.label("xlsx 파일을 업로드하면 분석 결과가 표시됩니다.").style(
                "color: var(--dg-text-tertiary); font-size: 14px"
            )
            ui.label("성별 / 연령대 / 캠페인 시트를 자동 감지합니다.").style(
                "color: var(--dg-text-caption); font-size: 12px"
            )


def _render_insights(container: ui.element, title: str, insights: list[Insight]) -> None:
    if not insights:
        return
    with container:
        ui.label(title).classes("dg-section-title mt-2")
        with ui.row().classes("w-full gap-3 flex-wrap"):
            for ins in insights:
                color, bg = (
                    ("var(--dg-success)", "var(--dg-success-light)")
                    if ins.kind == "best_efficiency"
                    else ("var(--dg-primary)", "var(--dg-primary-light)")
                    if ins.kind == "hidden_opportunity"
                    else ("var(--dg-error)", "var(--dg-error-light)")
                )
                with ui.card().style(
                    f"flex:1; min-width:260px; border-left:4px solid {color}; background:{bg}"
                ):
                    ui.label(
                        {
                            "best_efficiency": "최고 효율",
                            "hidden_opportunity": "숨겨진 기회",
                            "budget_imbalance": "예산 불균형",
                        }[ins.kind]
                    ).style(f"color:{color}; font-weight:700; font-size:12px")
                    ui.label(ins.message).style(
                        "color: var(--dg-text-primary); font-size:13px; line-height:1.5"
                    )


def _render_segment_table(container: ui.element, title: str, segments: list[Segment]) -> None:
    if not segments:
        return
    with container:
        ui.label(title).classes("dg-section-title mt-4")
        total_cost = sum(s.cost for s in segments) or 1
        rows = [
            {
                "구분": s.label,
                "비용": _fmt_won(s.cost),
                "비중(%)": f"{s.cost / total_cost * 100:.1f}",
                "총행동": f"{s.actions:,}",
                "행동당비용": _fmt_won(s.cpa) if s.actions else "-",
                "CTR(%)": f"{s.ctr:.2f}",
            }
            for s in segments
        ]
        columns = [
            {"name": k, "label": k, "field": k, "align": "right" if k != "구분" else "left"}
            for k in rows[0].keys()
        ]
        ui.table(columns=columns, rows=rows).classes("w-full dg-table").props("flat dense")


def _render_age_groups(container: ui.element, age_segments: list[Segment]) -> None:
    if not age_segments:
        return
    with container:
        ui.label("연령 그룹핑 추천 (행동당비용 유사도 기준)").classes("dg-section-title mt-4")
        group_count = {"value": 3}
        group_container = ui.column().classes("w-full gap-2")

        def _refresh() -> None:
            group_container.clear()
            groups = group_ages_by_cpa(age_segments, n_groups=group_count["value"])
            with group_container:
                ui.label(
                    f"→ 이 {len(groups)}개 묶음 각각을 **별도 캠페인**으로 찢어야 관리 가능해집니다. "
                    "수동+자동 같은 조건 쌍으로 운영하세요."
                ).style(
                    "color: var(--dg-text-secondary); font-size: 12px; padding: 4px 0"
                )
                for i, g in enumerate(groups):
                    accent = (
                        "var(--dg-success)"
                        if i == 0
                        else "var(--dg-primary)"
                        if g.avg_cpa != float("inf")
                        else "var(--dg-error)"
                    )
                    cpa_label = "OFF 권장" if g.avg_cpa == float("inf") else _fmt_won(g.avg_cpa)
                    with ui.card().style(f"border-left:4px solid {accent}"):
                        with ui.row().classes("w-full items-center justify-between"):
                            ui.label(
                                f"묶음 {i + 1} — {' / '.join(g.members)}"
                            ).style("font-weight:600; font-size:14px")
                            ui.label(f"평균 CPA {cpa_label}").style(
                                f"color:{accent}; font-weight:700"
                            )
                        ui.label(
                            f"비용 {_fmt_won(g.total_cost)} · 총행동 {g.total_actions:,}건"
                        ).style("color: var(--dg-text-tertiary); font-size:12px")

        with ui.row().classes("w-full items-center gap-3"):
            ui.label("묶음 수").style("color: var(--dg-text-secondary); font-size:13px")
            slider = ui.slider(min=2, max=5, value=3, step=1).classes("w-64").props("label-always")
            slider.bind_value(group_count, "value")
            slider.on_value_change(lambda _e: _refresh())

        _refresh()


def _render_judgments(
    container: ui.element, judgments: list[CampaignJudgment], plan: ReallocationPlan
) -> None:
    if not judgments:
        return
    with container:
        ui.label("캠페인별 판정").classes("dg-section-title mt-4")
        rows = [
            {
                "캠페인": j.campaign.name,
                "소재 수": j.campaign.creative_count,
                "비용": _fmt_won(j.campaign.cost),
                "비중(%)": f"{j.cost_share:.1f}",
                "총행동": f"{j.campaign.actions:,}",
                "행동당비용": _fmt_won(j.campaign.cpa) if j.campaign.actions else "-",
                "CTR(%)": f"{j.campaign.ctr:.2f}",
                "판정": j.verdict,
                "사유": j.reason,
            }
            for j in judgments
        ]
        columns = [
            {"name": k, "label": k, "field": k, "align": "left" if k in ("캠페인", "판정", "사유") else "right"}
            for k in rows[0].keys()
        ]
        table = ui.table(columns=columns, rows=rows).classes("w-full dg-table").props("flat dense")
        table.add_slot(
            "body-cell-판정",
            r"""
            <q-td :props="props">
              <q-badge :style="{background: $parent.verdictBg(props.value), color: $parent.verdictFg(props.value), padding: '4px 8px', fontWeight: 600}">{{ props.value }}</q-badge>
            </q-td>
            """,
        )

        # Budget reallocation summary
        ui.label("예산 재배분 시뮬레이션").classes("dg-section-title mt-4")
        with ui.card().classes("w-full").style("background: var(--dg-primary-50)"):
            with ui.row().classes("w-full gap-6"):
                with ui.column().classes("gap-1"):
                    ui.label("현재 총예산").style(
                        "font-size:11px; color: var(--dg-text-tertiary)"
                    )
                    ui.label(_fmt_won(plan.current_total)).style(
                        "font-size:18px; font-weight:700"
                    )
                with ui.column().classes("gap-1"):
                    ui.label("예상 절감액").style(
                        "font-size:11px; color: var(--dg-text-tertiary)"
                    )
                    ui.label(_fmt_won(plan.savings)).style(
                        "font-size:18px; font-weight:700; color: var(--dg-success)"
                    )
                with ui.column().classes("gap-1"):
                    ui.label("예상 행동 증가").style(
                        "font-size:11px; color: var(--dg-text-tertiary)"
                    )
                    ui.label(f"+{plan.expected_action_delta}건").style(
                        "font-size:18px; font-weight:700; color: var(--dg-primary)"
                    )
                with ui.column().classes("gap-1"):
                    ui.label("조정 후 총예산").style(
                        "font-size:11px; color: var(--dg-text-tertiary)"
                    )
                    ui.label(_fmt_won(plan.projected_total)).style(
                        "font-size:18px; font-weight:700"
                    )

            if plan.cuts:
                ui.separator().style("margin: 8px 0")
                with ui.column().classes("gap-1"):
                    ui.label("축소/OFF 대상").style(
                        "font-size:12px; font-weight:600; color: var(--dg-error)"
                    )
                    for name, amt in plan.cuts:
                        ui.label(f"  • {name}: {_fmt_won(amt)} 절감").style(
                            "font-size:13px; color: var(--dg-text-secondary)"
                        )
            if plan.boosts:
                with ui.column().classes("gap-1"):
                    ui.label("증액 대상").style(
                        "font-size:12px; font-weight:600; color: var(--dg-success)"
                    )
                    for name, amt in plan.boosts:
                        ui.label(f"  • {name}: +{_fmt_won(amt)}").style(
                            "font-size:13px; color: var(--dg-text-secondary)"
                        )


def _render_priority(container: ui.element, items: list[str]) -> None:
    if not items:
        return
    with container:
        ui.label("실행 우선순위").classes("dg-section-title mt-4")
        with ui.card().classes("w-full"):
            for item in items:
                ui.label(item).style(
                    "font-size:13px; color: var(--dg-text-primary); padding: 4px 0"
                )


def _render_warnings(
    container: ui.element,
    var_warnings: list[VariableControlWarning],
    pair_gaps: list[PairingGap],
) -> None:
    if not var_warnings and not pair_gaps:
        return
    with container:
        ui.label("운영 경고").classes("dg-section-title mt-4")

        if var_warnings:
            with ui.card().classes("w-full").style(
                "border-left:4px solid var(--dg-warning); background: var(--dg-warning-light)"
            ):
                ui.label("변수 통제 위반").style(
                    "font-weight:700; color: var(--dg-warning); font-size:13px"
                )
                ui.label(
                    "변수가 2개 이상 다른 캠페인 쌍은 원인 분석이 불가합니다. 1개 변수만 다르게 운영하세요."
                ).style("color: var(--dg-text-secondary); font-size:12px; margin-bottom:6px")
                for w in var_warnings:
                    ui.label(
                        f"  • {w.campaign_a} ↔ {w.campaign_b}: {', '.join(w.diffs)}"
                    ).style("font-size:13px; color: var(--dg-text-primary)")

        if pair_gaps:
            with ui.card().classes("w-full").style(
                "border-left:4px solid var(--dg-info); background: var(--dg-info-light)"
            ):
                ui.label("수동/자동 매칭 누락").style(
                    "font-weight:700; color: var(--dg-info); font-size:13px"
                )
                ui.label(
                    "수동 캠페인은 자동 캠페인과 동시 운영해야 노출이 안정됩니다 "
                    "(수동=성과 / 자동=노출 부스팅)."
                ).style("color: var(--dg-text-secondary); font-size:12px; margin-bottom:6px")
                for g in pair_gaps:
                    ui.label(
                        f"  • {g.campaign}: {g.missing_counterpart} 캠페인 쌍 없음"
                    ).style("font-size:13px; color: var(--dg-text-primary)")


@ui.page("/analysis")
def analysis_page() -> None:
    create_nav("/analysis")

    with ui.column().classes("dg-page-container"):
        section_header(
            "고급 분석 — 연령/성별 찢기",
            "당근 머신러닝 부재 환경에서 연령·성별 직접 최적화 + 캠페인 판정 + 재배분",
        )

        results = ui.column().classes("w-full gap-0")
        _empty_state(results)

        async def _on_upload(e: Any) -> None:
            content = e.content.read()
            try:
                parsed = parse_demographic_xlsx(content)
            except Exception as exc:  # noqa: BLE001
                ui.notify(f"파일을 읽지 못했습니다: {exc}", type="negative")
                return

            genders: list[Segment] = parsed["genders"]  # type: ignore[assignment]
            ages: list[Segment] = parsed["ages"]  # type: ignore[assignment]
            campaigns: list[CampaignPerf] = parsed["campaigns"]  # type: ignore[assignment]

            if not (genders or ages or campaigns):
                ui.notify("분석 가능한 시트를 찾지 못했습니다.", type="warning")
                return

            judgments = judge_campaigns(campaigns)
            plan = simulate_reallocation(judgments)
            priority = build_priority_checklist(judgments)
            var_warnings = check_variable_control(campaigns)
            pair_gaps = check_auto_manual_pairing(campaigns)

            results.clear()
            _render_segment_table(results, "성별 breakdown", genders)
            _render_insights(results, "성별 인사이트", analyze_segments(genders))
            _render_segment_table(results, "연령대 breakdown", ages)
            _render_insights(results, "연령 인사이트", analyze_segments(ages))
            _render_age_groups(results, ages)
            _render_judgments(results, judgments, plan)
            _render_priority(results, priority)
            _render_warnings(results, var_warnings, pair_gaps)

            ui.notify(
                f"분석 완료: 성별 {len(genders)}, 연령 {len(ages)}, 캠페인 {len(campaigns)}",
                type="positive",
            )

        ui.upload(
            label="당근 광고 관리자 xlsx 업로드 (성별/연령/캠페인 시트)",
            on_upload=_on_upload,
            auto_upload=True,
            max_file_size=10 * 1024 * 1024,
        ).classes("w-full").props("accept=.xlsx")
