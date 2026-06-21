# -*- coding: utf-8 -*-
"""슬라이드 HTML 보고서 빌더 테스트 (순수 함수)."""
import unittest

from app.reporting.slides_html import build_slides_html


_META = {"name": "지니스안경", "campaign_name": "4월 누진렌즈", "region": "공주", "period": "26.4.1~30"}
_KPI = {
    "total_cost": 328095, "total_impressions": 103010, "total_clicks": 1373,
    "ctr": 1.33, "cpc": 239, "cpm": 3185, "total_inquiries": 9, "cpa": 36455,
    "total_regulars": 96, "cpr": 3418, "total_coupons": 112, "cp_coupon": 2929,
}
_INSIGHTS = {
    "conclusion": "노출·클릭 정상, 클릭→문의 병목.",
    "good": "노출·클릭 단계 정상", "blocked": "클릭→문의 전환 낮음",
    "next_actions": ["소식글 CTA를 쿠폰 먼저로 재정비", "30~40대 여성 타겟 축소"],
    "experiments": [
        {"priority": "1", "change": "CTA 쿠폰 먼저", "success_criteria": "쿠폰 전환↑", "owner": "사장님", "schedule": "이번 주"},
    ],
    "judgment": {"expand": "CPA 기준 이하면 증액", "review": "기준 근처면 소재 재정의", "stop": "정체 시 중단"},
}
_FUNNEL = [
    {"label": "노출", "count": 103010, "cost_per": 3185, "cost_label": "1천회당"},
    {"label": "클릭", "count": 1373, "rate_label": "노출 대비", "rate": 1.33, "cost_per": 239, "cost_label": "1회당"},
]


class TestBuildSlidesHtml(unittest.TestCase):
    def test_returns_full_html_document(self):
        html = build_slides_html(_META, _KPI, _INSIGHTS, funnel_stages=_FUNNEL)
        self.assertTrue(html.lstrip().startswith("<!DOCTYPE html>"))
        self.assertIn("</html>", html)

    def test_contains_key_content(self):
        html = build_slides_html(_META, _KPI, _INSIGHTS, funnel_stages=_FUNNEL)
        self.assertIn("지니스안경", html)
        self.assertIn("328,095원", html)          # KPI 포맷
        self.assertIn("이렇게 하겠습니다", html)   # 액션 슬라이드
        self.assertIn("소식글 CTA를 쿠폰 먼저로 재정비", html)  # next action
        self.assertIn("판단 기준", html)
        self.assertIn("노출", html)                # 퍼널

    def test_segment_rows_render(self):
        seg = [{"label": "30-40 여성", "cost": 120000, "cpa": 9000, "verdict": "증액"}]
        html = build_slides_html(_META, _KPI, _INSIGHTS, segment_rows=seg)
        self.assertIn("세그먼트 심화", html)
        self.assertIn("30-40 여성", html)

    def test_empty_insights_still_valid(self):
        html = build_slides_html(_META, _KPI, {})
        self.assertIn("핵심 지표", html)           # 최소 표지+지표는 나온다
        self.assertNotIn("이렇게 하겠습니다", html)  # 액션 없으면 액션 슬라이드 생략

    def test_escapes_html(self):
        bad = dict(_INSIGHTS, conclusion="<script>alert(1)</script>")
        html = build_slides_html(_META, _KPI, bad)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
