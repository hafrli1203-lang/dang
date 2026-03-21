# -*- coding: utf-8 -*-
"""build_proposal_prompt / build_proposal_section_prompt news_post_content 통합 테스트."""

import unittest

from app.ai_engine import (
    build_proposal_prompt,
    build_proposal_section_prompt,
    SYSTEM_GUIDE_PROPOSAL,
)


class TestProposalPromptNewsPost(unittest.TestCase):
    """news_post_content 파라미터 동작 검증."""

    _SHOP = {"shop_name": "테스트안경", "industry": "안경점", "location": "강남구"}
    _NEWS = "【소식글 1 | 의심해소형】\n테스트 소식글 본문입니다."

    def test_news_post_content_injected(self):
        """news_post_content가 프롬프트에 포함된다."""
        _, prompt = build_proposal_prompt(
            shop_info=self._SHOP,
            promo_text="봄 할인",
            target_age="40대",
            news_post_content=self._NEWS,
        )
        self.assertIn("[NEWS_POST_CONTENT]", prompt)
        self.assertIn("테스트 소식글 본문", prompt)

    def test_empty_news_post_not_injected(self):
        """news_post_content가 비어있으면 태그 없음."""
        _, prompt = build_proposal_prompt(
            shop_info=self._SHOP,
            promo_text="봄 할인",
            target_age="40대",
            news_post_content="",
        )
        self.assertNotIn("[NEWS_POST_CONTENT]", prompt)

    def test_section_prompt_news_post(self):
        """build_proposal_section_prompt에 news_post_content 전달."""
        _, prompt = build_proposal_section_prompt(
            section_key="creative",
            current_content="## 7. 소재 제안\n기존 내용",
            shop_info=self._SHOP,
            news_post_content=self._NEWS,
        )
        self.assertIn("[NEWS_POST_CONTENT]", prompt)
        self.assertIn("테스트 소식글 본문", prompt)

    def test_system_guide_has_news_post_tag(self):
        """SYSTEM_GUIDE_PROPOSAL 섹션7에 NEWS_POST_CONTENT 언급."""
        self.assertIn("NEWS_POST_CONTENT", SYSTEM_GUIDE_PROPOSAL)


if __name__ == "__main__":
    unittest.main()
