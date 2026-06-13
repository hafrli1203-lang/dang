"""예산 기반 캠페인 설계 룰 엔진.

당근 광고 운영 원칙(자동/수동 동일 세팅 페어 + 연령 분리)을 예산 규모에 맞게
적용한다. 핵심: 예산이 작을수록 쪼개지 말고, 한 가설씩 순차 검증한다.

이 모듈은 AI를 호출하지 않는다. 모든 판단은 코드가 계산하고,
AI는 이 결과를 문장화할 때만 사용한다.

예산별 추천 구조:
- ~1.9만원/일: 단일 캠페인 1개 (신규=자동, 검증된 조합=수동)
- 2만원대/일: 핵심 연령대 1개에 자동+수동 페어
- 3~4만원대/일: 주력 페어 2개 + 실험 캠페인 1개
- 5~9만원대/일: 연령대 2개 자동+수동 페어
- 10만원/일 이상: 연령대 5개 자동+수동 풀 페어
"""
from dataclasses import dataclass, field
from typing import Literal

# 당근 캠페인 최소 일예산 (원)
MIN_CAMPAIGN_BUDGET = 10_000

# 1차 테스트 기본 연령대 (세분화)
DEFAULT_AGE_BANDS = ["10-19", "20-29", "30-39", "40-44", "45-54", "55-59", "60+"]

# 로컬 매장 간소화 기본 연령대
SIMPLE_AGE_BANDS = ["10-20대", "30대", "40대", "50대", "60대+"]

# 소액 시작용 넓은 타겟
BROAD_AGE_BAND = "20-59"

BidMode = Literal["자동", "수동"]


@dataclass
class CampaignRow:
    """세팅표 1행 = 캠페인 1개. 광고 관리자가 그대로 따라 만들 수 있어야 한다."""
    name: str
    purpose: str          # 역할 (성과 통제 / 노출 부스팅 / 실험)
    region: str
    gender: str
    age: str
    bid_mode: BidMode
    daily_budget: int
    creative: str = "소재01"
    note: str = ""


@dataclass
class BudgetPlan:
    daily_budget: int
    tier: str                       # single / pair / pair_plus_test / two_pairs / full_pairs
    mode_label: str
    campaigns: list[CampaignRow] = field(default_factory=list)
    principles: list[str] = field(default_factory=list)
    judgment_rules: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    feasibility_note: str = ""


def required_budget(
    n_age: int,
    n_gender: int = 1,
    n_bid: int = 2,
    n_creative: int = 1,
    min_budget: int = MIN_CAMPAIGN_BUDGET,
) -> int:
    """필요 예산 = 최소 예산 x 연령 x 성별 x 입찰방식 x 소재."""
    return min_budget * max(n_age, 1) * max(n_gender, 1) * max(n_bid, 1) * max(n_creative, 1)


def feasibility(
    daily_budget: int,
    n_age: int,
    n_gender: int = 1,
    n_bid: int = 2,
    n_creative: int = 1,
) -> dict:
    """원하는 구조가 현재 예산으로 가능한지 계산."""
    req = required_budget(n_age, n_gender, n_bid, n_creative)
    return {
        "required": req,
        "daily_budget": daily_budget,
        "feasible": daily_budget >= req,
        "shortfall": max(0, req - daily_budget),
    }


def make_campaign_name(
    region: str, gender: str, age: str, appeal: str, bid_mode: BidMode,
) -> str:
    """캠페인 네이밍: 지역_성별연령_소구_입찰방식."""
    g = "" if gender in ("전체", "") else gender
    return f"{region}_{g}{age}_{appeal}_{bid_mode}"


# ── 변수 통제 원칙 (모든 플랜 공통) ──────────────────────────────────────

_PAIR_PRINCIPLES = [
    "자동/수동 페어는 입찰 방식만 다르고 나머지(지역·성별·연령·소재·소식·쿠폰)는 전부 동일해야 해요. 자동-소재A / 수동-소재B는 비교가 깨져요.",
    "한 번에 1개 변수만 다르게 테스트해요. (연령을 볼지, 입찰을 볼지, 소재를 볼지 먼저 정하기)",
    "수동 캠페인은 성과(CPC) 통제 역할, 자동 캠페인은 노출 부스팅 역할이에요. 수동만 쓰면 노출이 들쭉날쭉하고, 자동만 쓰면 CPC가 비싸져요.",
    "당근은 머신러닝 보정이 사실상 없어요. 효율 나쁜 연령·성별은 보고서를 보고 직접 꺼야(OFF) 해요.",
    "연령대는 처음부터 다 쪼개지 말고, 보고서에서 문의당 비용이 비슷한 구간끼리 묶어서 운영해요.",
]


def judgment_rules(target_cpa: int | None = None) -> list[str]:
    """누적 광고비 기준 판단 규칙. 하루 데이터로 판단하지 않는다."""
    rules = [
        "누적 지출 3만원 미만: 판단 보류. CTR·클릭·단골·채팅 신호만 확인해요.",
        "누적 지출 3만~5만원: 소재·소식·쿠폰 문제를 1차 판단해요.",
        "누적 지출 5만원 이상 + 문의 0건: OFF 또는 소재 전면 교체 후보예요.",
        "CTR 낮음 + 전환 낮음 = 소재 문제 / CTR 높음 + 전환 낮음 = 소식·쿠폰·오퍼 문제예요.",
    ]
    if target_cpa and target_cpa > 0:
        rules.insert(0, f"목표 문의당 비용: {target_cpa:,}원 (사용자 입력값 최우선)")
        rules.extend([
            f"누적 지출이 {target_cpa * 2:,}원(목표 CPA 2배) 이상인데 문의 0건: 강한 OFF 후보예요.",
            f"문의당 비용이 {target_cpa:,}원 이하: 유지/증액 후보예요.",
            f"문의당 비용이 {int(target_cpa * 0.7):,}원 이하 + 문의 3건 이상: 증액 1순위예요.",
            f"문의당 비용이 {int(target_cpa * 1.5):,}원 초과 + 개선 추세 없음: 감액 또는 OFF 후보예요.",
        ])
    else:
        rules.append("목표 CPA가 없으면 객단가·마진 기준 임시 목표를 세우고 '가정'으로 표시해요.")
    return rules


def recommend_structure(
    daily_budget: int,
    *,
    region: str = "우리동네",
    gender: str = "여성",
    age_band: str = "45-54",
    appeal: str = "핵심소구",
    has_validated_creative: bool = False,
    target_cpa: int | None = None,
    age_bands: list[str] | None = None,
) -> BudgetPlan:
    """예산에 맞는 캠페인 구조를 계산한다.

    age_band: 가장 가능성 높은 핵심 연령대 1개.
    has_validated_creative: 이미 반응이 검증된 소재/타겟 조합이 있는지.
    """
    bands = age_bands or SIMPLE_AGE_BANDS
    plan = BudgetPlan(daily_budget=daily_budget, tier="", mode_label="")
    plan.principles = list(_PAIR_PRINCIPLES)
    plan.judgment_rules = judgment_rules(target_cpa)

    full = feasibility(daily_budget, n_age=len(bands))
    if not full["feasible"]:
        plan.feasibility_note = (
            f"연령대 {len(bands)}개 풀 페어 운영에는 하루 {full['required']:,}원이 필요해요. "
            f"현재 예산({daily_budget:,}원)으로는 {full['shortfall']:,}원이 부족해서 "
            f"'예산 제한 모드'로 설계했어요."
        )
    else:
        plan.feasibility_note = (
            f"하루 {daily_budget:,}원이면 연령대 {len(bands)}개 자동+수동 풀 페어"
            f"(필요 예산 {full['required']:,}원)가 가능해요."
        )

    def _row(age: str, bid: BidMode, budget: int, purpose: str, note: str = "") -> CampaignRow:
        return CampaignRow(
            name=make_campaign_name(region, gender, age, appeal, bid),
            purpose=purpose, region=region, gender=gender, age=age,
            bid_mode=bid, daily_budget=budget, note=note,
        )

    if daily_budget < MIN_CAMPAIGN_BUDGET:
        plan.tier = "below_minimum"
        plan.mode_label = "예산 부족 — 캠페인 최소 예산 미달"
        plan.warnings.append(
            f"캠페인 최소 일예산은 {MIN_CAMPAIGN_BUDGET:,}원이에요. "
            "예산을 늘리거나 격일 운영을 검토해 주세요."
        )
        return plan

    if daily_budget < 20_000:
        # 단일 캠페인: 신규 = 자동(노출 데이터 확보), 검증됨 = 수동(비용 통제)
        bid: BidMode = "수동" if has_validated_creative else "자동"
        why = (
            "검증된 조합이 있으니 자동의 비싼 CPC를 감수할 필요 없이 수동으로 비용을 통제해요."
            if has_validated_creative
            else "신규 광고는 수동으로 시작하면 노출이 안 타서 데이터가 안 쌓여요. 자동으로 반응 데이터부터 확보해요."
        )
        start_age = age_band if has_validated_creative else BROAD_AGE_BAND
        plan.tier = "single"
        plan.mode_label = f"단일 캠페인 ({bid} 1개) — 변수 1개만 테스트"
        plan.campaigns = [_row(start_age, bid, daily_budget, "반응 데이터 확보" if bid == "자동" else "성과 통제", why)]
        plan.warnings.append("이 예산에서 자동+수동 동시 운영은 데이터가 쪼개져서 판단이 더 어려워져요. 순차 운영이 맞아요.")
        plan.next_steps = [
            "1순위: 핵심 타겟 1개로 누적 3만원까지 집행",
            "2순위: 보고서에서 연령별 반응(채팅·단골·쿠폰) 확인",
            "3순위: 반응 좋은 연령대만 다음 캠페인으로 분리",
            "4순위: 일예산 2만원 확보되면 그 연령대에 자동+수동 페어 적용",
        ]
        return plan

    if daily_budget < 30_000:
        half = daily_budget // 2
        plan.tier = "pair"
        plan.mode_label = f"최소 페어 — {gender} {age_band} 1개 타겟에 자동+수동"
        plan.campaigns = [
            _row(age_band, "수동", half, "성과 통제 (CPC 상한)"),
            _row(age_band, "자동", daily_budget - half, "노출 부스팅"),
        ]
        plan.warnings.append("이 예산에서 연령대를 여러 개로 나누면 안 돼요. 가장 가능성 높은 연령대 1개만 페어로 검증해요.")
        plan.next_steps = [
            "누적 5만원까지 자동 vs 수동 문의당 비용 비교",
            "수동이 좋은데 지출이 안 타면 자동 페어 유지로 노출 보강",
            "자동만 잘 타는데 CPA가 높으면 자동 감액",
        ]
        return plan

    if daily_budget < 50_000:
        test_budget = MIN_CAMPAIGN_BUDGET
        main_total = daily_budget - test_budget
        half = main_total // 2
        next_band = _next_test_band(age_band, bands)
        plan.tier = "pair_plus_test"
        plan.mode_label = f"주력 페어 + 실험 1개 — 주력 {main_total:,}원 / 실험 {test_budget:,}원"
        plan.campaigns = [
            _row(age_band, "수동", half, "주력: 성과 통제"),
            _row(age_band, "자동", main_total - half, "주력: 노출 부스팅"),
            _row(next_band, "자동", test_budget, "실험: 새 연령대 탐색",
                 "주력과 소재·소식·쿠폰 동일, 연령만 다르게 (변수 1개)"),
        ]
        plan.next_steps = [
            "주력 페어에서 자동/수동 효율 비교",
            "실험 캠페인은 누적 3만원까지 신호만 관찰",
            "실험 연령대 반응이 좋으면 다음 기간에 페어로 승격",
        ]
        return plan

    if daily_budget < 100_000:
        quarter = daily_budget // 4
        second_band = _next_test_band(age_band, bands)
        plan.tier = "two_pairs"
        plan.mode_label = f"연령대 2개 자동+수동 페어 (캠페인당 {quarter:,}원)"
        plan.campaigns = [
            _row(age_band, "수동", quarter, "1군: 성과 통제"),
            _row(age_band, "자동", quarter, "1군: 노출 부스팅"),
            _row(second_band, "수동", quarter, "2군: 성과 통제"),
            _row(second_band, "자동", daily_budget - quarter * 3, "2군: 노출 부스팅"),
        ]
        plan.next_steps = [
            "두 연령대의 문의당 비용 비교 후 다음 기간 예산 재배분",
            "문의당 비용이 비슷하면 한 묶음으로 병합 운영 가능",
        ]
        return plan

    # 10만원 이상: 풀 페어
    per = daily_budget // (len(bands) * 2)
    plan.tier = "full_pairs"
    plan.mode_label = f"연령대 {len(bands)}개 자동+수동 풀 페어 (캠페인당 {per:,}원)"
    for band in bands:
        plan.campaigns.append(_row(band, "수동", per, "성과 통제"))
        plan.campaigns.append(_row(band, "자동", per, "노출 부스팅"))
    plan.next_steps = [
        "보고서의 연령별 문의당 비용으로 OFF/감액/증액 판정",
        "문의당 비용이 비슷한 연령대끼리 묶어서 캠페인 수 축소",
        "OFF한 연령대 예산은 최고 효율 연령대로 몰아주기",
        "최적 예산 지점 탐색: 풀어놓고 반응 보면서 서서히 감액",
    ]
    return plan


def _next_test_band(current: str, bands: list[str]) -> str:
    """주력 연령대 다음으로 테스트할 연령대 선택 (주력과 다른 첫 번째)."""
    for b in bands:
        if b != current and not _band_overlaps(b, current):
            return b
    return bands[0] if bands else "20-39"


def _band_overlaps(a: str, b: str) -> bool:
    return a.strip() == b.strip()


# ── 출력 변환 ────────────────────────────────────────────────────────────

SETTING_TABLE_COLUMNS = [
    {"name": "name", "label": "캠페인명", "field": "name", "align": "left"},
    {"name": "purpose", "label": "역할", "field": "purpose", "align": "left"},
    {"name": "gender", "label": "성별", "field": "gender", "align": "center"},
    {"name": "age", "label": "연령", "field": "age", "align": "center"},
    {"name": "bid_mode", "label": "입찰", "field": "bid_mode", "align": "center"},
    {"name": "daily_budget", "label": "일예산", "field": "daily_budget", "align": "right"},
    {"name": "note", "label": "비고", "field": "note", "align": "left"},
]


def plan_table_rows(plan: BudgetPlan) -> list[dict]:
    return [{
        "name": c.name,
        "purpose": c.purpose,
        "gender": c.gender,
        "age": c.age,
        "bid_mode": c.bid_mode,
        "daily_budget": f"{c.daily_budget:,}원",
        "note": c.note,
    } for c in plan.campaigns]


def plan_to_prompt_context(plan: BudgetPlan) -> str:
    """AI 프롬프트 주입용 텍스트. AI는 이 설계를 그대로 따라야 한다."""
    lines = [
        f"운영 모드: {plan.mode_label}",
        f"일예산: {plan.daily_budget:,}원",
        plan.feasibility_note,
        "",
        "캠페인 세팅표 (이 구조를 그대로 사용, 임의 변형 금지):",
        "| 캠페인명 | 역할 | 성별 | 연령 | 입찰 | 일예산 | 비고 |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in plan.campaigns:
        lines.append(
            f"| {c.name} | {c.purpose} | {c.gender} | {c.age} "
            f"| {c.bid_mode} | {c.daily_budget:,}원 | {c.note} |"
        )
    if plan.warnings:
        lines.append("")
        lines.append("주의사항:")
        lines.extend(f"- {w}" for w in plan.warnings)
    lines.append("")
    lines.append("변수 통제 원칙:")
    lines.extend(f"- {p}" for p in plan.principles)
    lines.append("")
    lines.append("판단 기준 (누적 광고비 기준):")
    lines.extend(f"- {r}" for r in plan.judgment_rules)
    if plan.next_steps:
        lines.append("")
        lines.append("다음 단계:")
        lines.extend(f"- {s}" for s in plan.next_steps)
    return "\n".join(lines)
