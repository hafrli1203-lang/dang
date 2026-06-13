"""AI provider abstractions.

Provides a common synchronous interface so callers don't care which SDK is used.
Each provider is a plain class; async wrapping (run_in_executor) is the caller's job.

Usage:
    from app.ai.providers import get_provider
    provider = get_provider("claude")          # or "gpt"
    text = provider.generate_text(prompt)      # blocking call

Environment variables (all optional — keys raise ValueError at call time if missing):
    ANTHROPIC_API_KEY   — Anthropic secret key
    CLAUDE_MODEL        — model override  (default: claude-opus-4-6)
    OPENAI_API_KEY      — OpenAI secret key
    OPENAI_MODEL        — text model override  (default: gpt-4o)
    OPENAI_IMAGE_MODEL  — image generation model (default: gpt-image-2)
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
_TRANSIENT_KEYWORDS = ("429", "529", "rate", "limit", "timeout", "timed out", "503", "500",
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


def _is_overloaded(exc: Exception) -> bool:
    """Check if an exception is a 529 overloaded error (needs longer waits)."""
    msg = str(exc).lower()
    return "529" in msg or "overloaded" in msg


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
            if not _is_transient(exc):
                raise
            # 529 overloaded: use longer delays and allow extra retries
            overloaded = _is_overloaded(exc)
            effective_max = max_retries + 2 if overloaded else max_retries
            if attempt >= effective_max:
                raise
            retry_after = _parse_retry_after(exc)
            if retry_after:
                delay = retry_after
            elif overloaded:
                delay = max(5.0, base_delay * (2 ** attempt))  # min 5s for 529
            else:
                delay = base_delay * (2 ** attempt)
            _log.warning(
                "%s 일시적 오류 (시도 %d/%d), %.1f초 후 재시도: %s",
                label, attempt + 1, effective_max + 1, delay, exc,
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
            if _is_overloaded(exc):
                raise ValueError(
                    "Claude 서버가 지금 많이 붐비고 있어요. "
                    "잠시 후 다시 시도해 주세요. (5회 재시도 실패)"
                ) from exc
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
            if _is_overloaded(exc):
                raise ValueError(
                    "Claude 서버가 지금 많이 붐비고 있어요. 잠시 후 다시 시도해 주세요."
                ) from exc
            raise ValueError(f"Claude 스트리밍 실패: {exc}") from exc


class OpenAIProvider(BaseProvider):
    """OpenAI GPT via the official openai SDK (text + image).

    Text uses chat.completions; images use the Images API (gpt-image-2).
    Signatures mirror the old GeminiProvider so callers are drop-in compatible.
    """

    DEFAULT_MODEL = "gpt-4o"
    DEFAULT_IMAGE_MODEL = "gpt-image-2"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_tokens: int = 16384,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai 패키지가 설치되지 않았습니다. "
                "pip install openai 를 실행해주세요."
            ) from None

        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. "
                "Add it to your .env file or environment."
            )
        self._model = model or os.getenv("OPENAI_MODEL", self.DEFAULT_MODEL)
        self._max_tokens = max_tokens
        self._client = OpenAI(api_key=self._api_key)

    def _messages(self, prompt: str, system_prompt: str | None) -> list[dict]:
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        try:
            _log.info("OpenAI API 호출 시작 (model=%s)", self._model)
            response = retry_api_call(
                lambda: self._client.chat.completions.create(
                    model=self._model,
                    max_completion_tokens=self._max_tokens,
                    messages=self._messages(prompt, system_prompt),
                ),
                label="OpenAI",
            )
            _log.info("OpenAI API 호출 완료")
        except Exception as exc:
            _log.error("OpenAI API 호출 실패: %s", exc)
            if _is_overloaded(exc):
                raise ValueError(
                    "OpenAI 서버가 지금 많이 붐비고 있어요. 잠시 후 다시 시도해 주세요."
                ) from exc
            raise ValueError(f"OpenAI API 호출 실패: {exc}") from exc
        text = response.choices[0].message.content if response.choices else ""
        if not text:
            _log.warning("OpenAI 응답이 비어 있습니다 (model=%s)", self._model)
            raise ValueError(
                "OpenAI 응답이 비어 있습니다. 프롬프트를 조정하거나 다시 시도해주세요."
            )
        return text

    def generate_text_stream(
        self, prompt: str, *, system_prompt: str | None = None
    ) -> Generator[str, None, None]:
        try:
            _log.info("OpenAI 스트리밍 시작 (model=%s)", self._model)
            stream = self._client.chat.completions.create(
                model=self._model,
                max_completion_tokens=self._max_tokens,
                messages=self._messages(prompt, system_prompt),
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
            _log.info("OpenAI 스트리밍 완료")
        except Exception as exc:
            _log.error("OpenAI 스트리밍 실패: %s", exc)
            raise ValueError(f"OpenAI 스트리밍 실패: {exc}") from exc

    def generate_image(
        self,
        prompt: str,
        *,
        reference_image: bytes | None = None,
        reference_mime: str = "image/png",
    ) -> tuple[bytes, str]:
        """Generate an image using OpenAI's Images API (gpt-image-2).

        Args:
            prompt: Text description for image generation.
            reference_image: Optional reference image bytes (uses images.edit).
            reference_mime: MIME type of the reference image.

        Returns:
            Tuple of (image_bytes, "image/png").

        Raises:
            ValueError: If the API call fails or no image is in the response.
        """
        import base64
        import io

        image_model = os.getenv("OPENAI_IMAGE_MODEL", self.DEFAULT_IMAGE_MODEL)

        try:
            _log.info("OpenAI 이미지 생성 시작 (model=%s)", image_model)
            if reference_image is not None:
                ext = "png" if "png" in reference_mime else (
                    "jpg" if ("jpeg" in reference_mime or "jpg" in reference_mime) else "png"
                )
                buf = io.BytesIO(reference_image)
                buf.name = f"reference.{ext}"
                response = retry_api_call(
                    lambda: self._client.images.edit(
                        model=image_model,
                        image=buf,
                        prompt=prompt,
                        size="1024x1024",
                        n=1,
                    ),
                    label="OpenAI 이미지(편집)",
                )
            else:
                response = retry_api_call(
                    lambda: self._client.images.generate(
                        model=image_model,
                        prompt=prompt,
                        size="1024x1024",
                        n=1,
                    ),
                    label="OpenAI 이미지",
                )
            _log.info("OpenAI 이미지 생성 완료")
        except Exception as exc:
            _log.error("OpenAI 이미지 생성 실패: %s", exc)
            raise ValueError(f"OpenAI 이미지 생성 실패: {exc}") from exc

        if not response.data:
            raise ValueError("OpenAI 이미지 응답이 비어 있습니다. 프롬프트를 조정해주세요.")
        b64 = response.data[0].b64_json
        if not b64:
            raise ValueError("OpenAI 응답에 이미지가 포함되지 않았습니다. 다른 프롬프트를 시도해주세요.")
        return (base64.b64decode(b64), "image/png")


class ClaudeCliProvider(BaseProvider):
    """Anthropic Claude via the locally-installed `claude` CLI (no API key).

    Why: 사용자가 Claude Code Pro/Max 구독 중일 때 추가 API 크레딧 소모 없이
    동일 모델을 사용할 수 있게 한다. subprocess로 `claude --print` 비대화형
    모드를 호출한다.

    Trade-offs vs ClaudeProvider:
      - No streaming (CLI returns full text after generation).
      - System prompt is appended via --append-system-prompt.
      - Auth is the CLI's own session (keychain / OAuth). API key not required.
    """

    DEFAULT_MODEL = "claude-opus-4-7"

    def __init__(self, model: str | None = None, timeout: float = 240.0) -> None:
        self._model = model or os.getenv("CLAUDE_MODEL", self.DEFAULT_MODEL)
        self._timeout = timeout
        # Locate `claude` executable (PATH lookup happens at call time too,
        # but we cache the resolved path for repeated invocations).
        import shutil
        self._cli_path = shutil.which("claude") or "claude"

    def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        image: bytes | None = None,
        image_mime: str = "image/png",
    ) -> str:
        import subprocess
        # Multi-modal path: when an image is attached, use stream-json input/output
        # so we can pass an Anthropic-style user-message with an image content block.
        if image is not None:
            return self._generate_with_image(
                prompt, image=image, image_mime=image_mime,
                system_prompt=system_prompt,
            )

        args: list[str] = [self._cli_path, "--print"]
        if self._model:
            args += ["--model", self._model]
        if system_prompt:
            args += ["--append-system-prompt", system_prompt]

        env = self._build_env()

        _log.info("Claude CLI 호출 시작 (model=%s)", self._model)
        try:
            result = subprocess.run(
                args,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            _log.error("Claude CLI 타임아웃")
            raise ValueError(
                f"Claude CLI 응답이 {self._timeout:.0f}초 안에 오지 않았습니다."
            ) from exc
        except FileNotFoundError as exc:
            _log.error("Claude CLI 실행 파일을 찾지 못함")
            raise ValueError(
                "claude CLI를 찾지 못했습니다. Claude Code가 설치되어 있고 "
                "PATH에 있는지 확인하세요."
            ) from exc

        if result.returncode != 0:
            err = (result.stderr or "").strip() or (result.stdout or "").strip()
            _log.error("Claude CLI 비정상 종료 (rc=%d): %s", result.returncode, err)
            if "Not logged in" in err or "/login" in err:
                raise ValueError(
                    "Claude CLI에 로그인되어 있지 않습니다. 터미널에서 "
                    "'claude /login'으로 로그인 후 다시 시도하세요."
                )
            raise ValueError(f"Claude CLI 호출 실패: {err}")

        text = (result.stdout or "").strip()
        if not text:
            raise ValueError("Claude CLI 응답이 비어 있습니다.")
        _log.info("Claude CLI 호출 완료 (%d chars)", len(text))
        return text

    def _build_env(self) -> dict:
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
        return env

    def _generate_with_image(
        self,
        prompt: str,
        *,
        image: bytes,
        image_mime: str,
        system_prompt: str | None,
    ) -> str:
        """Multi-modal CLI call via --input-format=stream-json.

        Sends an Anthropic-style user message with an image content block,
        parses 'assistant' events from stream-json output, and returns the
        concatenated text.
        """
        import base64
        import json
        import subprocess

        img_b64 = base64.b64encode(image).decode("ascii")
        msg = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_mime,
                            "data": img_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            },
        }
        stdin_text = json.dumps(msg, ensure_ascii=False) + "\n"

        args: list[str] = [
            self._cli_path, "--print", "--verbose",
            "--input-format", "stream-json",
            "--output-format", "stream-json",
        ]
        if self._model:
            args += ["--model", self._model]
        if system_prompt:
            args += ["--append-system-prompt", system_prompt]

        env = self._build_env()

        _log.info(
            "Claude CLI multimodal 호출 시작 (model=%s, image=%d bytes)",
            self._model, len(image),
        )
        try:
            result = subprocess.run(
                args,
                input=stdin_text,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError(
                f"Claude CLI multimodal 응답이 {self._timeout:.0f}초 안에 오지 않았습니다."
            ) from exc

        if result.returncode != 0:
            err = (result.stderr or "").strip() or (result.stdout or "").strip()
            _log.error("Claude CLI multimodal 실패 (rc=%d): %s", result.returncode, err)
            raise ValueError(f"Claude CLI multimodal 호출 실패: {err}")

        # Parse stream-json events
        collected: list[str] = []
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            if evt.get("type") == "assistant":
                content = evt.get("message", {}).get("content", [])
                for blk in content:
                    if blk.get("type") == "text":
                        collected.append(blk.get("text", ""))

        text = "".join(collected).strip()
        if not text:
            raise ValueError("Claude CLI multimodal 응답이 비어 있습니다.")
        _log.info("Claude CLI multimodal 완료 (%d chars)", len(text))
        return text


class OpenAICliProvider(BaseProvider):
    """OpenAI GPT via the local `codex` CLI (ChatGPT 구독, API 키 불필요).

    ClaudeCliProvider와 동일한 철학: `codex exec`를 비대화형으로 호출하고
    `--output-last-message`로 최종 메시지만 읽어온다. 사용자의 codex 로그인
    세션(구독)을 사용하므로 OPENAI_API_KEY가 필요 없다.

    텍스트 전용 — 이미지 생성(gpt-image-2)은 CLI 경로가 없어 OpenAIProvider(API)를 써야 한다.
    """

    def __init__(self, model: str | None = None, timeout: float = 300.0) -> None:
        import shutil
        # codex 기본 모델 사용 (빈 문자열이면 -m 미전달). OPENAI_CLI_MODEL로 override.
        self._model = model or os.getenv("OPENAI_CLI_MODEL", "")
        self._timeout = timeout
        self._cli_path = shutil.which("codex") or "codex"

    def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        import os as _os
        import subprocess
        import tempfile

        full = prompt if not system_prompt else f"{system_prompt}\n\n---\n\n{prompt}"

        with tempfile.TemporaryDirectory() as tmp:
            out_path = _os.path.join(tmp, "last.txt")
            args = [
                self._cli_path, "exec",
                "-s", "read-only",          # 파일 변경 금지 (순수 텍스트 생성)
                "--skip-git-repo-check",
                "--ephemeral",              # 세션 파일 미저장
                "--color", "never",
                "-C", tmp,                  # 작업 루트를 임시 폴더로
                "-o", out_path,
            ]
            if self._model:
                args += ["-m", self._model]
            args += ["-"]                   # 프롬프트는 stdin으로

            _log.info("Codex CLI 호출 시작 (model=%s)", self._model or "default")
            try:
                result = subprocess.run(
                    args, input=full, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=self._timeout,
                )
            except subprocess.TimeoutExpired as exc:
                _log.error("Codex CLI 타임아웃")
                raise ValueError(
                    f"Codex CLI 응답이 {self._timeout:.0f}초 안에 오지 않았습니다."
                ) from exc
            except FileNotFoundError as exc:
                _log.error("codex CLI 실행 파일을 찾지 못함")
                raise ValueError(
                    "codex CLI를 찾지 못했습니다. 'npm i -g @openai/codex'로 설치하고 "
                    "'codex login'으로 로그인되어 있는지 확인하세요."
                ) from exc

            text = ""
            try:
                with open(out_path, encoding="utf-8") as f:
                    text = f.read().strip()
            except OSError:
                text = (result.stdout or "").strip()

            if not text:
                err = (result.stderr or "").strip() or (result.stdout or "").strip()
                _log.error("Codex CLI 응답 비정상 (rc=%d): %s", result.returncode, err[:300])
                low = err.lower()
                if "login" in low or "not logged in" in low or "unauthorized" in low:
                    raise ValueError(
                        "codex CLI에 로그인되어 있지 않습니다. 터미널에서 "
                        "'codex login' 후 다시 시도하세요."
                    )
                raise ValueError(f"Codex CLI 호출 실패: {err or '응답이 비어 있습니다.'}")

            _log.info("Codex CLI 호출 완료 (%d chars)", len(text))
            return text


def get_provider(engine: str) -> BaseProvider:
    """Factory: 'claude' | 'claude-api' | 'gpt' | 'gpt-api' → instantiated provider.

    'claude' (default) uses the local `claude` CLI so the user's Claude Code
    subscription pays for the call. Set CLAUDE_BACKEND=api in the .env to
    force the legacy Anthropic API path. 'gpt' uses the OpenAI API.

    Raises:
        ValueError: unknown engine name, or the required API key is missing.
    """
    if engine == "claude":
        backend = os.getenv("CLAUDE_BACKEND", "cli").strip().lower()
        if backend == "api":
            return ClaudeProvider()
        return ClaudeCliProvider()
    elif engine == "claude-api":
        return ClaudeProvider()
    elif engine == "claude-cli":
        return ClaudeCliProvider()
    elif engine == "gpt":
        backend = os.getenv("OPENAI_BACKEND", "cli").strip().lower()
        if backend == "api":
            return OpenAIProvider()
        return OpenAICliProvider()
    elif engine == "gpt-cli":
        return OpenAICliProvider()
    elif engine == "gpt-api":
        return OpenAIProvider()
    else:
        raise ValueError(
            f"Unknown engine {engine!r}. "
            f"Valid values: 'claude', 'claude-cli', 'claude-api', 'gpt', 'gpt-cli', 'gpt-api'."
        )
