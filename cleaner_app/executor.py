from __future__ import annotations

import json
import os
import shutil
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

try:
    from send2trash import send2trash
except ImportError:  # pragma: no cover - covered by behavior tests through injection.
    send2trash = None

from .models import ActionStatus, CleanupItem, CleanupReport
from .path_utils import is_path_inside, normalize_path
from .safety import SafetyGuard


@dataclass(frozen=True)
class QuarantineRecord:
    manifest_path: Path
    source: Path | None
    quarantined: Path | None
    title: str
    created_at: datetime | None
    item_id: str
    valid: bool
    message: str = ""

    @property
    def source_label(self) -> str:
        return str(self.source) if self.source else "未知原路径"

    @property
    def quarantined_label(self) -> str:
        return str(self.quarantined) if self.quarantined else "未知隔离路径"

    @property
    def created_label(self) -> str:
        return self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "未知时间"


class CleanupExecutor:
    def __init__(
        self,
        safety_guard: SafetyGuard | None = None,
        app_data_dir: Path | None = None,
        trash_func=None,
    ) -> None:
        self.safety_guard = safety_guard or SafetyGuard()
        base_dir = app_data_dir or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "严谨清理"
        self.app_data_dir = Path(base_dir)
        self.quarantine_dir = self.app_data_dir / "quarantine"
        self.logs_dir = self.app_data_dir / "logs"
        self.trash_func = trash_func if trash_func is not None else send2trash
        self._cancel_event = threading.Event()
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def cancel(self) -> None:
        self._cancel_event.set()

    def reset(self) -> None:
        self._cancel_event.clear()

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def execute(self, items: list[CleanupItem]) -> CleanupReport:
        report = CleanupReport(started_at=datetime.now(), items=items)
        selected = [item for item in items if item.selected]
        report.selected_count = len(selected)
        report.total_bytes = sum(item.size_bytes for item in selected)

        for item in selected:
            if self.cancelled:
                item.status = ActionStatus.SKIPPED
                item.message = "用户取消。"
                continue
            allowed, reason = self.safety_guard.validate_item(item)
            if not allowed:
                item.status = ActionStatus.BLOCKED
                item.message = reason
                report.errors.append(f"{item.path}: {reason}")
                continue
            try:
                if self.trash_func is not None:
                    self.trash_func(item.path)
                    item.status = ActionStatus.TRASHED
                    item.message = "已移入回收站。"
                else:
                    self._move_to_quarantine(item)
                    item.status = ActionStatus.QUARANTINED
                    item.message = "send2trash 未安装，已改为移入应用隔离区。"
                report.freed_bytes += item.size_bytes
            except Exception as exc:  # noqa: BLE001 - cleanup must report all failures.
                item.status = ActionStatus.FAILED
                item.message = str(exc)
                report.errors.append(f"{item.path}: {exc}")

        for item in items:
            if not item.selected and item.status == ActionStatus.PENDING:
                item.status = ActionStatus.SKIPPED

        report.finished_at = datetime.now()
        self.write_report(report)
        return report

    def list_quarantine_records(self) -> list[QuarantineRecord]:
        manifests = sorted(
            self.quarantine_dir.glob("*/manifest.json"),
            key=lambda path: path.stat().st_mtime if path.exists() else 0,
            reverse=True,
        )
        return [self._record_from_manifest(path) for path in manifests]

    def restore_quarantine_item(self, manifest_path: Path) -> tuple[bool, str]:
        record = self._record_from_manifest(manifest_path)
        if not record.valid:
            return False, record.message
        if record.source is None or record.quarantined is None:
            return False, "隔离清单缺少恢复路径。"
        if record.source.exists():
            return False, f"原路径已存在，已阻止覆盖：{record.source}"
        try:
            record.source.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(record.quarantined), str(record.source))
            record.manifest_path.unlink(missing_ok=True)
            self._remove_empty_quarantine_batch(record.manifest_path.parent)
            return True, f"已恢复到 {record.source}"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)

    def write_report(self, report: CleanupReport) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.logs_dir / f"cleanup-{stamp}.json"
        payload = {
            "started_at": report.started_at.isoformat(),
            "finished_at": report.finished_at.isoformat() if report.finished_at else None,
            "selected_count": report.selected_count,
            "total_bytes": report.total_bytes,
            "freed_bytes": report.freed_bytes,
            "errors": report.errors,
            "items": [
                {
                    **asdict(item),
                    "kind": item.kind.value,
                    "risk": item.risk.value,
                    "status": item.status.value,
                }
                for item in report.items
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _move_to_quarantine(self, item: CleanupItem) -> None:
        source = Path(item.path)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        target = self.quarantine_dir / stamp / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        manifest = {
            "source": str(source),
            "quarantined": str(target),
            "item_id": item.item_id,
            "title": item.title,
            "created_at": datetime.now().isoformat(),
        }
        (target.parent / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _record_from_manifest(self, manifest_path: Path) -> QuarantineRecord:
        normalized_manifest = normalize_path(manifest_path)
        if not is_path_inside(normalized_manifest, normalize_path(self.quarantine_dir)):
            return self._invalid_record(normalized_manifest, "隔离清单不在应用隔离区内。")
        try:
            manifest = json.loads(normalized_manifest.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            return self._invalid_record(normalized_manifest, f"隔离清单无法读取：{exc}")

        source_text = str(manifest.get("source", "")).strip()
        quarantined_text = str(manifest.get("quarantined", "")).strip()
        if not source_text:
            return self._invalid_record(
                normalized_manifest,
                "隔离清单缺少原路径。",
                manifest=manifest,
            )
        if not quarantined_text:
            return self._invalid_record(
                normalized_manifest,
                "隔离清单缺少隔离路径。",
                source=Path(source_text),
                manifest=manifest,
            )

        source = Path(source_text)
        quarantined = normalize_path(Path(quarantined_text))
        if not source.is_absolute():
            return self._invalid_record(
                normalized_manifest,
                "隔离清单中的原路径不是绝对路径。",
                source=source,
                quarantined=quarantined,
                manifest=manifest,
            )
        if not is_path_inside(quarantined, normalize_path(self.quarantine_dir)):
            return self._invalid_record(
                normalized_manifest,
                "隔离清单指向了应用隔离区外的文件。",
                source=source,
                quarantined=quarantined,
                manifest=manifest,
            )
        if not quarantined.exists():
            return self._invalid_record(
                normalized_manifest,
                "隔离文件不存在。",
                source=source,
                quarantined=quarantined,
                manifest=manifest,
            )

        return QuarantineRecord(
            manifest_path=normalized_manifest,
            source=source,
            quarantined=quarantined,
            title=str(manifest.get("title") or source.name or "隔离项目"),
            created_at=self._parse_datetime(manifest.get("created_at")),
            item_id=str(manifest.get("item_id") or ""),
            valid=True,
        )

    @staticmethod
    def _invalid_record(
        manifest_path: Path,
        message: str,
        source: Path | None = None,
        quarantined: Path | None = None,
        manifest: dict | None = None,
    ) -> QuarantineRecord:
        manifest = manifest or {}
        return QuarantineRecord(
            manifest_path=manifest_path,
            source=source,
            quarantined=quarantined,
            title=str(manifest.get("title") or "无效隔离项目"),
            created_at=CleanupExecutor._parse_datetime(manifest.get("created_at")),
            item_id=str(manifest.get("item_id") or ""),
            valid=False,
            message=message,
        )

    @staticmethod
    def _parse_datetime(value) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None

    @staticmethod
    def _remove_empty_quarantine_batch(path: Path) -> None:
        try:
            if not any(path.iterdir()):
                path.rmdir()
        except OSError:
            return
