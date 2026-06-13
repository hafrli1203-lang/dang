"""Nano Banana prompt builders for Gemini image generation.

Two modes:
1. Style Fusion — reference images only (no product photo)
2. Image Mapping — product photo + benchmark/competitor images

Prompt structure follows templates/nanobanana_prompt.txt.
"""
from __future__ import annotations

_NEGATIVE_CONSTRAINTS = """
[NEGATIVE CONSTRAINTS]
- NO watermarks, logos, or brand marks from reference images
- NO UI chrome, device frames, browser bars, or borders
- NO black bars, letterboxing, or pillarboxing
- NO blurry, artifacted, or clipped text — all copy must be crisp and fully visible
- NO copyrighted characters, brand mascots, or trademarked logos
- If human faces appear, they must be natural (no distortion, extra limbs, etc.)
""".strip()


def compose_style_fusion_prompt(
    width: int,
    height: int,
    ratio: str,
    visual_guide: str,
    main: str,
    sub: str,
    cta: str,
) -> str:
    """Build a Style Fusion prompt (reference images + text overlay).

    The caller should pass reference images separately via
    OpenAIImageProvider.generate_image(images=[...]).

    Args:
        width: Canvas width in pixels.
        height: Canvas height in pixels.
        ratio: Aspect ratio string, e.g. "1:1", "16:9".
        visual_guide: Free-text visual direction (mood, colors, style keywords).
        main: Main headline copy.
        sub: Sub-headline copy.
        cta: Call-to-action text (button label).

    Returns:
        Fully formatted prompt string.
    """
    return f"""Role: MASTER AD GENERATOR V6.1
Mode: STYLE FUSION — blend reference image styles into a new ad creative.

Canvas: {width}x{height}px, aspect ratio {ratio}
Visual Guide: {visual_guide}

[TEXT OVERLAY]
Main Copy: "{main}" — large, bold, high-contrast, centered upper area
Sub Copy: "{sub}" — medium, below main copy
CTA: "{cta}" — button-style badge, bottom area, high visibility

[STYLE DIRECTIVES]
- Analyze the provided reference images for: color palette, texture, mood, composition
- Synthesize a COMPLETELY NEW image that blends those style elements
- Do NOT copy/paste or directly reproduce any reference image
- Ensure all text is crisp, legible, and never clipped by canvas edges
- Background must complement text readability (use contrast, subtle gradients, or overlays)

{_NEGATIVE_CONSTRAINTS}

Generate a single polished ad creative image at {width}x{height}px."""


def compose_image_mapping_prompt(
    width: int,
    height: int,
    ratio: str,
    product_desc: str,
    benchmark_desc: str,
    visual_guide: str,
    main: str,
    sub: str,
    cta: str,
) -> str:
    """Build an Image Mapping prompt (product photo + benchmark style).

    The caller should pass [product_image, *benchmark_images] via
    OpenAIImageProvider.generate_image(images=[...]).

    Args:
        width: Canvas width in pixels.
        height: Canvas height in pixels.
        ratio: Aspect ratio string.
        product_desc: Description of the product/subject in the first image.
        benchmark_desc: Description of the benchmark/competitor style images.
        visual_guide: Free-text visual direction.
        main: Main headline copy.
        sub: Sub-headline copy.
        cta: Call-to-action text.

    Returns:
        Fully formatted prompt string.
    """
    return f"""Role: MASTER AD GENERATOR V6.1
Mode: IMAGE MAPPING — create ad creative using the product photo with benchmark style influence.

Canvas: {width}x{height}px, aspect ratio {ratio}
Product (first image): {product_desc}
Benchmark Style (subsequent images): {benchmark_desc}
Visual Guide: {visual_guide}

[TEXT OVERLAY]
Main Copy: "{main}" — large, bold, high-contrast, centered upper area
Sub Copy: "{sub}" — medium, below main copy
CTA: "{cta}" — button-style badge, bottom area, high visibility

[COMPOSITION]
- The product (first image) is the HERO element — prominent, well-lit, clean presentation
- Benchmark images inform STYLE ONLY: extract color schemes, layout patterns, typography mood
- Do NOT reproduce or copy benchmark images; only use their design language
- Balance product prominence with decorative/stylistic elements from benchmark style
- Product must remain the focal point and be immediately recognizable

{_NEGATIVE_CONSTRAINTS}
- Product image must remain recognizable and undistorted

Generate a single polished ad creative image at {width}x{height}px."""
