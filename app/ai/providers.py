"""AI provider abstractions.

Provides a common synchronous interface so callers don't care which SDK is used.
Each provider is a plain class; async wrapping (run_in_executor) is the caller's job.

Usage:
    from app.ai.providers import get_provider
    provider = get_provider("claude")          # or "gemini"
    text = provider.generate_text(prompt)      # blocking call

Environment variables (all optional — keys raise ValueError at call time if missing):
    ANTHROPIC_API_KEY   — Anthropic secret key
    CLAUDE_MODEL        — model override  (default: claude-opus-4-6)
    GEMINI_API_KEY      — Google GenAI key
    GEMINI_MODEL        — model override  (default: gemini-3.1-pro-preview)
    GEMINI_IMAGE_MODEL  — image generation model (default: gemini-2.5-flash-image)
"""
from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from typing import Callable, Generator, TypeVar

from app.logger import get_logger

_log = get_logger("providers")

_T = TypeVar("_T")

# Transient error keywords for classification
_TRANSIENT_KEYWORDS = ("429", "rate", "limit", "timeout", "timed out", "503", "500",
                       "overloaded", "resource_exhausted", "unavailable", "connection")


def _is_transient(exc: Exception) -> bool:
    """Check if an exception is likely transient and retryable."""
    msg = str(exc).lower()
    # 404 NOT_FOUND is permanent — model doesn't exist, don't retry
    if "404" in msg or "not_found" in msg:
        return False
    return any(kw in msg for kw in _TRANSIENT_KEYWORDS)


def _parse_retry_after(exc: Exception) -> float | None:
    """Try to extract Retry-After seconds from exception."""
    msg = str(exc)
    import re
    match = re.search(r"[Rr]etry.?[Aa]fter[:\s]+(\d+)", msg)
    if match:
        return min(float(match.group(1)), 30.0)
    return None


def retry_api_call(
    fn: Callable[[], _T],
    *,
    max_retries: int = 3,
    base_delay: float = 2.0,
    label: str = "API",
) -> _T:
    """Execute fn with exponential backoff on transient errors.

    Args:
        fn: Zero-arg callable to retry.
        max_retries: Maximum retry attempts (default 3).
        base_delay: Initial delay in seconds (doubles each retry).
        label: Label for log messages.

    Returns:
        Result of fn().

    Raises:
        The last exception if all retries fail, or immediately for non-transient errors.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries or not _is_transient(exc):
                raise
            retry_after = _parse_retry_after(exc)
            delay = retry_after if retry_after else base_delay * (2 ** attempt)
            _log.warning(
                "%s 일시적 오류 (시도 %d/%d), %.1f초 후 재시도: %s",
                label, attempt + 1, max_retries + 1, delay, exc,
            )
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]  # unreachable but satisfies type checker


class BaseProvider(ABC):
    """Common interface for all AI providers."""

    @abstractmethod
    def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        """Send *prompt* to the model and return the generated text string.

        Args:
            prompt: User-visible prompt (data + section headings).
            system_prompt: Internal system instruction (톤·포맷 가이드).
                           Passed via the provider's system channel so that
                           the instruction text never appears in the output.
        """

    def generate_text_stream(
        self, prompt: str, *, system_prompt: str | None = None
    ) -> Generator[str, None, None]:
        """Yield text chunks as they arrive from the model.

        Default implementation calls generate_text() and yields the full result
        as a single chunk. Subclasses may override for true streaming.
        """
        yield self.generate_text(prompt, system_prompt=system_prompt)


class ClaudeProvider(BaseProvider):
    """Anthropic Claude via Messages API."""

    DEFAULT_MODEL = "claude-opus-4-6"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_tokens: int = 16384,
    ) -> None:
        import anthropic

        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to your .env file or environment."
            )
        self._model = model or os.getenv("CLAUDE_MODEL", self.DEFAULT_MODEL)
        self._max_tokens = max_tokens
        self._client = anthropic.Anthropic(api_key=self._api_key)

    def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        kwargs: dict = dict(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if system_prompt:
            kwargs["system"] = system_prompt
        try:
            _log.info("Claude API 호출 시작 (model=%s)", self._model)
            response = retry_api_call(
                lambda: self._client.messages.create(**kwargs),
                label="Claude",
            )
            _log.info("Claude API 호출 완료")
        except Exception as exc:
            _log.error("Claude API 호출 실패: %s", exc)
            raise ValueError(f"Claude API 호출 실패: {exc}") from exc
        return "".join(block.text for block in response.content if hasattr(block, "text"))

    def generate_text_stream(
        self, prompt: str, *, system_prompt: str | None = None
    ) -> Generator[str, None, None]:
        kwargs: dict = dict(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if system_prompt:
            kwargs["system"] = system_prompt
        try:
            _log.info("Claude 스트리밍 시작 (model=%s)", self._model)
            with self._client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    yield text
            _log.info("Claude 스트리밍 완료")
        except Exception as exc:
            _log.error("Claude 스트리밍 실패: %s", exc)
            raise ValueError(f"Claude 스트리밍 실패: {exc}") from exc


class GeminiProvider(BaseProvider):
    """Google Gemini via google-genai SDK."""

    DEFAULT_MODEL = "gemini-3.1-pro-preview"
    DEFAULT_IMAGE_MODEL = "gemini-2.5-flash-image"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        try:
            from google import genai
        except ImportError:
            raise ImportError(
                "google-genai 패키지가 설치되지 않았습니다. "
                "pip install google-genai 를 실행해주세요."
            ) from None

        self._api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Add it to your .env file or environment."
            )
        self._model = model or os.getenv("GEMINI_MODEL", self.DEFAULT_MODEL)
        self._client = genai.Client(api_key=self._api_key)

    def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        from google.genai import types
        config_kwargs: dict = {"max_output_tokens": 16384}
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt
        kwargs: dict = dict(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        try:
            _log.info("Gemini API 호출 시작 (model=%s)", self._model)
            response = retry_api_call(
                lambda: self._client.models.generate_content(**kwargs),
                label="Gemini",
            )
            _log.info("Gemini API 호출 완료")
        except Exception as exc:
            _log.error("Gemini API 호출 실패: %s", exc)
            raise ValueError(f"Gemini API 호출 실패: {exc}") from exc
        text = response.text
        if not text:
            _log.warning("Gemini 응답이 비어 있습니다 (model=%s)", self._model)
            raise ValueError(
                "Gemini 응답이 비어 있습니다. 프롬프트를 조정하거나 다시 시도해주세요."
            )
        return text

    def generate_text_stream(
        self, prompt: str, *, system_prompt: str | None = None
    ) -> Generator[str, None, None]:
        from google.genai import types
        config_kwargs: dict = {"max_output_tokens": 16384}
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt
        kwargs: dict = dict(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        try:
            _log.info("Gemini 스트리밍 시작 (model=%s)", self._model)
            for chunk in self._client.models.generate_content_stream(**kwargs):
                if chunk.text:
                    yield chunk.text
            _log.info("Gemini 스트리밍 완료")
        except Exception as exc:
            _log.error("Gemini 스트리밍 실패: %s", exc)
            raise ValueError(f"Gemini 스트리밍 실패: {exc}") from exc

    def generate_image(
        self,
        prompt: str,
        *,
        reference_image: bytes | None = None,
        reference_mime: str = "image/png",
    ) -> tuple[bytes, str]:
        """Generate an image using Gemini's image generation model.

        Args:
            prompt: Text description for image generation.
            reference_image: Optional reference image bytes.
            reference_mime: MIME type of the reference image.

        Returns:
            Tuple of (image_bytes, mime_type).

        Raises:
            ValueError: If the API call fails or no image is in the response.
        """
        from google.genai import types

        image_model = os.getenv("GEMINI_IMAGE_MODEL", self.DEFAULT_IMAGE_MODEL)

        contents: list = []
        if reference_image is not None:
            contents.append(types.Part.from_bytes(data=reference_image, mime_type=reference_mime))
        contents.append(prompt)

        config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        )

        try:
            _log.info("Gemini 이미지 생성 시작 (model=%s)", image_model)
            response = retry_api_call(
                lambda: self._client.models.generate_content(
                    model=image_model,
                    contents=contents,
                    config=config,
                ),
                label="Gemini 이미지",
            )
            _log.info("Gemini 이미지 생성 완료")
        except Exception as exc:
            _log.error("Gemini 이미지 생성 실패: %s", exc)
            raise ValueError(f"Gemini 이미지 생성 실패: {exc}") from exc

        # Extract image data from response parts
        if not response.candidates:
            raise ValueError("Gemini 이미지 응답이 비어 있습니다. 프롬프트를 조정해주세요.")
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                return (part.inline_data.data, part.inline_data.mime_type)

        raise ValueError("Gemini 응답에 이미지가 포함되지 않았습니다. 다른 프롬프트를 시도해주세요.")


def get_provider(engine: str) -> BaseProvider:
    """Factory: 'claude' | 'gemini' → instantiated provider.

    Raises:
        ValueError: unknown engine name, or the required API key is missing.
    """
    if engine == "claude":
        return ClaudeProvider()
    elif engine == "gemini":
        return GeminiProvider()
    else:
        raise ValueError(
            f"Unknown engine {engine!r}. Valid values: 'claude', 'gemini'."
        )
