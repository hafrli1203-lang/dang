"""build_natural_thumbnail_prompt 테스트 — 광고 티 제거 + 사용자 의도 보존.

[중요] 프롬프트는 명령형 산문이어야 한다(대괄호 헤더/규칙 나열형 금지). 규칙
나열형이면 codex 이미지 백엔드가 image_generation 툴을 호출하지 않는다.
"""
from __future__ import annotations

from unittest import TestCase

from app.ai.thumbnail_style import build_natural_thumbnail_prompt


class TestBuildNaturalThumbnailPrompt(TestCase):
    def test_includes_user_subject(self):
        out = build_natural_thumbnail_prompt("동네 빵집 갓 구운 크루아상")
        self.assertIn("동네 빵집 갓 구운 크루아상", out)

    def test_enforces_photoreal_not_ad(self):
        out = build_natural_thumbnail_prompt("제철 딸기").lower()
        self.assertIn("photorealistic", out)
        self.assertIn("not an advertisement", out)

    def test_forbids_baked_in_text_and_badges(self):
        out = build_natural_thumbnail_prompt("커피").lower()
        self.assertIn("do not bake in any text", out)
        self.assertIn("badges", out)
        self.assertIn("cta buttons", out)

    def test_imperative_form_triggers_image_tool(self):
        # 명령형으로 시작해야 모델이 이미지 생성 지시로 받아들인다.
        out = build_natural_thumbnail_prompt("샐러드")
        self.assertTrue(out.lstrip().lower().startswith("create one photorealistic photo"))
        # 대괄호 헤더 규칙 나열형은 쓰지 않는다(툴 미호출 회귀 방지).
        self.assertNotIn("[OUTPUT STYLE]", out)

    def test_reference_hint_only_when_reference_present(self):
        with_ref = build_natural_thumbnail_prompt("샐러드", has_reference=True)
        without_ref = build_natural_thumbnail_prompt("샐러드", has_reference=False)
        self.assertIn("attached image", with_ref)
        self.assertNotIn("attached image", without_ref)

    def test_empty_prompt_has_safe_fallback_subject(self):
        out = build_natural_thumbnail_prompt("")
        self.assertIn("described by the user", out)

    def test_person_realism_hint_present(self):
        out = build_natural_thumbnail_prompt("사장님이 김밥 마는 장면").lower()
        self.assertIn("natural expression", out)

    def test_closes_with_square_thumbnail_instruction(self):
        out = build_natural_thumbnail_prompt("커피").lower()
        self.assertIn("1:1", out)
        self.assertIn("thumbnail", out)
