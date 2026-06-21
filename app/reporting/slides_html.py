# -*- coding: utf-8 -*-
"""성과+세그먼트 통합 보고서를 '슬라이드'로 — 자체 완결 HTML 1파일.

문서(DOCX)가 글이 많아 보기 힘들다는 피드백 → 광고주에게 한 장씩 넘겨 보는
시각형 보고서. 브라우저에서 열고, Ctrl+P(가로)로 PDF 저장 가능. 설치 의존 없음(stdlib only).

build_slides_html()은 순수 함수(I/O 없음) — 이미 계산된 kpi/퍼널/인사이트만 받아 HTML 문자열을 반환한다.
"""
from __future__ import annotations

from html import escape
from typing import Optional


def _won(v) -> str:
    try:
        return f"{int(round(float(v))):,}원"
    except (TypeError, ValueError):
        return "-"


def _num(v) -> str:
    try:
        return f"{int(round(float(v))):,}"
    except (TypeError, ValueError):
        return "-"


def _pct(v) -> str:
    try:
        return f"{float(v):.1f}%"
    except (TypeError, ValueError):
        return "-"


def _slide(inner: str, *, cls: str = "") -> str:
    return f'<section class="slide {cls}">{inner}</section>'


def _kpi_card(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="kpi-sub">{escape(sub)}</div>' if sub else ""
    return (
        f'<div class="kpi"><div class="kpi-label">{escape(label)}</div>'
        f'<div class="kpi-value">{escape(value)}</div>{sub_html}</div>'
    )


def build_slides_html(
    meta: dict,
    kpi: dict,
    insights: dict,
    *,
    funnel_stages: Optional[list] = None,
    segment_rows: Optional[list] = None,
    generated_at: str = "",
) -> str:
    """통합 성과 보고서 슬라이드(HTML) 생성.

    meta: {name, campaign_name, region, period}
    kpi: calc_kpi() 결과
    insights: _parse_ai_insights() 결과(conclusion/next_actions/experiments/judgment/good/blocked)
    funnel_stages: build_funnel_stages()의 stages 리스트(옵션)
    segment_rows: [{"label","cost","cpa","verdict"}] 세그먼트 심화 요약(옵션)
    """
    meta = meta or {}
    kpi = kpi or {}
    insights = insights or {}
    name = escape(str(meta.get("name") or "광고 성과 보고서"))
    campaign = escape(str(meta.get("campaign_name") or ""))
    region = escape(str(meta.get("region") or ""))
    period = escape(str(meta.get("period") or ""))

    slides: list[str] = []

    # 1) 표지
    sub_bits = " · ".join(b for b in [campaign, region, period] if b)
    slides.append(_slide(
        f'<div class="cover"><div class="cover-tag">당근 광고 성과 보고서</div>'
        f'<h1>{name}</h1>'
        f'<div class="cover-sub">{sub_bits}</div>'
        f'<div class="cover-foot">{escape(generated_at)}</div></div>',
        cls="cover-slide",
    ))

    # 2) 핵심 지표
    cards = "".join([
        _kpi_card("총 광고비", _won(kpi.get("total_cost", 0))),
        _kpi_card("노출", _num(kpi.get("total_impressions", 0))),
        _kpi_card("클릭", _num(kpi.get("total_clicks", 0)), f"CTR {_pct(kpi.get('ctr', 0))} · CPC {_won(kpi.get('cpc', 0))}"),
        _kpi_card("문의", _num(kpi.get("total_inquiries", 0)), f"1건당 {_won(kpi.get('cpa', 0))}" if kpi.get("total_inquiries") else ""),
        _kpi_card("단골", _num(kpi.get("total_regulars", 0)), f"1명당 {_won(kpi.get('cpr', 0))}" if kpi.get("total_regulars") else ""),
        _kpi_card("쿠폰", _num(kpi.get("total_coupons", 0)), f"1건당 {_won(kpi.get('cp_coupon', 0))}" if kpi.get("total_coupons") else ""),
    ])
    slides.append(_slide(
        f'<h2>핵심 지표</h2><div class="kpi-grid">{cards}</div>',
    ))

    # 3) 퍼널
    if funnel_stages:
        steps = []
        for s in funnel_stages:
            rate = ""
            if s.get("rate_label") is not None:
                rate = f'<span class="fn-rate">{escape(str(s.get("rate_label","")))} {_pct(s.get("rate", 0))}</span>'
            cost = ""
            if s.get("cost_per", 0):
                cost = f'<span class="fn-cost">{escape(str(s.get("cost_label","")))} {_won(s.get("cost_per", 0))}</span>'
            steps.append(
                f'<div class="fn-step"><div class="fn-top"><span class="fn-name">{escape(str(s.get("label","")))}</span>'
                f'<span class="fn-count">{_num(s.get("count", 0))}</span></div>'
                f'<div class="fn-meta">{rate}{cost}</div></div>'
            )
        slides.append(_slide(
            f'<h2>광고 퍼널 — 노출에서 행동까지</h2><div class="funnel">{"".join(steps)}</div>',
        ))

    # 4) 한눈에 진단
    conclusion = escape(str(insights.get("conclusion") or "")).replace("\n", "<br>")
    good = escape(str(insights.get("good") or "")).replace("\n", "<br>")
    blocked = escape(str(insights.get("blocked") or "")).replace("\n", "<br>")
    if conclusion or good or blocked:
        diag = f'<div class="lead">{conclusion}</div>' if conclusion else ""
        cols = ""
        if good:
            cols += f'<div class="diag-col good"><div class="diag-h">잘 된 것</div><div>{good}</div></div>'
        if blocked:
            cols += f'<div class="diag-col bad"><div class="diag-h">막힌 것</div><div>{blocked}</div></div>'
        if cols:
            diag += f'<div class="diag-grid">{cols}</div>'
        slides.append(_slide(f'<h2>한눈에 진단</h2>{diag}'))

    # 5) 세그먼트 심화(있으면)
    if segment_rows:
        rows_html = "".join(
            f'<tr><td>{escape(str(r.get("label","")))}</td>'
            f'<td>{_won(r.get("cost", 0))}</td>'
            f'<td>{_won(r.get("cpa", 0))}</td>'
            f'<td>{escape(str(r.get("verdict","")))}</td></tr>'
            for r in segment_rows
        )
        slides.append(_slide(
            '<h2>세그먼트 심화 — 어디에 집중할까</h2>'
            '<table class="tbl"><thead><tr><th>세그먼트</th><th>비용</th>'
            f'<th>행동당 비용</th><th>판정</th></tr></thead><tbody>{rows_html}</tbody></table>'
        ))

    # 6) 이렇게 하겠습니다 (액션)
    next_actions = [a for a in (insights.get("next_actions") or []) if str(a).strip()]
    experiments = insights.get("experiments") or []
    if next_actions or experiments:
        acts = ""
        if next_actions:
            items = "".join(
                f'<li><span class="anum">{i}</span><span>{escape(str(a))}</span></li>'
                for i, a in enumerate(next_actions, 1)
            )
            acts += f'<ol class="actions">{items}</ol>'
        if experiments:
            exp_rows = "".join(
                f'<tr><td>{escape(str(e.get("priority","-")))}</td>'
                f'<td>{escape(str(e.get("change","-")))}</td>'
                f'<td>{escape(str(e.get("success_criteria","-")))}</td>'
                f'<td>{escape(str(e.get("schedule","-")))}</td></tr>'
                for e in experiments
            )
            acts += (
                '<table class="tbl"><thead><tr><th>순위</th><th>변경 내용</th>'
                f'<th>성공 기준</th><th>일정</th></tr></thead><tbody>{exp_rows}</tbody></table>'
            )
        slides.append(_slide(f'<h2>다음 기간, 이렇게 하겠습니다</h2>{acts}', cls="action-slide"))

    # 7) 판단 기준
    j = insights.get("judgment") or {}
    if isinstance(j, dict) and (j.get("expand") or j.get("review") or j.get("stop")):
        jl = ""
        for key, label, cls in [("expand", "확대", "j-up"), ("review", "검토", "j-mid"), ("stop", "중단", "j-down")]:
            if j.get(key):
                jl += f'<div class="jcard {cls}"><div class="jh">{label}</div><div>{escape(str(j.get(key)))}</div></div>'
        slides.append(_slide(f'<h2>판단 기준</h2><div class="jgrid">{jl}</div>'))

    body = "\n".join(slides)
    return _HTML_SHELL.replace("{{TITLE}}", name).replace("{{BODY}}", body)


_HTML_SHELL = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}} — 성과 보고서</title>
<style>
  :root { --primary:#FF6F0F; --ink:#1A1A2E; --muted:#6B7280; --line:#E7E2DA; --bg:#F8F9FC; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { font-family:'Paperlogy','Malgun Gothic',system-ui,sans-serif; color:var(--ink); background:var(--bg); }
  .deck { scroll-snap-type:y mandatory; }
  .slide { min-height:100vh; padding:64px 72px; display:flex; flex-direction:column; justify-content:center;
           scroll-snap-align:start; border-bottom:1px solid var(--line); background:#fff; }
  h1 { font-size:54px; font-weight:800; letter-spacing:-1.5px; line-height:1.1; }
  h2 { font-size:34px; font-weight:800; letter-spacing:-1px; margin-bottom:28px;
       padding-left:16px; border-left:6px solid var(--primary); }
  .cover-slide { background:linear-gradient(135deg,#fff 0%,#FFF4EC 100%); }
  .cover-tag { display:inline-block; background:var(--primary); color:#fff; font-weight:700; font-size:14px;
               padding:6px 14px; border-radius:999px; margin-bottom:22px; }
  .cover-sub { font-size:20px; color:var(--muted); margin-top:18px; font-weight:600; }
  .cover-foot { font-size:13px; color:#9AA3B2; margin-top:40px; }
  .kpi-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:18px; }
  .kpi { background:var(--bg); border:1px solid var(--line); border-radius:16px; padding:24px 26px; border-top:3px solid var(--primary); }
  .kpi-label { font-size:14px; color:var(--muted); font-weight:600; }
  .kpi-value { font-size:40px; font-weight:800; letter-spacing:-1.5px; margin-top:6px; }
  .kpi-sub { font-size:13px; color:var(--muted); margin-top:6px; }
  .funnel { display:flex; flex-direction:column; gap:10px; }
  .fn-step { background:var(--bg); border:1px solid var(--line); border-left:6px solid var(--primary); border-radius:12px; padding:16px 22px; }
  .fn-top { display:flex; justify-content:space-between; align-items:baseline; }
  .fn-name { font-size:20px; font-weight:700; }
  .fn-count { font-size:28px; font-weight:800; letter-spacing:-1px; }
  .fn-meta { margin-top:4px; color:var(--muted); font-size:14px; display:flex; gap:18px; }
  .lead { font-size:22px; line-height:1.6; font-weight:600; margin-bottom:24px; }
  .diag-grid { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
  .diag-col { border-radius:14px; padding:22px; font-size:16px; line-height:1.6; }
  .diag-col.good { background:#EEF7F1; border:1px solid #BFE3CC; }
  .diag-col.bad { background:#FBEDE8; border:1px solid #F2C9B8; }
  .diag-h { font-weight:800; margin-bottom:8px; }
  .actions { list-style:none; display:flex; flex-direction:column; gap:12px; margin-bottom:24px; }
  .actions li { display:flex; gap:12px; align-items:flex-start; font-size:18px; line-height:1.5; }
  .anum { flex-shrink:0; width:28px; height:28px; border-radius:8px; background:var(--primary); color:#fff;
          font-weight:800; font-size:14px; display:flex; align-items:center; justify-content:center; margin-top:2px; }
  .tbl { width:100%; border-collapse:collapse; font-size:15px; }
  .tbl th { text-align:left; background:var(--bg); padding:12px 14px; border-bottom:2px solid var(--line); font-weight:700; }
  .tbl td { padding:12px 14px; border-bottom:1px solid var(--line); vertical-align:top; }
  .jgrid { display:grid; grid-template-columns:repeat(3,1fr); gap:18px; }
  .jcard { border-radius:14px; padding:22px; font-size:16px; line-height:1.5; border:1px solid var(--line); }
  .jcard .jh { font-weight:800; font-size:20px; margin-bottom:8px; }
  .j-up { background:#EEF7F1; } .j-up .jh { color:#2E7D52; }
  .j-mid { background:#FFF7EC; } .j-mid .jh { color:#B26A00; }
  .j-down { background:#FBEDE8; } .j-down .jh { color:#B0402A; }
  @media print {
    body { background:#fff; }
    @page { size:A4 landscape; margin:0; }
    .slide { min-height:100vh; page-break-after:always; border:none; }
  }
</style></head>
<body><div class="deck">
{{BODY}}
</div></body></html>"""
