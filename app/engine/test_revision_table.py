"""캠페인 수정표 룰 엔진 테스트."""
import unittest

from app.reporting.demographic import (
    CampaignPerf,
    judge_campaigns,
    simulate_reallocation,
)
from app.engine.revision_table import (
    build_campaign_revision_table,
    revision_rows_for_table,
    revision_table_markdown,
)


def _campaigns():
    return [
        CampaignPerf(name="장유_여성40대_렌즈_수동", bid_mode="manual",
                     cost=100_000, impressions=20_000, clicks=300, actions=20),
        CampaignPerf(name="장유_여성20대_렌즈_자동", bid_mode="auto",
                     cost=80_000, impressions=30_000, clicks=400, actions=0),
        CampaignPerf(name="장유_여성50대_렌즈_수동", bid_mode="manual",
                     cost=15_000, impressions=4_000, clicks=80, actions=8),
    ]


class TestRevisionTable(unittest.TestCase):
    def setUp(self):
        self.judgments = judge_campaigns(_campaigns())
        self.plan = simulate_reallocation(self.judgments)
        self.rows = build_campaign_revision_table(self.judgments, self.plan)

    def test_off_campaign_is_priority_one(self):
        off_rows = [r for r in self.rows if r.action == "캠페인 OFF"]
        self.assertTrue(off_rows, "전환 0건 캠페인은 OFF 행이 있어야 함")
        self.assertEqual(off_rows[0].priority, 1)
        self.assertIn("20대", off_rows[0].target)
        self.assertIn("0건", off_rows[0].evidence)

    def test_rows_sorted_by_priority(self):
        priorities = [r.priority for r in self.rows]
        self.assertEqual(priorities, sorted(priorities))

    def test_keep_verdict_excluded(self):
        # 유지 판정은 수정표에 안 들어간다 (할 일이 아님)
        targets = " ".join(r.target for r in self.rows)
        judg_keep = [j for j in self.judgments if j.verdict == "유지"]
        for j in judg_keep:
            self.assertNotIn(j.campaign.name, targets)

    def test_new_value_is_concrete(self):
        # 수정값은 광고 관리자에 입력할 수 있는 구체 값이어야 함
        for r in self.rows:
            self.assertTrue(r.new_value.strip())
            self.assertNotIn("개선하세요", r.new_value)
            self.assertNotIn("검토하세요", r.new_value)

    def test_table_rows_shape(self):
        dicts = revision_rows_for_table(self.rows)
        self.assertEqual(len(dicts), len(self.rows))
        for d in dicts:
            for key in ("priority", "target", "problem", "evidence",
                        "action", "new_value", "expected"):
                self.assertIn(key, d)

    def test_markdown_has_header_and_all_rows(self):
        md = revision_table_markdown(self.rows)
        self.assertIn("| 우선순위 |", md)
        self.assertEqual(md.count("\n") - 1, len(self.rows))

    def test_no_plan_still_works(self):
        rows = build_campaign_revision_table(self.judgments, None)
        self.assertTrue(rows)


if __name__ == "__main__":
    unittest.main()
