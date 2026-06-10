from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Iterable


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"

    @property
    def label(self) -> str:
        return {
            RiskLevel.LOW: "低风险",
            RiskLevel.MEDIUM: "中风险",
            RiskLevel.HIGH: "高风险",
            RiskLevel.BLOCKED: "禁止清理",
        }[self]


class ItemKind(str, Enum):
    FILE = "file"
    DIRECTORY = "directory"
    REGISTRY = "registry"
    SERVICE = "service"
    TASK = "task"
    STARTUP = "startup"
    PROCESS = "process"
    NOTE = "note"

    @property
    def label(self) -> str:
        return {
            ItemKind.FILE: "文件",
            ItemKind.DIRECTORY: "目录",
            ItemKind.REGISTRY: "注册表",
            ItemKind.SERVICE: "服务",
            ItemKind.TASK: "计划任务",
            ItemKind.STARTUP: "启动项",
            ItemKind.PROCESS: "进程",
            ItemKind.NOTE: "说明",
        }[self]


class ActionStatus(str, Enum):
    PENDING = "pending"
    SKIPPED = "skipped"
    TRASHED = "trashed"
    QUARANTINED = "quarantined"
    FAILED = "failed"
    BLOCKED = "blocked"

    @property
    def label(self) -> str:
        return {
            ActionStatus.PENDING: "待处理",
            ActionStatus.SKIPPED: "已跳过",
            ActionStatus.TRASHED: "已移入回收站",
            ActionStatus.QUARANTINED: "已移入隔离区",
            ActionStatus.FAILED: "失败",
            ActionStatus.BLOCKED: "已阻止",
        }[self]


@dataclass(frozen=True)
class CleanupRule:
    rule_id: str
    title: str
    vendor: str
    category: str
    description: str
    safe_reason: str
    risk: RiskLevel
    item_kind: ItemKind = ItemKind.DIRECTORY
    path_patterns: tuple[str, ...] = ()
    process_names: tuple[str, ...] = ()
    service_keywords: tuple[str, ...] = ()
    task_keywords: tuple[str, ...] = ()
    registry_keywords: tuple[str, ...] = ()
    default_selected: bool = False
    requires_confirmation: bool = True

    @property
    def selectable(self) -> bool:
        return self.risk in {RiskLevel.LOW, RiskLevel.MEDIUM}


@dataclass
class CleanupItem:
    item_id: str
    title: str
    path: str
    kind: ItemKind
    risk: RiskLevel
    category: str
    vendor: str
    description: str
    safe_reason: str
    size_bytes: int = 0
    default_selected: bool = False
    selected: bool = False
    recoverable: bool = True
    source_rule: str = ""
    status: ActionStatus = ActionStatus.PENDING
    message: str = ""

    @property
    def size_label(self) -> str:
        return format_bytes(self.size_bytes)

    @property
    def is_file_system_item(self) -> bool:
        return self.kind in {ItemKind.FILE, ItemKind.DIRECTORY}

    @property
    def can_execute(self) -> bool:
        return self.is_file_system_item and self.risk in {RiskLevel.LOW, RiskLevel.MEDIUM}


@dataclass
class CleanupReport:
    started_at: datetime
    finished_at: datetime | None = None
    scanned_count: int = 0
    selected_count: int = 0
    total_bytes: int = 0
    freed_bytes: int = 0
    items: list[CleanupItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_label(self) -> str:
        return format_bytes(self.total_bytes)

    @property
    def freed_label(self) -> str:
        return format_bytes(self.freed_bytes)


def format_bytes(value: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(max(value, 0))
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{int(value)} B"


def summarize_items(items: Iterable[CleanupItem]) -> tuple[int, int]:
    item_list = list(items)
    return len(item_list), sum(item.size_bytes for item in item_list)


def stable_item_id(rule_id: str, raw_path: str) -> str:
    safe = raw_path.lower().replace("\\", "/")
    digest = sha256(safe.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{rule_id}:{digest}"


def normalize_path_for_display(path: Path | str) -> str:
    return str(path)
