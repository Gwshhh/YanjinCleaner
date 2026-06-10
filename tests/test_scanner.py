from __future__ import annotations

import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from cleaner_app.models import RiskLevel
from cleaner_app.scanner import CleanupScanner
from cleaner_app.safety import SafetyGuard
from tests.helpers import temporary_workspace_dir


def make_old(path: Path) -> None:
    old_timestamp = time.time() - (3 * 24 * 60 * 60)
    os.utime(path, (old_timestamp, old_timestamp))


class CleanupScannerTests(unittest.TestCase):
    def test_scanner_finds_2345_cache_from_rule_catalog(self) -> None:
        with temporary_workspace_dir() as temp:
            base = Path(temp)
            local = base / "LocalAppData"
            appdata = base / "AppData"
            program_data = base / "ProgramData"
            temp_dir = base / "Temp"
            for directory in (local, appdata, program_data, temp_dir):
                directory.mkdir()
            cache_file = local / "2345Foo" / "BrowserCache" / "cache.bin"
            cache_file.parent.mkdir(parents=True)
            cache_file.write_text("junk", encoding="utf-8")

            env = {
                "LOCALAPPDATA": str(local),
                "APPDATA": str(appdata),
                "PROGRAMDATA": str(program_data),
                "TEMP": str(temp_dir),
                "TMP": str(temp_dir),
                "WINDIR": str(base / "Windows"),
            }
            with patch.dict(os.environ, env, clear=False):
                with patch.object(CleanupScanner, "_fixed_drive_roots", return_value=[]):
                    scanner = CleanupScanner(SafetyGuard(protected_paths=[]))
                    report = scanner.scan(include_high_risk=False)

            matches = [item for item in report.items if "2345" in item.vendor or "2345" in item.title]
            self.assertTrue(matches)
            self.assertEqual(matches[0].risk, RiskLevel.MEDIUM)
            self.assertFalse(matches[0].selected)

    def test_scanner_finds_safe_junk_on_all_fixed_drives(self) -> None:
        with temporary_workspace_dir() as temp:
            base = Path(temp)
            local = base / "LocalAppData"
            appdata = base / "AppData"
            program_data = base / "ProgramData"
            temp_dir = base / "UserTemp"
            drive_c = base / "C"
            drive_d = base / "D"
            drive_e = base / "E"
            for directory in (local, appdata, program_data, temp_dir, drive_c, drive_d, drive_e):
                directory.mkdir()
            c_log_file = drive_c / "Logs" / "setup.log"
            c_log_file.parent.mkdir()
            c_log_file.write_text("log", encoding="utf-8")
            make_old(c_log_file)
            d_temp_file = drive_d / "Temp" / "junk.tmp"
            d_temp_file.parent.mkdir()
            d_temp_file.write_text("junk", encoding="utf-8")
            make_old(d_temp_file)
            d_new_temp_file = drive_d / "Temp" / "fresh.tmp"
            d_new_temp_file.write_text("fresh", encoding="utf-8")
            d_cache_file = drive_d / "Cache" / "asset.bin"
            d_cache_file.parent.mkdir()
            d_cache_file.write_text("cache", encoding="utf-8")
            d_log_file = drive_d / "Projects" / "Logs" / "run.log"
            d_log_file.parent.mkdir(parents=True)
            d_log_file.write_text("log", encoding="utf-8")
            make_old(d_log_file)
            d_backup_file = drive_d / "Projects" / "backup.bak"
            d_backup_file.write_text("backup", encoding="utf-8")
            e_temp_file = drive_e / "Tmp" / "leftover.temp"
            e_temp_file.parent.mkdir()
            e_temp_file.write_text("temp", encoding="utf-8")
            make_old(e_temp_file)

            env = {
                "LOCALAPPDATA": str(local),
                "APPDATA": str(appdata),
                "PROGRAMDATA": str(program_data),
                "TEMP": str(temp_dir),
                "TMP": str(temp_dir),
                "WINDIR": str(base / "Windows"),
            }
            with patch.dict(os.environ, env, clear=False):
                with patch.object(
                    CleanupScanner,
                    "_fixed_drive_roots",
                    return_value=[drive_c, drive_d, drive_e],
                ):
                    scanner = CleanupScanner(SafetyGuard(protected_paths=[]))
                    report = scanner.scan(include_high_risk=False)

            paths = {Path(item.path) for item in report.items}
            self.assertIn(c_log_file, paths)
            self.assertIn(d_temp_file, paths)
            self.assertIn(d_new_temp_file, paths)
            self.assertIn(d_cache_file, paths)
            self.assertIn(d_log_file, paths)
            self.assertIn(d_backup_file, paths)
            self.assertIn(e_temp_file, paths)
            by_path = {Path(item.path): item for item in report.items}
            self.assertTrue(by_path[c_log_file].selected)
            self.assertTrue(by_path[d_temp_file].selected)
            self.assertFalse(by_path[d_new_temp_file].selected)
            self.assertFalse(by_path[d_cache_file].selected)
            self.assertTrue(by_path[d_log_file].selected)
            self.assertFalse(by_path[d_backup_file].selected)
            self.assertTrue(by_path[e_temp_file].selected)

    def test_official_low_risk_windows_cache_can_be_default_selected_when_old(self) -> None:
        with temporary_workspace_dir() as temp:
            base = Path(temp)
            local = base / "LocalAppData"
            appdata = base / "AppData"
            program_data = base / "ProgramData"
            temp_dir = base / "UserTemp"
            explorer = local / "Microsoft" / "Windows" / "Explorer"
            for directory in (local, appdata, program_data, temp_dir, explorer):
                directory.mkdir(parents=True, exist_ok=True)
            thumbcache = explorer / "thumbcache_256.db"
            thumbcache.write_text("cache", encoding="utf-8")
            make_old(thumbcache)

            env = {
                "LOCALAPPDATA": str(local),
                "APPDATA": str(appdata),
                "PROGRAMDATA": str(program_data),
                "TEMP": str(temp_dir),
                "TMP": str(temp_dir),
                "WINDIR": str(base / "Windows"),
            }
            with patch.dict(os.environ, env, clear=False):
                with patch.object(CleanupScanner, "_fixed_drive_roots", return_value=[]):
                    scanner = CleanupScanner(SafetyGuard(protected_paths=[]))
                    report = scanner.scan(include_high_risk=False)

            by_path = {Path(item.path): item for item in report.items}
            self.assertIn(thumbcache, by_path)
            self.assertEqual(by_path[thumbcache].source_rule, "official.thumbnail_cache")
            self.assertEqual(by_path[thumbcache].risk, RiskLevel.LOW)
            self.assertTrue(by_path[thumbcache].selected)

    def test_system_cleanup_categories_are_inspection_only(self) -> None:
        with temporary_workspace_dir() as temp:
            base = Path(temp)
            local = base / "LocalAppData"
            appdata = base / "AppData"
            program_data = base / "ProgramData"
            temp_dir = base / "UserTemp"
            windows = base / "Windows"
            windows_temp = windows / "Temp"
            for directory in (local, appdata, program_data, temp_dir, windows_temp):
                directory.mkdir(parents=True, exist_ok=True)

            env = {
                "LOCALAPPDATA": str(local),
                "APPDATA": str(appdata),
                "PROGRAMDATA": str(program_data),
                "TEMP": str(temp_dir),
                "TMP": str(temp_dir),
                "WINDIR": str(windows),
                "SYSTEMDRIVE": str(base / "SystemDrive"),
            }
            with patch.dict(os.environ, env, clear=False):
                with patch.object(CleanupScanner, "_fixed_drive_roots", return_value=[]):
                    scanner = CleanupScanner(SafetyGuard(protected_paths=[]))
                    report = scanner.scan(include_high_risk=False)

            matches = [item for item in report.items if item.source_rule == "inspect.windows_temp"]
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].risk, RiskLevel.HIGH)
            self.assertFalse(matches[0].selected)
            self.assertFalse(matches[0].default_selected)
            self.assertFalse(matches[0].can_execute)
            self.assertFalse(matches[0].recoverable)

    def test_all_drive_scan_skips_protected_paths(self) -> None:
        with temporary_workspace_dir() as temp:
            base = Path(temp)
            local = base / "LocalAppData"
            appdata = base / "AppData"
            program_data = base / "ProgramData"
            temp_dir = base / "UserTemp"
            drive_d = base / "D"
            protected = drive_d / "Documents"
            for directory in (local, appdata, program_data, temp_dir, protected):
                directory.mkdir(parents=True)
            protected_log = protected / "Logs" / "private.log"
            protected_log.parent.mkdir()
            protected_log.write_text("private", encoding="utf-8")

            env = {
                "LOCALAPPDATA": str(local),
                "APPDATA": str(appdata),
                "PROGRAMDATA": str(program_data),
                "TEMP": str(temp_dir),
                "TMP": str(temp_dir),
                "WINDIR": str(base / "Windows"),
            }
            with patch.dict(os.environ, env, clear=False):
                with patch.object(CleanupScanner, "_fixed_drive_roots", return_value=[drive_d]):
                    scanner = CleanupScanner(SafetyGuard(protected_paths=[protected.resolve()]))
                    report = scanner.scan(include_high_risk=False)

            paths = {Path(item.path) for item in report.items}
            self.assertNotIn(protected_log, paths)


class ScannerCancellationTests(unittest.TestCase):
    def test_cancel_stops_scan_early(self) -> None:
        with temporary_workspace_dir() as temp:
            base = Path(temp)
            local = base / "LocalAppData"
            appdata = base / "AppData"
            program_data = base / "ProgramData"
            temp_dir = base / "UserTemp"
            drive = base / "DriveC"
            for directory in (local, appdata, program_data, temp_dir, drive):
                directory.mkdir()
            for i in range(50):
                folder = drive / "Temp" / f"sub{i}"
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "junk.tmp").write_text("x", encoding="utf-8")

            env = {
                "LOCALAPPDATA": str(local),
                "APPDATA": str(appdata),
                "PROGRAMDATA": str(program_data),
                "TEMP": str(temp_dir),
                "TMP": str(temp_dir),
                "WINDIR": str(base / "Windows"),
            }
            with patch.dict(os.environ, env, clear=False):
                with patch.object(CleanupScanner, "_fixed_drive_roots", return_value=[drive]):
                    scanner = CleanupScanner(SafetyGuard(protected_paths=[]))
                    scanner.cancel()
                    report = scanner.scan(include_high_risk=False)

            self.assertEqual(len(report.items), 0)

    def test_estimate_sizes_respects_cancellation(self) -> None:
        with temporary_workspace_dir() as temp:
            base = Path(temp)
            local = base / "LocalAppData"
            appdata = base / "AppData"
            program_data = base / "ProgramData"
            temp_dir = base / "UserTemp"
            drive = base / "DriveC"
            for directory in (local, appdata, program_data, temp_dir, drive):
                directory.mkdir()
            for i in range(10):
                f = drive / "Temp" / f"file{i}.tmp"
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text("data" * 100, encoding="utf-8")
                make_old(f)

            env = {
                "LOCALAPPDATA": str(local),
                "APPDATA": str(appdata),
                "PROGRAMDATA": str(program_data),
                "TEMP": str(temp_dir),
                "TMP": str(temp_dir),
                "WINDIR": str(base / "Windows"),
            }
            with patch.dict(os.environ, env, clear=False):
                with patch.object(CleanupScanner, "_fixed_drive_roots", return_value=[drive]):
                    scanner = CleanupScanner(SafetyGuard(protected_paths=[]))
                    report = scanner.scan(include_high_risk=False)

            scanner.cancel()
            scanner.estimate_sizes(report.items)
            zero_sizes = [item for item in report.items if item.size_bytes == 0 and item.is_file_system_item]
            self.assertTrue(len(zero_sizes) > 0)


if __name__ == "__main__":
    unittest.main()
