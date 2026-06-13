"""히트맵 색상 보간/스타일 순수 함수 테스트."""
from __future__ import annotations

from unittest import TestCase

from app.pages.analysis import _cpa_heat_style, _lerp_hex, _HEAT_LOW, _HEAT_HIGH


class TestLerpHex(TestCase):
    def test_endpoints(self):
        self.assertEqual(_lerp_hex(_HEAT_LOW, _HEAT_HIGH, 0.0), "#fbede0")
        self.assertEqual(_lerp_hex(_HEAT_LOW, _HEAT_HIGH, 1.0), "#b04f2f")

    def test_clamps_out_of_range(self):
        self.assertEqual(_lerp_hex(_HEAT_LOW, _HEAT_HIGH, -5), "#fbede0")
        self.assertEqual(_lerp_hex(_HEAT_LOW, _HEAT_HIGH, 5), "#b04f2f")


class TestCpaHeatStyle(TestCase):
    def test_low_cpa_is_light_with_dark_text(self):
        bg, fg = _cpa_heat_style(1000, 1000, 5000)
        self.assertEqual(bg, "#fbede0")
        self.assertEqual(fg, "#1A1A2E")

    def test_high_cpa_is_dark_with_white_text(self):
        bg, fg = _cpa_heat_style(5000, 1000, 5000)
        self.assertEqual(bg, "#b04f2f")
        self.assertEqual(fg, "#FFFFFF")

    def test_zero_cpa_is_neutral(self):
        self.assertEqual(_cpa_heat_style(0, 1000, 5000), ("#F1F3F7", "#9AA3B2"))

    def test_single_value_range_does_not_divide_by_zero(self):
        # lo == hi → t=0 (light), 크래시 없음
        bg, fg = _cpa_heat_style(3000, 3000, 3000)
        self.assertEqual(bg, "#fbede0")
