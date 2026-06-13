"""당근 피드용 '자연스러운(비광고)' 썸네일 프롬프트 빌더.

당근마켓 피드는 이웃이 직접 찍은 투박한 사진이 나열되는 환경이다. 광고 티가
나는 순간 유저는 스크롤로 넘어간다(상대성 원리). 그래서 생성 이미지는
'디자인된 광고 크리에이티브'가 아니라 '조금 더 신경 쓴 실제 동네 사진'처럼
보여야 한다.

ai_engine.py의 기획 가이드("자연스러운 사진 > 디자인된 사진",
"투박해도 실제 매장 사진 > AI 이미지")와 동일한 철학을, 실제 이미지 생성
프롬프트에도 강제한다. 텍스트(가격/문구)는 이미지에 굽지 않고 PIL 오버레이
(text_overlay.py)로 따로 얹는 것을 전제로, 베이스 이미지는 깨끗한 실사로 만든다.

[중요] 프롬프트는 '명령형 산문'으로 작성한다. 대괄호 헤더 + "NO ..." 규칙
나열형으로 쓰면 codex 이미지 백엔드가 채팅 요청으로 오해해 image_generation
툴을 호출하지 않고 텍스트로 답해버린다("response stream completed without an
image_generation_call result"). 실측으로 확인된 함정이므로 형식을 바꾸지 말 것.
"""
from __future__ import annotations

# 명령형 산문. 모델이 '이미지를 생성하라'는 지시로 명확히 받아들이도록 한 문단으로 잇는다.
_REALISM_PROSE = (
    "Create one photorealistic photo (this is NOT an advertisement and must not look "
    "like one) of the following: {subject}. "
    "Shoot it as a real, candid smartphone photo taken by a local small-business owner "
    "to post on a Korean neighborhood marketplace feed (당근마켓): natural available "
    "light (daylight or ordinary indoor/store lighting), realistic textures, casual and "
    "slightly imperfect framing, an honest documentary feel — like a real review photo, "
    "not a polished campaign visual. "
    "The subject is real and clearly visible, shot up close the way a neighbor would "
    "actually photograph it. "
    "Keep the image clean and natural: do not bake in any text, price tags, promotional "
    "copy, banners, CTA buttons, badges, stickers, logos, or watermarks. Avoid glossy "
    "studio gloss, heavy color grading, and stock-photo perfection. "
    "If a person appears, make them an ordinary real person with a natural expression "
    "looking toward the camera — no model or celebrity polish, no distorted faces or hands. "
    "Render real photography, not illustration, 3D, or CGI."
)

_REFERENCE_PROSE = (
    " Use the attached image only as a loose hint for subject, color, and mood — do not "
    "copy it; recreate a fresh natural photo while keeping the candid, non-advertising look."
)

_CLOSING_PROSE = (
    " Output a single square (1:1) image suitable as a marketplace feed thumbnail."
)

_FALLBACK_SUBJECT = "the product or scene described by the user"


def build_natural_thumbnail_prompt(
    user_prompt: str,
    *,
    has_reference: bool = False,
) -> str:
    """사용자 프롬프트를 '자연 실사' 명령형 지시로 감싸 광고 티를 제거한다.

    Args:
        user_prompt: 사용자가 입력한 장면/상품 설명.
        has_reference: 참고 이미지가 함께 전달되는지 여부 (스타일만 참고하도록 안내).

    Returns:
        이미지 생성기에 그대로 넘길 최종 프롬프트(명령형 산문).
    """
    subject = (user_prompt or "").strip() or _FALLBACK_SUBJECT

    prompt = _REALISM_PROSE.format(subject=subject)
    if has_reference:
        prompt += _REFERENCE_PROSE
    prompt += _CLOSING_PROSE
    return prompt
