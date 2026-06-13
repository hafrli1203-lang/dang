"""Unit tests for app.ai.coordination — mocked, no API keys needed."""
import unittest
from unittest.mock import MagicMock, patch


class TestBuildSynthesisPrompt(unittest.TestCase):
    def test_includes_both_drafts_and_label(self):
        from app.ai.coordination import build_synthesis_prompt
        system, user = build_synthesis_prompt("기획 콘텐츠", "초안A내용", "초안B내용")
        self.assertIn("초안A내용", user)
        self.assertIn("초안B내용", user)
        self.assertIn("기획 콘텐츠", user)
        # system prompt가 병합 편집자 역할을 지시해야 함
        self.assertIn("통합", system)

    def test_handles_empty_draft_placeholder(self):
        from app.ai.coordination import build_synthesis_prompt
        _system, user = build_synthesis_prompt("작업", "", "")
        self.assertIn("초안 없음", user)


class TestSynthesize(unittest.TestCase):
    def test_calls_provider_once_with_both_drafts(self):
        from app.ai import coordination
        mock_provider = MagicMock()
        mock_provider.generate_text.return_value = "통합된 결과물"
        with patch.object(coordination, "get_provider", return_value=mock_provider) as gp:
            result = coordination.synthesize("초안A", "초안B", "기획", engine="claude")
        self.assertEqual(result, "통합된 결과물")
        gp.assert_called_once_with("claude")
        mock_provider.generate_text.assert_called_once()
        # 종합 프롬프트에 두 초안이 모두 포함되어야 함
        call_args = mock_provider.generate_text.call_args
        self.assertIn("초안A", call_args[0][0])
        self.assertIn("초안B", call_args[0][0])

    def test_returns_other_when_one_draft_empty(self):
        """한쪽 초안이 비면 종합 호출 없이 나머지를 그대로 반환(부분 실패 흡수)."""
        from app.ai import coordination
        with patch.object(coordination, "get_provider") as gp:
            result = coordination.synthesize("", "초안B만 있음", "작업")
        self.assertEqual(result, "초안B만 있음")
        gp.assert_not_called()

    def test_raises_when_both_empty(self):
        from app.ai import coordination
        with self.assertRaises(ValueError):
            coordination.synthesize("", "", "작업")


class TestCoordinateGenerate(unittest.IsolatedAsyncioTestCase):
    async def test_parallel_drafts_then_synthesize(self):
        """Claude·GPT 초안을 병렬 생성 후 종합본을 반환."""
        import asyncio
        from app.ai import coordination

        claude_p = MagicMock()
        claude_p.generate_text.return_value = "클로드 초안"
        gpt_p = MagicMock()
        gpt_p.generate_text.return_value = "GPT 초안"

        loop = asyncio.get_running_loop()
        with patch.object(coordination, "get_provider", return_value=claude_p), \
             patch("app.ai.providers.OpenAIProvider", return_value=gpt_p), \
             patch.object(coordination, "synthesize", return_value="최종 종합본") as syn:
            result = await coordination.coordinate_generate(
                loop, "프롬프트", "시스템가이드", "전략 분석",
            )
        self.assertEqual(result, "최종 종합본")
        claude_p.generate_text.assert_called_once()
        gpt_p.generate_text.assert_called_once()
        # synthesize에 두 초안이 전달되어야 함
        syn.assert_called_once()
        self.assertEqual(syn.call_args[0][0], "클로드 초안")
        self.assertEqual(syn.call_args[0][1], "GPT 초안")


if __name__ == "__main__":
    unittest.main()
