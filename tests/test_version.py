from __future__ import annotations

import unittest

from cleaner_app.version import __version__, is_newer, parse_version


class VersionParseTests(unittest.TestCase):
    def test_parse_simple(self) -> None:
        self.assertEqual(parse_version("1.0.0"), (1, 0, 0))

    def test_parse_with_v_prefix(self) -> None:
        self.assertEqual(parse_version("v2.3.4"), (2, 3, 4))
        self.assertEqual(parse_version("V2.3.4"), (2, 3, 4))

    def test_parse_with_whitespace(self) -> None:
        self.assertEqual(parse_version("  v1.2.3 "), (1, 2, 3))

    def test_parse_invalid_format(self) -> None:
        with self.assertRaises(ValueError):
            parse_version("1.0")
        with self.assertRaises(ValueError):
            parse_version("abc")

    def test_parse_non_numeric(self) -> None:
        with self.assertRaises(ValueError):
            parse_version("a.b.c")


class VersionCompareTests(unittest.TestCase):
    def test_newer_major(self) -> None:
        self.assertTrue(is_newer("2.0.0", "1.0.0"))

    def test_newer_minor(self) -> None:
        self.assertTrue(is_newer("1.1.0", "1.0.0"))

    def test_newer_patch(self) -> None:
        self.assertTrue(is_newer("1.0.1", "1.0.0"))

    def test_same_version(self) -> None:
        self.assertFalse(is_newer("1.0.0", "1.0.0"))

    def test_older_version(self) -> None:
        self.assertFalse(is_newer("1.0.0", "2.0.0"))

    def test_with_v_prefix(self) -> None:
        self.assertTrue(is_newer("v2.0.0", "v1.0.0"))

    def test_current_version_exists(self) -> None:
        self.assertIsInstance(__version__, str)
        self.assertEqual(len(parse_version(__version__)), 3)


if __name__ == "__main__":
    unittest.main()
