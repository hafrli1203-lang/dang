"""GtiImageProvider + get_image_provider 테스트 (subprocess mock)."""
from __future__ import annotations

import os
import subprocess
from unittest import TestCase
from unittest.mock import MagicMock, patch

from app.ai.image_cli_provider import GtiImageProvider


def _fake_run_writing(png_bytes: bytes, returncode: int = 0):
    """subprocess.run 대역: --output 경로에 png_bytes를 쓰고 결과를 돌려준다."""
    def _run(args, **kwargs):
        out_path = args[args.index("--output") + 1]
        if returncode == 0:
            with open(out_path, "wb") as f:
                f.write(png_bytes)
        return MagicMock(returncode=returncode, stdout="", stderr="")
    return _run


class TestGtiImageProvider(TestCase):
    def test_generate_image_returns_png_bytes(self):
        with patch("subprocess.run", side_effect=_fake_run_writing(b"\x89PNG-data")):
            provider = GtiImageProvider()
            data, mime = provider.generate_image("당근 광고 썸네일")
        self.assertEqual(data, b"\x89PNG-data")
        self.assertEqual(mime, "image/png")

    def test_passes_provider_and_prompt_args(self):
        captured = {}

        def _run(args, **kwargs):
            captured["args"] = args
            out_path = args[args.index("--output") + 1]
            with open(out_path, "wb") as f:
                f.write(b"png")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=_run):
            GtiImageProvider().generate_image("hello", aspect_ratio="9:16")

        args = captured["args"]
        self.assertIn("--prompt", args)
        self.assertEqual(args[args.index("--prompt") + 1], "hello")
        # Windows ENOENT 회피: 기본 provider는 private-codex 고정.
        self.assertEqual(args[args.index("--provider") + 1], "private-codex")
        # 9:16 → 1024x1536 매핑.
        self.assertEqual(args[args.index("--size") + 1], "1024x1536")

    def test_reference_image_adds_image_arg(self):
        captured = {}

        def _run(args, **kwargs):
            captured["args"] = args
            out_path = args[args.index("--output") + 1]
            with open(out_path, "wb") as f:
                f.write(b"png")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=_run):
            GtiImageProvider().generate_image(
                "edit this", reference_image=b"\xff\xd8ref", reference_mime="image/jpeg"
            )

        args = captured["args"]
        self.assertIn("--image", args)
        ref_path = args[args.index("--image") + 1]
        self.assertTrue(ref_path.endswith(".jpg"))

    def test_unknown_size_is_not_passed(self):
        captured = {}

        def _run(args, **kwargs):
            captured["args"] = args
            out_path = args[args.index("--output") + 1]
            with open(out_path, "wb") as f:
                f.write(b"png")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=_run):
            GtiImageProvider().generate_image("x", image_size="999x999")
        self.assertNotIn("--size", captured["args"])

    def test_nonzero_returncode_raises(self):
        with patch("subprocess.run", side_effect=_fake_run_writing(b"", returncode=1)):
            with self.assertRaises(ValueError):
                GtiImageProvider().generate_image("fail")

    def test_login_error_message(self):
        def _run(args, **kwargs):
            return MagicMock(returncode=1, stdout="", stderr="Error: not logged in to codex")

        with patch("subprocess.run", side_effect=_run):
            with self.assertRaises(ValueError) as ctx:
                GtiImageProvider().generate_image("x")
        self.assertIn("codex login", str(ctx.exception))

    def test_timeout_raises_value_error(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("gti", 1)):
            with self.assertRaises(ValueError):
                GtiImageProvider().generate_image("x")

    def test_missing_binary_raises_value_error(self):
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with self.assertRaises(ValueError) as ctx:
                GtiImageProvider().generate_image("x")
        self.assertIn("gti", str(ctx.exception))


class TestGetImageProvider(TestCase):
    @patch.dict(os.environ, {"OPENAI_IMAGE_BACKEND": "cli"}, clear=False)
    def test_default_backend_is_cli(self):
        from app.ai.image_provider import get_image_provider
        self.assertIsInstance(get_image_provider(), GtiImageProvider)

    @patch.dict(os.environ, {"OPENAI_IMAGE_BACKEND": "api", "OPENAI_API_KEY": "sk-test"}, clear=False)
    def test_api_backend_returns_openai_provider(self):
        from app.ai.image_provider import get_image_provider
        from app.ai.providers import OpenAIProvider
        with patch("openai.OpenAI"):
            self.assertIsInstance(get_image_provider(), OpenAIProvider)
