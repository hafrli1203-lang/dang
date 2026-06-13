# -*- coding: utf-8 -*-
"""project.py 순수 헬퍼 테스트 — 월 파싱/라벨/예산축약/타겟요약."""

import unittest

from app.pages.project import (
    _month_key,
    _campaign_label,
    _fmt_budget,
    _targeting_summary,
)


class TestMonthKey(unittest.TestCase):
    def test_parses_month_from_campaign_name(self):
        self.assertEqual(_month_key({"campaign_name": "4월 변색렌즈"}), (4, "4월"))

    def test_parses_two_digit_month(self):
        self.assertEqual(_month_key({"campaign_name": "12월 행사"}), (12, "12월"))

    def test_falls_back_to_period(self):
        self.assertEqual(
            _month_key({"campaign_name": "변색렌즈", "period": "2026.05.01~05.31"}),
            (5, "5월"),
        )

    def test_no_month_is_etc(self):
        self.assertEqual(_month_key({"campaign_name": "블루라이트0원"}), (99, "기타"))

    def test_invalid_month_ignored(self):
        self.assertEqual(_month_key({"campaign_name": "13월 이상"}), (99, "기타"))


class TestCampaignLabel(unittest.TestCase):
    def test_strips_leading_month(self):
        self.assertEqual(_campaign_label({"campaign_name": "4월 변색렌즈"}, "4월"), "변색렌즈")

    def test_keeps_when_etc(self):
        self.assertEqual(_campaign_label({"campaign_name": "블루라이트0원"}, "기타"), "블루라이트0원")

    def test_empty_is_placeholder(self):
        self.assertEqual(_campaign_label({"campaign_name": ""}, "4월"), "캠페인명 미입력")

    def test_month_only_keeps_original(self):
        # 월만 있고 나머지가 비면 원본 유지
        self.assertEqual(_campaign_label({"campaign_name": "4월"}, "4월"), "4월")


class TestFmtBudget(unittest.TestCase):
    def test_man_round(self):
        self.assertEqual(_fmt_budget("300000"), "30만")
        self.assertEqual(_fmt_budget("300,000"), "30만")
        self.assertEqual(_fmt_budget("300,000원"), "30만")

    def test_man_fraction(self):
        self.assertEqual(_fmt_budget("15000"), "1.5만")

    def test_first_number_from_complex(self):
        self.assertEqual(_fmt_budget("월예산 300,000원 / 일예산 20,000원"), "30만")

    def test_small_number(self):
        self.assertEqual(_fmt_budget("5000"), "5,000")

    def test_empty(self):
        self.assertEqual(_fmt_budget(""), "")


class TestTargetingSummary(unittest.TestCase):
    def test_full(self):
        s = _targeting_summary({
            "target_radius_km": "5",
            "target_gender": "여성",
            "target_age": "35~39,40~44,55~59",
            "bid_type": "자동 입찰",
            "coupon_info": "변색렌즈 0원",
        })
        self.assertEqual(s, "5km · 여성 · 35~39~55~59 · 자동 입찰 · 쿠폰")

    def test_single_age(self):
        self.assertEqual(_targeting_summary({"target_age": "20~24"}), "20~24")

    def test_radius_already_km(self):
        self.assertEqual(_targeting_summary({"target_radius_km": "5km"}), "5km")

    def test_empty(self):
        self.assertEqual(_targeting_summary({}), "")


if __name__ == "__main__":
    unittest.main()
