"""온보딩 체크리스트 로직 테스트."""
from __future__ import annotations

from unittest import TestCase

from app.onboarding import (
    compute_onboarding_steps,
    is_onboarding_complete,
    onboarding_progress,
)


class TestOnboarding(TestCase):
    def test_all_flags_false_gives_all_incomplete(self):
        steps = compute_onboarding_steps({})
        self.assertTrue(all(not s.done for s in steps))
        self.assertFalse(is_onboarding_complete(steps))
        done, total = onboarding_progress(steps)
        self.assertEqual(done, 0)
        self.assertEqual(total, 6)

    def test_partial_progress(self):
        steps = compute_onboarding_steps({"has_project": True, "has_strategy": True})
        done, total = onboarding_progress(steps)
        self.assertEqual((done, total), (2, 6))
        self.assertFalse(is_onboarding_complete(steps))

    def test_complete_when_all_flags_true(self):
        flags = {
            "has_project": True, "has_strategy": True, "has_planning": True,
            "has_ad_settings": True, "has_proposal": True, "has_report": True,
        }
        steps = compute_onboarding_steps(flags)
        self.assertTrue(is_onboarding_complete(steps))
        self.assertEqual(onboarding_progress(steps), (6, 6))

    def test_first_step_is_project_and_routes_present(self):
        steps = compute_onboarding_steps({})
        self.assertEqual(steps[0].key, "project")
        self.assertEqual(steps[0].route, "/")
        # 모든 단계가 이동 경로를 가진다
        self.assertTrue(all(s.route for s in steps))

    def test_unknown_flag_keys_ignored(self):
        steps = compute_onboarding_steps({"bogus": True})
        self.assertTrue(all(not s.done for s in steps))
