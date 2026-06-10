from __future__ import annotations

import ctypes
import sys
from pathlib import Path


def is_windows() -> bool:
    return sys.platform.startswith("win")


def is_admin() -> bool:
    if not is_windows():
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def relaunch_as_admin() -> bool:
    if not is_windows():
        return False
    executable = sys.executable
    script = str(Path(sys.argv[0]).resolve())
    params = " ".join([quote_arg(script), *[quote_arg(arg) for arg in sys.argv[1:]]])
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        params,
        None,
        1,
    )
    return int(result) > 32


def quote_arg(value: str) -> str:
    escaped = value.replace('"', r"\"")
    return f'"{escaped}"'
