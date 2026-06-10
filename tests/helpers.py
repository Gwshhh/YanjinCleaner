from __future__ import annotations

import shutil
import uuid
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path


@contextmanager
def temporary_workspace_dir() -> Iterator[str]:
    root = Path(__file__).resolve().parents[1] / ".test_tmp"
    root.mkdir(exist_ok=True)
    path = root / f"case_{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)
