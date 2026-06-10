from __future__ import annotations

import glob
import os
import subprocess
import sys
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import psutil

from .models import (
    CleanupItem,
    CleanupReport,
    ItemKind,
    RiskLevel,
    stable_item_id,
)
from .path_utils import is_path_inside, normalize_path
from .rules import PUP_KEYWORDS, get_cleanable_rules
from .safety import SafetyGuard
from .settings import UserSettings


STARTUPINFO = None
CREATE_NO_WINDOW = 0
if sys.platform.startswith("win"):
    STARTUPINFO = subprocess.STARTUPINFO()
    STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    STARTUPINFO.wShowWindow = 0
    CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


ALL_DRIVE_JUNK_FOLDERS: tuple[tuple[str, str, RiskLevel], ...] = (
    ("Temp", "全盘临时文件", RiskLevel.LOW),
    ("Tmp", "全盘临时文件", RiskLevel.LOW),
    ("Cache", "全盘缓存文件", RiskLevel.MEDIUM),
    ("Caches", "全盘缓存文件", RiskLevel.MEDIUM),
    ("Log", "全盘日志文件", RiskLevel.LOW),
    ("Logs", "全盘日志文件", RiskLevel.LOW),
)
ALL_DRIVE_JUNK_NAMES = {name.lower() for name, _, _ in ALL_DRIVE_JUNK_FOLDERS}
ALL_DRIVE_JUNK_RULES = {
    name.lower(): (title, risk) for name, title, risk in ALL_DRIVE_JUNK_FOLDERS
}
ALL_DRIVE_DEFAULT_SELECTED_NAMES = {"temp", "tmp", "log", "logs"}
ALL_DRIVE_JUNK_FILE_RULES: dict[str, tuple[str, RiskLevel]] = {
    ".tmp": ("全盘临时文件", RiskLevel.LOW),
    ".temp": ("全盘临时文件", RiskLevel.LOW),
    ".log": ("全盘日志文件", RiskLevel.LOW),
    ".dmp": ("全盘崩溃转储", RiskLevel.LOW),
    ".chk": ("全盘磁盘检查碎片", RiskLevel.LOW),
    ".bak": ("全盘备份残留", RiskLevel.MEDIUM),
    ".old": ("全盘旧版本残留", RiskLevel.MEDIUM),
}
ALL_DRIVE_SCAN_SKIP_NAMES = {
    "$recycle.bin",
    "$windows.~bt",
    "$windows.~ws",
    "boot",
    "desktop",
    "documents",
    "downloads",
    "music",
    "onedrive",
    "pictures",
    "program files",
    "program files (x86)",
    "programdata",
    "recovery",
    "system volume information",
    "users",
    "videos",
    "windows",
}
ALL_DRIVE_SCAN_MAX_DIRS_PER_DRIVE = 12000
ALL_DRIVE_SCAN_MAX_DEPTH = 7
ALL_DRIVE_SCAN_MAX_CHILDREN_PER_FOLDER = 500
ALL_DRIVE_SCAN_MAX_FILES_PER_DIR = 2000
DEFAULT_SELECT_MIN_AGE = timedelta(days=1)
SYSTEM_INSPECTION_RULE_IDS = {"system.windows_temp"}
CLOUD_SYNC_FOLDER_NAMES = {
    "box",
    "creative cloud files",
    "dropbox",
    "google drive",
    "icloud drive",
    "iclouddrive",
    "onedrive",
    "onedrivecommercial",
    "onedriveconsumer",
}


OFFICIAL_LOW_RISK_PATTERNS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "%LOCALAPPDATA%\\Microsoft\\Windows\\Explorer\\thumbcache_*.db",
        "Windows 缩略图缓存",
        "official.thumbnail_cache",
        "Windows 官方临时文件类别中的缩略图缓存，系统会按需重新生成。",
        "依据 Windows 存储设置和磁盘清理中的官方清理类别识别，只匹配当前用户 Explorer 缓存文件。",
    ),
    (
        "%LOCALAPPDATA%\\Microsoft\\Windows\\Explorer\\iconcache_*.db",
        "Windows 图标缓存",
        "official.icon_cache",
        "Windows 图标缓存文件，删除后系统会重新生成。",
        "依据 Windows 存储设置和磁盘清理中的官方清理类别识别，只匹配当前用户 Explorer 缓存文件。",
    ),
    (
        "%LOCALAPPDATA%\\Microsoft\\Windows\\WER\\ReportArchive\\*",
        "Windows 错误报告归档",
        "official.wer_archive",
        "程序崩溃后留下的历史错误报告归档。",
        "依据 Windows 官方临时文件类别识别，仅包含历史诊断报告，不包含用户文档。",
    ),
    (
        "%LOCALAPPDATA%\\Microsoft\\Windows\\WER\\ReportQueue\\*",
        "Windows 错误报告队列",
        "official.wer_queue",
        "程序崩溃后等待上报的错误报告队列。",
        "依据 Windows 官方临时文件类别识别，仅包含历史诊断报告，不包含用户文档。",
    ),
    (
        "%LOCALAPPDATA%\\CrashDumps\\*",
        "Windows 崩溃转储",
        "official.crash_dumps",
        "程序崩溃后生成的本地诊断转储文件。",
        "依据 Windows 官方临时文件类别识别，仅包含崩溃诊断数据，不包含应用配置或用户文档。",
    ),
)


SYSTEM_INSPECTION_PATHS: tuple[tuple[str, str, str, str], ...] = (
    (
        "%WINDIR%\\Temp",
        "Windows 系统临时目录",
        "inspect.windows_temp",
        "系统级临时目录可能包含安装、更新或服务正在使用的文件，本程序只检查展示。",
    ),
    (
        "%WINDIR%\\SoftwareDistribution\\Download",
        "Windows 更新下载缓存",
        "inspect.windows_update_download",
        "Windows Update 使用的下载缓存，建议通过 Windows 设置或磁盘清理处理。",
    ),
    (
        "%PROGRAMDATA%\\Microsoft\\Windows\\DeliveryOptimization\\Cache",
        "Delivery Optimization 缓存",
        "inspect.delivery_optimization",
        "Windows 传递优化缓存属于官方清理类别，建议通过 Windows 设置处理。",
    ),
    (
        "%SYSTEMDRIVE%\\Windows.old",
        "旧版 Windows 安装文件",
        "inspect.windows_old",
        "Windows.old 可能包含回退系统或旧用户文件，必须人工确认后处理。",
    ),
    (
        "%SYSTEMDRIVE%\\$WINDOWS.~BT",
        "Windows 升级临时文件",
        "inspect.windows_upgrade_bt",
        "系统升级留下的临时目录，建议通过 Windows 设置或磁盘清理处理。",
    ),
    (
        "%SYSTEMDRIVE%\\$WINDOWS.~WS",
        "Windows 升级工作目录",
        "inspect.windows_upgrade_ws",
        "系统升级留下的工作目录，建议通过 Windows 设置或磁盘清理处理。",
    ),
)


@dataclass(frozen=True)
class CleanupCandidate:
    path: Path
    title: str
    risk: RiskLevel
    category: str
    vendor: str
    description: str
    safe_reason: str
    source_rule: str
    default_candidate: bool = False
    kind: ItemKind | None = None
    recoverable: bool = True
    inspect_only: bool = False


class CleanupScanner:
    def __init__(
        self,
        safety_guard: SafetyGuard | None = None,
        settings: UserSettings | None = None,
    ) -> None:
        self.safety_guard = safety_guard or SafetyGuard()
        self.settings = settings or UserSettings()
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def reset(self) -> None:
        self._cancel_event.clear()

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def scan(
        self,
        include_high_risk: bool = True,
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> CleanupReport:
        report = CleanupReport(started_at=datetime.now())
        items: list[CleanupItem] = []
        seen_paths: set[str] = set()

        for candidate in self._iter_cleanup_candidates(progress_callback):
            if self.cancelled:
                break
            item = self._candidate_to_item(candidate, seen_paths)
            if item is not None:
                items.append(item)

        if include_high_risk and not self.cancelled:
            items.extend(self.inspect_high_risk_items())
            if progress_callback:
                progress_callback("高风险检查完成", len(items))

        report.items = sorted(
            items,
            key=lambda item: (
                item.risk.value,
                item.category,
                item.vendor,
                item.path.lower(),
            ),
        )
        report.scanned_count = len(report.items)
        report.selected_count = sum(1 for item in report.items if item.selected)
        report.total_bytes = sum(item.size_bytes for item in report.items)
        report.finished_at = datetime.now()
        return report

    def estimate_sizes(self, items: list[CleanupItem]) -> None:
        for item in items:
            if self.cancelled:
                return
            if item.is_file_system_item and item.size_bytes == 0:
                item.size_bytes = estimate_size(Path(item.path))

    def inspect_high_risk_items(self) -> list[CleanupItem]:
        items: list[CleanupItem] = []
        items.extend(self._inspect_processes())
        items.extend(self._inspect_services())
        items.extend(self._inspect_scheduled_tasks())
        items.extend(self._inspect_startup_registry())
        return items

    def _iter_cleanup_candidates(
        self,
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> Iterable[CleanupCandidate]:
        count = 0
        for candidate in self._iter_official_low_risk_candidates():
            count += 1
            yield candidate
        if progress_callback:
            progress_callback("官方低风险项扫描完成", count)

        for candidate in self._iter_rule_candidates():
            count += 1
            yield candidate
        if progress_callback:
            progress_callback("规则扫描完成", count)

        yield from self._iter_system_inspection_candidates()

        for drive_root in self._fixed_drive_roots():
            for candidate in self._iter_drive_junk_candidates(drive_root):
                count += 1
                if progress_callback and count % 500 == 0:
                    progress_callback(f"全盘扫描中 ({drive_root})", count)
                yield candidate
        if progress_callback:
            progress_callback("全盘扫描完成", count)

    def _iter_rule_candidates(self) -> Iterable[CleanupCandidate]:
        for rule in get_cleanable_rules():
            if rule.rule_id in SYSTEM_INSPECTION_RULE_IDS:
                continue
            for pattern in rule.path_patterns:
                for path in self._expand_pattern(pattern):
                    yield CleanupCandidate(
                        path=path,
                        title=rule.title,
                        risk=rule.risk,
                        category=rule.category,
                        vendor=rule.vendor,
                        description=rule.description,
                        safe_reason=rule.safe_reason,
                        source_rule=rule.rule_id,
                        default_candidate=rule.default_selected,
                    )

    def _iter_official_low_risk_candidates(self) -> Iterable[CleanupCandidate]:
        for pattern, title, source_rule, description, safe_reason in OFFICIAL_LOW_RISK_PATTERNS:
            for path in self._expand_pattern(pattern):
                yield CleanupCandidate(
                    path=path,
                    title=title,
                    risk=RiskLevel.LOW,
                    category="Windows 官方清理类别",
                    vendor="Windows",
                    description=description,
                    safe_reason=safe_reason,
                    source_rule=source_rule,
                    default_candidate=True,
                )

    def _iter_system_inspection_candidates(self) -> Iterable[CleanupCandidate]:
        for pattern, title, source_rule, description in SYSTEM_INSPECTION_PATHS:
            path = Path(os.path.expandvars(pattern))
            if not path.exists():
                continue
            yield CleanupCandidate(
                path=path,
                title=title,
                risk=RiskLevel.HIGH,
                category="系统检查项",
                vendor="Windows",
                description=description,
                safe_reason="这是 Windows 官方可清理类别，但涉及系统更新、回退或服务缓存，本程序只展示，不直接删除。",
                source_rule=source_rule,
                kind=ItemKind.NOTE,
                recoverable=False,
                inspect_only=True,
            )

    def _candidate_to_item(
        self,
        candidate: CleanupCandidate,
        seen_paths: set[str],
    ) -> CleanupItem | None:
        normalized_path = candidate.path.resolve(strict=False)
        normalized_key = str(normalized_path).lower()
        if normalized_key in seen_paths:
            return None
        seen_paths.add(normalized_key)

        kind = candidate.kind
        if kind is None:
            kind = ItemKind.DIRECTORY if candidate.path.is_dir() else ItemKind.FILE

        item = CleanupItem(
            item_id=stable_item_id(candidate.source_rule, normalized_key),
            title=candidate.title,
            path=str(candidate.path),
            kind=kind,
            risk=candidate.risk,
            category=candidate.category,
            vendor=candidate.vendor,
            description=candidate.description,
            safe_reason=candidate.safe_reason,
            size_bytes=0,
            default_selected=False,
            selected=False,
            recoverable=candidate.recoverable,
            source_rule=candidate.source_rule,
        )

        if candidate.inspect_only:
            item.message = "检查项仅用于提示，请通过 Windows 设置、磁盘清理或人工确认后处理。"
            return item

        allowed, reason = self.safety_guard.validate_item(item)
        if not allowed:
            item.risk = RiskLevel.BLOCKED
            item.selected = False
            item.default_selected = False
            item.message = reason
            return item

        if self._should_default_select(candidate, item):
            item.default_selected = True
            item.selected = True
        elif candidate.default_candidate and item.risk == RiskLevel.LOW and item.can_execute:
            hours = self.settings.min_age_hours
            item.message = f"为避免清理正在使用的文件，{hours} 小时内修改过的项目不会默认勾选。"
        return item

    def _should_default_select(self, candidate: CleanupCandidate, item: CleanupItem) -> bool:
        return (
            candidate.default_candidate
            and not candidate.inspect_only
            and item.can_execute
            and item.risk == RiskLevel.LOW
            and item.recoverable
            and self._is_older_than_min_age(Path(item.path))
        )

    def _is_older_than_min_age(self, path: Path) -> bool:
        try:
            modified_at = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            return False
        return datetime.now() - modified_at >= timedelta(hours=self.settings.min_age_hours)

    def _expand_pattern(self, pattern: str) -> list[Path]:
        expanded = os.path.expandvars(pattern)
        matches = glob.glob(expanded)
        return [Path(match) for match in matches if Path(match).exists()]

    def _iter_drive_junk_candidates(self, drive_root: Path) -> Iterable[CleanupCandidate]:
        visited = 0
        max_dirs = self.settings.max_dirs_per_drive
        max_depth = self.settings.max_scan_depth
        for root, dirs, files in os.walk(drive_root):
            if self.cancelled:
                dirs[:] = []
                return
            root_path = Path(root)
            visited += 1
            if visited > max_dirs:
                dirs[:] = []
                break
            if self._drive_scan_depth(drive_root, root_path) >= max_depth:
                dirs[:] = []
                continue
            dirs[:] = [
                directory
                for directory in dirs
                if self._should_descend_drive_directory(root_path / directory)
            ]
            for directory in list(dirs):
                path = root_path / directory
                folder_key = directory.lower()
                if folder_key not in ALL_DRIVE_JUNK_NAMES:
                    continue
                title, risk = ALL_DRIVE_JUNK_RULES.get(
                    folder_key, ("全盘垃圾文件", RiskLevel.MEDIUM)
                )
                default_candidate = folder_key in ALL_DRIVE_DEFAULT_SELECTED_NAMES
                for child in self._iter_directory_children(path):
                    yield CleanupCandidate(
                        path=child,
                        title=title,
                        risk=risk,
                        category="全盘保守扫描",
                        vendor=str(drive_root),
                        description=(
                            f"位于 {drive_root} 磁盘常见临时、缓存或日志目录 "
                            f"{path.name} 下的项目。"
                        ),
                        safe_reason="只扫描明确命名的临时、缓存和日志目录，并跳过系统目录、用户资料目录和同步目录。",
                        source_rule=f"drive.{folder_key}",
                        default_candidate=default_candidate,
                    )
                dirs.remove(directory)

            for filename in files[:ALL_DRIVE_SCAN_MAX_FILES_PER_DIR]:
                file_path = root_path / filename
                if file_path.is_symlink():
                    continue
                title_and_risk = ALL_DRIVE_JUNK_FILE_RULES.get(file_path.suffix.lower())
                if not title_and_risk:
                    continue
                title, risk = title_and_risk
                parent_key = root_path.name.lower()
                default_candidate = (
                    risk == RiskLevel.LOW and parent_key in ALL_DRIVE_DEFAULT_SELECTED_NAMES
                )
                yield CleanupCandidate(
                    path=file_path,
                    title=title,
                    risk=risk,
                    category="全盘保守扫描",
                    vendor=str(drive_root),
                    description=(
                        f"位于 {drive_root} 磁盘，扩展名 {file_path.suffix} "
                        "符合临时、日志、转储或残留文件特征。"
                    ),
                    safe_reason="扩展名识别只作为保守扫描提示，默认勾选仍限制在低风险目录且文件超过 24 小时未修改。",
                    source_rule=f"drive.extension{file_path.suffix.lower()}",
                    default_candidate=default_candidate,
                )

    def _fixed_drive_roots(self) -> list[Path]:
        roots: list[Path] = []
        for partition in psutil.disk_partitions(all=False):
            opts = {option.lower() for option in partition.opts.split(",") if option}
            if opts.intersection({"cdrom", "remote"}):
                continue
            if sys.platform.startswith("win") and not partition.device:
                continue
            root = Path(partition.mountpoint)
            if root.exists():
                roots.append(root)
        return sorted(set(roots), key=lambda path: str(path).lower())

    @staticmethod
    def _iter_directory_children(directory: Path) -> list[Path]:
        try:
            children = [path for path in directory.iterdir() if not path.is_symlink()]
        except OSError:
            return []
        return children[:ALL_DRIVE_SCAN_MAX_CHILDREN_PER_FOLDER]

    def _should_descend_drive_directory(self, path: Path) -> bool:
        if path.is_symlink() or path.name.lower() in ALL_DRIVE_SCAN_SKIP_NAMES:
            return False
        if self._is_cloud_sync_directory(path):
            return False
        normalized = path.resolve(strict=False)
        for protected in self.safety_guard.protected_paths:
            if normalized == protected or is_path_inside(normalized, protected):
                return False
        return True

    @staticmethod
    def _is_cloud_sync_directory(path: Path) -> bool:
        name = path.name.lower()
        return name in CLOUD_SYNC_FOLDER_NAMES or name.startswith("onedrive")

    @staticmethod
    def _drive_scan_depth(drive_root: Path, path: Path) -> int:
        try:
            return len(path.relative_to(drive_root).parts)
        except ValueError:
            return ALL_DRIVE_SCAN_MAX_DEPTH

    def _run_hidden(self, command: list[str], timeout: int = 12) -> subprocess.CompletedProcess:
        kwargs = {
            "capture_output": True,
            "text": True,
            "timeout": timeout,
            "check": False,
        }
        if sys.platform.startswith("win"):
            kwargs["startupinfo"] = STARTUPINFO
            kwargs["creationflags"] = CREATE_NO_WINDOW
        return subprocess.run(command, **kwargs)

    def _inspect_processes(self) -> list[CleanupItem]:
        items: list[CleanupItem] = []
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            if self.cancelled:
                return items
            try:
                name = proc.info.get("name") or ""
                exe = proc.info.get("exe") or ""
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            haystack = f"{name} {exe}".lower()
            keyword = find_keyword(haystack)
            if not keyword:
                continue
            items.append(
                CleanupItem(
                    item_id=stable_item_id("inspect.process", f"{name}:{proc.pid}"),
                    title="疑似已知软件相关进程",
                    path=f"{name} PID {proc.pid} {exe}",
                    kind=ItemKind.PROCESS,
                    risk=RiskLevel.HIGH,
                    category="进程检查",
                    vendor=keyword,
                    description="进程名称或路径命中已知软件关键词。",
                    safe_reason="进程可能属于正在使用的软件，首版仅展示，不自动结束。",
                    selected=False,
                    recoverable=False,
                    source_rule="inspect.process",
                    message="高风险，请优先使用官方卸载器或确认来源后再处理。",
                )
            )
        return items

    def _inspect_services(self) -> list[CleanupItem]:
        try:
            output = self._run_hidden(["sc", "query", "type=", "service", "state=", "all"])
        except (OSError, subprocess.TimeoutExpired):
            return []
        items: list[CleanupItem] = []
        for line in output.stdout.splitlines():
            line = line.strip()
            if not line.upper().startswith("SERVICE_NAME:"):
                continue
            name = line.split(":", 1)[1].strip()
            keyword = find_keyword(name)
            if not keyword:
                continue
            items.append(
                CleanupItem(
                    item_id=stable_item_id("inspect.service", name),
                    title="疑似已知软件相关服务",
                    path=name,
                    kind=ItemKind.SERVICE,
                    risk=RiskLevel.HIGH,
                    category="服务检查",
                    vendor=keyword,
                    description="服务名称命中已知软件关键词。",
                    safe_reason="服务删除风险高，首版只展示并建议官方卸载。",
                    selected=False,
                    recoverable=False,
                    source_rule="inspect.services",
                    message="高风险，不要在未确认用途时删除服务。",
                )
            )
        return items

    def _inspect_scheduled_tasks(self) -> list[CleanupItem]:
        try:
            output = self._run_hidden(["schtasks", "/query", "/fo", "LIST"])
        except (OSError, subprocess.TimeoutExpired):
            return []
        items: list[CleanupItem] = []
        for line in output.stdout.splitlines():
            line = line.strip()
            if not line.lower().startswith("taskname:"):
                continue
            name = line.split(":", 1)[1].strip()
            keyword = find_keyword(name)
            if not keyword:
                continue
            items.append(
                CleanupItem(
                    item_id=stable_item_id("inspect.task", name),
                    title="疑似已知软件相关计划任务",
                    path=name,
                    kind=ItemKind.TASK,
                    risk=RiskLevel.HIGH,
                    category="计划任务检查",
                    vendor=keyword,
                    description="计划任务名称命中已知软件关键词。",
                    safe_reason="计划任务可能承担更新或安全功能，首版不自动删除。",
                    selected=False,
                    recoverable=False,
                    source_rule="inspect.scheduled_tasks",
                    message="高风险，请核对发布者和触发器后再处理。",
                )
            )
        return items

    def _inspect_startup_registry(self) -> list[CleanupItem]:
        try:
            import winreg
        except ImportError:
            return []
        roots = (
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run",
            ),
        )
        items: list[CleanupItem] = []
        for root, subkey in roots:
            try:
                with winreg.OpenKey(root, subkey) as key:
                    count, _, _ = winreg.QueryInfoKey(key)
                    for index in range(count):
                        name, value, _ = winreg.EnumValue(key, index)
                        haystack = f"{name} {value}".lower()
                        keyword = find_keyword(haystack)
                        if not keyword:
                            continue
                        display_path = f"{subkey}\\{name} = {value}"
                        items.append(
                            CleanupItem(
                                item_id=stable_item_id("inspect.startup", display_path),
                                title="疑似已知软件相关启动项",
                                path=display_path,
                                kind=ItemKind.STARTUP,
                                risk=RiskLevel.HIGH,
                                category="启动项管理",
                                vendor=keyword,
                                description="启动项名称或命令命中已知软件关键词。",
                                safe_reason="启动项可能是用户需要的软件，首版只展示。",
                                selected=False,
                                recoverable=False,
                                source_rule="inspect.startup_items",
                                message="高风险，建议先禁用而不是删除。",
                            )
                        )
            except OSError:
                continue
        return items


def estimate_size(path: Path, max_entries: int = 10000) -> int:
    if path.is_symlink():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    visited = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [
            directory
            for directory in dirs
            if not (Path(root) / directory).is_symlink()
        ]
        for filename in files:
            visited += 1
            if visited > max_entries:
                return total
            file_path = Path(root) / filename
            if file_path.is_symlink():
                continue
            try:
                total += file_path.stat().st_size
            except OSError:
                continue
    return total


def find_keyword(text: str) -> str | None:
    lowered = text.lower()
    for keyword in PUP_KEYWORDS:
        if keyword and keyword in lowered:
            return keyword
    return None
