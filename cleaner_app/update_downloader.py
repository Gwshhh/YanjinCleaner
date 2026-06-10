from __future__ import annotations

import hashlib
import os
import tempfile
import urllib.request
import urllib.error
from collections.abc import Callable
from pathlib import Path

from .update_checker import UpdateInfo

CHUNK_SIZE = 8192


class UpdateDownloader:
    def download(
        self,
        url: str,
        dest: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)
        return dest

    def verify_checksum(self, file_path: Path, expected_sha256: str) -> bool:
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                sha.update(chunk)
        return sha.hexdigest().lower() == expected_sha256.lower()

    def download_update(
        self,
        update_info: UpdateInfo,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> tuple[bool, str, Path | None]:
        ext = ".zip" if update_info.download_url.lower().endswith(".zip") else ".exe"
        dest = Path(tempfile.gettempdir()) / f"YanjinCleaner_update_{update_info.version}{ext}"

        expected_hash = ""
        if update_info.checksum_url:
            try:
                checksum_dest = Path(tempfile.gettempdir()) / f"YanjinCleaner_{update_info.version}.sha256"
                self.download(update_info.checksum_url, checksum_dest)
                text = checksum_dest.read_text(encoding="utf-8").strip()
                expected_hash = text.split()[0].strip()
                checksum_dest.unlink(missing_ok=True)
            except Exception:
                return False, "无法下载校验文件，已取消更新。", None

        try:
            self.download(update_info.download_url, dest, progress_callback)
        except urllib.error.URLError:
            dest.unlink(missing_ok=True)
            return False, "网络连接失败，请检查网络后重试。", None
        except OSError as e:
            dest.unlink(missing_ok=True)
            if "No space" in str(e) or "磁盘空间" in str(e):
                return False, "磁盘空间不足，请清理磁盘后重试。", None
            return False, f"下载失败：{e}", None

        if expected_hash:
            if not self.verify_checksum(dest, expected_hash):
                dest.unlink(missing_ok=True)
                return False, "下载的文件校验失败，可能已损坏或被篡改，已取消更新。", None

        return True, "下载完成", dest


def get_backup_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    return base / "严谨清理" / "backups"


def backup_current_exe(current_exe: Path, version: str) -> Path | None:
    backup_dir = get_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"YanjinCleaner_v{version}.exe.bak"
    try:
        import shutil
        shutil.copy2(current_exe, backup_path)
        _cleanup_old_backups(backup_dir, keep=3)
        return backup_path
    except Exception:
        return None


def _cleanup_old_backups(backup_dir: Path, keep: int = 3) -> None:
    backups = sorted(backup_dir.glob("*.exe.bak"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[keep:]:
        old.unlink(missing_ok=True)


def list_backups() -> list[tuple[str, Path]]:
    backup_dir = get_backup_dir()
    if not backup_dir.exists():
        return []
    results = []
    for path in sorted(backup_dir.glob("*.exe.bak"), key=lambda p: p.stat().st_mtime, reverse=True):
        name = path.stem.replace("YanjinCleaner_", "").replace(".exe", "")
        results.append((name, path))
    return results
