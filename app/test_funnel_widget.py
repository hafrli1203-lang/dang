# -*- coding: utf-8 -*-
"""공용 퍼널 위젯 — '있는 것만 솔직히' 단계 구성 로직 테스트(순수 함수만)."""
import unittest

from app.funnel_widget import (
    build_funnel_stages,
    _worst_dropoff,
    _shape_sizes,
)


class TestBuildFunnelStages(unittest.TestCase):
    def _conv(self):
        return {
            "inquiries": (10, 2.0, 1000.0),
            "regulars": (5, 1.0, 2000.0),
            "coupons": (3, 0.6, 3000.0),
        }

    def test_full_conversion_shows_five_stages(self):
        stages, has_conv = build_funnel_stages(
            impressions=1000, clicks=100, ctr=10.0, cpc=50, cpm=500,
            conversions=self._conv(),
            available={"impressions", "clicks", "inquiries", "regulars", "coupons"},
        )
        labels = [s["label"] for s in stages]
        self.assertEqual(labels, ["노출", "클릭", "문의", "단골", "쿠폰"])
        self.assertTrue(has_conv)

    def test_no_conversion_shows_two_stages(self):
        stages, has_conv = build_funnel_stages(
            impressions=1000, clicks=100, ctr=10.0, cpc=50, cpm=500,
            conversions={}, available={"impressions", "clicks"},
        )
        self.assertEqual([s["label"] for s in stages], ["노출", "클릭"])
        self.assertFalse(has_conv)  # 전환 미측정 → 안내문 경로

    def test_partial_conversion_only_measured_stages(self):
        stages, has_conv = build_funnel_stages(
            impressions=1000, clicks=100, ctr=10.0, cpc=50, cpm=500,
            conversions=self._conv(),
            available={"impressions", "clicks", "inquiries"},  # 단골/쿠폰 미측정
        )
        self.assertEqual([s["label"] for s in stages], ["노출", "클릭", "문의"])
        self.assertTrue(has_conv)

    def test_action_fallback_when_only_total_actions(self):
        # 구체 전환 컬럼은 없지만 총행동만 잡히는 레거시 양식 → '행동' 한 단계
        stages, has_conv = build_funnel_stages(
            impressions=1000, clicks=100, ctr=10.0, cpc=50, cpm=500,
            conversions={}, available={"impressions", "clicks", "actions"},
            action_fallback=(8, 8.0, 1250.0),
        )
        self.assertEqual([s["label"] for s in stages], ["노출", "클릭", "행동"])
        self.assertTrue(has_conv)

    def test_action_fallback_ignored_when_zero(self):
        stages, has_conv = build_funnel_stages(
            impressions=1000, clicks=100, ctr=10.0, cpc=50, cpm=500,
            conversions={}, available={"impressions", "clicks", "actions"},
            action_fallback=(0, 0.0, 0.0),
        )
        self.assertEqual([s["label"] for s in stages], ["노출", "클릭"])
        self.assertFalse(has_conv)


class TestFunnelHelpers(unittest.TestCase):
    def test_worst_dropoff_picks_biggest(self):
        stages = [
            {"label": "노출", "count": 1000},
            {"label": "클릭", "count": 100},   # 90% drop
            {"label": "문의", "count": 90},    # 10% drop
        ]
        name, pct = _worst_dropoff(stages)
        self.assertEqual(name, "노출→클릭")
        self.assertAlmostEqual(pct, 90.0, places=1)

    def test_shape_sizes_monotonic_decreasing(self):
        sizes = _shape_sizes(5)
        self.assertEqual(len(sizes), 5)
        self.assertEqual(sizes[0], 100.0)
        self.assertTrue(all(a >= b for a, b in zip(sizes, sizes[1:])))


if __name__ == "__main__":
    unittest.main()
