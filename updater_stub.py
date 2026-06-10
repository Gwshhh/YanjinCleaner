"""Updater stub — replaces the running EXE after the main process exits.

This script is packaged as a separate EXE via PyInstaller and bundled
inside the main application's _internal folder. It uses only stdlib.

Usage:
    UpdaterStub.exe <old_exe> <new_exe> <backup_dir> <new_version> <parent_pid>
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def log(message: str, log_path: Path) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def wait_for_exit(pid: int, timeout: int = 30) -> bool:
    for _ in range(timeout * 2):
        if not pid_alive(pid):
            return True
        time.sleep(0.5)
    return False


def main() -> int:
    if len(sys.argv) < 6:
        print("Usage: UpdaterStub <old_exe> <new_file> <backup_dir> <new_version> <parent_pid>")
        return 1

    old_exe = Path(sys.argv[1])
    new_file = Path(sys.argv[2])
    backup_dir = Path(sys.argv[3])
    new_version = sys.argv[4]
    parent_pid = int(sys.argv[5])

    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    log_path = base / "严谨清理" / "logs" / "update.log"

    log(f"Updater started: upgrading to {new_version}", log_path)
    log(f"Waiting for PID {parent_pid} to exit...", log_path)

    if not wait_for_exit(parent_pid):
        log(f"Timeout waiting for PID {parent_pid}", log_path)
        return 1

    time.sleep(0.5)

    is_zip = new_file.suffix.lower() == ".zip"
    app_dir = old_exe.parent

    backup_dir.mkdir(parents=True, exist_ok=True)

    if is_zip:
        backup_path = backup_dir / f"YanjinCleaner_v{new_version}_pre_backup"
        try:
            if backup_path.exists():
                shutil.rmtree(backup_path)
            shutil.copytree(app_dir, backup_path)
            log(f"Directory backup created: {backup_path}", log_path)
        except Exception as e:
            log(f"Backup failed: {e}", log_path)
            return 1

        try:
            import zipfile
            with zipfile.ZipFile(new_file, "r") as zf:
                top_dirs = {name.split("/")[0] for name in zf.namelist() if "/" in name}
                has_wrapper = len(top_dirs) == 1

                for member in zf.namelist():
                    if has_wrapper:
                        parts = member.split("/", 1)
                        if len(parts) < 2 or not parts[1]:
                            continue
                        rel_path = parts[1]
                    else:
                        rel_path = member

                    dest = app_dir / rel_path
                    if member.endswith("/"):
                        dest.mkdir(parents=True, exist_ok=True)
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as src, open(dest, "wb") as dst:
                            shutil.copyfileobj(src, dst)

            log(f"Extracted zip to {app_dir}", log_path)
        except Exception as e:
            log(f"Extract failed: {e}. Restoring backup...", log_path)
            try:
                shutil.rmtree(app_dir)
                shutil.copytree(backup_path, app_dir)
                log("Backup restored successfully", log_path)
            except Exception as e2:
                log(f"Restore also failed: {e2}", log_path)
            return 1
    else:
        backup_path = backup_dir / f"YanjinCleaner_v{new_version}_pre.exe.bak"
        try:
            if old_exe.exists():
                shutil.copy2(old_exe, backup_path)
                log(f"Backup created: {backup_path}", log_path)
        except Exception as e:
            log(f"Backup failed: {e}", log_path)
            return 1

        try:
            shutil.copy2(new_file, old_exe)
            log(f"Replaced {old_exe} with {new_file}", log_path)
        except Exception as e:
            log(f"Replace failed: {e}. Restoring backup...", log_path)
            try:
                shutil.copy2(backup_path, old_exe)
                log("Backup restored successfully", log_path)
            except Exception as e2:
                log(f"Restore also failed: {e2}", log_path)
            return 1

    try:
        new_file.unlink(missing_ok=True)
        log("Cleaned up temp download file", log_path)
    except Exception:
        pass

    try:
        subprocess.Popen(
            [str(old_exe)],
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        log(f"Launched new version {new_version}", log_path)
    except Exception as e:
        log(f"Failed to launch new version: {e}", log_path)
        return 1

    log("Update complete", log_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
