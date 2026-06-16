# -*- coding: utf-8 -*-
"""커뮤니티 리서치 엔진 — 순수 로직 테스트(네트워크/AI 없이 주입·모킹)."""
import unittest

from app.research import sources as S
from app.research import connectors as C
from app.research import fetch as F
from app.research import insight as I
from app.research import pipeline as P


class TestSources(unittest.TestCase):
    def test_registry_count_and_split(self):
        self.assertEqual(len(S.SOURCE_POLICIES), 23)
        self.assertEqual(len(S.naver_sources()), 5)
        self.assertEqual(len(S.cse_sources()), 18)
        self.assertEqual(S.get_source("nv_blog").naver_api_type, "blog")
        self.assertEqual(S.get_source("theqoo").cse_site_domain, "theqoo.net")
        for sid in S.DEFAULT_SOURCE_IDS:
            self.assertIn(sid, S.SOURCES_BY_ID)


class TestNaverConnector(unittest.TestCase):
    def setUp(self):
        import os
        os.environ["NAVER_CLIENT_ID"] = "cid"
        os.environ["NAVER_CLIENT_SECRET"] = "csec"

    def tearDown(self):
        import os
        os.environ.pop("NAVER_CLIENT_ID", None)
        os.environ.pop("NAVER_CLIENT_SECRET", None)

    def test_discover_parses_and_strips_html(self):
        def fake(url, headers=None, timeout=10):
            self.assertIn("openapi.naver.com", url)
            return {"items": [
                {"title": "<b>변색</b>렌즈 후기", "link": "http://x/1",
                 "description": "정말 <b>좋아요</b>&nbsp;"},
            ]}
        out = C.discover_naver("변색렌즈", "nv_blog", "blog", 5, http_get_json=fake)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].title, "변색렌즈 후기")
        self.assertNotIn("<b>", out[0].snippet)
        self.assertEqual(out[0].source_policy_id, "nv_blog")

    def test_missing_key_raises(self):
        import os
        os.environ.pop("NAVER_CLIENT_ID", None)
        with self.assertRaises(C.ResearchKeyMissing):
            C.discover_naver("kw", "nv_blog", "blog", 5, http_get_json=lambda *a, **k: {})


class TestGoogleCse(unittest.TestCase):
    def test_site_query_and_parse(self):
        import os
        os.environ["GOOGLE_CSE_API_KEY"] = "k"
        os.environ["GOOGLE_CSE_CX"] = "cx"
        captured = {}

        def fake(url, headers=None, timeout=10):
            captured["url"] = url
            return {"items": [{"title": "T", "link": "http://t/1", "snippet": "s"}]}
        try:
            out = C.discover_google_cse("렌즈", "theqoo", "theqoo.net", 3, http_get_json=fake)
        finally:
            os.environ.pop("GOOGLE_CSE_API_KEY", None)
            os.environ.pop("GOOGLE_CSE_CX", None)
        self.assertIn("site%3Atheqoo.net", captured["url"])  # site: url-encoded
        self.assertEqual(out[0].url, "http://t/1")


class TestFetchHelpers(unittest.TestCase):
    def test_classify_http_status(self):
        self.assertIsNone(F.classify_http_status(200))
        self.assertEqual(F.classify_http_status(403), "BLOCKED_403")
        self.assertEqual(F.classify_http_status(429), "RATE_LIMIT_429")
        self.assertEqual(F.classify_http_status(500), "NETWORK")

    def test_decode_cp949_fallback(self):
        text = "변색렌즈 가성비 후기"
        cp949_bytes = text.encode("cp949")
        # utf-8로 디코드하면 깨지므로 cp949로 복원돼야 함
        self.assertEqual(F._decode(cp949_bytes, None), text)

    def test_decode_utf8_passthrough(self):
        text = "변색렌즈"
        self.assertEqual(F._decode(text.encode("utf-8"), "utf-8"), text)

    def test_extract_comments_site_selector(self):
        html = (
            '<html><body>'
            '<div class="u_cbox_comment_box"><span class="u_cbox_contents">싸고 좋아요</span></div>'
            '<div class="u_cbox_comment_box"><span class="u_cbox_contents">또 살래요</span></div>'
            '</body></html>'
        )
        comments, count = F.extract_comments(html, "nv_blog")
        self.assertEqual(count, 2)
        self.assertIn("싸고 좋아요", comments)

    def test_extract_comments_generic_fallback(self):
        html = '<div class="comment-content">반응1</div><div class="comment-content">반응2</div>'
        comments, count = F.extract_comments(html, "unknown_site")
        self.assertEqual(count, 2)

    def test_to_mobile_naver(self):
        self.assertEqual(F._to_mobile("https://blog.naver.com/abc/123"),
                         "https://m.blog.naver.com/abc/123")
        self.assertEqual(F._to_mobile("https://cafe.naver.com/x/1"),
                         "https://m.cafe.naver.com/x/1")


class TestInsight(unittest.TestCase):
    def test_prompt_includes_comments(self):
        docs = [{"title": "후기", "content": "본문내용", "comments": "댓글내용",
                 "comment_count": 3, "source_label": "네이버 블로그"}]
        p = I.build_research_prompt("변색렌즈", docs)
        self.assertIn("변색렌즈", p)
        self.assertIn("[댓글 3개]", p)
        self.assertIn("댓글내용", p)
        self.assertIn("네이버 블로그", p)

    def test_parse_json_codeblock(self):
        text = '```json\n{"verdict":"좋음","pain_points":["비쌈"],"hook_ideas":["0원 한정"],"competitors":[{"name":"A안경","mention_count":2,"sentiment":"positive"}]}\n```'
        r = I.parse_research_result(text)
        self.assertEqual(r["verdict"], "좋음")
        self.assertEqual(r["pain_points"], ["비쌈"])
        self.assertEqual(r["hook_ideas"], ["0원 한정"])
        self.assertEqual(r["competitors"][0]["name"], "A안경")
        self.assertEqual(r["competitors"][0]["sentiment"], "positive")

    def test_parse_raw_json_and_sentiment_normalize(self):
        text = '쓸데없는말 {"verdict":"v","competitors":[{"name":"B","mention_count":"3","sentiment":"좋음"}]} 뒤'
        r = I.parse_research_result(text)
        self.assertEqual(r["verdict"], "v")
        self.assertEqual(r["competitors"][0]["mention_count"], 3)
        self.assertEqual(r["competitors"][0]["sentiment"], "neutral")  # 알 수 없는 값 → neutral

    def test_parse_fallback_on_garbage(self):
        r = I.parse_research_result("그냥 텍스트, JSON 아님")
        self.assertEqual(r["pain_points"], [])
        self.assertTrue(r["verdict"])  # 원문 일부를 verdict로


class TestPipeline(unittest.TestCase):
    def test_discover_dedup(self):
        import os
        os.environ["NAVER_CLIENT_ID"] = "c"
        os.environ["NAVER_CLIENT_SECRET"] = "s"
        # 두 소스가 같은 URL을 반환해도 1개로 dedup
        orig = C.discover_naver

        def fake_discover_naver(kw, sid, t, lim, http_get_json=None):
            return [C.DiscoveryResult("t", "http://dup/1", "s", 1, sid)]
        C.discover_naver = fake_discover_naver
        try:
            results, missing = P.discover("kw", ["nv_blog", "nv_kin"], 5)
        finally:
            C.discover_naver = orig
            os.environ.pop("NAVER_CLIENT_ID", None)
            os.environ.pop("NAVER_CLIENT_SECRET", None)
        self.assertEqual(len(results), 1)

    def test_discover_records_key_missing(self):
        # 키 없으면 해당 소스 label이 key_missing에 기록되고 결과는 빔
        results, missing = P.discover("kw", ["nv_blog"], 5)
        self.assertEqual(results, [])
        self.assertIn("네이버 블로그", missing)

    def test_analyze_uses_injected_generate(self):
        docs = [{"title": "t", "content": "c", "comments": "", "comment_count": 0,
                 "source_label": "네이버 블로그"}]
        captured = {}

        def fake_gen(prompt, system_prompt=None):
            captured["prompt"] = prompt
            captured["sys"] = system_prompt
            return '{"verdict":"분석됨","content_angles":["앵글1","앵글2"]}'
        out = P.analyze("렌즈", docs, fake_gen)
        self.assertEqual(out["verdict"], "분석됨")
        self.assertEqual(out["content_angles"], ["앵글1", "앵글2"])
        self.assertIn("렌즈", captured["prompt"])
        self.assertEqual(captured["sys"], I.SYSTEM_GUIDE_RESEARCH)

    def test_analyze_empty_docs(self):
        out = P.analyze("kw", [], lambda *a, **k: "x")
        self.assertEqual(out, dict(I._EMPTY))


if __name__ == "__main__":
    unittest.main()
