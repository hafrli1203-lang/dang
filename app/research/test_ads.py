# -*- coding: utf-8 -*-
"""경쟁 광고 관측 — 순수 점수 로직 + 구조 테스트(Playwright/네트워크 없이)."""
import unittest

from app.research import ads as A
from app.research import stealth as ST


class TestScoring(unittest.TestCase):
    def test_search_score_position_and_keyword(self):
        # position 1, 키워드 포함, 설명 있음 → (10-1)*2 + 5 + 3 = 26
        self.assertEqual(A.compute_search_ad_score("변색렌즈 0원", "후기", 1, "변색렌즈"), 26)
        # position 5, 키워드 없음, 설명 없음 → (10-5)*2 = 10
        self.assertEqual(A.compute_search_ad_score("안경", None, 5, "변색렌즈"), 10)
        # position 11(>10) → max(0,...) = 0
        self.assertEqual(A.compute_search_ad_score("x", None, 11, "kw"), 0)

    def test_naver_brand_search_bonus(self):
        base = A.compute_search_ad_score("렌즈", "d", 2, "렌즈")
        brand = A.compute_naver_ad_score("렌즈", "d", "brand_search", 2, "렌즈")
        self.assertEqual(brand, base + 5)
        powerlink = A.compute_naver_ad_score("렌즈", "d", "powerlink", 2, "렌즈")
        self.assertEqual(powerlink, base)

    def test_meta_score(self):
        # active + 2 platforms + body>50 → 3 + 2 + 2 = 7
        body = "x" * 60
        self.assertEqual(A.compute_meta_ad_score(["facebook", "instagram"], body, True),
                         3 + 2 + 2 + 1)  # +1 instagram
        # inactive, 0 platforms, no body → 0
        self.assertEqual(A.compute_meta_ad_score([], None, False), 0)
        # 3 platforms incl instagram, body>150 → 3 + 2 + 1 + 2 + 1 + 1
        long_body = "y" * 200
        self.assertEqual(
            A.compute_meta_ad_score(["facebook", "instagram", "messenger"], long_body, True),
            3 + 2 + 1 + 2 + 1 + 1,
        )


class TestJsConstants(unittest.TestCase):
    def test_js_scripts_present_and_balanced(self):
        # JS 스크립트가 비어있지 않고 괄호 균형이 맞는지(이식 누락 방지)
        for js in (A._GOOGLE_JS, A._NAVER_JS, A._META_JS):
            self.assertGreater(len(js), 100)
            self.assertEqual(js.count("("), js.count(")"))
            self.assertEqual(js.count("{"), js.count("}"))

    def test_meta_targets_korea(self):
        # country=KR은 extract_meta_ads의 URL params에 있고, JS엔 ad library 링크 파싱이 있다.
        import inspect
        src = inspect.getsource(A.extract_meta_ads)
        self.assertIn('"country": "KR"', src)
        self.assertIn("ads/library", A._META_JS)


class TestStealthHelpers(unittest.TestCase):
    def test_context_options_shape(self):
        opts = ST.stealth_context_options()
        self.assertIn("user_agent", opts)
        self.assertEqual(opts["locale"], "ko-KR")
        self.assertEqual(opts["timezone_id"], "Asia/Seoul")
        self.assertIn("width", opts["viewport"])

    def test_random_delay_range(self):
        for _ in range(20):
            d = ST.random_delay_seconds(1000, 2000)
            self.assertGreaterEqual(d, 1.0)
            self.assertLessEqual(d, 2.0)

    def test_playwright_missing_raises_in_context(self):
        # Playwright 미설치 환경이면 StealthBrowser 진입 시 PlaywrightMissing
        if not ST.playwright_available():
            with self.assertRaises(ST.PlaywrightMissing):
                with ST.StealthBrowser():
                    pass


class TestObservations(unittest.TestCase):
    def test_observation_dataclass(self):
        ob = A.AdObservation(
            engine="GOOGLE", keyword="kw", headline="h", description=None,
            display_url=None, landing_url=None, position=1, heuristic_score=5,
        )
        self.assertEqual(ob.engine, "GOOGLE")
        self.assertEqual(ob.raw, {})


if __name__ == "__main__":
    unittest.main()
