from __future__ import annotations

__version__ = "1.0.0"
__version_info__ = (1, 0, 0)


def parse_version(version_string: str) -> tuple[int, int, int]:
    cleaned = version_string.lstrip("vV").strip()
    parts = cleaned.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {version_string}")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def is_newer(remote: str, local: str) -> bool:
    return parse_version(remote) > parse_version(local)
