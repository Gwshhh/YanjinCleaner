from __future__ import annotations

from datetime import datetime
from pathlib import Path
import unittest

from cleaner_app.executor import QuarantineRecord
from cleaner_app.models import CleanupItem, ItemKind, RiskLevel
from cleaner_app.ui import MainWindow, item_summary


class TableTextTests(unittest.TestCase):
    def test_item_summary_uses_full_path_without_ellipsis(self) -> None:
        path = r"C:\Users\example\AppData\Local\Vendor\Product\Cache\deep\file.tmp"
        item = CleanupItem(
            item_id="item-1",
            title="Cache file",
            path=path,
            kind=ItemKind.FILE,
            risk=RiskLevel.LOW,
            category="Cache",
            vendor="Vendor",
            description="Temporary cache file",
            safe_reason="Can be regenerated",
        )

        summary = item_summary(item)

        self.assertIn(path, summary)
        self.assertNotIn("...", summary)

    def test_quarantine_record_text_shows_restore_state_and_paths(self) -> None:
        source = Path(r"C:\Users\example\AppData\Local\Temp\cache.tmp")
        quarantined = Path(r"C:\Users\example\AppData\Local\Yanjin\quarantine\case\cache.tmp")
        record = QuarantineRecord(
            manifest_path=quarantined.parent / "manifest.json",
            source=source,
            quarantined=quarantined,
            title="Cache file",
            created_at=datetime(2026, 6, 7, 8, 9, 10),
            item_id="item-1",
            valid=True,
        )

        list_text = MainWindow.quarantine_record_list_text(record)
        detail = MainWindow.quarantine_record_detail_text(record)

        self.assertIn("Cache file", list_text)
        self.assertIn("可恢复", list_text)
        self.assertIn(str(source), detail)
        self.assertIn(str(quarantined), detail)


if __name__ == "__main__":
    unittest.main()
