from __future__ import annotations

import unittest
from pathlib import Path

from cleaner_app.models import format_bytes, stable_item_id
from cleaner_app.scanner import estimate_size
from tests.helpers import temporary_workspace_dir


class FormatBytesTests(unittest.TestCase):
    def test_zero(self) -> None:
        self.assertEqual(format_bytes(0), "0 B")

    def test_bytes(self) -> None:
        self.assertEqual(format_bytes(512), "512 B")

    def test_kilobytes(self) -> None:
        self.assertEqual(format_bytes(1536), "1.5 KB")

    def test_megabytes(self) -> None:
        self.assertEqual(format_bytes(10 * 1024 * 1024), "10.0 MB")

    def test_gigabytes(self) -> None:
        self.assertEqual(format_bytes(2 * 1024 * 1024 * 1024), "2.0 GB")

    def test_negative_treated_as_zero(self) -> None:
        self.assertEqual(format_bytes(-100), "0 B")


class StableItemIdTests(unittest.TestCase):
    def test_same_input_same_output(self) -> None:
        a = stable_item_id("rule.test", r"C:\Users\foo\cache")
        b = stable_item_id("rule.test", r"C:\Users\foo\cache")
        self.assertEqual(a, b)

    def test_case_insensitive(self) -> None:
        a = stable_item_id("rule.test", r"C:\Users\FOO\Cache")
        b = stable_item_id("rule.test", r"C:\Users\foo\cache")
        self.assertEqual(a, b)

    def test_backslash_normalized(self) -> None:
        a = stable_item_id("rule.test", r"C:\Users\foo\cache")
        b = stable_item_id("rule.test", "C:/Users/foo/cache")
        self.assertEqual(a, b)

    def test_different_rule_different_id(self) -> None:
        a = stable_item_id("rule.a", r"C:\path")
        b = stable_item_id("rule.b", r"C:\path")
        self.assertNotEqual(a, b)


class EstimateSizeTests(unittest.TestCase):
    def test_file_returns_stat_size(self) -> None:
        with temporary_workspace_dir() as temp:
            f = Path(temp) / "test.txt"
            f.write_text("hello world", encoding="utf-8")
            self.assertEqual(estimate_size(f), f.stat().st_size)

    def test_empty_directory_returns_zero(self) -> None:
        with temporary_workspace_dir() as temp:
            d = Path(temp) / "empty"
            d.mkdir()
            self.assertEqual(estimate_size(d), 0)

    def test_directory_sums_files(self) -> None:
        with temporary_workspace_dir() as temp:
            d = Path(temp) / "stuff"
            d.mkdir()
            (d / "a.txt").write_text("aaa", encoding="utf-8")
            (d / "b.txt").write_text("bbbbb", encoding="utf-8")
            total = (d / "a.txt").stat().st_size + (d / "b.txt").stat().st_size
            self.assertEqual(estimate_size(d), total)

    def test_nonexistent_returns_zero(self) -> None:
        self.assertEqual(estimate_size(Path("nonexistent_path_xyz")), 0)


if __name__ == "__main__":
    unittest.main()
