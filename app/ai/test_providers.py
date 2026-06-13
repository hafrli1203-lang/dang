"""Unit tests for app.ai.providers — mocked, no API keys needed."""
import os
import unittest
from unittest.mock import patch, MagicMock

try:
    import openai  # noqa: F401
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


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
            max_tokens=16384,
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

    @patch("app.ai.providers.time.sleep")
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"})
    @patch("anthropic.Anthropic")
    def test_api_error_wrapped_as_valueerror(self, mock_anthropic_cls, _mock_sleep):
        """SDK/network exceptions should be wrapped as ValueError."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = RuntimeError("connection refused")

        from app.ai.providers import ClaudeProvider
        provider = ClaudeProvider(api_key="test-key-123")
        with self.assertRaises(ValueError) as ctx:
            provider.generate_text("prompt")
        self.assertIn("Claude API 호출 실패", str(ctx.exception))


@unittest.skipUnless(HAS_OPENAI, "openai not installed")
class TestOpenAIProvider(unittest.TestCase):
    """OpenAIProvider tests with mocked openai SDK."""

    def _mock_chat(self, mock_client, text):
        msg = MagicMock()
        msg.message.content = text
        resp = MagicMock()
        resp.choices = [msg]
        mock_client.chat.completions.create.return_value = resp

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"})
    @patch("openai.OpenAI")
    def test_generate_text_returns_content(self, mock_openai_cls):
        """generate_text should return text from the chat completion."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        self._mock_chat(mock_client, "GPT가 작성한 기획서입니다.")

        from app.ai.providers import OpenAIProvider
        provider = OpenAIProvider(api_key="test-openai-key")
        result = provider.generate_text("기획서 작성해줘")

        self.assertEqual(result, "GPT가 작성한 기획서입니다.")
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_kwargs["model"], provider._model)
        self.assertEqual(call_kwargs["messages"][-1]["content"], "기획서 작성해줘")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "key", "OPENAI_MODEL": "gpt-4.1"})
    @patch("openai.OpenAI")
    def test_respects_model_env_var(self, mock_openai_cls):
        """Should use OPENAI_MODEL env var when set."""
        mock_openai_cls.return_value = MagicMock()
        from app.ai.providers import OpenAIProvider
        provider = OpenAIProvider(api_key="key")
        self.assertEqual(provider._model, "gpt-4.1")

    @patch.dict(os.environ, {}, clear=True)
    def test_raises_without_api_key(self):
        """Should raise ValueError when OPENAI_API_KEY is missing."""
        os.environ.pop("OPENAI_API_KEY", None)
        from app.ai.providers import OpenAIProvider
        with self.assertRaises(ValueError) as ctx:
            OpenAIProvider()
        self.assertIn("OPENAI_API_KEY", str(ctx.exception))

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"})
    @patch("openai.OpenAI")
    def test_system_prompt_passed_as_system_message(self, mock_openai_cls):
        """system_prompt should be passed as the system message."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        self._mock_chat(mock_client, "output")

        from app.ai.providers import OpenAIProvider
        provider = OpenAIProvider(api_key="test-openai-key")
        provider.generate_text("user prompt", system_prompt="내부 가이드")

        msgs = mock_client.chat.completions.create.call_args[1]["messages"]
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[0]["content"], "내부 가이드")
        self.assertEqual(msgs[-1]["content"], "user prompt")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"})
    @patch("openai.OpenAI")
    def test_max_completion_tokens_in_request(self, mock_openai_cls):
        """Request should set max_completion_tokens (not the deprecated max_tokens)."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        self._mock_chat(mock_client, "ok")

        from app.ai.providers import OpenAIProvider
        provider = OpenAIProvider(api_key="test-openai-key")
        provider.generate_text("prompt")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_kwargs["max_completion_tokens"], 16384)

    @patch("app.ai.providers.time.sleep")
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"})
    @patch("openai.OpenAI")
    def test_api_error_wrapped_as_valueerror(self, mock_openai_cls, _mock_sleep):
        """SDK/network exceptions should be wrapped as ValueError."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RuntimeError("timeout")

        from app.ai.providers import OpenAIProvider
        provider = OpenAIProvider(api_key="test-openai-key")
        with self.assertRaises(ValueError) as ctx:
            provider.generate_text("prompt")
        self.assertIn("OpenAI API 호출 실패", str(ctx.exception))

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"})
    @patch("openai.OpenAI")
    def test_empty_response_raises_valueerror(self, mock_openai_cls):
        """Empty content should raise ValueError with clear message."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        self._mock_chat(mock_client, "")

        from app.ai.providers import OpenAIProvider
        provider = OpenAIProvider(api_key="test-openai-key")
        with self.assertRaises(ValueError) as ctx:
            provider.generate_text("prompt")
        self.assertIn("비어 있습니다", str(ctx.exception))


@unittest.skipUnless(HAS_OPENAI, "openai not installed")
class TestOpenAIImageGeneration(unittest.TestCase):
    """OpenAIProvider.generate_image tests with mocked openai SDK."""

    def _mock_image(self, mock_client, raw: bytes, *, edit=False):
        import base64
        item = MagicMock()
        item.b64_json = base64.b64encode(raw).decode()
        resp = MagicMock()
        resp.data = [item]
        target = mock_client.images.edit if edit else mock_client.images.generate
        target.return_value = resp

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"})
    @patch("openai.OpenAI")
    def test_generate_image_text_only(self, mock_openai_cls):
        """Text-only prompt should produce (bytes, mime_type) tuple via images.generate."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        self._mock_image(mock_client, b"\x89PNG_FAKE")

        from app.ai.providers import OpenAIProvider
        provider = OpenAIProvider(api_key="test-openai-key")
        data, mime = provider.generate_image("당근마켓 광고 썸네일")

        self.assertEqual(data, b"\x89PNG_FAKE")
        self.assertEqual(mime, "image/png")
        mock_client.images.generate.assert_called_once()
        mock_client.images.edit.assert_not_called()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"})
    @patch("openai.OpenAI")
    def test_generate_image_with_reference_uses_edit(self, mock_openai_cls):
        """reference_image should route through images.edit."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        self._mock_image(mock_client, b"IMG", edit=True)

        from app.ai.providers import OpenAIProvider
        provider = OpenAIProvider(api_key="test-openai-key")
        data, mime = provider.generate_image(
            "prompt", reference_image=b"REF_IMG", reference_mime="image/jpeg"
        )

        self.assertEqual(data, b"IMG")
        mock_client.images.edit.assert_called_once()
        mock_client.images.generate.assert_not_called()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"})
    @patch("openai.OpenAI")
    def test_no_image_in_response(self, mock_openai_cls):
        """Should raise ValueError when response data is empty."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        resp = MagicMock()
        resp.data = []
        mock_client.images.generate.return_value = resp

        from app.ai.providers import OpenAIProvider
        provider = OpenAIProvider(api_key="test-openai-key")
        with self.assertRaises(ValueError) as ctx:
            provider.generate_image("prompt")
        self.assertIn("비어 있습니다", str(ctx.exception))

    @patch.dict(os.environ, {"OPENAI_API_KEY": "key", "OPENAI_IMAGE_MODEL": "gpt-image-custom"})
    @patch("openai.OpenAI")
    def test_respects_image_model_env_var(self, mock_openai_cls):
        """Should use OPENAI_IMAGE_MODEL env var when set."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        self._mock_image(mock_client, b"IMG")

        from app.ai.providers import OpenAIProvider
        provider = OpenAIProvider(api_key="key")
        provider.generate_image("prompt")

        call_kwargs = mock_client.images.generate.call_args[1]
        self.assertEqual(call_kwargs["model"], "gpt-image-custom")

    @patch("app.ai.providers.time.sleep")
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"})
    @patch("openai.OpenAI")
    def test_api_error_wrapped(self, mock_openai_cls, _mock_sleep):
        """SDK exceptions should be wrapped as ValueError."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.images.generate.side_effect = RuntimeError("network error")

        from app.ai.providers import OpenAIProvider
        provider = OpenAIProvider(api_key="test-openai-key")
        with self.assertRaises(ValueError) as ctx:
            provider.generate_image("prompt")
        self.assertIn("OpenAI 이미지 생성 실패", str(ctx.exception))


class TestGetProvider(unittest.TestCase):
    """Tests for the get_provider factory function."""

    @patch.dict(os.environ, {"CLAUDE_BACKEND": "cli"}, clear=False)
    def test_returns_claude_cli_provider_by_default(self):
        """get_provider('claude') uses CLI by default (no API key needed)."""
        from app.ai.providers import get_provider, ClaudeCliProvider
        provider = get_provider("claude")
        self.assertIsInstance(provider, ClaudeCliProvider)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key", "CLAUDE_BACKEND": "api"})
    @patch("anthropic.Anthropic")
    def test_returns_claude_api_provider_when_backend_set(self, mock_cls):
        """CLAUDE_BACKEND=api forces the legacy ClaudeProvider path."""
        mock_cls.return_value = MagicMock()
        from app.ai.providers import get_provider, ClaudeProvider
        provider = get_provider("claude")
        self.assertIsInstance(provider, ClaudeProvider)

    def test_returns_claude_cli_provider_explicit(self):
        """Explicit 'claude-cli' returns ClaudeCliProvider regardless of env."""
        from app.ai.providers import get_provider, ClaudeCliProvider
        provider = get_provider("claude-cli")
        self.assertIsInstance(provider, ClaudeCliProvider)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"})
    @patch("anthropic.Anthropic")
    def test_returns_claude_api_provider_explicit(self, mock_cls):
        """Explicit 'claude-api' returns ClaudeProvider regardless of env."""
        mock_cls.return_value = MagicMock()
        from app.ai.providers import get_provider, ClaudeProvider
        provider = get_provider("claude-api")
        self.assertIsInstance(provider, ClaudeProvider)

    @unittest.skipUnless(HAS_OPENAI, "openai not installed")
    @patch.dict(os.environ, {"OPENAI_API_KEY": "key"})
    @patch("openai.OpenAI")
    def test_returns_openai_provider(self, mock_cls):
        """get_provider('gpt') should return OpenAIProvider."""
        mock_cls.return_value = MagicMock()
        from app.ai.providers import get_provider, OpenAIProvider
        provider = get_provider("gpt")
        self.assertIsInstance(provider, OpenAIProvider)

    def test_raises_on_unknown_engine(self):
        """get_provider with unknown name should raise ValueError."""
        from app.ai.providers import get_provider
        with self.assertRaises(ValueError) as ctx:
            get_provider("gpt4")
        self.assertIn("gpt4", str(ctx.exception))


class TestRetryApiCall(unittest.TestCase):
    """retry_api_call utility tests."""

    def test_succeeds_first_try(self):
        from app.ai.providers import retry_api_call
        result = retry_api_call(lambda: "ok", label="test")
        self.assertEqual(result, "ok")

    @patch("app.ai.providers.time.sleep")
    def test_retries_on_transient_error(self, mock_sleep):
        from app.ai.providers import retry_api_call
        call_count = 0
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("503 service unavailable")
            return "recovered"
        result = retry_api_call(flaky, max_retries=3, base_delay=1.0, label="test")
        self.assertEqual(result, "recovered")
        self.assertEqual(call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    def test_raises_immediately_on_permanent_error(self):
        from app.ai.providers import retry_api_call
        def bad_key():
            raise ValueError("401 unauthorized invalid api key")
        with self.assertRaises(ValueError):
            retry_api_call(bad_key, max_retries=3, label="test")

    @patch("app.ai.providers.time.sleep")
    def test_raises_after_max_retries(self, mock_sleep):
        from app.ai.providers import retry_api_call
        def always_fail():
            raise ConnectionError("429 rate limit exceeded")
        with self.assertRaises(ConnectionError):
            retry_api_call(always_fail, max_retries=2, base_delay=0.1, label="test")
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("app.ai.providers.time.sleep")
    def test_parses_retry_after_header(self, mock_sleep):
        from app.ai.providers import retry_api_call
        call_count = 0
        def rate_limited():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("429 Too Many Requests. Retry-After: 5")
            return "ok"
        result = retry_api_call(rate_limited, max_retries=3, label="test")
        self.assertEqual(result, "ok")
        mock_sleep.assert_called_once_with(5.0)


class TestIsTransient(unittest.TestCase):
    """_is_transient classification tests."""

    def test_transient_errors(self):
        from app.ai.providers import _is_transient
        self.assertTrue(_is_transient(Exception("429 rate limit")))
        self.assertTrue(_is_transient(Exception("503 service unavailable")))
        self.assertTrue(_is_transient(Exception("connection timeout")))
        self.assertTrue(_is_transient(Exception("resource_exhausted")))

    def test_permanent_errors(self):
        from app.ai.providers import _is_transient
        self.assertFalse(_is_transient(ValueError("invalid prompt format")))
        self.assertFalse(_is_transient(ValueError("401 unauthorized")))


class TestBaseProviderStreamDefault(unittest.TestCase):
    """BaseProvider.generate_text_stream() default fallback."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"})
    @patch("anthropic.Anthropic")
    def test_default_stream_yields_single_chunk(self, mock_anthropic_cls):
        """Default generate_text_stream yields full generate_text result as one chunk."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_block = MagicMock()
        mock_block.text = "전체 결과 텍스트"
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response

        from app.ai.providers import BaseProvider, ClaudeProvider
        # Use BaseProvider's default by calling it directly
        provider = ClaudeProvider(api_key="test-key-123")
        # Call the BASE class's default implementation explicitly
        chunks = list(BaseProvider.generate_text_stream(provider, "test"))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], "전체 결과 텍스트")


class TestClaudeProviderStream(unittest.TestCase):
    """ClaudeProvider.generate_text_stream() tests."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"})
    @patch("anthropic.Anthropic")
    def test_stream_yields_chunks(self, mock_anthropic_cls):
        """generate_text_stream should yield text chunks from SDK stream."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # Mock the stream context manager
        mock_stream = MagicMock()
        mock_stream.text_stream = iter(["청크1", "청크2", "청크3"])
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_client.messages.stream.return_value = mock_stream

        from app.ai.providers import ClaudeProvider
        provider = ClaudeProvider(api_key="test-key-123")
        chunks = list(provider.generate_text_stream("테스트", system_prompt="가이드"))
        self.assertEqual(chunks, ["청크1", "청크2", "청크3"])
        mock_client.messages.stream.assert_called_once()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"})
    @patch("anthropic.Anthropic")
    def test_stream_error_raises_valueerror(self, mock_anthropic_cls):
        """generate_text_stream should wrap SDK errors in ValueError."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.stream.side_effect = Exception("connection failed")

        from app.ai.providers import ClaudeProvider
        provider = ClaudeProvider(api_key="test-key-123")
        with self.assertRaises(ValueError) as ctx:
            list(provider.generate_text_stream("test"))
        self.assertIn("스트리밍 실패", str(ctx.exception))


@unittest.skipUnless(HAS_OPENAI, "openai not installed")
class TestOpenAIProviderStream(unittest.TestCase):
    """OpenAIProvider.generate_text_stream() tests."""

    @staticmethod
    def _chunk(text):
        c = MagicMock()
        delta = MagicMock()
        delta.content = text
        choice = MagicMock()
        choice.delta = delta
        c.choices = [choice]
        return c

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-456"})
    @patch("openai.OpenAI")
    def test_stream_yields_chunks(self, mock_openai_cls):
        """generate_text_stream should yield delta tokens from the stream."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = iter(
            [self._chunk("제안서 "), self._chunk("작성 중"), self._chunk("입니다.")]
        )

        from app.ai.providers import OpenAIProvider
        provider = OpenAIProvider(api_key="test-key-456")
        chunks = list(provider.generate_text_stream("테스트"))
        self.assertEqual(chunks, ["제안서 ", "작성 중", "입니다."])

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-456"})
    @patch("openai.OpenAI")
    def test_stream_skips_empty_chunks(self, mock_openai_cls):
        """generate_text_stream should skip chunks with empty delta content."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = iter(
            [self._chunk("내용"), self._chunk(None), self._chunk("추가")]
        )

        from app.ai.providers import OpenAIProvider
        provider = OpenAIProvider(api_key="test-key-456")
        chunks = list(provider.generate_text_stream("test"))
        self.assertEqual(chunks, ["내용", "추가"])


if __name__ == "__main__":
    unittest.main()
