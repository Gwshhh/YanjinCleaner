from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.helpers import temporary_workspace_dir
from cleaner_app.update_checker import UpdateInfo
from cleaner_app.update_downloader import UpdateDownloader, list_backups, _cleanup_old_backups


class DownloaderChecksumTests(unittest.TestCase):
    def test_verify_correct_checksum(self) -> None:
        with temporary_workspace_dir() as workspace:
            file_path = Path(workspace) / "test.exe"
            content = b"hello world"
            file_path.write_bytes(content)
            expected = hashlib.sha256(content).hexdigest()
            downloader = UpdateDownloader()
            self.assertTrue(downloader.verify_checksum(file_path, expected))

    def test_verify_wrong_checksum(self) -> None:
        with temporary_workspace_dir() as workspace:
            file_path = Path(workspace) / "test.exe"
            file_path.write_bytes(b"hello world")
            downloader = UpdateDownloader()
            self.assertFalse(downloader.verify_checksum(file_path, "0" * 64))

    def test_verify_case_insensitive(self) -> None:
        with temporary_workspace_dir() as workspace:
            file_path = Path(workspace) / "test.exe"
            content = b"test data"
            file_path.write_bytes(content)
            expected = hashlib.sha256(content).hexdigest().upper()
            downloader = UpdateDownloader()
            self.assertTrue(downloader.verify_checksum(file_path, expected))


class BackupTests(unittest.TestCase):
    def test_cleanup_old_backups(self) -> None:
        with temporary_workspace_dir() as workspace:
            backup_dir = Path(workspace) / "backups"
            backup_dir.mkdir()
            import time
            for i in range(5):
                f = backup_dir / f"YanjinCleaner_v{i}.exe.bak"
                f.write_bytes(b"test")
                time.sleep(0.05)
            _cleanup_old_backups(backup_dir, keep=2)
            remaining = list(backup_dir.glob("*.exe.bak"))
            self.assertEqual(len(remaining), 2)

    def test_list_backups_empty(self) -> None:
        with temporary_workspace_dir() as workspace:
            backup_dir = Path(workspace) / "nonexistent"
            with patch("cleaner_app.update_downloader.get_backup_dir", return_value=backup_dir):
                result = list_backups()
                self.assertEqual(result, [])

    def test_list_backups_with_files(self) -> None:
        with temporary_workspace_dir() as workspace:
            backup_dir = Path(workspace) / "backups"
            backup_dir.mkdir()
            for name in ["YanjinCleaner_v1.0.0.exe.bak", "YanjinCleaner_v1.1.0.exe.bak"]:
                (backup_dir / name).write_bytes(b"test")
            with patch("cleaner_app.update_downloader.get_backup_dir", return_value=backup_dir):
                result = list_backups()
                self.assertEqual(len(result), 2)


class DownloadUpdateTests(unittest.TestCase):
    @patch("cleaner_app.update_downloader.UpdateDownloader.download")
    @patch("cleaner_app.update_downloader.UpdateDownloader.verify_checksum")
    def test_download_update_success_no_checksum(self, mock_verify, mock_download) -> None:
        with temporary_workspace_dir() as workspace:
            dest = Path(workspace) / "update.exe"
            mock_download.return_value = dest

            info = UpdateInfo(
                version="2.0.0",
                download_url="https://example.com/app.exe",
                checksum_url="",
                changelog="",
                release_date="",
                size_bytes=1024,
            )

            downloader = UpdateDownloader()
            ok, msg, path = downloader.download_update(info)
            self.assertTrue(ok)
            self.assertEqual(msg, "下载完成")
            mock_verify.assert_not_called()

    @patch("cleaner_app.update_downloader.UpdateDownloader.download")
    def test_download_update_network_failure(self, mock_download) -> None:
        import urllib.error
        mock_download.side_effect = urllib.error.URLError("connection refused")

        info = UpdateInfo(
            version="2.0.0",
            download_url="https://example.com/app.exe",
            checksum_url="",
            changelog="",
            release_date="",
            size_bytes=1024,
        )

        downloader = UpdateDownloader()
        ok, msg, path = downloader.download_update(info)
        self.assertFalse(ok)
        self.assertIn("网络", msg)
        self.assertIsNone(path)


if __name__ == "__main__":
    unittest.main()
