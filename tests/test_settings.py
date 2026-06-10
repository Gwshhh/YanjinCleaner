from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.helpers import temporary_workspace_dir
from cleaner_app.settings import UserSettings


class UserSettingsTests(unittest.TestCase):
    def test_load_returns_defaults_when_file_missing(self) -> None:
        with temporary_workspace_dir() as workspace:
            fake_path = Path(workspace) / "missing" / "settings.json"
            original = UserSettings._settings_path
            UserSettings._settings_path = staticmethod(lambda: fake_path)
            try:
                settings = UserSettings.load()
                self.assertEqual(settings.min_age_hours, 24)
                self.assertEqual(settings.max_scan_depth, 7)
                self.assertEqual(settings.max_dirs_per_drive, 12000)
                self.assertEqual(settings.excluded_paths, [])
                self.assertTrue(settings.auto_select_low_risk)
            finally:
                UserSettings._settings_path = original

    def test_save_then_load_roundtrips(self) -> None:
        with temporary_workspace_dir() as workspace:
            fake_path = Path(workspace) / "settings.json"
            original = UserSettings._settings_path
            UserSettings._settings_path = staticmethod(lambda: fake_path)
            try:
                settings = UserSettings(
                    min_age_hours=12,
                    max_scan_depth=5,
                    max_dirs_per_drive=8000,
                    excluded_paths=["D:\\MyProject"],
                    auto_select_low_risk=False,
                )
                settings.save()
                loaded = UserSettings.load()
                self.assertEqual(loaded.min_age_hours, 12)
                self.assertEqual(loaded.max_scan_depth, 5)
                self.assertEqual(loaded.max_dirs_per_drive, 8000)
                self.assertEqual(loaded.excluded_paths, ["D:\\MyProject"])
                self.assertFalse(loaded.auto_select_low_risk)
            finally:
                UserSettings._settings_path = original

    def test_load_returns_defaults_on_corrupt_json(self) -> None:
        with temporary_workspace_dir() as workspace:
            fake_path = Path(workspace) / "settings.json"
            fake_path.write_text("{invalid json!!!", encoding="utf-8")
            original = UserSettings._settings_path
            UserSettings._settings_path = staticmethod(lambda: fake_path)
            try:
                settings = UserSettings.load()
                self.assertEqual(settings.min_age_hours, 24)
            finally:
                UserSettings._settings_path = original

    def test_load_handles_bad_type_values(self) -> None:
        with temporary_workspace_dir() as workspace:
            fake_path = Path(workspace) / "settings.json"
            fake_path.write_text(
                json.dumps({"min_age_hours": "not_a_number"}),
                encoding="utf-8",
            )
            original = UserSettings._settings_path
            UserSettings._settings_path = staticmethod(lambda: fake_path)
            try:
                settings = UserSettings.load()
                self.assertEqual(settings.min_age_hours, 24)
            finally:
                UserSettings._settings_path = original


if __name__ == "__main__":
    unittest.main()
