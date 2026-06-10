from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from cleaner_app.models import CleanupItem, ItemKind, RiskLevel
from cleaner_app.safety import SafetyGuard
from tests.helpers import temporary_workspace_dir


class SafetyGuardTests(unittest.TestCase):
    def test_blocks_protected_directory_children(self) -> None:
        with temporary_workspace_dir() as temp:
            protected = Path(temp) / "Documents"
            target = protected / "important.txt"
            target.parent.mkdir()
            target.write_text("keep", encoding="utf-8")

            guard = SafetyGuard(protected_paths=[protected.resolve()])
            allowed, reason = guard.validate_path(target)

            self.assertFalse(allowed)
            self.assertIn("受保护路径", reason)

    def test_allows_safe_temp_file(self) -> None:
        with temporary_workspace_dir() as temp:
            target = Path(temp) / "cache" / "data.tmp"
            target.parent.mkdir()
            target.write_text("junk", encoding="utf-8")

            guard = SafetyGuard(protected_paths=[])
            allowed, _ = guard.validate_path(target)

            self.assertTrue(allowed)

    def test_blocks_default_onedrive_children(self) -> None:
        with temporary_workspace_dir() as temp:
            base = Path(temp)
            profile = base / "User"
            onedrive = profile / "OneDrive"
            target = onedrive / "Temp" / "cache.tmp"
            target.parent.mkdir(parents=True)
            target.write_text("keep", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "USERPROFILE": str(profile),
                    "OneDrive": str(onedrive),
                    "WINDIR": str(base / "Windows"),
                    "ProgramFiles": str(base / "Program Files"),
                    "ProgramFiles(x86)": str(base / "Program Files (x86)"),
                },
                clear=False,
            ):
                guard = SafetyGuard()

            allowed, reason = guard.validate_path(target)

            self.assertFalse(allowed)
            self.assertIn(str(onedrive.resolve()), reason)

    def test_blocks_high_risk_item(self) -> None:
        with temporary_workspace_dir() as temp:
            target = Path(temp) / "service.marker"
            target.write_text("service", encoding="utf-8")
            item = CleanupItem(
                item_id="x",
                title="service",
                path=str(target),
                kind=ItemKind.SERVICE,
                risk=RiskLevel.HIGH,
                category="服务检查",
                vendor="test",
                description="high risk",
                safe_reason="inspect only",
                selected=True,
            )

            guard = SafetyGuard(protected_paths=[])
            allowed, reason = guard.validate_item(item)

            self.assertFalse(allowed)
            self.assertIn("非文件系统项目", reason)


if __name__ == "__main__":
    unittest.main()
