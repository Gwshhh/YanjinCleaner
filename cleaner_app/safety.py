from __future__ import annotations

import os
from pathlib import Path

from .models import CleanupItem, RiskLevel
from .path_utils import is_path_inside, normalize_path
from .settings import UserSettings


class SafetyGuard:
    """Central filesystem safety gate used before every cleanup operation."""

    def __init__(
        self,
        protected_paths: list[Path] | None = None,
        settings: UserSettings | None = None,
    ) -> None:
        self.settings = settings or UserSettings()
        base_protected = self._default_protected_paths() if protected_paths is None else protected_paths
        excluded = [normalize_path(Path(p)) for p in self.settings.excluded_paths if p.strip()]
        self.protected_paths = base_protected + excluded
        self.allowed_windows_temp = normalize_path(
            Path(os.environ.get("WINDIR", r"C:\Windows")) / "Temp"
        )

    def validate_item(self, item: CleanupItem) -> tuple[bool, str]:
        if not item.is_file_system_item:
            return False, "非文件系统项目仅供检查，不能在首版中直接清理。"
        if item.risk in {RiskLevel.HIGH, RiskLevel.BLOCKED}:
            return False, "高风险或禁止清理项目不会被自动执行。"
        return self.validate_path(Path(item.path))

    def validate_path(self, path: Path) -> tuple[bool, str]:
        normalized = normalize_path(path)
        if not str(normalized).strip():
            return False, "路径为空。"
        if self._is_drive_root(normalized):
            return False, "磁盘根目录禁止清理。"
        if not normalized.exists():
            return False, "路径不存在，已跳过。"
        if normalized == self.allowed_windows_temp:
            return False, "不会清理 Windows Temp 目录本身，只允许清理其中项目。"
        if is_path_inside(normalized, self.allowed_windows_temp):
            return True, "Windows Temp 子项目允许清理。"
        for protected in self.protected_paths:
            if normalized == protected or is_path_inside(normalized, protected):
                return False, f"受保护路径：{protected}"
        if len(normalized.parts) <= 2:
            return False, "路径层级过浅，已阻止。"
        return True, "允许清理。"

    def explain_protected_paths(self) -> list[str]:
        return [str(path) for path in self.protected_paths]

    def _default_protected_paths(self) -> list[Path]:
        paths = [
            Path(os.environ.get("WINDIR", r"C:\Windows")),
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        ]
        user_profile = Path(os.environ.get("USERPROFILE", str(Path.home())))
        paths.extend(
            user_profile / name
            for name in ("Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music")
        )
        paths.extend(
            user_profile / name
            for name in (
                "OneDrive",
                "OneDrive - Personal",
                "OneDrive - Business",
                "Dropbox",
                "Google Drive",
                "iCloudDrive",
                "iCloud Drive",
                "Box",
            )
        )
        paths.extend(
            Path(value)
            for key in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")
            for value in (os.environ.get(key),)
            if value
        )
        return [normalize_path(path) for path in paths if str(path)]

    @staticmethod
    def _is_drive_root(path: Path) -> bool:
        anchor = Path(path.anchor)
        return bool(path.anchor) and path == anchor
