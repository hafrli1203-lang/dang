"""Unit tests for app.paths module."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestPathConstants(unittest.TestCase):
    """Verify that path constants are correctly initialised."""

    def test_data_dir_is_absolute_and_exists(self):
        from app.paths import DATA_DIR
        self.assertTrue(DATA_DIR.is_absolute())
        self.assertTrue(DATA_DIR.exists())

    def test_db_path_under_data_dir(self):
        from app.paths import DATA_DIR, DB_PATH
        self.assertEqual(DB_PATH.parent, DATA_DIR)
        self.assertEqual(DB_PATH.name, "daangn_ads.db")

    def test_log_path_under_data_dir(self):
        from app.paths import DATA_DIR, LOG_PATH
        self.assertEqual(LOG_PATH.parent, DATA_DIR)
        self.assertEqual(LOG_PATH.name, "app.log")

    def test_subdirs_exist(self):
        from app.paths import EXPORTS_DIR, CHARTS_DIR, STORAGE_DIR
        for d in (EXPORTS_DIR, CHARTS_DIR, STORAGE_DIR):
            with self.subTest(d=d):
                self.assertTrue(d.exists(), f"{d} should exist")
                self.assertTrue(d.is_dir(), f"{d} should be a directory")

    def test_is_frozen_false_in_dev(self):
        from app.paths import IS_FROZEN
        self.assertFalse(IS_FROZEN)


class TestGetEnvPath(unittest.TestCase):
    """Test get_env_path() with isolated temp directories."""

    def test_returns_none_when_no_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch("app.paths.DATA_DIR", tmp_path), \
                 patch("app.paths.APP_DIR", tmp_path):
                from app.paths import get_env_path
                self.assertIsNone(get_env_path())

    def test_prefers_data_dir_over_app_dir(self):
        with tempfile.TemporaryDirectory() as data_tmp, \
             tempfile.TemporaryDirectory() as app_tmp:
            data_dir = Path(data_tmp)
            app_dir = Path(app_tmp)
            (data_dir / ".env").write_text("DATA")
            (app_dir / ".env").write_text("APP")
            with patch("app.paths.DATA_DIR", data_dir), \
                 patch("app.paths.APP_DIR", app_dir):
                from app.paths import get_env_path
                result = get_env_path()
                self.assertIsNotNone(result)
                self.assertEqual(result, data_dir / ".env")

    def test_falls_back_to_app_dir(self):
        with tempfile.TemporaryDirectory() as data_tmp, \
             tempfile.TemporaryDirectory() as app_tmp:
            data_dir = Path(data_tmp)
            app_dir = Path(app_tmp)
            # Only .env in app_dir
            (app_dir / ".env").write_text("APP")
            with patch("app.paths.DATA_DIR", data_dir), \
                 patch("app.paths.APP_DIR", app_dir):
                from app.paths import get_env_path
                result = get_env_path()
                self.assertIsNotNone(result)
                self.assertEqual(result, app_dir / ".env")


class TestMigrateLegacyFiles(unittest.TestCase):
    """Test migrate_legacy_files() with isolated temp directories."""

    def test_copies_db_when_missing_in_data_dir(self):
        from app.paths import migrate_legacy_files
        with tempfile.TemporaryDirectory() as src_tmp, \
             tempfile.TemporaryDirectory() as dst_tmp:
            src_dir = Path(src_tmp)
            dst_dir = Path(dst_tmp)
            (src_dir / "daangn_ads.db").write_text("TESTDB")
            with patch("app.paths.APP_DIR", src_dir), \
                 patch("app.paths.DATA_DIR", dst_dir):
                result = migrate_legacy_files()
            self.assertTrue(len(result) > 0)
            self.assertTrue((dst_dir / "daangn_ads.db").exists())
            self.assertEqual((dst_dir / "daangn_ads.db").read_text(), "TESTDB")
            # Source preserved
            self.assertTrue((src_dir / "daangn_ads.db").exists())

    def test_does_not_overwrite_existing(self):
        from app.paths import migrate_legacy_files
        with tempfile.TemporaryDirectory() as src_tmp, \
             tempfile.TemporaryDirectory() as dst_tmp:
            src_dir = Path(src_tmp)
            dst_dir = Path(dst_tmp)
            (src_dir / "daangn_ads.db").write_text("OLD")
            (dst_dir / "daangn_ads.db").write_text("NEW")
            with patch("app.paths.APP_DIR", src_dir), \
                 patch("app.paths.DATA_DIR", dst_dir):
                result = migrate_legacy_files()
            self.assertEqual(len(result), 0)
            self.assertEqual((dst_dir / "daangn_ads.db").read_text(), "NEW")

    def test_skips_when_src_equals_dst(self):
        from app.paths import migrate_legacy_files
        with tempfile.TemporaryDirectory() as same_tmp:
            same_dir = Path(same_tmp)
            (same_dir / "daangn_ads.db").write_text("DATA")
            with patch("app.paths.APP_DIR", same_dir), \
                 patch("app.paths.DATA_DIR", same_dir):
                result = migrate_legacy_files()
            self.assertEqual(len(result), 0)

    def test_returns_empty_when_no_legacy(self):
        from app.paths import migrate_legacy_files
        with tempfile.TemporaryDirectory() as src_tmp, \
             tempfile.TemporaryDirectory() as dst_tmp:
            with patch("app.paths.APP_DIR", Path(src_tmp)), \
                 patch("app.paths.DATA_DIR", Path(dst_tmp)):
                result = migrate_legacy_files()
            self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
