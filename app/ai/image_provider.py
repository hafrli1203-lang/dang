"""Gemini native image generation provider (Nano Banana).

Dedicated image generation class with support for:
- Style Fusion (reference images + text)
- Image Mapping (product + benchmark images)
- Configurable aspect ratio and image size
"""
from __future__ import annotations

import os
from io import BytesIO

from app.logger import get_logger
from app.ai.providers import retry_api_call

_log = get_logger("image_provider")


class GeminiImageProvider:
    """High-level Gemini image generation via google-genai SDK.

    Unlike GeminiProvider.generate_image() in providers.py (which returns raw bytes),
    this class returns PIL.Image objects and supports multiple input images,
    aspect_ratio, and image_size configuration.
    """

    DEFAULT_MODEL = "gemini-3-pro-image-preview"

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
        self._model = model or os.getenv("GEMINI_IMAGE_MODEL", self.DEFAULT_MODEL)
        self._client = genai.Client(api_key=self._api_key)

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
            images: List of (image_bytes, mime_type) tuples. These are sent
                    as inline image parts in the content.
            aspect_ratio: e.g. "1:1", "16:9", "9:16", "4:3", "3:4".
            image_size: e.g. "1024x1024", "1536x1024" (if model supports).

        Returns:
            PIL.Image.Image — the generated image.

        Raises:
            ValueError: API failure or no image in response.
            ImportError: Pillow not installed.
        """
        from google.genai import types
        from PIL import Image

        if images is None:
            images = []

        # Build contents: images first, then text prompt
        contents: list = []
        for img_data, mime_type in images:
            contents.append(types.Part.from_bytes(data=img_data, mime_type=mime_type))
        contents.append(prompt)

        # Build config
        config_kwargs: dict = {
            "response_modalities": ["IMAGE", "TEXT"],
        }

        # image_generation_config for aspect_ratio / image_size if supported
        image_config: dict = {}
        if aspect_ratio:
            image_config["aspect_ratio"] = aspect_ratio
        if image_size:
            image_config["image_size"] = image_size
        if image_config:
            try:
                config_kwargs["image_generation_config"] = types.ImageGenerationConfig(
                    **image_config
                )
            except AttributeError:
                config_kwargs["image_generation_config"] = image_config

        config = types.GenerateContentConfig(**config_kwargs)

        try:
            _log.info(
                "Gemini 이미지 생성 시작 (model=%s, images=%d, aspect=%s)",
                self._model,
                len(images),
                aspect_ratio,
            )
            response = retry_api_call(
                lambda: self._client.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config,
                ),
                label="Gemini 썸네일",
            )
            _log.info("Gemini 이미지 생성 완료")
        except Exception as exc:
            _log.error("Gemini 이미지 생성 실패: %s", exc)
            raise ValueError(f"Gemini 이미지 생성 실패: {exc}") from exc

        # Extract image from response
        if not response.candidates:
            raise ValueError(
                "Gemini 이미지 응답이 비어 있습니다. 프롬프트를 조정해주세요."
            )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                _log.info(
                    "이미지 추출 성공: %s (%d bytes)",
                    part.inline_data.mime_type,
                    len(part.inline_data.data),
                )
                return Image.open(BytesIO(part.inline_data.data))

        raise ValueError(
            "Gemini 응답에 이미지가 포함되지 않았습니다. 다른 프롬프트를 시도해주세요."
        )


def get_image_failure_guide(error_msg: str) -> str:
    """이미지 생성 실패 시 프롬프트 개선 가이드를 반환."""
    msg = str(error_msg).lower()

    if any(kw in msg for kw in ("safety", "blocked", "filter", "policy", "harmful")):
        return (
            "안전 필터가 이미지를 차단했어요. 이렇게 해 보세요.\n"
            "- 사람 얼굴, 실제 브랜드, 로고 묘사를 빼 주세요\n"
            "- 의료, 약품, 폭력 관련 묘사를 피해 주세요\n"
            "- 추상적이거나 일러스트 스타일로 바꿔 보세요"
        )
    if any(kw in msg for kw in ("이미지가 포함되지", "no image", "empty", "비어")):
        return (
            "이미지가 만들어지지 않았어요. 이렇게 해 보세요.\n"
            "- 색상, 구도, 스타일 같은 시각 묘사를 더 구체적으로 적어 주세요\n"
            "- 'photo of', 'illustration of' 같은 표현을 앞에 붙여 보세요\n"
            "- 프롬프트가 너무 짧다면 세부 내용을 더해 주세요"
        )
    if any(kw in msg for kw in ("429", "rate", "limit", "resource_exhausted", "quota")):
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
