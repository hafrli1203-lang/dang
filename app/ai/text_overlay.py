# -*- coding: utf-8 -*-
"""PIL-based text overlay for thumbnail post-processing.

Renders Korean text (main/sub/CTA) onto a generated image with
adaptive contrast (white text + dark shadow on busy backgrounds).
"""
from __future__ import annotations

import os
import textwrap
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.logger import get_logger

_log = get_logger("text_overlay")

# ── Font resolution ──────────────────────────────────────────────────────────

_FONT_CANDIDATES = [
    "malgun.ttf",       # Windows: Malgun Gothic
    "malgunbd.ttf",     # Windows: Malgun Gothic Bold
    "NanumGothicBold.ttf",
    "NanumGothic.ttf",
    "AppleSDGothicNeo.ttc",
]

_SYSTEM_FONT_DIRS = [
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
    Path.home() / ".fonts",
    Path("/System/Library/Fonts"),
    Path("/Library/Fonts"),
]


def _find_korean_font() -> str | None:
    """Find a Korean-capable TrueType font on the system."""
    for font_dir in _SYSTEM_FONT_DIRS:
        if not font_dir.exists():
            continue
        for candidate in _FONT_CANDIDATES:
            font_path = font_dir / candidate
            if font_path.exists():
                _log.info("Korean font found: %s", font_path)
                return str(font_path)
            # Search subdirectories
            for match in font_dir.rglob(candidate):
                _log.info("Korean font found: %s", match)
                return str(match)
    _log.warning("No Korean font found; text overlay may show boxes")
    return None


_KOREAN_FONT_PATH = _find_korean_font()


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Get a font at the given size."""
    if _KOREAN_FONT_PATH:
        try:
            return ImageFont.truetype(_KOREAN_FONT_PATH, size)
        except (IOError, OSError):
            pass
    return ImageFont.load_default()


# ── Text rendering ───────────────────────────────────────────────────────────

def _measure_text(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    """Measure text bounding box, return (width, height)."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_text_with_shadow(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font,
    fill: str = "white",
    shadow_color: str = "#000000",
    shadow_offset: int = 2,
) -> None:
    """Draw text with a dark shadow for readability on any background."""
    x, y = xy
    # Shadow
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color)
    # Main text
    draw.text((x, y), text, font=font, fill=fill)


def _wrap_text(text: str, max_chars: int = 20) -> list[str]:
    """Wrap Korean text into lines of max_chars."""
    return textwrap.wrap(text, width=max_chars) or [text]


def render_text_overlay(
    img: Image.Image,
    main: str = "",
    sub: str = "",
    cta: str = "",
    *,
    text_color: str = "white",
    shadow_color: str = "#000000",
) -> Image.Image:
    """Render text overlay onto a PIL image.

    Layout:
        - Main text: upper area (30% from top), large bold
        - Sub text: below main, medium
        - CTA: bottom area (badge-style), small with background

    Args:
        img: Source PIL image.
        main: Main headline text.
        sub: Sub-headline text.
        cta: Call-to-action text.
        text_color: Text fill color.
        shadow_color: Shadow color for contrast.

    Returns:
        New PIL image with text overlay applied.
    """
    result = img.copy().convert("RGBA")
    w, h = result.size
    draw = ImageDraw.Draw(result)

    # Scale font sizes relative to image height
    main_size = max(int(h * 0.06), 24)
    sub_size = max(int(h * 0.04), 18)
    cta_size = max(int(h * 0.035), 16)
    shadow_offset = max(int(h * 0.003), 2)
    line_spacing = int(main_size * 0.4)

    main_font = _get_font(main_size, bold=True)
    sub_font = _get_font(sub_size)
    cta_font = _get_font(cta_size)

    # ── Main text (upper 30%) ──
    if main:
        lines = _wrap_text(main, max_chars=max(15, w // main_size))
        y_cursor = int(h * 0.25)
        for line in lines:
            tw, th = _measure_text(draw, line, main_font)
            x = (w - tw) // 2
            _draw_text_with_shadow(
                draw, (x, y_cursor), line, main_font,
                fill=text_color, shadow_color=shadow_color,
                shadow_offset=shadow_offset,
            )
            y_cursor += th + line_spacing

    # ── Sub text (below main) ──
    if sub:
        lines = _wrap_text(sub, max_chars=max(20, w // sub_size))
        y_cursor = int(h * 0.50)
        for line in lines:
            tw, th = _measure_text(draw, line, sub_font)
            x = (w - tw) // 2
            _draw_text_with_shadow(
                draw, (x, y_cursor), line, sub_font,
                fill=text_color, shadow_color=shadow_color,
                shadow_offset=shadow_offset,
            )
            y_cursor += th + int(sub_size * 0.3)

    # ── CTA badge (bottom) ──
    if cta:
        tw, th = _measure_text(draw, cta, cta_font)
        pad_x, pad_y = int(tw * 0.3), int(th * 0.4)
        badge_w = tw + pad_x * 2
        badge_h = th + pad_y * 2
        badge_x = (w - badge_w) // 2
        badge_y = int(h * 0.82)

        # Semi-transparent background
        badge_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
        badge_draw = ImageDraw.Draw(badge_layer)
        badge_draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
            radius=int(badge_h * 0.3),
            fill=(0, 0, 0, 160),
        )
        result = Image.alpha_composite(result, badge_layer)
        draw = ImageDraw.Draw(result)

        text_x = badge_x + pad_x
        text_y = badge_y + pad_y
        draw.text((text_x, text_y), cta, font=cta_font, fill=text_color)

    return result.convert("RGB")


def overlay_to_bytes(
    img: Image.Image,
    main: str = "",
    sub: str = "",
    cta: str = "",
    fmt: str = "PNG",
) -> bytes:
    """Convenience: render overlay and return as bytes."""
    result = render_text_overlay(img, main, sub, cta)
    buf = BytesIO()
    result.save(buf, format=fmt)
    return buf.getvalue()
