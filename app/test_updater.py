"""Unit tests for app.updater — no network calls needed."""
import json
import unittest
from unittest.mock import patch, MagicMock


class TestParseVersion(unittest.TestCase):

    def test_standard_version(self):
        from app.updater import _parse_version
        self.assertEqual(_parse_version("1.2.3"), (1, 2, 3))

    def test_v_prefix(self):
        from app.updater import _parse_version
        self.assertEqual(_parse_version("v2.0.1"), (2, 0, 1))

    def test_two_parts(self):
        from app.updater import _parse_version
        self.assertEqual(_parse_version("1.5"), (1, 5))

    def test_empty_string(self):
        from app.updater import _parse_version
        self.assertEqual(_parse_version(""), (0,))


class TestCheckForUpdate(unittest.TestCase):

    @patch("app.updater.GITHUB_REPO", "")
    def test_disabled_when_no_repo(self):
        from app.updater import check_for_update
        self.assertIsNone(check_for_update("1.0.0"))

    @patch("app.updater.GITHUB_REPO", "org/repo")
    @patch("urllib.request.urlopen")
    def test_newer_version_available(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "tag_name": "v2.0.0",
            "html_url": "https://github.com/org/repo/releases/tag/v2.0.0",
            "body": "New features",
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        from app.updater import check_for_update
        result = check_for_update("1.0.0")

        self.assertIsNotNone(result)
        self.assertEqual(result["version"], "2.0.0")
        self.assertIn("github.com", result["url"])

    @patch("app.updater.GITHUB_REPO", "org/repo")
    @patch("urllib.request.urlopen")
    def test_same_version_returns_none(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/org/repo/releases/tag/v1.0.0",
            "body": "",
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        from app.updater import check_for_update
        self.assertIsNone(check_for_update("1.0.0"))

    @patch("app.updater.GITHUB_REPO", "org/repo")
    @patch("urllib.request.urlopen", side_effect=Exception("network error"))
    def test_network_error_returns_none(self, mock_urlopen):
        from app.updater import check_for_update
        self.assertIsNone(check_for_update("1.0.0"))


if __name__ == "__main__":
    unittest.main()
