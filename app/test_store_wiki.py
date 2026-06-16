"""매장 위키 계층 테스트 (TASK-1)."""
import unittest

from app import store_wiki
from app.ai_engine import build_strategy_prompt, build_report_prompt, calc_kpi


class TestTrackingLimited(unittest.TestCase):
    def test_optical_is_tracking_limited(self):
        self.assertTrue(store_wiki.is_tracking_limited("안경원"))
        self.assertTrue(store_wiki.is_tracking_limited("치과의원"))

    def test_generic_retail_not_limited(self):
        self.assertFalse(store_wiki.is_tracking_limited("카페"))
        self.assertFalse(store_wiki.is_tracking_limited(""))


class TestInitialWiki(unittest.TestCase):
    def test_optical_wiki_states_tracking_limit(self):
        wiki = store_wiki.build_initial_wiki(
            {"name": "지니스안경", "industry": "안경원", "region": "충남 공주시"}
        )
        self.assertIn("매장 위키", wiki)
        self.assertIn("추적 한계", wiki)
        # 안경원은 디지털 추적 한계 사실이 들어가야 한다 (문의 0 = 실패 아님)
        self.assertIn("실패가 아니다", wiki)
        self.assertIn("내방", wiki)

    def test_generic_wiki_no_false_tracking_claim(self):
        wiki = store_wiki.build_initial_wiki(
            {"name": "동네카페", "industry": "카페", "region": "서울"}
        )
        self.assertNotIn("실패가 아니다", wiki)

    def test_performance_patterns_refined_into_wiki(self):
        rows = [
            {"period_label": "D1", "cost": 10000, "impressions": 3000, "clicks": 30,
             "inquiries": 0, "regulars": 1, "coupons": 2},
            {"period_label": "D2", "cost": 10000, "impressions": 2000, "clicks": 10,
             "inquiries": 0, "regulars": 0, "coupons": 0},
        ]
        kpi = calc_kpi(rows)
        wiki = store_wiki.build_initial_wiki(
            {"name": "X", "industry": "안경원", "region": "공주"}, kpi
        )
        self.assertIn("검증된 패턴", wiki)
        self.assertIn("CTR", wiki)  # 내부 성과 raw data가 패턴으로 정제됨


class TestPromptBlock(unittest.TestCase):
    def test_empty_wiki_block_is_blank(self):
        self.assertEqual(store_wiki.wiki_prompt_block(""), "")
        self.assertEqual(store_wiki.wiki_prompt_block("   "), "")

    def test_nonempty_block_has_marker(self):
        block = store_wiki.wiki_prompt_block("- 안경원 추적 한계 있음")
        self.assertIn("매장 위키", block)
        self.assertIn("안경원 추적 한계 있음", block)


class TestPromptInjection(unittest.TestCase):
    def test_strategy_prompt_includes_wiki(self):
        _guide, prompt = build_strategy_prompt(
            {"name": "지니스안경", "industry": "안경원", "region": "공주"},
            wiki="- 핵심 사실: 안경원은 전화·내방 중심",
        )
        self.assertIn("매장 위키", prompt)
        self.assertIn("전화·내방 중심", prompt)

    def test_report_prompt_includes_wiki(self):
        rows = [{"period_label": "D1", "cost": 1000, "impressions": 100,
                 "clicks": 5, "inquiries": 0, "regulars": 0, "coupons": 1}]
        kpi = calc_kpi(rows)
        prompt = build_report_prompt(
            {"name": "X", "industry": "안경원", "region": "공주"}, rows, kpi,
            wiki="- 안경원 추적 한계: 문의 0 정상",
        )
        self.assertIn("매장 위키", prompt)
        self.assertIn("문의 0 정상", prompt)

    def test_no_wiki_keeps_prompt_working(self):
        # wiki 미지정 시 위키 주입 블록은 없어야 한다(템플릿 본문의 '매장 위키' 언급과 구분).
        _guide, prompt = build_strategy_prompt({"name": "X", "industry": "카페", "region": "서울"})
        self.assertNotIn("지금까지 정제된 사실/패턴", prompt)


class TestExtractLearnings(unittest.TestCase):
    def test_extract_from_json_block(self):
        text = (
            "## 1. 결론\n본문...\n\n```json\n"
            '{"blocked": "클릭→문의 0.23% 병목", "hypothesis": "CTA 분산"}\n```'
        )
        out = store_wiki.extract_report_learnings(text)
        self.assertEqual(out["blocked"], "클릭→문의 0.23% 병목")
        self.assertEqual(out["hypothesis"], "CTA 분산")

    def test_no_json_returns_empty(self):
        out = store_wiki.extract_report_learnings("그냥 마크다운 본문, JSON 없음")
        self.assertEqual(out["blocked"], "")
        self.assertEqual(out["hypothesis"], "")


class TestMergeSection(unittest.TestCase):
    def test_append_to_existing_section(self):
        wiki = "# W\n\n## 과거 진단\n- (없음)\n\n## 사장님\n- x"
        out = store_wiki._merge_section(wiki, "과거 진단", ["- [5월] 병목: A"])
        self.assertIn("- [5월] 병목: A", out)
        # 새 줄이 과거 진단 섹션 안(사장님 섹션 위)에 들어가야 함
        self.assertLess(out.index("병목: A"), out.index("## 사장님"))
        # 기존 내용 보존
        self.assertIn("- x", out)

    def test_dedup_skips_existing_line(self):
        wiki = "## 과거 진단\n- [5월] 병목: A"
        out = store_wiki._merge_section(wiki, "과거 진단", ["- [5월] 병목: A"])
        self.assertEqual(out.count("병목: A"), 1)

    def test_missing_section_is_created(self):
        wiki = "# W\n\n## 시장 특성\n- 소도시"
        out = store_wiki._merge_section(wiki, "과거 진단", ["- [6월] 병목: B"])
        self.assertIn("## 과거 진단", out)
        self.assertIn("- [6월] 병목: B", out)
        self.assertIn("- 소도시", out)  # 기존 보존

    def test_accumulates_across_periods(self):
        wiki = "## 과거 진단\n- [5월] 병목: A"
        out = store_wiki._merge_section(wiki, "과거 진단", ["- [6월] 병목: B"])
        self.assertIn("- [5월] 병목: A", out)
        self.assertIn("- [6월] 병목: B", out)  # 지난달 이어받아 누적


if __name__ == "__main__":
    unittest.main()
