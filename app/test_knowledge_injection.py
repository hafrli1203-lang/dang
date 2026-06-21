# -*- coding: utf-8 -*-
"""교재 지식 + 실전 운영 플레이북이 실제 기획 프롬프트(system guide)까지 도달하는지 잠금.

사용자 지시: 교재는 요약이 아니라 원문 전문 주입(KNOWLEDGE_MODE=full 기본),
실전 고수 플레이북(연령 찢기·자동수동 페어·변수통제)은 모든 scope에 최우선 주입.
"""
import unittest

from app import knowledge
from app.ai_engine import build_strategy_prompt, build_ad_settings_prompt, build_report_prompt, calc_kpi

# 플레이북 핵심 개념 토큰(반드시 프롬프트에 들어가야 함)
_PLAYBOOK_TOKENS = ["머신러닝이 없다", "연령", "자동", "수동", "변수"]


class TestPlaybookInjection(unittest.TestCase):
    def test_playbook_loaded(self):
        self.assertIn("머신러닝이 없다", knowledge._PLAYBOOK)
        self.assertIn("수동", knowledge._PLAYBOOK)
        self.assertIn("자동", knowledge._PLAYBOOK)

    def test_all_scopes_include_playbook(self):
        for scope in ["strategy", "content", "setting", "report", "full"]:
            block = knowledge.domain_knowledge(scope)
            self.assertIn("머신러닝이 없다", block, f"{scope} scope에 플레이북 누락")

    def test_strategy_guide_carries_playbook(self):
        guide, _prompt = build_strategy_prompt({"name": "X", "industry": "안경원", "region": "공주"})
        for tok in _PLAYBOOK_TOKENS:
            self.assertIn(tok, guide, f"전략 system guide에 '{tok}' 누락")

    def test_ad_settings_guide_carries_playbook(self):
        guide, _prompt = build_ad_settings_prompt({"name": "X", "industry": "안경원", "region": "공주"})
        self.assertIn("머신러닝이 없다", guide)
        self.assertIn("자동", guide)

    def test_report_guide_carries_playbook(self):
        rows = [{"period_label": "D1", "cost": 1000, "impressions": 100, "clicks": 5,
                 "inquiries": 0, "regulars": 0, "coupons": 1}]
        # build_report_prompt는 user prompt만 반환 — guide는 SYSTEM_GUIDE_REPORT+domain_knowledge
        from app.ai_engine import SYSTEM_GUIDE_REPORT
        guide = SYSTEM_GUIDE_REPORT + knowledge.domain_knowledge("report")
        self.assertIn("머신러닝이 없다", guide)


if __name__ == "__main__":
    unittest.main()
