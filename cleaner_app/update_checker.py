from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime, timezone

from .version import __version__, is_newer

GITHUB_REPO = "Gwshhh/YanjinCleaner"
RELEASES_URL = os.environ.get(
    "YANJIN_UPDATE_URL",
    f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
)
REQUEST_TIMEOUT = 10
USER_AGENT = f"YanjinCleaner/{__version__} (Windows)"


@dataclass
class UpdateInfo:
    version: str
    download_url: str
    checksum_url: str
    changelog: str
    release_date: str
    size_bytes: int


class UpdateChecker:
    def __init__(self) -> None:
        self._cached: UpdateInfo | None = None
        self._cache_time: datetime | None = None

    def check_for_updates(self) -> UpdateInfo | None:
        now = datetime.now(timezone.utc)
        if (
            self._cached is not None
            and self._cache_time is not None
            and (now - self._cache_time).total_seconds() < 3600
        ):
            return self._cached

        try:
            info = self._fetch_latest()
        except Exception:
            return None

        self._cache_time = now

        if info is None or not is_newer(info.version, __version__):
            self._cached = None
            return None

        self._cached = info
        return info

    def _fetch_latest(self) -> UpdateInfo | None:
        req = urllib.request.Request(
            RELEASES_URL,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        tag = data.get("tag_name", "")
        version = tag.lstrip("vV").strip()
        if not version:
            return None

        changelog = data.get("body", "") or ""
        release_date = data.get("published_at", "")

        download_url = ""
        checksum_url = ""
        size_bytes = 0

        for asset in data.get("assets", []):
            name = asset.get("name", "")
            url = asset.get("browser_download_url", "")
            if name.lower().endswith(".exe") and not name.lower().endswith(".sha256"):
                download_url = url
                size_bytes = asset.get("size", 0)
            elif name.lower().endswith(".sha256"):
                checksum_url = url

        if not download_url:
            return None

        return UpdateInfo(
            version=version,
            download_url=download_url,
            checksum_url=checksum_url,
            changelog=changelog,
            release_date=release_date,
            size_bytes=size_bytes,
        )
