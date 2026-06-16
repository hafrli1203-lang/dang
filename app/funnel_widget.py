# -*- coding: utf-8 -*-
"""공용 퍼널 시각 — 성과보고서/고급분석이 동일한 그림을 쓰도록 한 곳에 모음.

원칙(있는 것만 솔직히): 노출·클릭은 어떤 양식에서도 측정되므로 항상 표시하고,
전환(문의·단골·쿠폰/행동)은 **실제로 측정된 단계만** 그린다. 측정 안 됐으면
사다리꼴에서 빼고 '데이터 없음' 안내문을 단다(가짜 0 단계 금지).
"""
from __future__ import annotations

from typing import Sequence

from nicegui import ui

# 단계별 색 램프 (테라코타). 최대 5단계(노출·클릭·문의·단골·쿠폰).
_STAGE_COLORS = ["#FBEDE0", "#F6D9BE", "#F0C19A", "#E9A977", "#E08F55"]

FULL_METRICS = frozenset({"impressions", "clicks", "inquiries", "regulars", "coupons"})

# 전환 단계 스펙: (metrics_available 키, 라벨, 단가 라벨)
_CONVERSION_SPECS = (
    ("inquiries", "문의", "1건당"),
    ("regulars", "단골", "1명당"),
    ("coupons", "쿠폰", "1건당"),
)


def _shape_sizes(n: int) -> list[float]:
    """단계 수에 맞춰 사다리꼴 시각 폭을 100→28로 균등 분배(값 비율 아님, 단계 표현)."""
    if n <= 1:
        return [100.0]
    return [100.0 - (100.0 - 28.0) * i / (n - 1) for i in range(n)]


def build_funnel_stages(
    *,
    impressions: int,
    clicks: int,
    ctr: float,
    cpc: float,
    cpm: float,
    conversions: dict,
    available,
    action_fallback: tuple | None = None,
) -> tuple[list[dict], bool]:
    """퍼널 단계 리스트와 has_conversion_data 플래그를 만든다.

    conversions: {"inquiries": (count, rate, cost_per), "regulars": (...), "coupons": (...)}
      rate는 '클릭 대비' 전환율(%), cost_per는 단가(원).
    available: 측정된 지표 집합. 전환 키가 여기 있을 때만 단계로 포함한다.
    action_fallback: (count, rate, cost_per) — 문의/단골/쿠폰 컬럼은 없지만 총행동만
      잡히는 레거시 양식에서 '행동' 한 단계로 폴백. 'actions'가 available에 있고
      구체 전환 단계가 하나도 안 잡힐 때만 사용된다.
    """
    avail = set(available)
    stages: list[dict] = [
        {"label": "노출", "count": impressions, "cost_per": cpm, "cost_label": "1천회당"},
        {"label": "클릭", "count": clicks, "rate_label": "노출 대비", "rate": ctr,
         "cost_per": cpc, "cost_label": "1회당"},
    ]
    shown = 0
    for key, label, cost_label in _CONVERSION_SPECS:
        if key not in avail:
            continue
        count, rate, cost_per = conversions.get(key, (0, 0.0, 0.0))
        stages.append({
            "label": label, "count": count, "rate_label": "클릭 대비",
            "rate": rate, "cost_per": cost_per, "cost_label": cost_label,
        })
        shown += 1
    if shown == 0 and "actions" in avail and action_fallback and action_fallback[0] > 0:
        count, rate, cost_per = action_fallback
        stages.append({
            "label": "행동", "count": count, "rate_label": "클릭 대비",
            "rate": rate, "cost_per": cost_per, "cost_label": "1건당",
        })
        shown += 1
    return stages, shown > 0


def _funnel_echart_options(stages: Sequence[dict]) -> dict:
    sizes = _shape_sizes(len(stages))
    data = []
    for i, s in enumerate(stages):
        lines = [f"{s['label']}  {int(s['count']):,}"]
        if s.get("rate_label") is not None:
            lines.append(f"{s['rate_label']} {s.get('rate', 0):.1f}%")
        if s.get("cost_per", 0) > 0:
            lines.append(f"{s['cost_label']} ₩{s['cost_per']:,.0f}")
        data.append({
            "value": sizes[i],
            "name": "\n".join(lines),
            "itemStyle": {"color": _STAGE_COLORS[min(i, len(_STAGE_COLORS) - 1)]},
        })
    return {
        "series": [{
            "type": "funnel", "sort": "none", "gap": 6,
            "left": "8%", "width": "84%", "top": 8, "bottom": 8,
            "minSize": "24%", "maxSize": "100%",
            "label": {
                "show": True, "position": "inside",
                "fontSize": 13, "lineHeight": 19,
                "fontWeight": 600, "color": "#212124",
            },
            "labelLine": {"show": False},
            "itemStyle": {"borderColor": "#FFFFFF", "borderWidth": 2},
            "data": data,
        }],
    }


def _worst_dropoff(stages: Sequence[dict]) -> tuple[str, float] | None:
    """연속 단계 사이에서 가장 큰 이탈 구간을 (이름, 이탈%)로."""
    drops = []
    for a, b in zip(stages, stages[1:]):
        ca, cb = int(a["count"]), int(b["count"])
        if ca > 0 and cb >= 0:
            drops.append((f"{a['label']}→{b['label']}", (1 - cb / ca) * 100))
    if not drops:
        return None
    return max(drops, key=lambda x: x[1])


def render_funnel(container, stages: Sequence[dict], *, has_conversion_data: bool) -> None:
    """공용 렌더: ECharts 사다리꼴 퍼널 + (이탈 배너 | 데이터 없음 안내)."""
    container.clear()
    with container:
        ui.echart(_funnel_echart_options(stages)).classes("w-full").style("height: 380px")
        if not has_conversion_data:
            with ui.element("div").classes("dg-banner dg-banner-info w-full mt-3"):
                ui.icon("info", size="18px")
                ui.label(
                    "이 파일엔 전환(문의·단골·쿠폰) 데이터가 없어 노출→클릭까지만 "
                    "보여 드려요. 당근 내보내기에서 전환 항목을 추가하면 클릭 이후 "
                    "단계까지 분석할 수 있어요."
                )
            return
        worst = _worst_dropoff(stages)
        if worst:
            with ui.element("div").classes("dg-banner dg-banner-warning w-full mt-3"):
                ui.icon("warning", size="18px")
                ui.label(
                    f"최대 이탈 구간: {worst[0]} ({worst[1]:.1f}% 이탈) "
                    f"- 이 구간의 전환율을 개선하면 효과가 가장 커요."
                )
