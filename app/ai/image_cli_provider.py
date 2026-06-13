"""gti CLI 기반 이미지 생성 프로바이더 (ChatGPT 구독, API 키 불필요).

god-tibo-imagen(`gti`)을 subprocess로 호출한다. `gti`는 codex 로그인 세션
(`~/.codex/auth.json`)을 사용해 ChatGPT 백엔드의 빌트인 `image_generation`
툴을 호출하므로 OPENAI_API_KEY가 필요 없다. 텍스트 생성(codex CLI)과 동일하게
구독만으로 동작한다.

OpenAIProvider.generate_image()와 동일한 (bytes, mime) 계약을 따른다 — 호출부
드롭인 교체 가능.

주의: gti는 비공식 private 백엔드를 사용한다. OpenAI 측 변경 시 깨질 수 있어
`OPENAI_IMAGE_BACKEND=api`로 OpenAIProvider(공식 API) 폴백이 가능하다.
Windows에서 `--provider auto`는 내부 codex spawn ENOENT가 나므로 기본을
`private-codex`로 고정한다.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from app.logger import get_logger

_log = get_logger("image_cli_provider")

# aspect_ratio → gti(private-codex) 지원 size 매핑.
_ASPECT_TO_SIZE = {
    "1:1": "1024x1024",
    "4:3": "1536x1024",
    "3:2": "1536x1024",
    "16:9": "1536x1024",
    "3:4": "1024x1536",
    "2:3": "1024x1536",
    "9:16": "1024x1536",
}

# gti --size 가 받는 값(private-codex). 그 외 값은 전달하지 않고 모델 기본에 맡긴다.
_VALID_SIZES = {
    "auto", "1024x1024", "1536x1024", "1024x1536",
    "2048x2048", "2048x1152", "3840x2160", "2160x3840",
}


class GtiImageProvider:
    """`gti` CLI를 통한 이미지 생성 (구독 인증, 키 불필요).

    Returns: generate_image() → (png_bytes, "image/png").
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        timeout: float = 300.0,
    ) -> None:
        self._cli_path = shutil.which("gti") or "gti"
        # Windows에서 auto는 내부 codex spawn ENOENT → private-codex 고정.
        self._provider = provider or os.getenv("OPENAI_IMAGE_CLI_PROVIDER", "private-codex")
        # 빈 문자열이면 --model 미전달 (gti 기본 모델 사용).
        self._model = model or os.getenv("OPENAI_IMAGE_CLI_MODEL", "")
        self._timeout = timeout

    def _resolve_size(self, aspect_ratio: str | None, image_size: str | None) -> str | None:
        if image_size and image_size in _VALID_SIZES:
            return image_size
        if aspect_ratio and aspect_ratio in _ASPECT_TO_SIZE:
            return _ASPECT_TO_SIZE[aspect_ratio]
        return None

    def generate_image(
        self,
        prompt: str,
        *,
        reference_image: bytes | None = None,
        reference_mime: str = "image/png",
        aspect_ratio: str | None = None,
        image_size: str | None = None,
    ) -> tuple[bytes, str]:
        """프롬프트(+선택 참고 이미지)로 PNG를 생성한다.

        Args:
            prompt: 이미지 생성 프롬프트.
            reference_image: 참고 이미지 bytes (있으면 --image 로 전달).
            reference_mime: 참고 이미지 MIME.
            aspect_ratio: "1:1" / "16:9" / "9:16" / "4:3" / "3:4" 등.
            image_size: "1024x1024" 등 명시 사이즈 (aspect_ratio보다 우선).

        Returns:
            (png_bytes, "image/png").

        Raises:
            ValueError: gti 호출 실패 / 로그인 안 됨 / 결과 비어 있음.
        """
        size = self._resolve_size(aspect_ratio, image_size)

        with tempfile.TemporaryDirectory(prefix="dang-gti-") as tmp:
            out_path = os.path.join(tmp, "out.png")
            args = [
                self._cli_path,
                "--prompt", prompt,
                "--output", out_path,
                "--provider", self._provider,
            ]
            if size:
                args += ["--size", size]
            if self._model:
                args += ["--model", self._model]
            if reference_image is not None:
                ext = "png" if "png" in reference_mime else (
                    "jpg" if ("jpeg" in reference_mime or "jpg" in reference_mime) else "png"
                )
                ref_path = os.path.join(tmp, f"reference.{ext}")
                with open(ref_path, "wb") as f:
                    f.write(reference_image)
                args += ["--image", ref_path]

            _log.info(
                "gti 이미지 생성 시작 (provider=%s, size=%s, ref=%s)",
                self._provider, size or "default", reference_image is not None,
            )
            try:
                result = subprocess.run(
                    args, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=self._timeout,
                )
            except subprocess.TimeoutExpired as exc:
                _log.error("gti 타임아웃")
                raise ValueError(
                    f"이미지 생성이 {self._timeout:.0f}초 안에 끝나지 않았습니다. "
                    "잠시 후 다시 시도해 주세요."
                ) from exc
            except FileNotFoundError as exc:
                _log.error("gti 실행 파일을 찾지 못함")
                raise ValueError(
                    "gti CLI를 찾지 못했습니다. 'npm i -g god-tibo-imagen'으로 설치하고 "
                    "'codex login'으로 로그인되어 있는지 확인하세요."
                ) from exc

            if result.returncode != 0 or not os.path.exists(out_path):
                err = (result.stderr or "").strip() or (result.stdout or "").strip()
                _log.error("gti 호출 실패 (rc=%d): %s", result.returncode, err[:300])
                low = err.lower()
                if any(k in low for k in ("login", "not logged in", "unauthorized", "auth", "401")):
                    raise ValueError(
                        "codex CLI에 로그인되어 있지 않습니다. 터미널에서 'codex login' 후 "
                        "다시 시도하세요. (gti는 ChatGPT 구독 세션을 사용합니다)"
                    )
                raise ValueError(f"이미지 생성 실패: {err or '응답이 비어 있습니다.'}")

            with open(out_path, "rb") as f:
                data = f.read()

        if not data:
            raise ValueError("이미지가 비어 있습니다. 프롬프트를 조정해 다시 시도해 주세요.")
        _log.info("gti 이미지 생성 완료 (%d bytes)", len(data))
        return (data, "image/png")
