"""매장 위키 — 매장(프로젝트)별 누적 지식 + 내부 raw data 정제 계층.

해자(moat)는 외부 크롤링이 아니라 **내부 raw data를 패턴으로 정제**하는 데 있다.
이 모듈은 SQLite의 원자료(성과·생성물)와 리서치를 매장별 '검증된 패턴'으로 정제해
모든 생성 프롬프트에 주입하고, 분석이 끝나면 학습을 다시 누적한다.
설계 참고(스펙 아님): _ops/AI_OPERATING_FRAME.md, Karpathy LLM Wiki.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from app.database import get_latest_content, save_generated_content

WIKI_CONTENT_TYPE = "store_wiki"

# 디지털 전환(문의·단골·쿠폰)이 실제 성과를 다 못 잡는 업종.
# 전화·직접 방문이 핵심이라 당근 채팅 문의가 0~1건이어도 실패가 아니다.
_TRACKING_LIMITED_KEYWORDS = (
    "안경", "병원", "의원", "치과", "한의원", "피부", "성형", "시술",
    "정형", "안과", "이비인후", "네일", "미용", "헤어", "필라테스",
    "학원", "교습", "공방", "정비", "수리", "부동산", "법무",
)


def is_tracking_limited(industry: str) -> bool:
    """전화·내방 중심이라 디지털 전환 추적이 한계인 업종인지."""
    return any(k in (industry or "") for k in _TRACKING_LIMITED_KEYWORDS)


def summarize_performance_patterns(kpi: Optional[dict]) -> List[str]:
    """내부 성과 raw data(kpi)를 매장별 '검증된 패턴' 줄로 정제한다.

    이게 데이터 해자의 핵심: 실제로 뭐가 효율적이었는지를 재사용 가능한 패턴으로 남긴다.
    """
    if not kpi:
        return []
    lines: List[str] = []
    ctr = kpi.get("ctr", 0.0)
    cpc = kpi.get("cpc", 0.0)
    if kpi.get("total_clicks"):
        lines.append(f"- 누적 기준: CTR {ctr:.2f}%, CPC {cpc:,.0f}원 (이 매장의 평균선)")
    eff = kpi.get("efficient_periods") or []
    ineff = kpi.get("inefficient_periods") or []
    if eff:
        lines.append(f"- 효율 좋았던 기간: {', '.join(map(str, eff))} → 이 시점 조건(소재/타겟) 재사용 가치 있음")
    if ineff:
        lines.append(f"- 효율 낮았던 기간: {', '.join(map(str, ineff))} → 반복 지양")
    cpr = kpi.get("cpr", 0.0)
    cp_coupon = kpi.get("cp_coupon", 0.0)
    if kpi.get("total_regulars") or kpi.get("total_coupons"):
        lines.append(f"- 단골당 {cpr:,.0f}원 / 쿠폰당 {cp_coupon:,.0f}원 (다음 분석의 비교 기준선)")
    return lines


def build_initial_wiki(project: dict, kpi: Optional[dict] = None) -> str:
    """매장 정보(+있으면 성과)로 최소 위키를 만든다(룰 기반, AI 호출 없음).

    사장님/AI가 운영하며 채워나가는 씨앗. 추적 한계·검증 패턴을 미리 박아 둔다.
    """
    p = project or {}
    name = (p.get("name") or "").strip() or "매장"
    industry = (p.get("industry") or "").strip()
    region = (p.get("region") or "").strip()
    benefits = (p.get("benefits") or "").strip()

    out: List[str] = [f"# 매장 위키 — {name}", ""]
    out += ["## 시장 특성",
            f"- 지역: {region or '(미입력)'}",
            f"- 업종: {industry or '(미입력)'}",
            ""]

    out.append("## 추적 한계")
    if is_tracking_limited(industry):
        out.append(
            f"- {industry or '이 업종'}은 전화·직접 방문이 핵심이라 당근 디지털 전환"
            "(문의·단골·쿠폰)이 실제 성과를 다 못 잡는다. 채팅 문의가 0~1건이어도 실패가 아니다."
        )
        out.append("- 성과는 쿠폰 사용·전화·내방 기준으로 본다. 매장에 '당근 보고 오셨어요?' 한 줄 확인 권장.")
    else:
        out.append("- (특이사항 파악 전. 운영하며 채워 넣는다.)")
    out.append("")

    out.append("## 검증된 패턴 (내부 성과 데이터 정제)")
    perf = summarize_performance_patterns(kpi)
    if perf:
        out += perf
    else:
        out.append("- (성과 데이터가 쌓이면 효율 좋았던 미끼/소재/타겟/기간을 여기 정제해 둠)")
    if benefits:
        out.append(f"- 주요 혜택(후보 미끼): {benefits}")
    out.append("")

    out += ["## 안 먹힌 것",
            "- (효율 낮았던 것 기록 — 반복 방지)",
            "",
            "## 과거 진단",
            "- (지난 보고서의 핵심 병목·가설 — 다음 분석이 이어받음)",
            "",
            "## 사장님 사실관계 / 피드백",
            "- (행사 사실관계, 정정 사항 — 모든 콘텐츠의 기준)"]
    return "\n".join(out)


def load_wiki(project_id: int) -> Optional[str]:
    """저장된 매장 위키 마크다운. 없으면 None."""
    rec = get_latest_content(project_id, WIKI_CONTENT_TYPE)
    if rec and (rec.get("content") or "").strip():
        return rec["content"]
    return None


def save_wiki(project_id: int, content: str) -> None:
    """매장 위키를 누적 저장(최신본이 로드됨)."""
    save_generated_content(project_id, "system", content, content_type=WIKI_CONTENT_TYPE)


def ensure_wiki(project_id: int, project: dict, kpi: Optional[dict] = None) -> str:
    """위키가 없으면 초기 위키를 만들어 저장하고 반환."""
    existing = load_wiki(project_id)
    if existing:
        return existing
    wiki = build_initial_wiki(project, kpi)
    save_wiki(project_id, wiki)
    return wiki


def wiki_context(project_id: Optional[int], project: dict, kpi: Optional[dict] = None) -> str:
    """프롬프트 주입용 위키 텍스트. 저장본이 있으면 그걸, 없으면 즉석 초기 위키."""
    if project_id:
        existing = load_wiki(project_id)
        if existing:
            return existing
    return build_initial_wiki(project or {}, kpi)


_PATTERNS_HEADER = "검증된 패턴 (내부 성과 데이터 정제)"
_DIAGNOSIS_HEADER = "과거 진단"


def extract_report_learnings(report_text: str) -> Dict[str, str]:
    """보고서 본문에서 병목/가설을 뽑는다(끝의 JSON 블록 우선)."""
    out = {"blocked": "", "hypothesis": ""}
    if not report_text:
        return out
    m = re.search(r"```json\s*(\{.*?\})\s*```", report_text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            out["blocked"] = str(data.get("blocked") or "").strip()
            out["hypothesis"] = str(data.get("hypothesis") or "").strip()
        except (ValueError, TypeError):
            pass
    return out


def _merge_section(wiki: str, header: str, new_lines: List[str]) -> str:
    """위키 '## header' 섹션 끝에 new_lines를 append. 이미 있는 줄은 건너뛴다.

    섹션이 없으면 문서 끝에 새 섹션으로 추가. 기존 큐레이션 내용은 보존(덮어쓰지 않음).
    """
    lines = wiki.split("\n")
    existing = {l.strip() for l in lines}
    add = [l for l in new_lines if l.strip() and l.strip() not in existing]
    if not add:
        return wiki

    idx = next((i for i, l in enumerate(lines) if l.strip() == f"## {header}"), None)
    if idx is None:
        if lines and lines[-1].strip():
            lines.append("")
        return "\n".join(lines + [f"## {header}"] + add)

    end = next((j for j in range(idx + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
    insert_at = end
    while insert_at - 1 > idx and not lines[insert_at - 1].strip():
        insert_at -= 1
    return "\n".join(lines[:insert_at] + add + lines[insert_at:])


def update_wiki_from_report(
    project_id: int, project: dict, kpi: Optional[dict],
    report_text: str = "", period: str = "",
) -> str:
    """보고서 분석의 학습을 매장 위키에 누적(append)한다 — 닫힌 누적 루프의 핵심.

    과거 진단(병목·가설)과 검증된 패턴(성과 정제)을 기간 마커와 함께 쌓아,
    다음 분석이 지난 분석을 이어받게 한다. 기존 내용은 보존.
    """
    # 시드는 패턴 없이(placeholder) 만들고, 아래에서 기간 마커가 붙은 정제 줄을 쌓는다.
    wiki = ensure_wiki(project_id, project)
    marker = (period or "최근").strip()

    learn = extract_report_learnings(report_text)
    diag: List[str] = []
    if learn["blocked"]:
        diag.append(f"- [{marker}] 병목: {learn['blocked']}")
    if learn["hypothesis"]:
        diag.append(f"- [{marker}] 가설: {learn['hypothesis']}")

    perf = [f"- [{marker}] {p.lstrip('- ').strip()}" for p in summarize_performance_patterns(kpi)]

    updated = _merge_section(wiki, _DIAGNOSIS_HEADER, diag)
    updated = _merge_section(updated, _PATTERNS_HEADER, perf)
    if updated != wiki:
        save_wiki(project_id, updated)
    return updated


def wiki_prompt_block(wiki: str) -> str:
    """프롬프트에 끼울 위키 블록. 비면 ''."""
    w = (wiki or "").strip()
    if not w:
        return ""
    return (
        "[매장 위키 — 이 매장에 대해 지금까지 정제된 사실/패턴. "
        "여기 적힌 추적 한계·검증 패턴·사장님 사실관계를 반드시 따른다]\n"
        f"{w}\n\n"
    )
