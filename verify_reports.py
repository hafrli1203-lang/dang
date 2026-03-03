"""verify_reports.py — 샘플 DOCX 생성 및 (선택) PDF 변환 검증 스크립트

Usage:
    python verify_reports.py            # DOCX 생성만
    python verify_reports.py --pdf      # DOCX + PDF 변환 시도 (docx2pdf 필요)

출력물:
    verify_성과보고서.docx
    verify_기획서.docx
    verify_성과보고서.pdf  (--pdf 플래그 && docx2pdf 설치 시)
    verify_기획서.pdf      (--pdf 플래그 && docx2pdf 설치 시)
"""

import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent.resolve()

from app.reporting.docx_report import (
    ProjectMeta, KPI, TimeseriesRow, Insights, ReportInsights,
    build_report_docx, build_planning_docx,
)

# ── 샘플 데이터 ────────────────────────────────────────────────────────────────

PROJECT: ProjectMeta = {
    "name":     "테스트카페",
    "period":   "2024년 6월",
    "goal":     "방문 고객 증대 및 단골 전환",
    "industry": "카페",
    "region":   "서울 강남구",
    "budget":   "300,000원",
    "campaign_name": "6월 신메뉴 런칭 캠페인",
    "author":   "김마케팅",
    "target":   "서울 강남구 20~40대 직장인",
    "operation_method": "당근 피드 광고 + 쿠폰 연계",
    "benefits": "신메뉴 10% 할인, 아메리카노 1+1",
}

TIMESERIES: list[TimeseriesRow] = [
    {"date": "1주차", "spend": 75000,  "clicks": 480, "chats": 18, "impressions": 12000, "followers": 3,  "coupons": 5},
    {"date": "2주차", "spend": 80000,  "clicks": 540, "chats": 21, "impressions": 13500, "followers": 4,  "coupons": 7},
    {"date": "3주차", "spend": 70000,  "clicks": 420, "chats": 15, "impressions": 11000, "followers": 2,  "coupons": 4},
    {"date": "4주차", "spend": 75000,  "clicks": 610, "chats": 26, "impressions": 14000, "followers": 5,  "coupons": 9},
]

KPI_DATA: KPI = {
    "total_spend":       300000,
    "total_impressions": 50500,
    "total_clicks":      2050,
    "total_chats":       80,
    "total_followers":   14,
    "total_coupons":     25,
    "ctr":               4.06,
    "cpc":               146.3,
    "cpa":               3750.0,
}

INSIGHTS: ReportInsights = {
    "conclusion": (
        "전반적으로 양호한 성과를 거뒀습니다. "
        "CTR이 업종 평균을 62% 상회하며 소재 효율이 검증되었습니다. "
        "단골 전환은 꾸준히 발생 중이며 광고 누적 효과가 관찰됩니다."
    ),
    "next_actions": [
        "현재 소재를 최소 2주 더 유지하며 성과 추이를 관찰하세요.",
        "예산을 20% 증대하여 도달 범위를 확대할 수 있습니다.",
        "쿠폰 연계 캠페인 추가로 문의 전환율 향상을 기대할 수 있습니다.",
        "주말 타겟 광고를 별도 실험하여 비용 효율을 비교하세요.",
    ],
    "good": (
        "CTR 4.06%는 카페 업종 평균(2.5%) 대비 62% 높은 수준입니다.\n"
        "4주차 클릭 수 610건으로 최고치를 기록했습니다.\n"
        "단골 전환이 매주 꾸준히 발생하고 있습니다."
    ),
    "blocked": (
        "3주차에 노출이 11,000으로 하락하며 클릭도 감소했습니다.\n"
        "쿠폰 사용률이 전체 문의 대비 31%로 기대보다 낮습니다."
    ),
    "hypothesis": (
        "3주차 노출 하락은 주중 경쟁 입찰 증가가 원인일 수 있습니다.\n"
        "쿠폰 사용률이 낮은 이유는 혜택 인지도 부족일 수 있습니다."
    ),
    "experiments": [
        {"priority": "1", "change": "소재 A를 메인 카피로 교체", "success_criteria": "CTR 5% 이상", "owner": "마케팅팀", "schedule": "7월 1주"},
        {"priority": "2", "change": "주말 한정 쿠폰 푸시 추가", "success_criteria": "쿠폰 사용률 50%", "owner": "운영팀", "schedule": "7월 2주"},
        {"priority": "3", "change": "타겟 연령 30~40대로 축소 테스트", "success_criteria": "CPA 3,000원 이하", "owner": "마케팅팀", "schedule": "7월 3주"},
    ],
    "judgment": {
        "expand": "CTR 4% 이상 유지 + CPA 4,000원 이하일 때 예산을 30% 증액합니다.",
        "review": "CTR 2.5~4% 구간이면 소재 교체 후 2주간 재검토합니다.",
        "stop": "CTR 2% 미만 또는 CPA 8,000원 초과 시 캠페인을 일시 중단합니다.",
    },
    # 레거시 호환 필드
    "summary": (
        "전반적으로 양호한 성과를 거뒀습니다. "
        "CTR이 업종 평균을 62% 상회하며 소재 효율이 검증되었습니다. "
        "단골 전환은 꾸준히 발생 중이며 광고 누적 효과가 관찰됩니다."
    ),
    "insights": [
        "CTR 4.06%는 카페 업종 평균(2.5%) 대비 62% 높은 수준입니다.",
        "3주차 비용 대비 클릭 효율이 가장 우수합니다 (CPC 167원).",
        "단골 전환은 꾸준히 발생 중이며 광고 누적 효과가 관찰됩니다.",
    ],
    "actions": [
        "현재 소재를 최소 2주 더 유지하며 성과 추이를 관찰하세요.",
        "예산을 20% 증대하여 도달 범위를 확대할 수 있습니다.",
        "쿠폰 연계 캠페인 추가로 문의 전환율 향상을 기대할 수 있습니다.",
    ],
}

PLANNING_AI = """\
## 1. 기획 요약

### 목표
방문 고객 증대 및 단골 전환율 향상

### 핵심 KPI
- CTR 3% 이상
- 월 문의 100건 이상
- 단골 전환 20명 이상

### 전략 방향
강남구 인근 잠재 고객을 타겟으로, 화요일 1+1 이벤트와 쿠폰 연계로
재방문을 유도합니다. 당근 이웃 특화 혜택을 강조하여 지역 충성 고객을 확보합니다.

## 2. 당근 소식글

안녕하세요, 테스트카페입니다 :)
매주 화요일 아메리카노 1+1 행사를 진행합니다.
당근 이웃 여러분께 특별히 10% 추가 할인도 드려요.
근처 오시는 길에 꼭 들러주세요!

## 3. 광고 카피 9개

1. 동네 카페의 따뜻한 한 잔, 지금 바로 만나보세요
2. 오늘 하루도 수고했어요 — 달콤한 브레이크 타임
3. 이웃에게 추천하고 싶은 카페
4. 매일 아침 시작하는 곳, 테스트카페
5. 합리적인 가격, 변함없는 맛
6. 단골 할인 혜택이 기다립니다
7. 당근 이웃만을 위한 스페셜 오퍼
8. 강남구 최고의 커피 명소
9. 재방문율 98%, 믿고 오세요
"""


# ── 생성 함수 ──────────────────────────────────────────────────────────────────

def generate_report(out: Path) -> None:
    print(f"  성과보고서 생성 중…  →  {out}")
    build_report_docx(
        project_meta=PROJECT,
        kpi=KPI_DATA,
        timeseries=TIMESERIES,
        insights=INSIGHTS,
        output_path=out,
    )
    size_kb = out.stat().st_size / 1024
    print(f"  [OK] 성과보고서  {size_kb:,.1f} KB  ({out})")


def generate_planning(out: Path) -> None:
    print(f"  기획서 생성 중…  →  {out}")
    build_planning_docx(
        project_meta=PROJECT,
        ai_content=PLANNING_AI,
        output_path=out,
    )
    size_kb = out.stat().st_size / 1024
    print(f"  [OK] 기획서       {size_kb:,.1f} KB  ({out})")


def try_pdf_convert(docx_path: Path) -> None:
    pdf_path = docx_path.with_suffix(".pdf")
    try:
        from docx2pdf import convert  # type: ignore
        print(f"  PDF 변환 중…  →  {pdf_path}")
        convert(str(docx_path), str(pdf_path))
        size_kb = pdf_path.stat().st_size / 1024
        print(f"  [OK] PDF  {size_kb:,.1f} KB  ({pdf_path})")
    except ImportError:
        print(
            "  [SKIP] docx2pdf 미설치 -- PDF 변환 건너뜀\n"
            "         설치: pip install docx2pdf\n"
            "         (Windows: Microsoft Word 필요 / macOS: LibreOffice 또는 Word)"
        )
    except Exception as exc:
        print(f"  [FAIL] PDF 변환 실패: {exc}")


# ── 진입점 ─────────────────────────────────────────────────────────────────────

def main() -> None:
    want_pdf = "--pdf" in sys.argv

    report_path  = _SCRIPT_DIR / "verify_성과보고서.docx"
    planning_path = _SCRIPT_DIR / "verify_기획서.docx"

    print("\n── 성과 보고서 ─────────────────────────────────────────────────────────")
    generate_report(report_path)
    if want_pdf:
        try_pdf_convert(report_path)

    print("\n── 광고 기획서 ─────────────────────────────────────────────────────────")
    generate_planning(planning_path)
    if want_pdf:
        try_pdf_convert(planning_path)

    print("\n완료. 위 파일을 열어 레이아웃을 확인하세요.")


if __name__ == "__main__":
    main()
