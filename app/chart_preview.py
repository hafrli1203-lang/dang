"""Chart generation for preview (DOCX export lives in app.reporting.docx_report)."""
from pathlib import Path
from typing import List, Dict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm


# ── Korean font setup ────────────────────────────────────────────────────────

def _best_korean_font() -> str:
    candidates = ["Malgun Gothic", "맑은 고딕", "NanumGothic", "AppleGothic", "DejaVu Sans"]
    available = {f.name for f in fm.fontManager.ttflist}
    for c in candidates:
        if c in available:
            return c
    return "sans-serif"

_KR_FONT = _best_korean_font()
plt.rcParams["font.family"] = _KR_FONT
plt.rcParams["axes.unicode_minus"] = False

_ORANGE = "#FF6F00"
_GREEN = "#4CAF50"
_BLUE = "#1E88E5"
_PURPLE = "#8E24AA"


# ── Charts ───────────────────────────────────────────────────────────────────

def make_charts(rows: List[Dict], output_dir: Path) -> List[Path]:
    if not rows:
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    charts = []

    labels = [r.get("period_label", f"기간{i+1}") for i, r in enumerate(rows)]
    costs = [r.get("cost", 0) for r in rows]
    clicks = [r.get("clicks", 0) for r in rows]
    inquiries = [r.get("inquiries", 0) for r in rows]
    impressions = [r.get("impressions", 0) for r in rows]

    # Chart 1 – 기간별 광고 비용
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(labels, costs, color=_ORANGE, alpha=0.85, edgecolor="white")
    ax.set_title("기간별 광고 비용", fontsize=14, fontweight="bold")
    ax.set_ylabel("비용 (원)")
    for i, v in enumerate(costs):
        ax.text(i, v + max(costs, default=1) * 0.01, f"{v:,}", ha="center", fontsize=8)
    ax.tick_params(axis="x", rotation=30)
    plt.tight_layout()
    p1 = output_dir / "chart_cost.png"
    fig.savefig(p1, dpi=150)
    plt.close(fig)
    charts.append(p1)

    # Chart 2 – 클릭 및 문의
    fig, ax = plt.subplots(figsize=(8, 4))
    x = range(len(labels))
    w = 0.35
    ax.bar([i - w / 2 for i in x], clicks, w, label="클릭", color=_GREEN, alpha=0.85)
    ax.bar([i + w / 2 for i in x], inquiries, w, label="문의", color=_BLUE, alpha=0.85)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=30)
    ax.set_title("기간별 클릭 및 문의", fontsize=14, fontweight="bold")
    ax.legend()
    plt.tight_layout()
    p2 = output_dir / "chart_clicks.png"
    fig.savefig(p2, dpi=150)
    plt.close(fig)
    charts.append(p2)

    # Chart 3 – CTR 추이 (노출이 있을 때만)
    if any(imp > 0 for imp in impressions):
        ctrs = [(c / i * 100 if i > 0 else 0) for c, i in zip(clicks, impressions)]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(labels, ctrs, marker="o", color=_PURPLE, linewidth=2.5)
        ax.fill_between(labels, ctrs, alpha=0.15, color=_PURPLE)
        ax.set_title("기간별 CTR 추이", fontsize=14, fontweight="bold")
        ax.set_ylabel("CTR (%)")
        ax.tick_params(axis="x", rotation=30)
        plt.tight_layout()
        p3 = output_dir / "chart_ctr.png"
        fig.savefig(p3, dpi=150)
        plt.close(fig)
        charts.append(p3)

    return charts
