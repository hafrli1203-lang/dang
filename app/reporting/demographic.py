"""Demographic analysis for Daangn ads.

Input contract: demographic breakdown rows from 당근 광고 관리자 내보내기.
Output: insights (최고효율/숨겨진기회/예산불균형), age groupings,
campaign judgments (유지/OFF/교체/증액), budget reallocation simulation,
variable control warnings, and auto/manual pairing checks.

This module contains pure logic (no I/O, no UI) so it can be unit-tested
independently of NiceGUI.

Based on operator playbook:
- 당근은 머신러닝 체감상 없음 → 연령/성별 직접 찢기
- 수동+자동 캠페인 동시 운영 (수동=성과, 자동=노출부스팅)
- 변수 통제 원칙: 캠페인 간 1개만 다르게
- 연령 그룹핑은 행동당비용 유사도 기준
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Sequence


# ───────────────────────── dataclasses ─────────────────────────


@dataclass(frozen=True)
class Segment:
    """One row of demographic breakdown (성별 또는 연령대)."""

    label: str  # "남성", "여성", "15-19", "20-24", ...
    cost: int
    actions: int  # 총행동 (문의+단골+쿠폰 합)
    impressions: int = 0
    clicks: int = 0

    @property
    def cpa(self) -> float:
        return self.cost / self.actions if self.actions > 0 else 0.0

    @property
    def ctr(self) -> float:
        return (self.clicks / self.impressions * 100) if self.impressions > 0 else 0.0


@dataclass(frozen=True)
class CampaignPerf:
    """One campaign's performance row."""

    name: str
    cost: int
    actions: int
    creative_count: int = 1
    impressions: int = 0
    clicks: int = 0
    # Optional metadata for variable control + auto/manual pairing:
    bid_mode: Literal["auto", "manual", "unknown"] = "unknown"
    age_range: str = ""  # "20-29" etc.
    creative_id: str = ""

    @property
    def cpa(self) -> float:
        return self.cost / self.actions if self.actions > 0 else 0.0

    @property
    def ctr(self) -> float:
        return (self.clicks / self.impressions * 100) if self.impressions > 0 else 0.0

    @property
    def cost_share(self) -> float:
        # Filled in by analyze_campaigns() since it requires total
        return 0.0


@dataclass(frozen=True)
class Insight:
    kind: Literal["best_efficiency", "hidden_opportunity", "budget_imbalance"]
    label: str
    message: str
    numbers: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class AgeGroup:
    """A cluster of age segments with similar CPA."""

    members: tuple[str, ...]  # e.g. ("40-44", "55-59")
    avg_cpa: float
    total_cost: int
    total_actions: int


@dataclass(frozen=True)
class CampaignJudgment:
    campaign: CampaignPerf
    verdict: Literal["유지", "소재정리후유지", "소재전면교체", "캠페인OFF", "증액"]
    reason: str
    cost_share: float  # percent 0~100


@dataclass(frozen=True)
class ReallocationPlan:
    current_total: int
    projected_total: int  # after OFF/cuts
    savings: int
    expected_action_delta: int  # estimated +N inquiries from reallocation
    cuts: tuple[tuple[str, int], ...]  # (campaign_name, cut_amount)
    boosts: tuple[tuple[str, int], ...]  # (campaign_name, boost_amount)


@dataclass(frozen=True)
class VariableControlWarning:
    campaign_a: str
    campaign_b: str
    diff_count: int
    diffs: tuple[str, ...]  # names of differing attributes


@dataclass(frozen=True)
class PairingGap:
    campaign: str
    missing_counterpart: Literal["auto", "manual"]


# ───────────────────────── demographic analysis ─────────────────────────


def analyze_segments(segments: Sequence[Segment]) -> list[Insight]:
    """Produce insights for a set of demographic segments (either 성별 or 연령).

    Rules:
    - best_efficiency: lowest CPA AND CTR ≥ average
    - hidden_opportunity: CPA below median but cost share < 5%
    - budget_imbalance: cost share > average AND CPA above median
    """
    active = [s for s in segments if s.actions > 0 and s.cost > 0]
    if not active:
        return []

    total_cost = sum(s.cost for s in active)
    if total_cost <= 0:
        return []

    cpas = sorted(s.cpa for s in active)
    median_cpa = cpas[len(cpas) // 2]
    avg_ctr = sum(s.ctr for s in active) / len(active) if active else 0.0

    insights: list[Insight] = []

    best = min(active, key=lambda s: s.cpa)
    if best.ctr >= avg_ctr:
        insights.append(
            Insight(
                kind="best_efficiency",
                label=best.label,
                message=f"최고 효율 {best.label} (행동당비용 {int(best.cpa):,}원, CTR {best.ctr:.2f}%)",
                numbers={"cpa": best.cpa, "ctr": best.ctr},
            )
        )

    for s in active:
        share_pct = s.cost / total_cost * 100
        if s.cpa <= median_cpa and share_pct < 5.0:
            insights.append(
                Insight(
                    kind="hidden_opportunity",
                    label=s.label,
                    message=f"숨겨진 기회: {s.label} (행동당비용 {int(s.cpa):,}원이나 비용비중 {share_pct:.1f}%로 낮음)",
                    numbers={"cpa": s.cpa, "cost_share": share_pct},
                )
            )

    avg_share = 100.0 / len(active)
    for s in active:
        share_pct = s.cost / total_cost * 100
        if share_pct > avg_share and s.cpa > median_cpa:
            insights.append(
                Insight(
                    kind="budget_imbalance",
                    label=s.label,
                    message=f"예산 불균형: {s.label} (비용비중 {share_pct:.1f}%인데 행동당비용 {int(s.cpa):,}원으로 비효율)",
                    numbers={"cpa": s.cpa, "cost_share": share_pct},
                )
            )

    return insights


# ───────────────────────── age grouping ─────────────────────────


def group_ages_by_cpa(
    age_segments: Sequence[Segment],
    n_groups: int = 3,
) -> list[AgeGroup]:
    """Cluster age segments by CPA similarity using 1D k-means.

    Returns groups sorted by avg_cpa ascending (가장 효율 좋은 묶음이 첫번째).
    n_groups must be 2~5. Segments with 0 actions are placed in a catch-all
    group at the end (cpa=inf, recommend OFF).
    """
    if n_groups < 2:
        n_groups = 2
    if n_groups > 5:
        n_groups = 5

    active = [s for s in age_segments if s.actions > 0]
    inactive = [s for s in age_segments if s.actions == 0 and s.cost > 0]

    groups: list[AgeGroup] = []

    if active:
        n = min(n_groups, len(active))
        clusters = _kmeans_1d([s.cpa for s in active], n)

        for cluster_indices in clusters:
            members = tuple(active[i].label for i in cluster_indices)
            total_cost = sum(active[i].cost for i in cluster_indices)
            total_actions = sum(active[i].actions for i in cluster_indices)
            avg_cpa = total_cost / total_actions if total_actions > 0 else 0.0
            groups.append(
                AgeGroup(
                    members=members,
                    avg_cpa=avg_cpa,
                    total_cost=total_cost,
                    total_actions=total_actions,
                )
            )

        groups.sort(key=lambda g: g.avg_cpa)

    if inactive:
        members = tuple(s.label for s in inactive)
        total_cost = sum(s.cost for s in inactive)
        groups.append(
            AgeGroup(
                members=members,
                avg_cpa=float("inf"),
                total_cost=total_cost,
                total_actions=0,
            )
        )

    return groups


def _kmeans_1d(values: list[float], k: int, max_iter: int = 50) -> list[list[int]]:
    """Simple 1D k-means. Returns list of index-lists (clusters)."""
    if not values or k <= 0:
        return []

    k = min(k, len(values))
    sorted_idx = sorted(range(len(values)), key=lambda i: values[i])

    # Initialize centroids evenly across sorted values
    step = max(1, len(values) // k)
    centroids = [values[sorted_idx[min(i * step, len(values) - 1)]] for i in range(k)]

    assignments = [0] * len(values)
    for _ in range(max_iter):
        changed = False
        for i, v in enumerate(values):
            best = min(range(k), key=lambda c: abs(v - centroids[c]))
            if assignments[i] != best:
                assignments[i] = best
                changed = True

        new_centroids = []
        for c in range(k):
            members = [values[i] for i in range(len(values)) if assignments[i] == c]
            new_centroids.append(sum(members) / len(members) if members else centroids[c])

        if not changed:
            break
        centroids = new_centroids

    clusters: list[list[int]] = [[] for _ in range(k)]
    for i, a in enumerate(assignments):
        clusters[a].append(i)
    return [c for c in clusters if c]


# ───────────────────────── campaign judgment ─────────────────────────


def judge_campaigns(
    campaigns: Sequence[CampaignPerf],
    *,
    min_actions: int = 10,
    cpa_replace_multiplier: float = 1.5,
    cost_share_high: float = 20.0,
    cost_share_low: float = 5.0,
    boost_cpa_multiplier: float = 0.6,
) -> list[CampaignJudgment]:
    """Judge each campaign using action count × CPA × cost share.

    Priority order (first match wins):
    1. actions < min_actions + spent significant → 캠페인OFF (dead campaign)
    2. CPA > avg_cpa × cpa_replace_multiplier → 소재전면교체 (creative problem)
    3. share ≥ cost_share_high AND CPA ≤ avg_cpa → 소재정리후유지 (주력 유지)
    4. CPA < avg_cpa × boost_cpa_multiplier AND share < cost_share_low → 증액 (hidden gem)
    5. else → 유지 (normal range)
    """
    active = [c for c in campaigns if c.cost > 0]
    if not active:
        return []

    total_cost = sum(c.cost for c in active)
    total_actions = sum(c.actions for c in active)
    avg_cpa = total_cost / total_actions if total_actions > 0 else 0.0

    judgments: list[CampaignJudgment] = []
    for c in active:
        share = c.cost / total_cost * 100
        verdict: str
        reason: str

        if c.actions == 0:
            verdict = "캠페인OFF"
            reason = f"행동 0건 ({c.cost:,}원 소진, 즉시 중단 권장)"
        elif c.actions < min_actions:
            verdict = "캠페인OFF"
            reason = f"행동 {c.actions}건 (기준 {min_actions}건 미만, CPA {int(c.cpa):,}원 비효율)"
        elif avg_cpa > 0 and c.cpa > avg_cpa * cpa_replace_multiplier:
            verdict = "소재전면교체"
            reason = f"CPA {int(c.cpa):,}원 (평균 {int(avg_cpa):,}원 대비 {c.cpa/avg_cpa:.1f}배 높음)"
        elif share >= cost_share_high and (avg_cpa == 0 or c.cpa <= avg_cpa):
            verdict = "소재정리후유지"
            reason = f"비중 {share:.1f}% + CPA {int(c.cpa):,}원 (평균 이하, 주력 유지)"
        elif avg_cpa > 0 and c.cpa < avg_cpa * boost_cpa_multiplier and share < cost_share_low:
            verdict = "증액"
            reason = f"CPA {int(c.cpa):,}원 (평균 {int(avg_cpa):,}원 대비 우수)인데 비중 {share:.1f}%로 작음"
        else:
            verdict = "유지"
            reason = f"평균 범위 (CPA {int(c.cpa):,}원, 비중 {share:.1f}%)"

        judgments.append(
            CampaignJudgment(
                campaign=c,
                verdict=verdict,  # type: ignore[arg-type]
                reason=reason,
                cost_share=share,
            )
        )

    return judgments


# ───────────────────────── budget reallocation ─────────────────────────


def simulate_reallocation(judgments: Sequence[CampaignJudgment]) -> ReallocationPlan:
    """Build a reallocation plan based on judgments.

    OFF: remove entire cost from budget.
    소재전면교체: cut 50% while testing new creatives.
    증액: double the budget (capped by total saved).
    Expected action delta is estimated with each boosted campaign's current CPA.
    """
    current_total = sum(j.campaign.cost for j in judgments)

    cuts: list[tuple[str, int]] = []
    boost_candidates: list[tuple[CampaignJudgment, int]] = []  # (judgment, desired_boost)

    for j in judgments:
        if j.verdict == "캠페인OFF":
            cuts.append((j.campaign.name, j.campaign.cost))
        elif j.verdict == "소재전면교체":
            cuts.append((j.campaign.name, j.campaign.cost // 2))
        elif j.verdict == "증액":
            boost_candidates.append((j, j.campaign.cost))  # double = +current

    total_savings = sum(amt for _, amt in cuts)
    total_boost_desired = sum(amt for _, amt in boost_candidates)

    boosts: list[tuple[str, int]] = []
    expected_delta = 0

    if total_boost_desired > 0 and total_savings > 0:
        ratio = min(1.0, total_savings / total_boost_desired)
        for j, desired in boost_candidates:
            applied = int(desired * ratio)
            boosts.append((j.campaign.name, applied))
            if j.campaign.cpa > 0:
                expected_delta += int(applied / j.campaign.cpa)

    projected_total = current_total - total_savings + sum(amt for _, amt in boosts)

    return ReallocationPlan(
        current_total=current_total,
        projected_total=projected_total,
        savings=total_savings - sum(amt for _, amt in boosts),
        expected_action_delta=expected_delta,
        cuts=tuple(cuts),
        boosts=tuple(boosts),
    )


# ───────────────────────── execution priority ─────────────────────────


def build_priority_checklist(
    judgments: Sequence[CampaignJudgment],
) -> list[str]:
    """Deterministic execution order aligned with the reference image.

    1순위: 비효율 캠페인 축소/OFF
    2순위: 고효율 캠페인 증액
    3순위: 소재 정리 및 A/B 테스트
    4순위: 신규 소재/타겟 테스트
    """
    off = [j.campaign.name for j in judgments if j.verdict == "캠페인OFF"]
    boost = [j.campaign.name for j in judgments if j.verdict == "증액"]
    replace = [j.campaign.name for j in judgments if j.verdict == "소재전면교체"]
    keep = [j.campaign.name for j in judgments if j.verdict == "소재정리후유지"]

    items: list[str] = []
    if off:
        items.append(f"1순위 — 비효율 캠페인 축소/OFF: {', '.join(off)}")
    if boost:
        items.append(f"2순위 — 고효율 캠페인 예산 확대: {', '.join(boost)}")
    if replace or keep:
        targets = replace + keep
        items.append(f"3순위 — 소재 정리 및 A/B 테스트: {', '.join(targets)}")
    items.append("4순위 — 신규 소재/타겟 테스트 (연령 그룹별 신규 캠페인 투입)")
    return items


# ───────────────────────── variable control ─────────────────────────


def check_variable_control(
    campaigns: Sequence[CampaignPerf],
) -> list[VariableControlWarning]:
    """Detect campaigns that differ by >1 variable (bid_mode/age_range/creative_id).

    Operator rule: 비교 목적으로 운영되는 캠페인 쌍은 1개 변수만 달라야 한다.
    Compares pairs sharing at least one attribute (grouping key) and flags the
    rest that differ.
    """
    warnings: list[VariableControlWarning] = []
    campaigns = [c for c in campaigns if c.cost > 0]

    for i in range(len(campaigns)):
        for j in range(i + 1, len(campaigns)):
            a, b = campaigns[i], campaigns[j]
            diffs: list[str] = []
            if a.bid_mode != b.bid_mode and "unknown" not in (a.bid_mode, b.bid_mode):
                diffs.append("bid_mode(자동/수동)")
            if a.age_range != b.age_range and a.age_range and b.age_range:
                diffs.append("age_range(연령)")
            if a.creative_id != b.creative_id and a.creative_id and b.creative_id:
                diffs.append("creative_id(소재)")

            if len(diffs) >= 2:
                warnings.append(
                    VariableControlWarning(
                        campaign_a=a.name,
                        campaign_b=b.name,
                        diff_count=len(diffs),
                        diffs=tuple(diffs),
                    )
                )
    return warnings


# ───────────────────────── auto/manual pairing ─────────────────────────


def check_auto_manual_pairing(
    campaigns: Sequence[CampaignPerf],
) -> list[PairingGap]:
    """Verify each 수동 campaign has a 자동 twin (same age_range + creative_id).

    Operator rule: 수동+자동을 같은 조건으로 동시 운영해야 노출이 안정됨.
    """
    gaps: list[PairingGap] = []
    campaigns = [c for c in campaigns if c.cost > 0 and c.bid_mode in ("auto", "manual")]

    def _key(c: CampaignPerf) -> tuple[str, str]:
        return (c.age_range, c.creative_id)

    manual = {_key(c): c for c in campaigns if c.bid_mode == "manual"}
    auto = {_key(c): c for c in campaigns if c.bid_mode == "auto"}

    for key, c in manual.items():
        if key not in auto:
            gaps.append(PairingGap(campaign=c.name, missing_counterpart="auto"))
    for key, c in auto.items():
        if key not in manual:
            gaps.append(PairingGap(campaign=c.name, missing_counterpart="manual"))

    return gaps


# ───────────────────────── xlsx parser ─────────────────────────


def parse_demographic_xlsx(content: bytes) -> dict[str, list[Segment] | list[CampaignPerf]]:
    """Parse a 당근 광고 관리자 내보내기 xlsx.

    Auto-detects sheets by header row:
    - Sheet with '성별' column → gender segments
    - Sheet with '연령' or '연령대' column → age segments
    - Sheet with '캠페인' column → campaigns

    Returns a dict with keys "genders", "ages", "campaigns".
    Missing sheets return empty lists.
    """
    import io

    import openpyxl  # local import so tests can stub if needed

    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)

    result: dict[str, list] = {"genders": [], "ages": [], "campaigns": []}

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue

        header_idx = _find_header_row(rows)
        if header_idx < 0:
            continue
        header = [str(c or "").strip() for c in rows[header_idx]]

        kind = _detect_sheet_kind(header)
        if not kind:
            continue

        col_map = _map_demographic_columns(header, kind)
        if col_map.get("label") is None:
            continue

        for row in rows[header_idx + 1 :]:
            if not row or all(c is None or str(c).strip() == "" for c in row):
                continue

            label = _cell_str(row, col_map["label"])
            if not label or label in {"합계", "Total", "소계"}:
                continue

            cost = _cell_int(row, col_map.get("cost"))
            actions = _cell_int(row, col_map.get("actions"))
            impressions = _cell_int(row, col_map.get("impressions"))
            clicks = _cell_int(row, col_map.get("clicks"))

            if kind == "campaign":
                creatives = _cell_int(row, col_map.get("creative_count")) or 1
                bid_mode = _cell_str(row, col_map.get("bid_mode")).lower()
                if "자동" in bid_mode or "auto" in bid_mode:
                    bm = "auto"
                elif "수동" in bid_mode or "manual" in bid_mode:
                    bm = "manual"
                else:
                    bm = "unknown"
                result["campaigns"].append(
                    CampaignPerf(
                        name=label,
                        cost=cost,
                        actions=actions,
                        creative_count=creatives,
                        impressions=impressions,
                        clicks=clicks,
                        bid_mode=bm,
                        age_range=_cell_str(row, col_map.get("age_range")),
                        creative_id=_cell_str(row, col_map.get("creative_id")),
                    )
                )
            else:
                seg = Segment(
                    label=label,
                    cost=cost,
                    actions=actions,
                    impressions=impressions,
                    clicks=clicks,
                )
                result["genders" if kind == "gender" else "ages"].append(seg)

    return result


def _find_header_row(rows: list[tuple]) -> int:
    keywords = ("성별", "연령", "캠페인", "비용", "노출", "클릭", "행동")
    for idx, row in enumerate(rows[:15]):
        if not row:
            continue
        text = " ".join(str(c or "") for c in row)
        if sum(1 for kw in keywords if kw in text) >= 2:
            return idx
    return -1


def _detect_sheet_kind(header: list[str]) -> str | None:
    joined = " ".join(header)
    if "성별" in joined:
        return "gender"
    if "연령" in joined:
        return "age"
    if "캠페인" in joined:
        return "campaign"
    return None


def _map_demographic_columns(header: list[str], kind: str) -> dict[str, int | None]:
    m: dict[str, int | None] = {
        "label": None,
        "cost": None,
        "actions": None,
        "impressions": None,
        "clicks": None,
        "creative_count": None,
        "bid_mode": None,
        "age_range": None,
        "creative_id": None,
    }
    for idx, h in enumerate(header):
        normalized = h.replace(" ", "").replace("(원)", "").replace("(%)", "").replace("(회)", "")
        if m["label"] is None:
            if kind == "gender" and "성별" in normalized:
                m["label"] = idx
                continue
            if kind == "age" and ("연령" in normalized):
                m["label"] = idx
                continue
            if kind == "campaign" and ("캠페인" in normalized):
                m["label"] = idx
                continue
        if m["cost"] is None and ("비용" in normalized or "광고비" in normalized or "집행" in normalized):
            m["cost"] = idx
            continue
        if m["actions"] is None and ("총행동" in normalized or "행동수" in normalized or "문의" in normalized or "전환" in normalized):
            m["actions"] = idx
            continue
        if m["impressions"] is None and ("노출" in normalized):
            m["impressions"] = idx
            continue
        if m["clicks"] is None and ("클릭" in normalized):
            m["clicks"] = idx
            continue
        if m["creative_count"] is None and ("소재수" in normalized or "소재" == normalized):
            m["creative_count"] = idx
            continue
        if m["bid_mode"] is None and ("모드" in normalized or "자동수동" in normalized or "입찰" in normalized):
            m["bid_mode"] = idx
            continue
        if m["age_range"] is None and kind == "campaign" and "연령" in normalized:
            m["age_range"] = idx
            continue
        if m["creative_id"] is None and ("소재id" in normalized.lower() or "소재명" in normalized):
            m["creative_id"] = idx
    return m


def _cell_int(row: tuple, idx: int | None) -> int:
    if idx is None or idx >= len(row):
        return 0
    v = row[idx]
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    try:
        s = str(v).replace(",", "").replace("원", "").replace("%", "").strip()
        if not s or s in {"-", "nan"}:
            return 0
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def _cell_str(row: tuple, idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    v = row[idx]
    return "" if v is None else str(v).strip()
