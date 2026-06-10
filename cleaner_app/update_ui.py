from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from .update_checker import UpdateChecker, UpdateInfo
from .update_downloader import UpdateDownloader, backup_current_exe, get_backup_dir, list_backups
from .version import __version__


class UpdateCheckThread(QThread):
    result = Signal(object)

    def __init__(self, checker: UpdateChecker, parent=None):
        super().__init__(parent)
        self._checker = checker

    def run(self) -> None:
        info = self._checker.check_for_updates()
        self.result.emit(info)


class UpdateDownloadThread(QThread):
    progress = Signal(int, int)
    finished_download = Signal(bool, str, object)

    def __init__(self, downloader: UpdateDownloader, update_info: UpdateInfo, parent=None):
        super().__init__(parent)
        self._downloader = downloader
        self._info = update_info
        self._cancelled = False

    def run(self) -> None:
        ok, msg, path = self._downloader.download_update(
            self._info,
            progress_callback=self._on_progress,
        )
        self.finished_download.emit(ok, msg, path)

    def _on_progress(self, downloaded: int, total: int) -> None:
        if not self._cancelled:
            self.progress.emit(downloaded, total)

    def cancel(self) -> None:
        self._cancelled = True


class UpdateNotificationBar(QFrame):
    view_update = Signal()
    skip_version = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("updateBar")
        self.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        self._label = QLabel()
        self._label.setObjectName("updateBarLabel")
        layout.addWidget(self._label, stretch=1)

        view_btn = QPushButton("查看更新")
        view_btn.setObjectName("updateBarViewBtn")
        view_btn.clicked.connect(self.view_update.emit)
        layout.addWidget(view_btn)

        skip_btn = QPushButton("忽略此版本")
        skip_btn.setObjectName("updateBarSkipBtn")
        skip_btn.clicked.connect(self.skip_version.emit)
        layout.addWidget(skip_btn)

    def show_update(self, version: str) -> None:
        self._label.setText(f"发现新版本 {version} 可用")
        self.setVisible(True)

    def hide_update(self) -> None:
        self.setVisible(False)


class UpdateDialog(QDialog):
    def __init__(self, update_info: UpdateInfo, parent=None):
        super().__init__(parent)
        self.setWindowTitle("软件更新")
        self.setMinimumSize(480, 400)

        self._info = update_info
        self._download_thread: UpdateDownloadThread | None = None
        self._downloaded_path: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("发现新版本")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #111827;")
        layout.addWidget(title)

        info_text = (
            f"当前版本：{__version__}\n"
            f"最新版本：{update_info.version}\n"
            f"发布日期：{self._format_date(update_info.release_date)}\n"
            f"下载大小：{self._format_size(update_info.size_bytes)}"
        )
        info_label = QLabel(info_text)
        info_label.setStyleSheet("color: #374151; line-height: 1.6;")
        layout.addWidget(info_label)

        changelog_title = QLabel("更新内容")
        changelog_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #111827;")
        layout.addWidget(changelog_title)

        self._changelog = QTextEdit()
        self._changelog.setReadOnly(True)
        self._changelog.setPlainText(update_info.changelog or "暂无更新说明。")
        self._changelog.setMaximumHeight(160)
        layout.addWidget(self._changelog)

        self._progress_frame = QFrame()
        self._progress_frame.setVisible(False)
        progress_layout = QVBoxLayout(self._progress_frame)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(6)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setTextVisible(False)
        progress_layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("准备下载...")
        self._progress_label.setStyleSheet("color: #667085; font-size: 12px;")
        progress_layout.addWidget(self._progress_label)

        layout.addWidget(self._progress_frame)

        self._button_frame = QFrame()
        button_layout = QHBoxLayout(self._button_frame)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)
        button_layout.addStretch()

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.clicked.connect(self._on_cancel)
        button_layout.addWidget(self._cancel_btn)

        self._later_btn = QPushButton("稍后提醒")
        self._later_btn.setStyleSheet(
            "background: #e5e7eb; color: #374151;"
            "QPushButton:hover { background: #d1d5db; }"
        )
        self._later_btn.clicked.connect(self.reject)
        button_layout.addWidget(self._later_btn)

        self._update_btn = QPushButton("立即更新")
        self._update_btn.clicked.connect(self._start_download)
        button_layout.addWidget(self._update_btn)

        layout.addWidget(self._button_frame)

    def _start_download(self) -> None:
        self._update_btn.setEnabled(False)
        self._later_btn.setVisible(False)
        self._cancel_btn.setText("取消下载")
        self._progress_frame.setVisible(True)
        self._changelog.setVisible(False)

        downloader = UpdateDownloader()
        self._download_thread = UpdateDownloadThread(downloader, self._info, self)
        self._download_thread.progress.connect(self._on_progress)
        self._download_thread.finished_download.connect(self._on_download_finished)
        self._download_thread.start()

    def _on_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            pct = int(downloaded * 100 / total)
            self._progress_bar.setValue(pct)
            self._progress_label.setText(
                f"已下载：{self._format_size(downloaded)} / {self._format_size(total)}"
            )
        else:
            self._progress_bar.setRange(0, 0)
            self._progress_label.setText(f"已下载：{self._format_size(downloaded)}")

    def _on_download_finished(self, ok: bool, message: str, path: object) -> None:
        if not ok:
            self._progress_frame.setVisible(False)
            self._changelog.setVisible(True)
            self._update_btn.setEnabled(True)
            self._later_btn.setVisible(True)
            self._cancel_btn.setText("取消")
            QMessageBox.warning(self, "下载失败", message)
            return

        self._downloaded_path = path
        self._progress_label.setText("下载完成，准备安装...")
        self._progress_bar.setValue(100)
        self._install_update()

    def _install_update(self) -> None:
        if self._downloaded_path is None:
            return

        current_exe = Path(sys.executable)

        if getattr(sys, "frozen", False):
            stub_path = Path(sys._MEIPASS) / "UpdaterStub.exe" if hasattr(sys, "_MEIPASS") else current_exe.parent / "_internal" / "UpdaterStub.exe"
            if not stub_path.exists():
                stub_path = current_exe.parent / "UpdaterStub.exe"
        else:
            stub_path = Path(__file__).resolve().parent.parent / "updater_stub.py"

        if not stub_path.exists():
            QMessageBox.warning(self, "更新失败", "更新组件缺失，请重新下载完整版本。")
            return

        backup_dir = get_backup_dir()
        backup_current_exe(current_exe, __version__)

        if stub_path.suffix == ".py":
            cmd = [sys.executable, str(stub_path)]
        else:
            cmd = [str(stub_path)]

        cmd.extend([
            str(current_exe),
            str(self._downloaded_path),
            str(backup_dir),
            self._info.version,
            str(os.getpid()),
        ])

        try:
            subprocess.Popen(
                cmd,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        except Exception as e:
            QMessageBox.warning(self, "更新失败", f"无法启动更新程序：{e}")
            return

        QMessageBox.information(
            self,
            "即将重启",
            "更新已准备就绪，程序将自动重启以完成更新。",
        )
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()

    def _on_cancel(self) -> None:
        if self._download_thread and self._download_thread.isRunning():
            self._download_thread.cancel()
            self._download_thread.wait(3000)
            self._progress_frame.setVisible(False)
            self._changelog.setVisible(True)
            self._update_btn.setEnabled(True)
            self._later_btn.setVisible(True)
            self._cancel_btn.setText("取消")
            return
        self.reject()

    @staticmethod
    def _format_date(date_str: str) -> str:
        if not date_str:
            return "未知"
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return date_str[:10] if len(date_str) >= 10 else date_str

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes <= 0:
            return "未知"
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"


class AboutDialog(QDialog):
    check_update = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于")
        self.setFixedSize(360, 240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(10)

        name = QLabel("严谨清理")
        name.setStyleSheet("font-size: 22px; font-weight: 800; color: #111827;")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)

        subtitle = QLabel("YanjinCleaner")
        subtitle.setStyleSheet("font-size: 13px; color: #667085;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        ver = QLabel(f"版本 {__version__}")
        ver.setStyleSheet("font-size: 13px; color: #374151;")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver)

        desc = QLabel("Windows 安全清理与软件残留检查中心")
        desc.setStyleSheet("font-size: 12px; color: #667085;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        check_btn = QPushButton("检查更新")
        check_btn.clicked.connect(self.check_update.emit)
        btn_layout.addWidget(check_btn)

        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)


class BackupRestoreDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("恢复历史版本")
        self.setMinimumSize(400, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title = QLabel("可用备份")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #111827;")
        layout.addWidget(title)

        self._backups = list_backups()
        self._list = QTextEdit()
        self._list.setReadOnly(True)
        if self._backups:
            lines = []
            for i, (name, path) in enumerate(self._backups):
                mtime = path.stat().st_mtime
                from datetime import datetime
                dt = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                lines.append(f"{i + 1}. {name}  ({dt})")
                lines.append(f"   路径: {path}")
                lines.append("")
            self._list.setPlainText("\n".join(lines))
        else:
            self._list.setPlainText("暂无可用备份。")
        layout.addWidget(self._list, stretch=1)

        note = QLabel("恢复操作将使用更新器替换当前版本，程序会自动重启。")
        note.setStyleSheet("color: #667085; font-size: 12px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        if self._backups:
            restore_btn = buttons.addButton("恢复最近备份", QDialogButtonBox.ButtonRole.ActionRole)
            restore_btn.clicked.connect(self._restore_latest)

        layout.addWidget(buttons)

    def _restore_latest(self) -> None:
        if not self._backups:
            return
        name, path = self._backups[0]
        reply = QMessageBox.question(
            self,
            "确认恢复",
            f"确定要恢复到 {name} 吗？\n程序将自动重启。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        current_exe = Path(sys.executable)
        backup_dir = get_backup_dir()

        if getattr(sys, "frozen", False):
            stub_path = Path(sys._MEIPASS) / "UpdaterStub.exe" if hasattr(sys, "_MEIPASS") else current_exe.parent / "_internal" / "UpdaterStub.exe"
            if not stub_path.exists():
                stub_path = current_exe.parent / "UpdaterStub.exe"
        else:
            stub_path = Path(__file__).resolve().parent.parent / "updater_stub.py"

        if not stub_path.exists():
            QMessageBox.warning(self, "恢复失败", "更新组件缺失。")
            return

        if stub_path.suffix == ".py":
            cmd = [sys.executable, str(stub_path)]
        else:
            cmd = [str(stub_path)]

        cmd.extend([
            str(current_exe),
            str(path),
            str(backup_dir),
            name,
            str(os.getpid()),
        ])

        try:
            subprocess.Popen(
                cmd,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        except Exception as e:
            QMessageBox.warning(self, "恢复失败", f"无法启动更新程序：{e}")
            return

        QMessageBox.information(self, "即将重启", "程序将自动重启以���成恢复。")
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()
