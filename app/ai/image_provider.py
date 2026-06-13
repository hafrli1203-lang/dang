"""OpenAI image generation provider (gpt-image-2).

High-level image generation with support for:
- Style Fusion (reference images + text)
- Image Mapping (product + benchmark images)
- Configurable aspect ratio / size

gpt-image-2 returns base64 PNG. Multiple input images are supported via images.edit.
"""
from __future__ import annotations

import base64
import io
import os
from io import BytesIO

from app.logger import get_logger
from app.ai.providers import retry_api_call

_log = get_logger("image_provider")

# aspect_ratio → gpt-image 지원 size 매핑 (gpt-image-2/1.5/1 공통 지원 사이즈)
_ASPECT_TO_SIZE = {
    "1:1": "1024x1024",
    "4:3": "1536x1024",
    "3:2": "1536x1024",
    "16:9": "1536x1024",
    "3:4": "1024x1536",
    "2:3": "1024x1536",
    "9:16": "1024x1536",
}


class OpenAIImageProvider:
    """High-level OpenAI image generation via the official openai SDK.

    Unlike OpenAIProvider.generate_image() in providers.py (which returns raw
    bytes for the simple thumbnail path), this class returns PIL.Image objects
    and supports multiple input images and aspect_ratio.
    """

    DEFAULT_MODEL = "gpt-image-2"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
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
        self._model = model or os.getenv("OPENAI_IMAGE_MODEL", self.DEFAULT_MODEL)
        self._client = OpenAI(api_key=self._api_key)

    def _resolve_size(self, aspect_ratio: str | None, image_size: str | None) -> str:
        if image_size:
            return image_size
        if aspect_ratio and aspect_ratio in _ASPECT_TO_SIZE:
            return _ASPECT_TO_SIZE[aspect_ratio]
        return "1024x1024"

    def generate_image(
        self,
        prompt: str,
        images: list[tuple[bytes, str]] | None = None,
        *,
        aspect_ratio: str | None = None,
        image_size: str | None = None,
    ) -> "PIL.Image.Image":
        """Generate an image from prompt + optional input images.

        Args:
            prompt: Full text prompt (use nanobanana_prompt builders).
            images: List of (image_bytes, mime_type) tuples sent as input images
                    (uses images.edit when present).
            aspect_ratio: e.g. "1:1", "16:9", "9:16", "4:3", "3:4".
            image_size: explicit size like "1024x1024" (overrides aspect_ratio).

        Returns:
            PIL.Image.Image — the generated image.

        Raises:
            ValueError: API failure or no image in response.
            ImportError: Pillow not installed.
        """
        from PIL import Image

        size = self._resolve_size(aspect_ratio, image_size)
        images = images or []

        try:
            _log.info(
                "OpenAI 이미지 생성 시작 (model=%s, images=%d, size=%s)",
                self._model, len(images), size,
            )
            if images:
                file_objs = []
                for idx, (img_data, mime) in enumerate(images):
                    ext = "png" if "png" in mime else (
                        "jpg" if ("jpeg" in mime or "jpg" in mime) else "png"
                    )
                    buf = io.BytesIO(img_data)
                    buf.name = f"input_{idx}.{ext}"
                    file_objs.append(buf)
                response = retry_api_call(
                    lambda: self._client.images.edit(
                        model=self._model,
                        image=file_objs if len(file_objs) > 1 else file_objs[0],
                        prompt=prompt,
                        size=size,
                        n=1,
                    ),
                    label="OpenAI 이미지(편집)",
                )
            else:
                response = retry_api_call(
                    lambda: self._client.images.generate(
                        model=self._model,
                        prompt=prompt,
                        size=size,
                        n=1,
                    ),
                    label="OpenAI 이미지",
                )
            _log.info("OpenAI 이미지 생성 완료")
        except Exception as exc:
            _log.error("OpenAI 이미지 생성 실패: %s", exc)
            raise ValueError(f"OpenAI 이미지 생성 실패: {exc}") from exc

        if not response.data:
            raise ValueError(
                "OpenAI 이미지 응답이 비어 있습니다. 프롬프트를 조정해주세요."
            )
        b64 = response.data[0].b64_json
        if not b64:
            raise ValueError(
                "OpenAI 응답에 이미지가 포함되지 않았습니다. 다른 프롬프트를 시도해주세요."
            )
        data = base64.b64decode(b64)
        _log.info("이미지 추출 성공 (%d bytes)", len(data))
        return Image.open(BytesIO(data))


def get_image_provider(backend: str | None = None):
    """이미지 프로바이더 팩토리.

    기본은 gti CLI(`OPENAI_IMAGE_BACKEND=cli`) — ChatGPT 구독 세션으로 동작하며
    API 키가 필요 없다. 텍스트(Claude/codex CLI)와 동일한 '구독만으로' 정책.

    `OPENAI_IMAGE_BACKEND=api`로 두면 공식 OpenAI Images API(gpt-image-2,
    OpenAIProvider)를 쓴다 — gti private 백엔드가 막혔을 때의 폴백.

    두 프로바이더 모두 generate_image(prompt, *, reference_image=, reference_mime=)
    → (bytes, mime) 동일 계약을 따른다.
    """
    backend = (backend or os.getenv("OPENAI_IMAGE_BACKEND", "cli")).strip().lower()
    if backend == "api":
        from app.ai.providers import OpenAIProvider
        return OpenAIProvider()
    from app.ai.image_cli_provider import GtiImageProvider
    return GtiImageProvider()


def get_image_failure_guide(error_msg: str) -> str:
    """이미지 생성 실패 시 프롬프트 개선 가이드를 반환."""
    msg = str(error_msg).lower()

    if any(kw in msg for kw in ("codex login", "logged in", "gti", "구독 세션")):
        return (
            "이미지 생성에 쓰는 codex 로그인 세션에 문제가 있어요.\n"
            "- 터미널에서 'codex login'으로 로그인했는지 확인해 주세요\n"
            "- gti CLI가 설치돼 있는지 확인해 주세요 (npm i -g god-tibo-imagen)\n"
            "- 그래도 안 되면 .env에 OPENAI_IMAGE_BACKEND=api 와 OPENAI_API_KEY를 넣어 공식 API로 전환할 수 있어요"
        )
    if any(kw in msg for kw in ("safety", "blocked", "filter", "policy", "content_policy", "harmful", "moderation")):
        return (
            "안전 필터가 이미지를 차단했어요. 이렇게 해 보세요.\n"
            "- 사람 얼굴, 실제 브랜드, 로고 묘사를 빼 주세요\n"
            "- 의료, 약품, 폭력 관련 묘사를 피해 주세요\n"
            "- 추상적이거나 일러스트 스타일로 바꿔 보세요"
        )
    if any(kw in msg for kw in ("api key", "api_key", "invalid_api_key", "unauthorized", "401", "verification", "verify")):
        return (
            "OpenAI API 키 또는 조직 인증에 문제가 있어요.\n"
            "- .env의 OPENAI_API_KEY가 올바른지 확인해 주세요\n"
            "- gpt-image는 OpenAI 콘솔에서 조직 인증(Organization Verification)이 필요할 수 있어요\n"
            "- 결제 수단이 등록돼 있는지 확인해 주세요"
        )
    if any(kw in msg for kw in ("billing", "insufficient", "quota", "exceeded your current quota")):
        return (
            "OpenAI 사용 한도 또는 결제 문제로 생성하지 못했어요.\n"
            "- OpenAI 콘솔에서 잔액/결제 수단을 확인해 주세요\n"
            "- 사용 한도(rate limit)에 걸렸다면 잠시 후 다시 시도해 주세요"
        )
    if any(kw in msg for kw in ("이미지가 포함되지", "no image", "empty", "비어")):
        return (
            "이미지가 만들어지지 않았어요. 이렇게 해 보세요.\n"
            "- 색상, 구도, 스타일 같은 시각 묘사를 더 구체적으로 적어 주세요\n"
            "- 'photo of', 'illustration of' 같은 표현을 앞에 붙여 보세요\n"
            "- 프롬프트가 너무 짧다면 세부 내용을 더해 주세요"
        )
    if any(kw in msg for kw in ("429", "rate", "limit", "resource_exhausted")):
        return (
            "지금은 요청이 너무 많아 잠시 쉬어야 해요.\n"
            "- 1~2분 뒤에 다시 시도해 주세요\n"
            "- 한 번에 하나씩만 생성해 보세요"
        )
    if any(kw in msg for kw in ("timeout", "timed out", "deadline")):
        return (
            "응답이 너무 오래 걸려 중단했어요. 이렇게 해 보세요.\n"
            "- 프롬프트를 짧고 간결하게 줄여 보세요\n"
            "- 참고 이미지 크기를 줄여 보세요 (2MB 이하 권장)\n"
            "- 인터넷 연결 상태를 확인해 주세요"
        )
    if any(kw in msg for kw in ("503", "500", "overloaded", "unavailable")):
        return (
            "AI 서버가 잠시 붐비고 있어요.\n"
            "- 30초~1분 뒤에 다시 시도해 주세요\n"
            "- 그래도 안 되면 한 번 더 눌러 주세요"
        )
    return (
        "이미지를 만들지 못했어요. 이렇게 해 보세요.\n"
        "- 프롬프트를 조금 바꿔서 다시 시도해 주세요\n"
        "- API 키 설정을 확인해 주세요\n"
        "- 같은 문제가 반복되면 다른 모델로 시도해 보세요"
    )
