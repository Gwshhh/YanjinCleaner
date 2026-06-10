from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from cleaner_app.executor import CleanupExecutor
from cleaner_app.models import ActionStatus, CleanupItem, ItemKind, RiskLevel
from cleaner_app.safety import SafetyGuard
from tests.helpers import temporary_workspace_dir


def make_item(path: Path, risk: RiskLevel = RiskLevel.LOW) -> CleanupItem:
    return CleanupItem(
        item_id="item-1",
        title="临时文件",
        path=str(path),
        kind=ItemKind.FILE,
        risk=risk,
        category="安全垃圾",
        vendor="test",
        description="temp",
        safe_reason="safe temp",
        size_bytes=path.stat().st_size,
        selected=True,
    )


class CleanupExecutorTests(unittest.TestCase):
    def test_uses_trash_function_for_selected_safe_item(self) -> None:
        with temporary_workspace_dir() as temp:
            temp_path = Path(temp)
            target = temp_path / "cache.tmp"
            target.write_text("junk", encoding="utf-8")
            calls: list[str] = []

            def fake_trash(path: str) -> None:
                calls.append(path)

            executor = CleanupExecutor(
                safety_guard=SafetyGuard(protected_paths=[]),
                app_data_dir=temp_path / "appdata",
                trash_func=fake_trash,
            )
            report = executor.execute([make_item(target)])

            self.assertEqual(calls, [str(target)])
            self.assertEqual(report.items[0].status, ActionStatus.TRASHED)
            self.assertEqual(report.errors, [])

    def test_falls_back_to_quarantine_without_trash_function(self) -> None:
        with temporary_workspace_dir() as temp:
            temp_path = Path(temp)
            target = temp_path / "cache.tmp"
            target.write_text("junk", encoding="utf-8")

            with patch("cleaner_app.executor.send2trash", None):
                executor = CleanupExecutor(
                    safety_guard=SafetyGuard(protected_paths=[]),
                    app_data_dir=temp_path / "appdata",
                )
                report = executor.execute([make_item(target)])

            self.assertEqual(report.items[0].status, ActionStatus.QUARANTINED)
            self.assertFalse(target.exists())
            self.assertTrue(
                any((temp_path / "appdata" / "quarantine").glob("*/manifest.json"))
            )

    def test_blocks_protected_item_before_execution(self) -> None:
        with temporary_workspace_dir() as temp:
            temp_path = Path(temp)
            protected = temp_path / "Documents"
            protected.mkdir()
            target = protected / "important.txt"
            target.write_text("keep", encoding="utf-8")
            calls: list[str] = []

            executor = CleanupExecutor(
                safety_guard=SafetyGuard(protected_paths=[protected.resolve()]),
                app_data_dir=temp_path / "appdata",
                trash_func=lambda path: calls.append(path),
            )
            report = executor.execute([make_item(target)])

            self.assertEqual(calls, [])
            self.assertEqual(report.items[0].status, ActionStatus.BLOCKED)
            self.assertTrue(target.exists())

    def test_lists_quarantine_records_after_fallback(self) -> None:
        with temporary_workspace_dir() as temp:
            temp_path = Path(temp)
            target = temp_path / "cache.tmp"
            target.write_text("junk", encoding="utf-8")

            with patch("cleaner_app.executor.send2trash", None):
                executor = CleanupExecutor(
                    safety_guard=SafetyGuard(protected_paths=[]),
                    app_data_dir=temp_path / "appdata",
                )
                executor.execute([make_item(target)])

            records = executor.list_quarantine_records()

            self.assertEqual(len(records), 1)
            self.assertTrue(records[0].valid)
            self.assertEqual(records[0].source, target)
            self.assertTrue(records[0].quarantined.exists())

    def test_restores_quarantined_item_to_original_path(self) -> None:
        with temporary_workspace_dir() as temp:
            temp_path = Path(temp)
            target = temp_path / "cache.tmp"
            target.write_text("junk", encoding="utf-8")

            with patch("cleaner_app.executor.send2trash", None):
                executor = CleanupExecutor(
                    safety_guard=SafetyGuard(protected_paths=[]),
                    app_data_dir=temp_path / "appdata",
                )
                executor.execute([make_item(target)])

            record = executor.list_quarantine_records()[0]
            ok, message = executor.restore_quarantine_item(record.manifest_path)

            self.assertTrue(ok, message)
            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(encoding="utf-8"), "junk")
            self.assertFalse(record.manifest_path.exists())
            self.assertEqual(executor.list_quarantine_records(), [])

    def test_restore_blocks_existing_original_path(self) -> None:
        with temporary_workspace_dir() as temp:
            temp_path = Path(temp)
            target = temp_path / "cache.tmp"
            target.write_text("junk", encoding="utf-8")

            with patch("cleaner_app.executor.send2trash", None):
                executor = CleanupExecutor(
                    safety_guard=SafetyGuard(protected_paths=[]),
                    app_data_dir=temp_path / "appdata",
                )
                executor.execute([make_item(target)])

            target.write_text("new file", encoding="utf-8")
            record = executor.list_quarantine_records()[0]
            quarantined = record.quarantined
            ok, message = executor.restore_quarantine_item(record.manifest_path)

            self.assertFalse(ok)
            self.assertIn("已阻止覆盖", message)
            self.assertEqual(target.read_text(encoding="utf-8"), "new file")
            self.assertTrue(quarantined.exists())

    def test_restore_rejects_manifest_outside_quarantine(self) -> None:
        with temporary_workspace_dir() as temp:
            temp_path = Path(temp)
            executor = CleanupExecutor(
                safety_guard=SafetyGuard(protected_paths=[]),
                app_data_dir=temp_path / "appdata",
                trash_func=None,
            )
            outside_manifest = temp_path / "manifest.json"
            outside_manifest.write_text(
                json.dumps({"source": str(temp_path / "x"), "quarantined": str(temp_path / "y")}),
                encoding="utf-8",
            )

            ok, message = executor.restore_quarantine_item(outside_manifest)

            self.assertFalse(ok)
            self.assertIn("不在应用隔离区", message)

    def test_restore_rejects_quarantined_path_outside_quarantine(self) -> None:
        with temporary_workspace_dir() as temp:
            temp_path = Path(temp)
            outside_file = temp_path / "outside.tmp"
            outside_file.write_text("outside", encoding="utf-8")
            executor = CleanupExecutor(
                safety_guard=SafetyGuard(protected_paths=[]),
                app_data_dir=temp_path / "appdata",
                trash_func=None,
            )
            batch = executor.quarantine_dir / "case"
            batch.mkdir(parents=True)
            manifest = batch / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "source": str(temp_path / "restore.tmp"),
                        "quarantined": str(outside_file),
                        "title": "bad",
                    }
                ),
                encoding="utf-8",
            )

            records = executor.list_quarantine_records()
            ok, message = executor.restore_quarantine_item(manifest)

            self.assertEqual(len(records), 1)
            self.assertFalse(records[0].valid)
            self.assertFalse(ok)
            self.assertIn("隔离区外", message)
            self.assertTrue(outside_file.exists())

    def test_list_quarantine_records_reports_broken_manifest(self) -> None:
        with temporary_workspace_dir() as temp:
            temp_path = Path(temp)
            executor = CleanupExecutor(
                safety_guard=SafetyGuard(protected_paths=[]),
                app_data_dir=temp_path / "appdata",
                trash_func=None,
            )
            batch = executor.quarantine_dir / "case"
            batch.mkdir(parents=True)
            (batch / "manifest.json").write_text("{not-json", encoding="utf-8")

            records = executor.list_quarantine_records()

            self.assertEqual(len(records), 1)
            self.assertFalse(records[0].valid)
            self.assertIn("无法读取", records[0].message)


    def test_cancel_skips_remaining_items(self) -> None:
        with temporary_workspace_dir() as temp:
            temp_path = Path(temp)
            files = []
            for i in range(5):
                f = temp_path / f"file{i}.tmp"
                f.write_text(f"data{i}", encoding="utf-8")
                files.append(f)

            call_count = 0

            def cancel_after_two(path: str) -> None:
                nonlocal call_count
                call_count += 1
                if call_count >= 2:
                    executor.cancel()

            executor = CleanupExecutor(
                safety_guard=SafetyGuard(protected_paths=[]),
                app_data_dir=temp_path / "appdata",
                trash_func=cancel_after_two,
            )
            items = [
                CleanupItem(
                    item_id=f"item-{i}",
                    title="tmp",
                    path=str(f),
                    kind=ItemKind.FILE,
                    risk=RiskLevel.LOW,
                    category="test",
                    vendor="test",
                    description="t",
                    safe_reason="s",
                    size_bytes=5,
                    selected=True,
                )
                for i, f in enumerate(files)
            ]
            report = executor.execute(items)

            trashed = [it for it in report.items if it.status == ActionStatus.TRASHED]
            skipped = [it for it in report.items if it.status == ActionStatus.SKIPPED]
            self.assertEqual(len(trashed), 2)
            self.assertGreater(len(skipped), 0)


if __name__ == "__main__":
    unittest.main()
