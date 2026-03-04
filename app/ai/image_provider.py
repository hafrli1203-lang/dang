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
            "안전 필터에 의해 차단되었습니다.\n"
            "- 사람 얼굴/실명 브랜드/로고 직접 묘사를 제거하세요\n"
            "- 의료/약품/폭력 관련 묘사를 피하세요\n"
            "- 추상적 또는 일러스트 스타일로 변경해보세요"
        )
    if any(kw in msg for kw in ("이미지가 포함되지", "no image", "empty", "비어")):
        return (
            "이미지가 생성되지 않았습니다.\n"
            "- 더 구체적인 시각 묘사를 추가하세요 (색상, 구도, 스타일)\n"
            "- 'photo of', 'illustration of' 같은 접두어를 사용해보세요\n"
            "- 프롬프트가 너무 짧으면 세부 사항을 추가하세요"
        )
    if any(kw in msg for kw in ("429", "rate", "limit", "resource_exhausted", "quota")):
        return (
            "API 사용량 한도에 도달했습니다.\n"
            "- 잠시 후 다시 시도해주세요 (1-2분 대기)\n"
            "- 동시 생성 요청 수를 줄여보세요"
        )
    if any(kw in msg for kw in ("timeout", "timed out", "deadline")):
        return (
            "요청 시간이 초과되었습니다.\n"
            "- 프롬프트를 간결하게 줄여보세요\n"
            "- 참고 이미지 크기를 줄여보세요 (2MB 이하 권장)\n"
            "- 네트워크 상태를 확인하세요"
        )
    if any(kw in msg for kw in ("503", "500", "overloaded", "unavailable")):
        return (
            "서버가 일시적으로 과부하 상태입니다.\n"
            "- 30초~1분 후 다시 시도해주세요\n"
            "- 자동 재시도가 실패한 경우 직접 다시 시도하세요"
        )
    return (
        "이미지 생성에 실패했습니다.\n"
        "- 프롬프트를 수정하여 다시 시도해주세요\n"
        "- API 키 설정을 확인하세요\n"
        "- 오류가 반복되면 다른 모델을 시도해보세요"
    )
