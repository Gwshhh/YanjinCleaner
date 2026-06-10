from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from cleaner_app.update_checker import UpdateChecker, UpdateInfo


MOCK_RELEASE = {
    "tag_name": "v2.0.0",
    "name": "Version 2.0.0",
    "body": "## Changes\n- New feature\n- Bug fix",
    "published_at": "2026-06-10T12:00:00Z",
    "assets": [
        {
            "name": "YanjinCleaner.exe",
            "browser_download_url": "https://github.com/owner/repo/releases/download/v2.0.0/YanjinCleaner.exe",
            "size": 5242880,
        },
        {
            "name": "YanjinCleaner.exe.sha256",
            "browser_download_url": "https://github.com/owner/repo/releases/download/v2.0.0/YanjinCleaner.exe.sha256",
            "size": 96,
        },
    ],
}

MOCK_OLD_RELEASE = {
    "tag_name": "v0.0.1",
    "name": "Version 0.0.1",
    "body": "Old release",
    "published_at": "2025-01-01T00:00:00Z",
    "assets": [
        {
            "name": "YanjinCleaner.exe",
            "browser_download_url": "https://example.com/old.exe",
            "size": 1000,
        },
    ],
}

MOCK_NO_ASSETS = {
    "tag_name": "v3.0.0",
    "body": "",
    "published_at": "",
    "assets": [],
}


def _mock_urlopen(data: dict):
    response = MagicMock()
    response.read.return_value = json.dumps(data).encode("utf-8")
    response.__enter__ = lambda s: s
    response.__exit__ = MagicMock(return_value=False)
    return response


class UpdateCheckerTests(unittest.TestCase):
    @patch("cleaner_app.update_checker.urllib.request.urlopen")
    def test_finds_newer_version(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen(MOCK_RELEASE)
        checker = UpdateChecker()
        info = checker.check_for_updates()
        self.assertIsNotNone(info)
        self.assertEqual(info.version, "2.0.0")
        self.assertIn("YanjinCleaner.exe", info.download_url)
        self.assertIn(".sha256", info.checksum_url)
        self.assertEqual(info.size_bytes, 5242880)
        self.assertIn("New feature", info.changelog)

    @patch("cleaner_app.update_checker.urllib.request.urlopen")
    def test_returns_none_for_older_version(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen(MOCK_OLD_RELEASE)
        checker = UpdateChecker()
        info = checker.check_for_updates()
        self.assertIsNone(info)

    @patch("cleaner_app.update_checker.urllib.request.urlopen")
    def test_returns_none_on_no_assets(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen(MOCK_NO_ASSETS)
        checker = UpdateChecker()
        info = checker.check_for_updates()
        self.assertIsNone(info)

    @patch("cleaner_app.update_checker.urllib.request.urlopen")
    def test_returns_none_on_network_error(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = Exception("network error")
        checker = UpdateChecker()
        info = checker.check_for_updates()
        self.assertIsNone(info)

    @patch("cleaner_app.update_checker.urllib.request.urlopen")
    def test_caches_result(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen(MOCK_RELEASE)
        checker = UpdateChecker()

        info1 = checker.check_for_updates()
        self.assertIsNotNone(info1)
        self.assertEqual(mock_urlopen.call_count, 1)

        mock_urlopen.return_value = _mock_urlopen(MOCK_RELEASE)
        info2 = checker.check_for_updates()
        self.assertIsNotNone(info2)
        self.assertEqual(mock_urlopen.call_count, 1)


class UpdateInfoTests(unittest.TestCase):
    def test_dataclass_fields(self) -> None:
        info = UpdateInfo(
            version="1.0.0",
            download_url="https://example.com/app.exe",
            checksum_url="https://example.com/app.exe.sha256",
            changelog="test",
            release_date="2026-01-01",
            size_bytes=1024,
        )
        self.assertEqual(info.version, "1.0.0")
        self.assertEqual(info.size_bytes, 1024)


if __name__ == "__main__":
    unittest.main()
