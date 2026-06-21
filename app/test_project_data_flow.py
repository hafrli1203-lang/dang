# -*- coding: utf-8 -*-
"""프로젝트 자료(타겟·입찰·예산·현재 소재·쿠폰)가 기획 프롬프트에 반영되는지 회귀 잠금.

이전엔 원클릭 경로에서 타게팅/쿠폰/현재광고/캠페인명 8개 필드가 누락됐다.
project_setting_block 주입으로 위자드/원클릭 무관하게 반영되어야 한다.
"""
import unittest

from app.ai_engine import (
    project_setting_block,
    build_strategy_prompt,
    build_planning_prompt,
    build_ad_settings_prompt,
)


_FULL = {
    "name": "지니스안경", "campaign_name": "MK_CAMP", "industry": "안경원", "region": "공주",
    "goal": "단골", "budget": "30만원", "period": "4월", "benefits": "변색렌즈 0원",
    "target_radius_km": "3", "target_gender": "여성", "target_age": "30-50",
    "bid_type": "수동", "daily_budget": "10000", "ad_titles": "MK_TITLE", "coupon_info": "MK_COUPON",
}
# 원클릭 경로(타게팅 정보가 프롬프트에 반드시 들어가야 하는 필드)
_TARGETING = ["MK_CAMP", "3km", "여성", "30-50", "수동", "10000원", "MK_TITLE", "MK_COUPON"]


class TestProjectSettingBlock(unittest.TestCase):
    def test_block_contains_all_setting_fields(self):
        blk = project_setting_block(_FULL)
        for token in ["3km", "여성", "30-50", "수동", "10000원", "MK_CAMP", "MK_TITLE", "MK_COUPON"]:
            self.assertIn(token, blk)

    def test_empty_project_returns_blank(self):
        self.assertEqual(project_setting_block({}), "")
        self.assertEqual(project_setting_block({"name": "x", "industry": "카페"}), "")

    def test_strategy_reflects_targeting_via_project_only(self):
        # current_ad 없이(원클릭) project만으로도 타게팅이 들어가야 한다
        _g, prompt = build_strategy_prompt(_FULL)
        for token in _TARGETING:
            self.assertIn(token, prompt, f"전략 프롬프트에 {token} 누락")

    def test_planning_reflects_targeting_via_project_only(self):
        _g, prompt = build_planning_prompt(_FULL, category="default", engine="claude")
        for token in _TARGETING:
            self.assertIn(token, prompt, f"소식글 프롬프트에 {token} 누락")

    def test_ad_settings_reflects_targeting(self):
        _g, prompt = build_ad_settings_prompt(_FULL)
        for token in ["3km", "여성", "30-50", "수동", "10000원", "MK_COUPON"]:
            self.assertIn(token, prompt, f"세팅 프롬프트에 {token} 누락")


if __name__ == "__main__":
    unittest.main()
