from __future__ import annotations

import unittest
from pathlib import Path

from cleaner_app.path_utils import is_path_inside, normalize_path


class NormalizePathTests(unittest.TestCase):
    def test_resolves_relative_path(self) -> None:
        result = normalize_path(Path("some/relative"))
        self.assertTrue(result.is_absolute())

    def test_expands_user_home(self) -> None:
        result = normalize_path(Path("~"))
        self.assertNotIn("~", str(result))
        self.assertTrue(result.is_absolute())


class IsPathInsideTests(unittest.TestCase):
    def test_child_is_inside_parent(self) -> None:
        parent = Path("C:/Users/example")
        child = Path("C:/Users/example/Documents/file.txt")
        self.assertTrue(is_path_inside(child, parent))

    def test_path_equal_to_parent_returns_false(self) -> None:
        path = Path("C:/Users/example")
        self.assertFalse(is_path_inside(path, path))

    def test_unrelated_path_returns_false(self) -> None:
        parent = Path("C:/Users/example")
        other = Path("D:/Other/folder")
        self.assertFalse(is_path_inside(other, parent))

    def test_parent_is_not_inside_child(self) -> None:
        parent = Path("C:/Users/example")
        child = Path("C:/Users/example/Documents")
        self.assertFalse(is_path_inside(parent, child))

    def test_direct_child_is_inside(self) -> None:
        parent = Path("C:/Users")
        child = Path("C:/Users/example")
        self.assertTrue(is_path_inside(child, parent))


if __name__ == "__main__":
    unittest.main()
