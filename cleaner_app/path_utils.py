from __future__ import annotations

from pathlib import Path


def normalize_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def is_path_inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return path != parent
    except ValueError:
        return False
