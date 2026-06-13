# -*- coding: utf-8 -*-
"""news_post_guard 유닛 테스트 — Asset Pack v1.0 (이모지/고정섹션명 기반)."""

import re
import unittest

from app.ai.news_post_guard import (
    FORCED_TEMPLATE,
    VALIDATION_RULES,
    format_forced_template,
    validate_news_post,
    build_news_post_repair_prompt,
    _split_blocks,
    _extract_body_text,
)

# ── 정상 출력 픽스처 ──────────────────────────────────────────────────────

_BODY_PAD = "동네에서 가장 정성스러운 빵을 만드는 곳이에요. 채팅으로 문의 주시면 바로 안내해드립니다.\n" * 25

_GOOD_BLOCK = """\
👆 쿠폰부터 받고 글을 읽어주세요! 👆

제목: 동네 빵집, 크로아상 2,500원?

요즘 빵값 너무 비싸지 않으셨어요?
저희 매장은 매일 새벽 반죽합니다.
크로아상 한 개 2,500원, 세 개 사면 6,000원에 드려요.

{body_pad}
오늘 갓 구운 빵이 준비되어 있습니다.
채팅으로 문의 주시면 예약도 도와드려요.

궁금한 점 있으시면 편하게 채팅 주세요!

강남구에서 만나요!
""".format(body_pad=_BODY_PAD)

# 가성비형에 숫자 앵커가 전혀 없는 블록 (가격/구성 숫자 누락) — 검증 실패 픽스처
_NO_ANCHOR_BLOCK = """\
👆 쿠폰부터 받고 글을 읽어주세요! 👆

제목: 동네 빵집, 이 구성 실화인가요?

요즘 빵값 너무 비싸지 않으셨어요?
저희 매장은 매일 새벽 반죽합니다.

{body_pad}
오늘 갓 구운 빵이 준비되어 있습니다.
채팅으로 문의 주시면 예약도 도와드려요.

궁금한 점 있으시면 편하게 채팅 주세요!

강남구에서 만나요!
""".format(body_pad=_BODY_PAD)

_GOOD_OUTPUT = f"""\
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【소식글 1 | 의심해소형】
{_GOOD_BLOCK}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【소식글 2 | 가성비형】
{_GOOD_BLOCK}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


class TestConstants(unittest.TestCase):
    """상수 존재 확인."""

    def test_forced_template_exists(self):
        self.assertIn("[INSTRUCTION]", FORCED_TEMPLATE)
        self.assertIn("[OUTPUT FORMAT", FORCED_TEMPLATE)
        self.assertIn("【소식글 1 | 의심해소형】", FORCED_TEMPLATE)
        self.assertIn("【소식글 2 | 가성비형】", FORCED_TEMPLATE)

    def test_validation_rules_dict(self):
        self.assertIsInstance(VALIDATION_RULES, dict)
        self.assertIn("block_headers", VALIDATION_RULES)
        self.assertIn("forbidden", VALIDATION_RULES)


class TestFormatForcedTemplate(unittest.TestCase):
    """format_forced_template 테스트."""

    def test_replaces_placeholders(self):
        project = {"name": "동네빵집", "region": "강남구", "industry": "베이커리",
                    "goal": "인지도", "period": "1개월", "benefits": "크로아상 50% 할인"}
        result = format_forced_template(project, extra="20대 타겟")
        self.assertIn("동네빵집", result)
        self.assertIn("강남구", result)
        self.assertIn("베이커리", result)
        self.assertIn("20대 타겟", result)
        self.assertNotIn("{{store_name}}", result)

    def test_missing_fields_get_placeholder(self):
        result = format_forced_template({})
        self.assertIn("(상호명)", result)


class TestValidateNewsPost(unittest.TestCase):
    """validate_news_post 정규식 기반 검증 테스트."""

    def test_good_output_passes(self):
        ok, errors = validate_news_post(_GOOD_OUTPUT)
        self.assertTrue(ok, f"정상 출력이 실패: {errors}")
        self.assertEqual(errors, [])

    def test_empty_text_fails(self):
        ok, errors = validate_news_post("")
        self.assertFalse(ok)
        self.assertTrue(len(errors) >= 2)  # 최소 블록 헤더 2개 누락

    def test_missing_block_header(self):
        """가성비형 블록 헤더 누락."""
        no_v2 = _GOOD_OUTPUT.replace("【소식글 2 | 가성비형】", "")
        ok, errors = validate_news_post(no_v2)
        self.assertFalse(ok)
        self.assertTrue(any("가성비" in e for e in errors))

    def test_short_body_fails(self):
        """본문 500자 미만."""
        short = _GOOD_OUTPUT.replace(_BODY_PAD, "짧은 본문.\n")
        ok, errors = validate_news_post(short)
        self.assertFalse(ok)
        self.assertTrue(any("500자" in e for e in errors), f"본문 길이 미달이 잡히지 않음: {errors}")

    def test_missing_cta_fails(self):
        """CTA 2회 미만 감지."""
        # 채팅/문의 키워드를 모두 제거하면 CTA 0회
        no_cta = _GOOD_OUTPUT.replace("채팅", "연락").replace("문의", "연락").replace("확인해", "봐")
        ok, errors = validate_news_post(no_cta)
        self.assertFalse(ok)
        self.assertTrue(any("CTA 부족" in e for e in errors))

    def test_price_anchor_missing_in_value_block_fails(self):
        """가성비형 블록에 가격/숫자 앵커가 없으면 실패 (근본 해결 검증)."""
        out = f"""\
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【소식글 1 | 의심해소형】
{_GOOD_BLOCK}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【소식글 2 | 가성비형】
{_NO_ANCHOR_BLOCK}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        ok, errors = validate_news_post(out)
        self.assertFalse(ok)
        self.assertTrue(
            any("앵커" in e and "가성비" in e for e in errors),
            f"가성비형 가격 앵커 누락이 잡히지 않음: {errors}",
        )

    def test_doubt_block_without_number_still_ok(self):
        """의심해소형엔 숫자 규칙이 없다 — 가성비형만 앵커 필요(스코프 고정)."""
        out = f"""\
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【소식글 1 | 의심해소형】
{_NO_ANCHOR_BLOCK}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【소식글 2 | 가성비형】
{_GOOD_BLOCK}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        ok, errors = validate_news_post(out)
        self.assertTrue(ok, f"의심해소형 숫자 없음은 통과해야 함: {errors}")


    def test_greeting_fails(self):
        """첫 줄 '안녕하세요' 감지."""
        greeted = _GOOD_OUTPUT.replace(
            "요즘 빵값 너무 비싸지 않으셨어요?",
            "안녕하세요 이웃 여러분! 빵값 비싸죠?"
        )
        ok, errors = validate_news_post(greeted)
        self.assertFalse(ok)
        self.assertTrue(any("안녕하세요" in e for e in errors))

    def test_forbidden_word_fails(self):
        """금지어 '무조건' 감지."""
        forbidden = _GOOD_OUTPUT + "\n무조건 만족하실 거예요!"
        ok, errors = validate_news_post(forbidden)
        self.assertFalse(ok)
        self.assertTrue(any("무조건" in e for e in errors))

    def test_forbidden_100_percent(self):
        """금지어 '100%' 감지."""
        forbidden = _GOOD_OUTPUT + "\n100% 만족 보장!"
        ok, errors = validate_news_post(forbidden)
        self.assertFalse(ok)
        self.assertTrue(any("100%" in e for e in errors))

    def test_forbidden_word_all(self):
        """금지어 '전부' 감지."""
        forbidden = _GOOD_OUTPUT + "\n전부 무료입니다!"
        ok, errors = validate_news_post(forbidden)
        self.assertFalse(ok)
        self.assertTrue(any("전부" in e for e in errors))

    def test_forbidden_word_absolute_no_extra_cost(self):
        """금지어 '절대 추가금 없음' 감지."""
        forbidden = _GOOD_OUTPUT + "\n절대 추가금 없음!"
        ok, errors = validate_news_post(forbidden)
        self.assertFalse(ok)
        self.assertTrue(any("절대 추가금 없음" in e for e in errors))

    def test_missing_title_fails(self):
        """제목 누락 감지."""
        no_title = _GOOD_OUTPUT.replace("제목: 동네 빵집, 크로아상 2,500원?", "")
        ok, errors = validate_news_post(no_title)
        self.assertFalse(ok)
        self.assertTrue(any("제목" in e for e in errors))

    def test_coupon_hook_missing_fails(self):
        """쿠폰/혜택 훅 문구 누락 감지."""
        no_hook = _GOOD_OUTPUT.replace("👆 쿠폰부터 받고 글을 읽어주세요! 👆", "글을 읽어주세요")
        ok, errors = validate_news_post(no_hook)
        self.assertFalse(ok)
        self.assertTrue(any("쿠폰" in e or "훅" in e for e in errors))

    def test_coupon_hook_passes_with_keywords(self):
        """쿠폰 키워드가 있으면 통과."""
        with_coupon = _GOOD_OUTPUT.replace(
            "👆 쿠폰부터 받고 글을 읽어주세요! 👆",
            "쿠폰 받고 글을 읽어주세요!"
        )
        ok, errors = validate_news_post(with_coupon)
        # 쿠폰 관련 에러가 없어야 함
        coupon_errors = [e for e in errors if "쿠폰" in e or "훅" in e]
        self.assertEqual(coupon_errors, [])

    def test_line_breaks_insufficient(self):
        """줄바꿈 14개 미만 감지."""
        minimal = (
            "【소식글 1 | 의심해소형】\n제목: 테스트\n본문" + "긴문자열" * 200
            + "\n【소식글 2 | 가성비형】\n제목: 테스트\n본문" + "긴문자열" * 200
        )
        ok, errors = validate_news_post(minimal)
        self.assertFalse(ok)
        self.assertTrue(any("줄바꿈" in e for e in errors))


class TestSplitBlocks(unittest.TestCase):
    """_split_blocks 분리 테스트."""

    def test_splits_two_blocks(self):
        text = "【소식글 1 | 의심해소형】\n본문1\n【소식글 2 | 가성비형】\n본문2"
        blocks = _split_blocks(text)
        self.assertIn("의심해소", blocks)
        self.assertIn("가성비", blocks)
        self.assertIn("본문1", blocks["의심해소"])
        self.assertIn("본문2", blocks["가성비"])

    def test_empty_input(self):
        blocks = _split_blocks("")
        self.assertEqual(blocks, {})

    def test_single_block_only(self):
        text = "【소식글 1 | 의심해소형】\n본문만 있음"
        blocks = _split_blocks(text)
        self.assertIn("의심해소", blocks)
        self.assertNotIn("가성비", blocks)


class TestExtractBodyText(unittest.TestCase):
    """_extract_body_text 테스트."""

    def test_includes_body_content(self):
        block = "본문 내용\n추가 내용\n더 많은 내용"
        result = _extract_body_text(block)
        self.assertIn("본문 내용", result)
        self.assertIn("추가 내용", result)

    def test_strips_title_line(self):
        block = "제목: 테스트 제목\n본문 시작"
        result = _extract_body_text(block)
        self.assertNotIn("테스트 제목", result)
        self.assertIn("본문 시작", result)


class TestBuildRepairPrompt(unittest.TestCase):
    """build_news_post_repair_prompt 테스트."""

    def test_contains_errors(self):
        errors = ["[의심해소형] 본문 너무 짧음", "[가성비형] 고지 섹션 누락"]
        prompt = build_news_post_repair_prompt(
            errors=errors,
            project={"name": "테스트", "region": "강남"},
        )
        for err in errors:
            self.assertIn(err, prompt)

    def test_contains_output_format(self):
        prompt = build_news_post_repair_prompt(
            errors=["에러1"],
            project={"name": "테스트"},
        )
        self.assertIn("OUTPUT FORMAT", prompt)
        self.assertIn("【소식글 1 | 의심해소형】", prompt)

    def test_contains_input_data(self):
        prompt = build_news_post_repair_prompt(
            errors=["에러"],
            project={"name": "동네빵집", "industry": "베이커리"},
        )
        self.assertIn("동네빵집", prompt)
        self.assertIn("베이커리", prompt)


class TestParsePlanningSections(unittest.TestCase):
    """_parse_planning_sections 로직 테스트 (planning.py에서 분리 검증).

    planning.py의 _parse_planning_sections()는 _split_blocks + re.split으로
    구성되므로 동일 로직을 여기서 직접 테스트한다.
    """

    @staticmethod
    def _parse(content: str) -> dict:
        """planning.py의 _parse_planning_sections과 동일한 로직."""
        blocks = _split_blocks(content)
        v1 = ("【소식글 1 | 의심해소형】\n" + blocks["의심해소"]) if "의심해소" in blocks else ""
        v2 = ("【소식글 2 | 가성비형】\n" + blocks["가성비"]) if "가성비" in blocks else ""
        summary = ""
        ad_copies = ""
        parts = re.split(r"(?m)^(## .+)", content)
        for i, part in enumerate(parts):
            if not part.startswith("## "):
                continue
            if "기획" in part and "요약" in part:
                summary = parts[i + 1] if i + 1 < len(parts) else ""
            elif "카피" in part or "광고" in part:
                ad_copies = parts[i + 1] if i + 1 < len(parts) else ""
        return {"version_1": v1, "version_2": v2, "summary": summary, "ad_copies": ad_copies, "raw": content}

    def test_both_versions_parsed(self):
        content = "【소식글 1 | 의심해소형】\nV1 본문\n【소식글 2 | 가성비형】\nV2 본문"
        result = self._parse(content)
        self.assertIn("의심해소", result["version_1"])
        self.assertIn("V1 본문", result["version_1"])
        self.assertIn("가성비", result["version_2"])
        self.assertIn("V2 본문", result["version_2"])

    def test_empty_input(self):
        result = self._parse("")
        self.assertEqual(result["version_1"], "")
        self.assertEqual(result["version_2"], "")
        self.assertEqual(result["summary"], "")
        self.assertEqual(result["ad_copies"], "")
        self.assertEqual(result["raw"], "")

    def test_summary_and_ad_copies_extracted(self):
        content = "## 기획 요약\n요약 내용입니다.\n## 광고 카피\n카피 내용입니다."
        result = self._parse(content)
        self.assertIn("요약 내용", result["summary"])
        self.assertIn("카피 내용", result["ad_copies"])

    def test_no_blocks_returns_empty_versions(self):
        content = "## 기획 요약\n요약만 있는 콘텐츠"
        result = self._parse(content)
        self.assertEqual(result["version_1"], "")
        self.assertEqual(result["version_2"], "")

    def test_raw_preserved(self):
        content = "원본 텍스트"
        result = self._parse(content)
        self.assertEqual(result["raw"], content)


if __name__ == "__main__":
    unittest.main()
