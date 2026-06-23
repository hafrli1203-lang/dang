# -*- coding: utf-8 -*-
"""DB 기록 모델 테스트 (격리 임시 DB) — 광고 기록 필드 + 썸네일 CRUD."""

import os
import tempfile
import unittest

import app.database as db


class _IsolatedDB(unittest.TestCase):
    """각 테스트마다 임시 DB로 격리 (실제 사용자 DB 미오염)."""

    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._tmp_path = tmp.name
        self._orig_path = db._db_path
        self._orig_migrate = db._migrate_legacy_db
        db._db_path = self._tmp_path
        db._migrate_legacy_db = lambda: None  # 실 DB 복사 방지
        db.init_db()

    def tearDown(self):
        db._db_path = self._orig_path
        db._migrate_legacy_db = self._orig_migrate
        try:
            os.unlink(self._tmp_path)
        except OSError:
            pass


class TestBriefingMessages(_IsolatedDB):
    """AI 상담 대화 매장별 저장/이어보기/비우기."""

    def test_save_and_load_in_order(self):
        pid = db.save_project({"name": "브리핑매장"})
        db.save_briefing_message(pid, "user", "이 행사 어떻게 풀지?")
        db.save_briefing_message(pid, "ai", "연령 찢어서 가시죠.")
        msgs = db.get_briefing_messages(pid)
        self.assertEqual(
            [(m["role"], m["text"]) for m in msgs],
            [("user", "이 행사 어떻게 풀지?"), ("ai", "연령 찢어서 가시죠.")],
        )

    def test_scoped_per_project(self):
        a = db.save_project({"name": "A"})
        b = db.save_project({"name": "B"})
        db.save_briefing_message(a, "user", "A질문")
        db.save_briefing_message(b, "user", "B질문")
        self.assertEqual([m["text"] for m in db.get_briefing_messages(a)], ["A질문"])
        self.assertEqual([m["text"] for m in db.get_briefing_messages(b)], ["B질문"])

    def test_clear_only_target_project(self):
        a = db.save_project({"name": "A"})
        b = db.save_project({"name": "B"})
        db.save_briefing_message(a, "user", "A")
        db.save_briefing_message(b, "user", "B")
        db.clear_briefing_messages(a)
        self.assertEqual(db.get_briefing_messages(a), [])
        self.assertEqual(len(db.get_briefing_messages(b)), 1)

    def test_empty_when_none(self):
        pid = db.save_project({"name": "빈"})
        self.assertEqual(db.get_briefing_messages(pid), [])


class TestAdObservations(_IsolatedDB):
    """경쟁 광고 관측 매장별 저장/복원/스냅샷 교체."""

    def _rows(self, *headlines):
        return [{
            "engine": "NAVER", "keyword": "렌즈", "headline": h, "description": "",
            "display_url": "", "landing_url": "", "position": i + 1,
            "heuristic_score": float(10 - i), "ad_type": "powerlink",
        } for i, h in enumerate(headlines)]

    def test_save_and_load_ordered_by_score(self):
        pid = db.save_project({"name": "관측매장"})
        db.save_ad_observations(pid, self._rows("A", "B", "C"))
        got = db.get_ad_observations(pid)
        # heuristic_score DESC → A(10) 먼저.
        self.assertEqual([r["headline"] for r in got], ["A", "B", "C"])
        self.assertEqual(got[0]["heuristic_score"], 10.0)

    def test_replace_is_latest_snapshot(self):
        pid = db.save_project({"name": "S"})
        db.save_ad_observations(pid, self._rows("old1", "old2"))
        db.save_ad_observations(pid, self._rows("new1"))
        got = db.get_ad_observations(pid)
        self.assertEqual([r["headline"] for r in got], ["new1"])

    def test_empty_list_keeps_existing(self):
        pid = db.save_project({"name": "S"})
        db.save_ad_observations(pid, self._rows("keep"))
        db.save_ad_observations(pid, [])  # 빈 관측은 기존 유지
        self.assertEqual(len(db.get_ad_observations(pid)), 1)

    def test_scoped_per_project(self):
        a = db.save_project({"name": "A"})
        b = db.save_project({"name": "B"})
        db.save_ad_observations(a, self._rows("Aad"))
        db.save_ad_observations(b, self._rows("Bad"))
        self.assertEqual([r["headline"] for r in db.get_ad_observations(a)], ["Aad"])
        self.assertEqual([r["headline"] for r in db.get_ad_observations(b)], ["Bad"])


class TestAdRecordFields(_IsolatedDB):
    def test_save_and_load_roundtrip(self):
        pid = db.save_project({
            "name": "엄마손반찬",
            "target_radius_km": "5", "target_gender": "여성",
            "target_age": "35~39,40~44", "bid_type": "자동 입찰",
            "daily_budget": "10,000원", "ad_titles": "제목A\n제목B",
            "coupon_info": "변색렌즈 0원",
        })
        p = db.get_project(pid)
        self.assertEqual(p["target_radius_km"], "5")
        self.assertEqual(p["target_gender"], "여성")
        self.assertEqual(p["target_age"], "35~39,40~44")
        self.assertEqual(p["ad_titles"], "제목A\n제목B")
        self.assertEqual(p["coupon_info"], "변색렌즈 0원")

    def test_partial_dict_is_safe(self):
        # name만 줘도 저장돼야 한다 (_PROJECT_DEFAULTS).
        pid = db.save_project({"name": "최소"})
        p = db.get_project(pid)
        self.assertEqual(p["name"], "최소")
        self.assertEqual(p["target_gender"], "")

    def test_update_persists_ad_fields(self):
        pid = db.save_project({"name": "S"})
        db.update_project(pid, {"name": "S", "target_radius_km": "3", "target_age": "20~24"})
        p = db.get_project(pid)
        self.assertEqual(p["target_radius_km"], "3")
        self.assertEqual(p["target_age"], "20~24")

    def test_migration_idempotent(self):
        # init_db 두 번 호출해도 에러 없어야 (ALTER 멱등).
        db.init_db()
        db.init_db()

    def test_latest_for_store(self):
        p1 = db.save_project({"name": "매장A", "target_radius_km": "5"})
        p2 = db.save_project({"name": "매장A", "target_radius_km": "3"})
        db.save_project({"name": "매장B"})
        latest = db.get_latest_project_for_store("매장A")
        self.assertEqual(latest["id"], p2)
        self.assertEqual(latest["target_radius_km"], "3")
        # 현재 캠페인 제외 → 직전 것
        prev = db.get_latest_project_for_store("매장A", exclude_id=p2)
        self.assertEqual(prev["id"], p1)
        # 없는 매장
        self.assertIsNone(db.get_latest_project_for_store("없는매장"))


class TestThumbnails(_IsolatedDB):
    def test_crud_roundtrip(self):
        pid = db.save_project({"name": "테스트매장"})
        t1 = db.save_thumbnail(pid, "/x/a.png", title="A", prompt="p1")
        db.save_thumbnail(pid, "/x/b.png", title="B")
        items = db.get_thumbnails(pid)
        self.assertEqual(len(items), 2)
        self.assertEqual({i["file_path"] for i in items}, {"/x/a.png", "/x/b.png"})
        one = db.get_thumbnail(t1)
        self.assertEqual(one["title"], "A")
        self.assertEqual(one["prompt"], "p1")

    def test_counts(self):
        p1 = db.save_project({"name": "A"})
        p2 = db.save_project({"name": "B"})
        db.save_thumbnail(p1, "/x/1.png")
        db.save_thumbnail(p1, "/x/2.png")
        db.save_thumbnail(p2, "/x/3.png")
        counts = db.get_thumbnail_counts()
        self.assertEqual(counts.get(p1), 2)
        self.assertEqual(counts.get(p2), 1)

    def test_delete(self):
        pid = db.save_project({"name": "S"})
        t = db.save_thumbnail(pid, "/x/a.png")
        db.delete_thumbnail(t)
        self.assertEqual(db.get_thumbnails(pid), [])
        self.assertIsNone(db.get_thumbnail(t))

    def test_empty(self):
        self.assertEqual(db.get_thumbnails(99999), [])
        self.assertEqual(db.get_thumbnail_counts(), {})


if __name__ == "__main__":
    unittest.main()
