"""Unit tests for app.ai.providers — mocked, no API keys needed."""
import os
import unittest
from unittest.mock import patch, MagicMock

try:
    import google.genai  # noqa: F401
    HAS_GOOGLE_GENAI = True
except ImportError:
    HAS_GOOGLE_GENAI = False


class TestClaudeProvider(unittest.TestCase):
    """ClaudeProvider tests with mocked anthropic SDK."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"})
    @patch("anthropic.Anthropic")
    def test_generate_text_returns_content(self, mock_anthropic_cls):
        """generate_text should return the text from the API response."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_block = MagicMock()
        mock_block.text = "AI가 작성한 보고서 내용입니다."
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response

        from app.ai.providers import ClaudeProvider
        provider = ClaudeProvider(api_key="test-key-123")
        result = provider.generate_text("테스트 프롬프트")

        self.assertEqual(result, "AI가 작성한 보고서 내용입니다.")
        mock_client.messages.create.assert_called_once_with(
            model=provider._model,
            max_tokens=4096,
            messages=[{"role": "user", "content": "테스트 프롬프트"}],
        )

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123", "CLAUDE_MODEL": "claude-sonnet-4-20250514"})
    @patch("anthropic.Anthropic")
    def test_respects_model_env_var(self, mock_anthropic_cls):
        """Should use CLAUDE_MODEL env var when set."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_block = MagicMock()
        mock_block.text = "ok"
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response

        from app.ai.providers import ClaudeProvider
        provider = ClaudeProvider(api_key="test-key-123")
        provider.generate_text("hello")

        self.assertEqual(provider._model, "claude-sonnet-4-20250514")

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"})
    @patch("anthropic.Anthropic")
    def test_explicit_model_overrides_env(self, mock_anthropic_cls):
        """Explicit model param should override env var."""
        mock_anthropic_cls.return_value = MagicMock()
        from app.ai.providers import ClaudeProvider
        provider = ClaudeProvider(api_key="test-key-123", model="custom-model")
        self.assertEqual(provider._model, "custom-model")

    @patch.dict(os.environ, {}, clear=True)
    def test_raises_without_api_key(self):
        """Should raise ValueError when ANTHROPIC_API_KEY is missing."""
        # Remove ANTHROPIC_API_KEY from env
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from app.ai.providers import ClaudeProvider
        with self.assertRaises(ValueError) as ctx:
            ClaudeProvider()
        self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"})
    @patch("anthropic.Anthropic")
    def test_custom_max_tokens(self, mock_anthropic_cls):
        """max_tokens parameter should be forwarded to API call."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_block = MagicMock()
        mock_block.text = "result"
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response

        from app.ai.providers import ClaudeProvider
        provider = ClaudeProvider(api_key="test-key-123", max_tokens=8192)
        provider.generate_text("prompt")

        call_kwargs = mock_client.messages.create.call_args[1]
        self.assertEqual(call_kwargs["max_tokens"], 8192)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"})
    @patch("anthropic.Anthropic")
    def test_system_prompt_passed_to_api(self, mock_anthropic_cls):
        """system_prompt should be forwarded as 'system' kwarg to Claude API."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_block = MagicMock()
        mock_block.text = "output"
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response

        from app.ai.providers import ClaudeProvider
        provider = ClaudeProvider(api_key="test-key-123")
        provider.generate_text("user prompt", system_prompt="내부 가이드")

        call_kwargs = mock_client.messages.create.call_args[1]
        self.assertEqual(call_kwargs["system"], "내부 가이드")
        self.assertEqual(call_kwargs["messages"][0]["content"], "user prompt")

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"})
    @patch("anthropic.Anthropic")
    def test_no_system_key_when_none(self, mock_anthropic_cls):
        """When system_prompt is None, 'system' key should not be in API call."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_block = MagicMock()
        mock_block.text = "ok"
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response

        from app.ai.providers import ClaudeProvider
        provider = ClaudeProvider(api_key="test-key-123")
        provider.generate_text("prompt")

        call_kwargs = mock_client.messages.create.call_args[1]
        self.assertNotIn("system", call_kwargs)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"})
    @patch("anthropic.Anthropic")
    def test_joins_multiple_text_blocks(self, mock_anthropic_cls):
        """generate_text should join all text blocks in response.content."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        block1 = MagicMock()
        block1.text = "첫 번째 "
        block2 = MagicMock(spec=[])  # no text attr
        block3 = MagicMock()
        block3.text = "세 번째 블록"
        mock_response = MagicMock()
        mock_response.content = [block1, block2, block3]
        mock_client.messages.create.return_value = mock_response

        from app.ai.providers import ClaudeProvider
        provider = ClaudeProvider(api_key="test-key-123")
        result = provider.generate_text("테스트")

        self.assertEqual(result, "첫 번째 세 번째 블록")

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"})
    @patch("anthropic.Anthropic")
    def test_api_error_wrapped_as_valueerror(self, mock_anthropic_cls):
        """SDK/network exceptions should be wrapped as ValueError."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = RuntimeError("connection refused")

        from app.ai.providers import ClaudeProvider
        provider = ClaudeProvider(api_key="test-key-123")
        with self.assertRaises(ValueError) as ctx:
            provider.generate_text("prompt")
        self.assertIn("Claude API 호출 실패", str(ctx.exception))


@unittest.skipUnless(HAS_GOOGLE_GENAI, "google-genai not installed")
class TestGeminiProvider(unittest.TestCase):
    """GeminiProvider tests with mocked google-genai SDK."""

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-gemini-key"})
    @patch("google.genai.Client")
    def test_generate_text_returns_content(self, mock_client_cls):
        """generate_text should return text from the Gemini response."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "Gemini가 작성한 기획서입니다."
        mock_client.models.generate_content.return_value = mock_response

        from app.ai.providers import GeminiProvider
        provider = GeminiProvider(api_key="test-gemini-key")
        result = provider.generate_text("기획서 작성해줘")

        self.assertEqual(result, "Gemini가 작성한 기획서입니다.")
        mock_client.models.generate_content.assert_called_once_with(
            model=provider._model,
            contents="기획서 작성해줘",
        )

    @patch.dict(os.environ, {"GEMINI_API_KEY": "key", "GEMINI_MODEL": "gemini-2.0-flash"})
    @patch("google.genai.Client")
    def test_respects_model_env_var(self, mock_client_cls):
        """Should use GEMINI_MODEL env var when set."""
        mock_client_cls.return_value = MagicMock()
        from app.ai.providers import GeminiProvider
        provider = GeminiProvider(api_key="key")
        self.assertEqual(provider._model, "gemini-2.0-flash")

    @patch.dict(os.environ, {}, clear=True)
    def test_raises_without_api_key(self):
        """Should raise ValueError when GEMINI_API_KEY is missing."""
        os.environ.pop("GEMINI_API_KEY", None)
        from app.ai.providers import GeminiProvider
        with self.assertRaises(ValueError) as ctx:
            GeminiProvider()
        self.assertIn("GEMINI_API_KEY", str(ctx.exception))

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-gemini-key"})
    @patch("google.genai.Client")
    def test_system_prompt_passed_as_config(self, mock_client_cls):
        """system_prompt should be passed via GenerateContentConfig."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "output"
        mock_client.models.generate_content.return_value = mock_response

        from app.ai.providers import GeminiProvider
        provider = GeminiProvider(api_key="test-gemini-key")
        provider.generate_text("user prompt", system_prompt="내부 가이드")

        call_kwargs = mock_client.models.generate_content.call_args[1]
        self.assertEqual(call_kwargs["contents"], "user prompt")
        self.assertIn("config", call_kwargs)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-gemini-key"})
    @patch("google.genai.Client")
    def test_no_config_when_no_system_prompt(self, mock_client_cls):
        """When system_prompt is None, config should not be in API call."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "ok"
        mock_client.models.generate_content.return_value = mock_response

        from app.ai.providers import GeminiProvider
        provider = GeminiProvider(api_key="test-gemini-key")
        provider.generate_text("prompt")

        call_kwargs = mock_client.models.generate_content.call_args[1]
        self.assertNotIn("config", call_kwargs)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-gemini-key"})
    @patch("google.genai.Client")
    def test_api_error_wrapped_as_valueerror(self, mock_client_cls):
        """SDK/network exceptions should be wrapped as ValueError."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.side_effect = RuntimeError("timeout")

        from app.ai.providers import GeminiProvider
        provider = GeminiProvider(api_key="test-gemini-key")
        with self.assertRaises(ValueError) as ctx:
            provider.generate_text("prompt")
        self.assertIn("Gemini API 호출 실패", str(ctx.exception))


class TestGetProvider(unittest.TestCase):
    """Tests for the get_provider factory function."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"})
    @patch("anthropic.Anthropic")
    def test_returns_claude_provider(self, mock_cls):
        """get_provider('claude') should return ClaudeProvider."""
        mock_cls.return_value = MagicMock()
        from app.ai.providers import get_provider, ClaudeProvider
        provider = get_provider("claude")
        self.assertIsInstance(provider, ClaudeProvider)

    @unittest.skipUnless(HAS_GOOGLE_GENAI, "google-genai not installed")
    @patch.dict(os.environ, {"GEMINI_API_KEY": "key"})
    @patch("google.genai.Client")
    def test_returns_gemini_provider(self, mock_cls):
        """get_provider('gemini') should return GeminiProvider."""
        mock_cls.return_value = MagicMock()
        from app.ai.providers import get_provider, GeminiProvider
        provider = get_provider("gemini")
        self.assertIsInstance(provider, GeminiProvider)

    def test_raises_on_unknown_engine(self):
        """get_provider with unknown name should raise ValueError."""
        from app.ai.providers import get_provider
        with self.assertRaises(ValueError) as ctx:
            get_provider("gpt4")
        self.assertIn("gpt4", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
