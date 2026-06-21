# -*- coding: utf-8 -*-
"""커뮤니티 리서치 → 기획 연결 테스트 (선행 리서치가 기획 프롬프트에 주입되는지)."""
import unittest

from app.research.insight import format_research_insight
from app.research import saved_research
from app.ai_engine import build_strategy_prompt, build_planning_prompt


_SAMPLE = {
    "verdict": "가격 부담과 효과 의심이 핵심",
    "pain_points": ["렌즈 가격이 부담", "정말 효과 있나 의심"],
    "desires": ["오래 쓰는 렌즈", "눈 편한 제품"],
    "real_expressions": ["눈뽕 없는 렌즈", "이거 찐이에요?"],
    "offer_signals": ["1+1 행사에 반응"],
    "content_angles": ["가격 의심 정면돌파"],
    "hook_ideas": ["눈뽕 없는 그 렌즈"],
    "next_actions": ["가격표 공개"],
}


class TestFormatResearchInsight(unittest.TestCase):
    def test_empty_for_empty_or_non_dict(self):
        self.assertEqual(format_research_insight({}), "")
        self.assertEqual(format_research_insight(None), "")
        self.assertEqual(format_research_insight({"pain_points": [], "verdict": ""}), "")

    def test_summary_contains_voice(self):
        out = format_research_insight(_SAMPLE, "변색렌즈")
        self.assertIn("변색렌즈", out)
        self.assertIn("고충", out)
        self.assertIn("눈뽕 없는 렌즈", out)  # 실제 표현 포함
        self.assertIn("종합", out)


class TestResearchContext(unittest.TestCase):
    def setUp(self):
        # DB 의존 격리: 인메모리 fake로 save/get 대체
        self._store: dict = {}

        def _fake_save(pid, engine, content, content_type="planning"):
            self._store[(pid, content_type)] = {"content": content}
            return 1

        def _fake_get(pid, content_type="planning"):
            return self._store.get((pid, content_type))

        self._orig_save = saved_research.save_generated_content
        self._orig_get = saved_research.get_latest_content
        saved_research.save_generated_content = _fake_save
        saved_research.get_latest_content = _fake_get

    def tearDown(self):
        saved_research.save_generated_content = self._orig_save
        saved_research.get_latest_content = self._orig_get

    def test_no_saved_research_returns_blank(self):
        self.assertEqual(saved_research.research_context(999), "")
        self.assertEqual(saved_research.research_context(0), "")

    def test_save_then_context_roundtrip(self):
        ok = saved_research.save_research_insight(7, _SAMPLE, "변색렌즈")
        self.assertTrue(ok)
        block = saved_research.research_context(7)
        self.assertIn("커뮤니티 리서치", block)
        self.assertIn("눈뽕 없는 렌즈", block)

    def test_empty_insight_not_saved(self):
        self.assertFalse(saved_research.save_research_insight(7, {}, "x"))
        self.assertEqual(saved_research.research_context(7), "")


class TestBuilderInjection(unittest.TestCase):
    def test_strategy_prompt_includes_research_block(self):
        _guide, prompt = build_strategy_prompt(
            {"name": "지니스안경", "industry": "안경원", "region": "공주"},
            research_block="\n\n[커뮤니티 리서치]\n- 실제 표현: 눈뽕 없는 렌즈\n",
        )
        self.assertIn("커뮤니티 리서치", prompt)
        self.assertIn("눈뽕 없는 렌즈", prompt)

    def test_planning_prompt_includes_research_block(self):
        _guide, prompt = build_planning_prompt(
            {"name": "X", "industry": "안경원", "region": "공주"},
            category="default",
            research_block="\n\n[커뮤니티 리서치]\n- 고충: 가격 부담\n",
        )
        self.assertIn("커뮤니티 리서치", prompt)
        self.assertIn("가격 부담", prompt)

    def test_no_research_block_keeps_prompt_working(self):
        _guide, prompt = build_strategy_prompt({"name": "X", "industry": "카페", "region": "서울"})
        self.assertNotIn("커뮤니티 리서치 — 실제 고객의 목소리", prompt)


if __name__ == "__main__":
    unittest.main()
