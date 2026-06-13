"""자동/수동 페어 head-to-head 비교 테스트."""
from __future__ import annotations

from unittest import TestCase

from app.reporting.demographic import (
    CampaignPerf,
    PairComparison,
    compare_auto_manual_pairs,
)


def _camp(name, cost, actions, bid, key="C1", age="20-29", imp=1000, clk=50):
    return CampaignPerf(
        name=name, cost=cost, actions=actions, bid_mode=bid,
        creative_id=key, age_range=age, impressions=imp, clicks=clk,
    )


class TestCompareAutoManualPairs(TestCase):
    def test_pairs_only_when_both_present(self):
        camps = [
            _camp("A_수동", 10000, 10, "manual", key="A"),
            _camp("A_자동", 10000, 5, "auto", key="A"),
            _camp("B_수동", 5000, 5, "manual", key="B"),  # 자동 없음 → 제외
        ]
        pairs = compare_auto_manual_pairs(camps)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].creative_key, "A")

    def test_manual_wins_lower_cpa(self):
        camps = [
            _camp("A_수동", 10000, 10, "manual", key="A"),  # CPA 1000
            _camp("A_자동", 10000, 5, "auto", key="A"),     # CPA 2000
        ]
        p = compare_auto_manual_pairs(camps)[0]
        self.assertEqual(p.winner, "manual")
        self.assertAlmostEqual(p.cpa_gap_pct, 100.0)
        self.assertIn("수동", p.recommendation)
        self.assertIn("자동을 종료", p.recommendation)

    def test_auto_wins_lower_cpa(self):
        camps = [
            _camp("A_수동", 20000, 5, "manual", key="A"),   # CPA 4000
            _camp("A_자동", 10000, 5, "auto", key="A"),     # CPA 2000
        ]
        p = compare_auto_manual_pairs(camps)[0]
        self.assertEqual(p.winner, "auto")
        self.assertIn("자동", p.recommendation)

    def test_tie_within_threshold(self):
        camps = [
            _camp("A_수동", 10000, 10, "manual", key="A"),  # CPA 1000
            _camp("A_자동", 10500, 10, "auto", key="A"),    # CPA 1050 (5% 차이)
        ]
        p = compare_auto_manual_pairs(camps)[0]
        self.assertEqual(p.winner, "tie")
        self.assertIn("비슷", p.recommendation)

    def test_zero_actions_side_loses(self):
        camps = [
            _camp("A_수동", 10000, 0, "manual", key="A"),   # 행동 없음
            _camp("A_자동", 10000, 5, "auto", key="A"),
        ]
        p = compare_auto_manual_pairs(camps)[0]
        self.assertEqual(p.winner, "auto")

    def test_sorted_by_gap_desc(self):
        camps = [
            # 작은 격차 페어 (B)
            _camp("B_수동", 10000, 10, "manual", key="B"),  # 1000
            _camp("B_자동", 12000, 10, "auto", key="B"),    # 1200 (20%)
            # 큰 격차 페어 (A)
            _camp("A_수동", 10000, 10, "manual", key="A"),  # 1000
            _camp("A_자동", 10000, 2, "auto", key="A"),     # 5000 (400%)
        ]
        pairs = compare_auto_manual_pairs(camps)
        self.assertEqual([p.creative_key for p in pairs], ["A", "B"])

    def test_no_pairs_returns_empty(self):
        camps = [_camp("A_수동", 10000, 10, "manual", key="A")]
        self.assertEqual(compare_auto_manual_pairs(camps), [])
