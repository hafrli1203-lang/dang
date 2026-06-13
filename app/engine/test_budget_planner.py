"""budget_planner 룰 엔진 테스트."""
import unittest

from app.engine.budget_planner import (
    MIN_CAMPAIGN_BUDGET,
    SIMPLE_AGE_BANDS,
    BudgetPlan,
    feasibility,
    judgment_rules,
    make_campaign_name,
    plan_table_rows,
    plan_to_prompt_context,
    recommend_structure,
    required_budget,
)


class TestRequiredBudget(unittest.TestCase):
    def test_doc_example(self):
        # 최소 1만 x 연령 5 x 성별 1 x 입찰 2 x 소재 1 = 10만원
        self.assertEqual(required_budget(n_age=5, n_gender=1, n_bid=2, n_creative=1), 100_000)

    def test_gender_split_doubles(self):
        self.assertEqual(required_budget(n_age=5, n_gender=2, n_bid=2), 200_000)

    def test_zero_inputs_clamped_to_one(self):
        self.assertEqual(required_budget(n_age=0, n_gender=0, n_bid=0, n_creative=0), MIN_CAMPAIGN_BUDGET)


class TestFeasibility(unittest.TestCase):
    def test_infeasible_reports_shortfall(self):
        f = feasibility(30_000, n_age=5)
        self.assertFalse(f["feasible"])
        self.assertEqual(f["required"], 100_000)
        self.assertEqual(f["shortfall"], 70_000)

    def test_feasible_no_shortfall(self):
        f = feasibility(120_000, n_age=5)
        self.assertTrue(f["feasible"])
        self.assertEqual(f["shortfall"], 0)


class TestCampaignNaming(unittest.TestCase):
    def test_name_format(self):
        name = make_campaign_name("장유", "여성", "40-54", "누진렌즈", "자동")
        self.assertEqual(name, "장유_여성40-54_누진렌즈_자동")

    def test_gender_all_omitted(self):
        name = make_campaign_name("장유", "전체", "20-59", "렌즈0원", "수동")
        self.assertEqual(name, "장유_20-59_렌즈0원_수동")


class TestRecommendStructure(unittest.TestCase):
    def test_below_minimum(self):
        plan = recommend_structure(5_000)
        self.assertEqual(plan.tier, "below_minimum")
        self.assertEqual(len(plan.campaigns), 0)
        self.assertTrue(plan.warnings)

    def test_10k_new_creative_uses_auto_single(self):
        plan = recommend_structure(10_000, has_validated_creative=False)
        self.assertEqual(plan.tier, "single")
        self.assertEqual(len(plan.campaigns), 1)
        self.assertEqual(plan.campaigns[0].bid_mode, "자동")
        # 신규는 넓은 타겟으로 시작
        self.assertEqual(plan.campaigns[0].age, "20-59")

    def test_10k_validated_creative_uses_manual_single(self):
        plan = recommend_structure(10_000, has_validated_creative=True, age_band="45-54")
        self.assertEqual(plan.campaigns[0].bid_mode, "수동")
        self.assertEqual(plan.campaigns[0].age, "45-54")

    def test_20k_is_minimum_pair_one_age_band(self):
        plan = recommend_structure(20_000, age_band="45-54")
        self.assertEqual(plan.tier, "pair")
        self.assertEqual(len(plan.campaigns), 2)
        bids = {c.bid_mode for c in plan.campaigns}
        self.assertEqual(bids, {"자동", "수동"})
        # 페어는 같은 연령대여야 한다 (변수 통제)
        ages = {c.age for c in plan.campaigns}
        self.assertEqual(ages, {"45-54"})
        # 예산 합 = 입력 예산
        self.assertEqual(sum(c.daily_budget for c in plan.campaigns), 20_000)

    def test_30k_adds_one_experiment(self):
        plan = recommend_structure(30_000, age_band="40대")
        self.assertEqual(plan.tier, "pair_plus_test")
        self.assertEqual(len(plan.campaigns), 3)
        experiment = plan.campaigns[2]
        self.assertEqual(experiment.daily_budget, MIN_CAMPAIGN_BUDGET)
        # 실험 캠페인은 주력과 다른 연령대
        self.assertNotEqual(experiment.age, "40대")
        self.assertEqual(sum(c.daily_budget for c in plan.campaigns), 30_000)

    def test_50k_two_age_pairs(self):
        plan = recommend_structure(50_000, age_band="40대")
        self.assertEqual(plan.tier, "two_pairs")
        self.assertEqual(len(plan.campaigns), 4)
        ages = {c.age for c in plan.campaigns}
        self.assertEqual(len(ages), 2)
        self.assertEqual(sum(c.daily_budget for c in plan.campaigns), 50_000)

    def test_100k_full_pairs(self):
        plan = recommend_structure(100_000)
        self.assertEqual(plan.tier, "full_pairs")
        self.assertEqual(len(plan.campaigns), len(SIMPLE_AGE_BANDS) * 2)
        # 모든 연령대에 자동+수동 페어
        for band in SIMPLE_AGE_BANDS:
            modes = {c.bid_mode for c in plan.campaigns if c.age == band}
            self.assertEqual(modes, {"자동", "수동"})

    def test_infeasible_full_pair_flagged(self):
        plan = recommend_structure(30_000)
        self.assertIn("예산 제한 모드", plan.feasibility_note)

    def test_feasible_full_pair_flagged(self):
        plan = recommend_structure(120_000)
        self.assertIn("가능해요", plan.feasibility_note)


class TestJudgmentRules(unittest.TestCase):
    def test_cumulative_rules_always_present(self):
        rules = "\n".join(judgment_rules())
        self.assertIn("3만원 미만", rules)
        self.assertIn("5만원 이상", rules)
        self.assertIn("가정", rules)

    def test_target_cpa_rules(self):
        rules = "\n".join(judgment_rules(target_cpa=20_000))
        self.assertIn("20,000원", rules)
        self.assertIn("40,000원", rules)   # 2배 강한 OFF
        self.assertIn("14,000원", rules)   # 0.7배 증액
        self.assertIn("30,000원", rules)   # 1.5배 감액


class TestOutputs(unittest.TestCase):
    def test_table_rows_match_campaigns(self):
        plan = recommend_structure(20_000, region="공주신관", gender="여성", age_band="45-54", appeal="렌즈0원")
        rows = plan_table_rows(plan)
        self.assertEqual(len(rows), 2)
        self.assertIn("공주신관_여성45-54_렌즈0원", rows[0]["name"])
        self.assertTrue(rows[0]["daily_budget"].endswith("원"))

    def test_prompt_context_contains_table_and_rules(self):
        plan = recommend_structure(30_000, target_cpa=15_000)
        text = plan_to_prompt_context(plan)
        self.assertIn("| 캠페인명 |", text)
        self.assertIn("임의 변형 금지", text)
        self.assertIn("변수 통제 원칙", text)
        self.assertIn("판단 기준", text)
        self.assertIn("15,000원", text)

    def test_prompt_context_no_empty_plan_crash(self):
        plan = recommend_structure(5_000)
        text = plan_to_prompt_context(plan)
        self.assertIn("예산 부족", text)


if __name__ == "__main__":
    unittest.main()
