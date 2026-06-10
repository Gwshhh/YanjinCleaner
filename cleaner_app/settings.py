from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class UserSettings:
    min_age_hours: int = 24
    max_scan_depth: int = 7
    max_dirs_per_drive: int = 12000
    excluded_paths: list[str] = field(default_factory=list)
    auto_select_low_risk: bool = True
    auto_check_updates: bool = True
    skipped_version: str = ""
    last_update_check: str = ""

    @classmethod
    def load(cls) -> UserSettings:
        path = cls._settings_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(
                min_age_hours=int(data.get("min_age_hours", 24)),
                max_scan_depth=int(data.get("max_scan_depth", 7)),
                max_dirs_per_drive=int(data.get("max_dirs_per_drive", 12000)),
                excluded_paths=list(data.get("excluded_paths", [])),
                auto_select_low_risk=bool(data.get("auto_select_low_risk", True)),
                auto_check_updates=bool(data.get("auto_check_updates", True)),
                skipped_version=str(data.get("skipped_version", "")),
                last_update_check=str(data.get("last_update_check", "")),
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            return cls()

    def save(self) -> None:
        path = self._settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _settings_path() -> Path:
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "严谨清理" / "settings.json"
