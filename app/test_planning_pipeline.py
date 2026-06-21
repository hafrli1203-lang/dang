# -*- coding: utf-8 -*-
"""원클릭 통합 기획 파이프라인 통합 테스트 (QS-2).

AI·DB 호출을 가짜로 대체해(비용 0) 다음을 검증한다:
- 선행 리서치(research_context) 결과가 전략 프롬프트에 실제로 주입된다.
- 전략→소식글→세팅→제안서 4단계가 각 content_type으로 저장된다.
"""
import asyncio
import unittest

from app import planning_pipeline as PP
from app.research import competitor as COMP
from app.research import saved_research as SR


_RESEARCH_MARKER = "[[RESEARCH_VOICE_눈뽕없는렌즈]]"


class TestGenerateFullPlan(unittest.TestCase):
    def setUp(self):
        self.saved: list[tuple] = []
        self.strategy_prompt = {"text": ""}

        self._orig = {
            "get_project": PP.get_project,
            "save": PP.save_generated_content,
            "coordinate": PP.coordinate_generate,
            "get_provider": PP.get_provider,
            "repair": PP.repair_output,
            "wiki": PP.store_wiki.wiki_context,
            "competitor": COMP.competitor_context,
            "research": SR.research_context,
        }

        PP.get_project = lambda pid: {
            "id": pid, "name": "지니스안경", "industry": "안경원",
            "region": "공주", "benefits": "변색렌즈 0원", "budget": "30만원",
        }

        def _fake_save(pid, engine, content, content_type="planning"):
            self.saved.append((content_type, content))
            return len(self.saved)

        PP.save_generated_content = _fake_save

        async def _fake_coordinate(loop, prompt, guide, label, **kw):
            if label == "전략 분석":
                self.strategy_prompt["text"] = prompt
            return f"## 1. {label}\n생성된 내용"

        PP.coordinate_generate = _fake_coordinate

        class _FakeProvider:
            def generate_text(self, prompt, system_prompt=None):
                return "## 1. 소식글\n생성된 소식글 본문"

        PP.get_provider = lambda eng: _FakeProvider()
        PP.repair_output = lambda out, schema, engine="claude": out
        PP.store_wiki.wiki_context = lambda pid, project: ""
        COMP.competitor_context = lambda project, **kw: ""
        SR.research_context = lambda pid: _RESEARCH_MARKER

    def tearDown(self):
        PP.get_project = self._orig["get_project"]
        PP.save_generated_content = self._orig["save"]
        PP.coordinate_generate = self._orig["coordinate"]
        PP.get_provider = self._orig["get_provider"]
        PP.repair_output = self._orig["repair"]
        PP.store_wiki.wiki_context = self._orig["wiki"]
        COMP.competitor_context = self._orig["competitor"]
        SR.research_context = self._orig["research"]

    def test_pipeline_saves_four_stages_and_injects_research(self):
        result = asyncio.run(
            PP.generate_full_plan(42, engine="coordinate", with_thumbnail=False)
        )
        # 4단계 결과 반환
        for key in ("strategy", "content", "ad_settings", "proposal"):
            self.assertIn(key, result)
        # 4단계가 각 content_type으로 저장됨
        saved_types = [t for t, _ in self.saved]
        self.assertEqual(
            saved_types, ["strategy", "content", "ad_settings", "wizard_proposal"]
        )
        # 선행 리서치가 전략 프롬프트에 실제 주입됨(연결 단절 회귀 방지)
        self.assertIn(_RESEARCH_MARKER, self.strategy_prompt["text"])

    def test_missing_project_raises(self):
        PP.get_project = lambda pid: None
        with self.assertRaises(ValueError):
            asyncio.run(PP.generate_full_plan(999, with_thumbnail=False))


if __name__ == "__main__":
    unittest.main()
