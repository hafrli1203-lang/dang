"""캠페인 수정표 생성 룰 엔진.

판정(judge_campaigns)과 예산 재배분(simulate_reallocation) 결과를
광고 관리자가 오늘 그대로 따라 할 수 있는 한 장의 수정표로 합친다.

우선순위: OFF(1) > 소재교체(2) > 증액(3) > 연령 조치(4) > 소재정리(5)
"""
from dataclasses import dataclass

_VERDICT_PRIORITY = {
    "캠페인OFF": 1,
    "소재전면교체": 2,
    "증액": 3,
    "소재정리후유지": 5,
}


@dataclass
class RevisionRow:
    priority: int
    target: str        # 캠페인명 또는 [연령] 세그먼트
    problem: str       # 현재 문제
    evidence: str      # 데이터 근거
    action: str        # 조치
    new_value: str     # 수정값 (광고 관리자에 입력할 값)
    expected: str      # 기대 효과


def build_campaign_revision_table(judgments, plan=None) -> list[RevisionRow]:
    """판정 + 재배분 plan에서 실행용 수정표 행을 만든다.

    judgments: CampaignJudgment 시퀀스 (verdict/reason/campaign 보유)
    plan: ReallocationPlan (cuts/boosts) — 없으면 증액액 없이 판정만 반영
    """
    boosts = dict(plan.boosts) if plan is not None else {}
    rows: list[RevisionRow] = []

    for j in judgments:
        verdict = j.verdict
        if verdict == "유지":
            continue
        c = j.campaign
        cpa_txt = f"CPA {int(c.cpa):,}원" if c.actions > 0 else "전환 0건"
        evidence = f"{c.cost:,}원 소진 / 행동 {c.actions}건 / {cpa_txt}"

        if verdict == "캠페인OFF":
            rows.append(RevisionRow(
                priority=_VERDICT_PRIORITY[verdict],
                target=c.name,
                problem="지출 대비 전환 없음 또는 기준 미달",
                evidence=evidence,
                action="캠페인 OFF",
                new_value="일예산 0원 (게재 중단)",
                expected=f"월 환산 약 {c.cost:,}원 낭비 차단",
            ))
        elif verdict == "소재전면교체":
            rows.append(RevisionRow(
                priority=_VERDICT_PRIORITY[verdict],
                target=c.name,
                problem="평균 대비 CPA 과다 (소재 문제 추정)",
                evidence=j.reason,
                action="소재 전면 교체 + 검증 기간 감액",
                new_value=f"일예산 {max(c.cost // 2, 0):,}원 (50% 감액)",
                expected="새 소재 CTR/CPA 재검증",
            ))
        elif verdict == "증액":
            boost_amt = boosts.get(c.name, 0)
            extra = int(boost_amt / c.cpa) if c.cpa > 0 and boost_amt > 0 else 0
            rows.append(RevisionRow(
                priority=_VERDICT_PRIORITY[verdict],
                target=c.name,
                problem="고효율인데 예산 비중이 작음 (기회 손실)",
                evidence=j.reason,
                action="예산 증액",
                new_value=(
                    f"+{boost_amt:,}원 증액" if boost_amt > 0
                    else "OFF 절감분 내에서 증액"
                ),
                expected=(
                    f"추가 전환 약 +{extra}건 예상" if extra > 0
                    else "동일 CPA 가정 시 전환 증가"
                ),
            ))
        elif verdict == "소재정리후유지":
            rows.append(RevisionRow(
                priority=_VERDICT_PRIORITY[verdict],
                target=c.name,
                problem="주력 캠페인 — 비중 크고 평균 이하 CPA",
                evidence=j.reason,
                action="저효율 소재만 정리 후 유지",
                new_value="일예산 유지",
                expected="주력 효율 방어",
            ))

    # 연령 단위 조치 (plan의 [연령] cuts/boosts)
    if plan is not None:
        judged_names = {j.campaign.name for j in judgments}
        for name, amt in plan.cuts:
            if name.startswith("[연령]") and name not in judged_names:
                rows.append(RevisionRow(
                    priority=4,
                    target=name,
                    problem="해당 연령 지출 대비 전환 미달",
                    evidence=f"{amt:,}원 회수 대상",
                    action="해당 연령 타겟 제외(OFF)",
                    new_value="캠페인 타겟에서 이 연령 제거",
                    expected=f"약 {amt:,}원 재배분 재원 확보",
                ))
        for name, amt in plan.boosts:
            if name.startswith("[연령]") and name not in judged_names:
                rows.append(RevisionRow(
                    priority=4,
                    target=name,
                    problem="해당 연령 고효율인데 예산 부족",
                    evidence=f"+{amt:,}원 배분 권장",
                    action="이 연령 전용 캠페인 분리/증액",
                    new_value=f"+{amt:,}원",
                    expected="저비용 전환 확대",
                ))

    rows.sort(key=lambda r: (r.priority, r.target))
    return rows


REVISION_TABLE_COLUMNS = [
    {"name": "priority", "label": "우선순위", "field": "priority", "align": "center", "sortable": True},
    {"name": "target", "label": "캠페인/세그먼트", "field": "target", "align": "left"},
    {"name": "problem", "label": "현재 문제", "field": "problem", "align": "left"},
    {"name": "evidence", "label": "데이터 근거", "field": "evidence", "align": "left"},
    {"name": "action", "label": "조치", "field": "action", "align": "left"},
    {"name": "new_value", "label": "수정값", "field": "new_value", "align": "left"},
    {"name": "expected", "label": "기대 효과", "field": "expected", "align": "left"},
]


def revision_rows_for_table(rows: list[RevisionRow]) -> list[dict]:
    return [{
        "priority": r.priority,
        "target": r.target,
        "problem": r.problem,
        "evidence": r.evidence,
        "action": r.action,
        "new_value": r.new_value,
        "expected": r.expected,
    } for r in rows]


def revision_table_markdown(rows: list[RevisionRow]) -> str:
    """클립보드 복사용 마크다운 표."""
    lines = [
        "| 우선순위 | 캠페인/세그먼트 | 현재 문제 | 데이터 근거 | 조치 | 수정값 | 기대 효과 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.priority} | {r.target} | {r.problem} | {r.evidence} "
            f"| {r.action} | {r.new_value} | {r.expected} |"
        )
    return "\n".join(lines)
