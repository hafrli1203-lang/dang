# -*- coding: utf-8 -*-
"""_parse_ai_insights 판단기준 파싱 테스트."""

import unittest

from app.pages.report import _parse_ai_insights


class TestJudgmentParsing(unittest.TestCase):
    """판단기준(judgment) 파싱 검증."""

    def test_korean_keys_normalized_in_json(self):
        """JSON 블록의 한국어 키(확대/검토/중단)가 영어로 정규화."""
        content = '''```json
{
  "conclusion": "테스트 결론",
  "judgment": {
    "확대": "문의 전환율 2% 이상 시",
    "검토": "CPR 유지 시 2주 추가 테스트",
    "중단": "CPR 5,000원 초과 시 중단"
  }
}
```'''
        result = _parse_ai_insights(content)
        j = result["judgment"]
        self.assertIn("expand", j)
        self.assertIn("review", j)
        self.assertIn("stop", j)
        self.assertNotIn("확대", j)
        self.assertIn("문의 전환율", j["expand"])

    def test_markdown_plain_format(self):
        """마크다운 '확대: ...' 기본 형식 파싱."""
        content = "## 판단기준\n확대: 전환율 2% 이상\n검토: 현 예산 유지\n중단: CPR 초과 시"
        result = _parse_ai_insights(content)
        j = result["judgment"]
        self.assertEqual(j["expand"], "전환율 2% 이상")
        self.assertEqual(j["review"], "현 예산 유지")
        self.assertEqual(j["stop"], "CPR 초과 시")

    def test_markdown_bullet_bold_format(self):
        """마크다운 '- **확대**: ...' bullet+bold 형식 파싱."""
        content = (
            "## 판단기준\n"
            "- **확대**: 문의 2% 달성 시 예산 확대\n"
            "- **검토**: CPR 유지 시 추가 테스트\n"
            "- **중단**: 효율 저하 시 축소\n"
        )
        result = _parse_ai_insights(content)
        j = result["judgment"]
        self.assertIn("expand", j)
        self.assertIn("review", j)
        self.assertIn("stop", j)
        self.assertIn("문의 2%", j["expand"])

    def test_json_english_keys_preserved(self):
        """JSON 블록의 영어 키(expand/review/stop)는 그대로 유지."""
        content = '''```json
{
  "conclusion": "결론",
  "judgment": {
    "expand": "확대 조건",
    "review": "검토 조건",
    "stop": "중단 조건"
  }
}
```'''
        result = _parse_ai_insights(content)
        j = result["judgment"]
        self.assertEqual(j["expand"], "확대 조건")
        self.assertEqual(j["review"], "검토 조건")
        self.assertEqual(j["stop"], "중단 조건")


if __name__ == "__main__":
    unittest.main()
