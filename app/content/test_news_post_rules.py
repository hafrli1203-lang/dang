# -*- coding: utf-8 -*-
"""news_post_rules 유닛 테스트."""

import unittest

from app.content.news_post_rules import (
    validate_news_post,
    build_news_repair_prompt,
    MIN_BODY_LENGTH,
    SECTION_TYPES,
    _split_sections,
)

# ── 픽스처 ──────────────────────────────────────────────────────────────────

_BODY_PAD = "동네에서 가장 정성스러운 안경을 맞추는 곳이에요. 시력검사부터 맞춤 피팅까지 꼼꼼하게 도와드립니다.\n" * 25

_GOOD_BLOCK = """\
제목: 0원 안경? 진짜 가능합니다
본문: {body_pad}
오늘도 많은 분들이 방문해주셨습니다.
채팅으로 문의 주시면 바로 안내해드려요.
CTA: 지금 채팅으로 문의하세요!
FAQ:
Q1. 정말 0원인가요?
A1. 네, 기본 안경테+렌즈 기준 0원입니다.
Q2. 추가금이 있나요?
A2. 특수 렌즈(블루라이트 등)는 옵션별 추가금이 있을 수 있어요.
Q3. 예약이 필요한가요?
A3. 예약 없이 방문 가능하지만, 채팅 예약 시 대기 없이 바로 상담됩니다.
고지: ※ 기본 혜택 범위 내 적용. 특수 렌즈/코팅은 추가금 가능. 정확한 비용은 매장 상담 후 안내.
""".format(body_pad=_BODY_PAD)

_GOOD_OUTPUT = f"""\
[소식글 Type C(가성비)]
{_GOOD_BLOCK}
[소식글 Type B(긴급성)]
{_GOOD_BLOCK}
"""


class TestValidateNewsPostPass(unittest.TestCase):
    """정상 출력 통과 테스트."""

    def test_good_output_passes(self):
        errors = validate_news_post(_GOOD_OUTPUT)
        self.assertEqual(errors, [], f"정상 출력이 실패: {errors}")


class TestValidateNewsPostFail(unittest.TestCase):
    """실패 케이스 테스트."""

    def test_empty_text(self):
        errors = validate_news_post("")
        self.assertTrue(len(errors) >= 2)

    def test_missing_type_b(self):
        no_b = _GOOD_OUTPUT.replace("[소식글 Type B(긴급성)]", "")
        errors = validate_news_post(no_b)
        self.assertTrue(any("Type B" in e for e in errors))

    def test_missing_type_c(self):
        no_c = _GOOD_OUTPUT.replace("[소식글 Type C(가성비)]", "")
        errors = validate_news_post(no_c)
        self.assertTrue(any("Type C" in e for e in errors))

    def test_missing_title_subsection(self):
        no_title = _GOOD_OUTPUT.replace("제목:", "타이틀:")
        errors = validate_news_post(no_title)
        self.assertTrue(any("제목" in e for e in errors))

    def test_missing_cta_subsection(self):
        no_cta = _GOOD_OUTPUT.replace("CTA:", "행동유도:")
        errors = validate_news_post(no_cta)
        self.assertTrue(any("CTA" in e for e in errors))

    def test_short_body(self):
        short = _GOOD_OUTPUT.replace(_BODY_PAD, "짧은 본문.\n")
        errors = validate_news_post(short)
        self.assertTrue(any("짧음" in e for e in errors))

    def test_cta_missing_keyword(self):
        bad_cta = _GOOD_OUTPUT.replace(
            "CTA: 지금 채팅으로 문의하세요!",
            "CTA: 지금 바로 확인하세요!",
        )
        errors = validate_news_post(bad_cta)
        self.assertTrue(any("키워드" in e for e in errors))

    def test_faq_too_few(self):
        # Remove Q2/A2 and Q3/A3
        few_faq = _GOOD_OUTPUT.replace(
            "Q2. 추가금이 있나요?\nA2. 특수 렌즈(블루라이트 등)는 옵션별 추가금이 있을 수 있어요.\n"
            "Q3. 예약이 필요한가요?\nA3. 예약 없이 방문 가능하지만, 채팅 예약 시 대기 없이 바로 상담됩니다.",
            "",
        )
        errors = validate_news_post(few_faq)
        self.assertTrue(any("FAQ" in e for e in errors))

    def test_forbidden_word(self):
        forbidden = _GOOD_OUTPUT + "\n무조건 만족!"
        errors = validate_news_post(forbidden)
        self.assertTrue(any("무조건" in e for e in errors))

    def test_forbidden_100_percent(self):
        forbidden = _GOOD_OUTPUT + "\n100% 보장!"
        errors = validate_news_post(forbidden)
        self.assertTrue(any("100%" in e for e in errors))


class TestSplitSections(unittest.TestCase):
    """_split_sections 테스트."""

    def test_splits_two(self):
        text = "[소식글 Type C(가성비)]\n본문C\n[소식글 Type B(긴급성)]\n본문B"
        sections = _split_sections(text)
        self.assertIn("type_c", sections)
        self.assertIn("type_b", sections)

    def test_empty(self):
        sections = _split_sections("")
        self.assertEqual(sections, {})

    def test_single_section(self):
        text = "[소식글 Type C(가성비)]\n본문만"
        sections = _split_sections(text)
        self.assertIn("type_c", sections)
        self.assertNotIn("type_b", sections)


class TestBuildRepairPrompt(unittest.TestCase):
    """repair 프롬프트 생성 테스트."""

    def test_contains_errors(self):
        errors = ["[Type C] 본문 짧음", "[Type B] FAQ 부족"]
        prompt = build_news_repair_prompt(
            original_text="원본",
            errors=errors,
            context={"name": "지니스안경", "region": "강남"},
        )
        for err in errors:
            self.assertIn(err, prompt)

    def test_contains_context(self):
        prompt = build_news_repair_prompt(
            original_text="원본",
            errors=["에러"],
            context={"name": "지니스안경", "industry": "안경점"},
        )
        self.assertIn("지니스안경", prompt)
        self.assertIn("안경점", prompt)

    def test_contains_format_spec(self):
        prompt = build_news_repair_prompt(
            original_text="원본",
            errors=["에러"],
            context={},
        )
        self.assertIn("Type C(가성비)", prompt)
        self.assertIn("Type B(긴급성)", prompt)
        self.assertIn(str(MIN_BODY_LENGTH), prompt)

    def test_style_guide_present(self):
        prompt = build_news_repair_prompt(
            original_text="원본",
            errors=["에러"],
            context={},
        )
        self.assertIn("모바일 가독성", prompt)
        self.assertIn("과장", prompt)


if __name__ == "__main__":
    unittest.main()
