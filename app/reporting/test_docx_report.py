"""Unit tests for app.reporting.docx_report v2.0

Run:
    python -m unittest app.reporting.test_docx_report -v

No external services or API keys required.
"""
import tempfile
import unittest
from pathlib import Path

from app.reporting.docx_report import build_planning_docx, build_report_docx, make_charts

# ── Shared fixtures ────────────────────────────────────────────────────────────

_TIMESERIES = [
    {"date": "1주차", "spend": 75000, "clicks": 480, "chats": 18, "impressions": 12000, "followers": 3, "coupons": 5},
    {"date": "2주차", "spend": 80000, "clicks": 540, "chats": 21, "impressions": 13500, "followers": 4, "coupons": 7},
    {"date": "3주차", "spend": 70000, "clicks": 420, "chats": 15, "impressions": 11000, "followers": 2, "coupons": 4},
    {"date": "4주차", "spend": 75000, "clicks": 610, "chats": 26, "impressions": 14000, "followers": 5, "coupons": 9},
]
_PROJECT = {
    "name": "테스트카페", "period": "2024.06", "goal": "방문증가",
    "industry": "카페", "region": "서울 강남구", "budget": "300,000원",
}
_KPI = {
    "total_spend": 300000, "total_impressions": 50500, "total_clicks": 2050,
    "total_chats": 80, "total_followers": 14, "total_coupons": 25,
    "ctr": 4.06, "cpc": 146.3, "cpa": 3750.0,
}
_INSIGHTS = {
    "summary": "전반적으로 양호한 성과를 거뒀습니다. CTR이 업종 평균을 상회하며 소재 효율이 검증되었습니다.",
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
_PLANNING_AI = """\
## 1. 기획 요약

### 목표
방문 고객 증대 및 단골 전환율 향상

### 핵심 KPI
- CTR 3% 이상
- 월 문의 100건 이상
- 단골 전환 20명 이상

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


# ── TestMakeCharts ─────────────────────────────────────────────────────────────

class TestMakeCharts(unittest.TestCase):

    def test_creates_three_charts(self):
        with tempfile.TemporaryDirectory() as d:
            paths = make_charts(_TIMESERIES, Path(d))
            names = {p.name for p in paths}
            self.assertEqual(len(paths), 3)
            self.assertIn("chart_spend_action.png", names)
            self.assertIn("chart_cpa.png", names)
            self.assertIn("chart_funnel.png", names)
            for p in paths:
                self.assertGreater(p.stat().st_size, 0)

    def test_landing_mode_charts(self):
        rows = [
            {"date": "1주차", "spend": 50000, "clicks": 300, "conversions": 30, "impressions": 10000},
            {"date": "2주차", "spend": 60000, "clicks": 400, "conversions": 45, "impressions": 12000},
        ]
        with tempfile.TemporaryDirectory() as d:
            paths = make_charts(rows, Path(d), mode="landing")
            names = {p.name for p in paths}
            self.assertEqual(len(paths), 3)
            self.assertIn("chart_spend_action.png", names)
            self.assertIn("chart_cpa.png", names)
            self.assertIn("chart_funnel.png", names)

    def test_reaction_mode_charts(self):
        rows = [
            {"date": "1주차", "spend": 50000, "impressions": 10000,
             "likes": 120, "comments": 30, "shares": 15},
            {"date": "2주차", "spend": 60000, "impressions": 12000,
             "likes": 150, "comments": 40, "shares": 20},
        ]
        with tempfile.TemporaryDirectory() as d:
            paths = make_charts(rows, Path(d), mode="reaction")
            names = {p.name for p in paths}
            self.assertEqual(len(paths), 3)
            self.assertIn("chart_funnel.png", names)

    def test_no_impressions_still_generates_charts(self):
        """All 3 charts are generated even when impressions=0 (funnel shows zeros)."""
        rows = [
            {"date": "1주차", "spend": 50000, "clicks": 300, "chats": 10, "impressions": 0},
            {"date": "2주차", "spend": 60000, "clicks": 400, "chats": 15, "impressions": 0},
        ]
        with tempfile.TemporaryDirectory() as d:
            paths = make_charts(rows, Path(d))
            self.assertEqual(len(paths), 3)

    def test_empty_input_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(make_charts([], Path(d)), [])


# ── TestBuildReportDocx ────────────────────────────────────────────────────────

class TestBuildReportDocx(unittest.TestCase):

    def _build(self, tmpdir, **kw):
        defaults = dict(
            project_meta=_PROJECT, kpi=_KPI,
            timeseries=_TIMESERIES, insights=_INSIGHTS,
            output_path=Path(tmpdir) / "report.docx",
        )
        defaults.update(kw)
        return build_report_docx(**defaults)

    def test_creates_file_above_20kb(self):
        """Full sample → DOCX with charts should be > 20 KB."""
        with tempfile.TemporaryDirectory() as d:
            out = self._build(d)
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 20 * 1024)

    def test_returns_output_path(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "report.docx"
            result = build_report_docx(
                project_meta=_PROJECT, kpi=_KPI,
                timeseries=_TIMESERIES, insights=_INSIGHTS,
                output_path=out,
            )
            self.assertEqual(result, out)

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "a" / "b" / "report.docx"
            build_report_docx(
                project_meta=_PROJECT, kpi=_KPI,
                timeseries=_TIMESERIES, insights=_INSIGHTS,
                output_path=out,
            )
            self.assertTrue(out.exists())

    def test_custom_chart_dir(self):
        with tempfile.TemporaryDirectory() as d:
            charts_dir = Path(d) / "my_charts"
            build_report_docx(
                project_meta=_PROJECT, kpi=_KPI,
                timeseries=_TIMESERIES, insights=_INSIGHTS,
                output_path=Path(d) / "r.docx",
                chart_dir=charts_dir,
            )
            self.assertGreater(len(list(charts_dir.glob("*.png"))), 0)

    def test_landing_mode_report(self):
        landing_kpi = {
            "total_spend": 300000, "total_impressions": 50000, "total_clicks": 2000,
            "total_conversions": 150, "ctr": 4.0, "cpc": 150.0, "cvr": 7.5, "cpa": 2000.0,
        }
        landing_ts = [
            {"date": "1주차", "spend": 75000, "clicks": 480, "conversions": 35, "impressions": 12000},
            {"date": "2주차", "spend": 80000, "clicks": 540, "conversions": 42, "impressions": 13500},
        ]
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "landing.docx"
            build_report_docx(
                project_meta=_PROJECT, kpi=landing_kpi,
                timeseries=landing_ts, insights=_INSIGHTS,
                output_path=out, tracking_mode="landing",
            )
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 20 * 1024)

    def test_reaction_mode_report(self):
        reaction_kpi = {
            "total_spend": 300000, "total_impressions": 50000,
            "total_reactions": 800, "total_likes": 500,
            "total_comments": 200, "total_shares": 100,
            "engagement_rate": 1.6, "cpe": 375.0,
        }
        reaction_ts = [
            {"date": "1주차", "spend": 75000, "impressions": 12000,
             "likes": 120, "comments": 45, "shares": 20},
            {"date": "2주차", "spend": 80000, "impressions": 13500,
             "likes": 140, "comments": 55, "shares": 25},
        ]
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "reaction.docx"
            build_report_docx(
                project_meta=_PROJECT, kpi=reaction_kpi,
                timeseries=reaction_ts, insights=_INSIGHTS,
                output_path=out, tracking_mode="reaction",
            )
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 20 * 1024)


# ── TestBuildPlanningDocx ──────────────────────────────────────────────────────

class TestBuildPlanningDocx(unittest.TestCase):

    def test_creates_file_above_10kb(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "plan.docx"
            build_planning_docx(_PROJECT, _PLANNING_AI, out)
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 10 * 1024)

    def test_returns_output_path(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "plan.docx"
            self.assertEqual(build_planning_docx(_PROJECT, _PLANNING_AI, out), out)

    def test_empty_ai_content_no_crash(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "plan.docx"
            build_planning_docx(_PROJECT, "", out)
            self.assertTrue(out.exists())

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "deep" / "plan.docx"
            build_planning_docx(_PROJECT, _PLANNING_AI, out)
            self.assertTrue(out.exists())


# ── TestMissingOrNoneFields ────────────────────────────────────────────────────

class TestMissingOrNoneFields(unittest.TestCase):

    def test_all_empty_dicts_no_crash(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "r.docx"
            build_report_docx(project_meta={}, kpi={}, timeseries=[], insights={}, output_path=out)
            self.assertTrue(out.exists())

    def test_none_values_no_crash(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "r.docx"
            build_report_docx(
                project_meta={"name": None, "period": None, "goal": None},
                kpi={"total_spend": None, "ctr": None, "cpc": None},
                timeseries=[{"date": None, "spend": None, "clicks": None, "chats": None}],
                insights={"summary": None, "insights": None, "actions": None},
                output_path=out,
            )
            self.assertTrue(out.exists())

    def test_partial_timeseries_no_impressions(self):
        rows = [
            {"date": "1주차", "spend": 50000, "clicks": 200, "chats": 10},
            {"date": "2주차", "spend": 60000, "clicks": 300, "chats": 15},
        ]
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "r.docx"
            build_report_docx(
                project_meta=_PROJECT, kpi=_KPI,
                timeseries=rows, insights=_INSIGHTS, output_path=out,
            )
            self.assertTrue(out.exists())

    def test_planning_none_meta_no_crash(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "plan.docx"
            build_planning_docx(
                project_meta={"name": None, "goal": None},
                ai_content="## 1. 기획 요약\n내용 없음",
                output_path=out,
            )
            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
