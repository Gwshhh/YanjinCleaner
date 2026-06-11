from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from PySide6.QtCore import (
    QAbstractTableModel,
    QEvent,
    QModelIndex,
    QRect,
    Qt,
    QThread,
    Signal,
)
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QIcon, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionButton,
    QStyleOptionViewItem,
    QTabWidget,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .executor import CleanupExecutor, QuarantineRecord
from .models import CleanupItem, CleanupReport, RiskLevel, format_bytes
from .scanner import CleanupScanner, estimate_size
from .safety import SafetyGuard
from .settings import UserSettings
from .update_checker import UpdateChecker
from .update_ui import (
    AboutDialog,
    BackupRestoreDialog,
    UpdateCheckThread,
    UpdateDialog,
    UpdateNotificationBar,
)
from .version import __version__

import csv
import json
import sys
from datetime import datetime, timezone


ALL_CATEGORIES = "全部项目"
RISK_FILTERS = {
    "全部风险": None,
    "低风险": RiskLevel.LOW,
    "中风险": RiskLevel.MEDIUM,
    "高风险": RiskLevel.HIGH,
    "禁止清理": RiskLevel.BLOCKED,
}
RISK_COLORS = {
    RiskLevel.LOW: QColor("#78f5a1"),
    RiskLevel.MEDIUM: QColor("#ffd84a"),
    RiskLevel.HIGH: QColor("#ff7474"),
    RiskLevel.BLOCKED: QColor("#cdd6e4"),
}
RISK_TEXT_COLORS = {
    RiskLevel.LOW: QColor("#064e3b"),
    RiskLevel.MEDIUM: QColor("#713f12"),
    RiskLevel.HIGH: QColor("#7f1d1d"),
    RiskLevel.BLOCKED: QColor("#334155"),
}
RISK_STRIP_WIDTH = 4
RISK_STRIP_VERTICAL_GAP = 8
RISK_BADGE_HEIGHT = 24
RISK_BADGE_HORIZONTAL_PADDING = 10
TABLE_ROW_MIN_HEIGHT = 44
TABLE_TEXT_HORIZONTAL_PADDING = 18
TABLE_TEXT_VERTICAL_PADDING = 18

COL_SELECT = 0
COL_RISK = 1
COL_SUMMARY = 2
COL_SIZE = 3
COL_GUIDANCE = 4
COLUMN_COUNT = 5
COLUMN_HEADERS = ["选择", "风险", "项目与说明", "大小", "能否清理 / 后果"]


class CleanupTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[CleanupItem] = []

    def set_items(self, items: list[CleanupItem]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def item_at(self, row: int) -> CleanupItem | None:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._items)

    def columnCount(self, parent=QModelIndex()):
        return COLUMN_COUNT

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMN_HEADERS[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == COL_SELECT:
            item = self._items[index.row()]
            if item.can_execute:
                base |= Qt.ItemFlag.ItemIsUserCheckable
        return base

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self._items[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_SELECT:
                return ""
            if col == COL_RISK:
                return item.risk.label
            if col == COL_SUMMARY:
                return item_summary(item)
            if col == COL_SIZE:
                return item.size_label
            if col == COL_GUIDANCE:
                return deletion_guidance(item)
            return None

        if role == Qt.ItemDataRole.CheckStateRole and col == COL_SELECT:
            return Qt.CheckState.Checked if item.selected else Qt.CheckState.Unchecked

        if role == Qt.ItemDataRole.UserRole:
            return item.item_id

        if role == Qt.ItemDataRole.UserRole + 1:  # risk color
            return RISK_COLORS[item.risk].name()

        if role == Qt.ItemDataRole.UserRole + 2:  # checkbox enabled
            return item.can_execute

        if role == Qt.ItemDataRole.ForegroundRole:
            return QBrush(RISK_TEXT_COLORS[item.risk])

        if role == Qt.ItemDataRole.FontRole:
            font = QFont()
            if col in {COL_RISK, COL_GUIDANCE}:
                font.setBold(True)
            return font

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in {COL_SELECT, COL_RISK, COL_SIZE}:
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        if role == Qt.ItemDataRole.ToolTipRole:
            if col in {COL_SUMMARY, COL_GUIDANCE}:
                return item_detail_text(item)
            return None

        return None

    def setData(self, index: QModelIndex, value, role=Qt.ItemDataRole.EditRole) -> bool:
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == COL_SELECT:
            item = self._items[index.row()]
            if not item.can_execute:
                return False
            item.selected = value == Qt.CheckState.Checked
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def update_sizes(self) -> None:
        if not self._items:
            return
        top = self.index(0, COL_SIZE)
        bottom = self.index(len(self._items) - 1, COL_SIZE)
        self.dataChanged.emit(top, bottom, [Qt.ItemDataRole.DisplayRole])


RISK_COLOR_ROLE = Qt.ItemDataRole.UserRole + 1
CHECKBOX_ENABLED_ROLE = Qt.ItemDataRole.UserRole + 2
RESTORE_MANIFEST_ROLE = Qt.ItemDataRole.UserRole + 3
RESTORE_VALID_ROLE = Qt.ItemDataRole.UserRole + 4


class RiskRowDelegate(QStyledItemDelegate):
    @staticmethod
    def is_checked(value) -> bool:
        return value in {Qt.CheckState.Checked, Qt.CheckState.Checked.value}

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        col = index.column()
        if col in {COL_SUMMARY, COL_GUIDANCE}:
            text = index.data(Qt.ItemDataRole.DisplayRole) or ""
            font = index.data(Qt.ItemDataRole.FontRole) or option.font
            metrics = QFontMetrics(font)
            text_width = max(1, option.rect.width() - TABLE_TEXT_HORIZONTAL_PADDING) if option.rect.width() > 0 else 200
            text_rect = metrics.boundingRect(
                QRect(0, 0, text_width, 100000),
                Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextWrapAnywhere,
                text,
            )
            hint.setHeight(max(TABLE_ROW_MIN_HEIGHT, text_rect.height() + TABLE_TEXT_VERTICAL_PADDING))
        else:
            hint.setHeight(max(TABLE_ROW_MIN_HEIGHT, hint.height()))
        return hint

    def paint(self, painter, option, index) -> None:
        risk_color = index.data(RISK_COLOR_ROLE)
        if risk_color and index.column() == COL_SELECT and index.data(Qt.ItemDataRole.CheckStateRole) is not None:
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            opt.text = ""
            opt.features &= ~QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
            style = opt.widget.style() if opt.widget else QApplication.style()
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter)

            color = QColor(risk_color)
            strip_rect = QRect(
                option.rect.left(),
                option.rect.top() + RISK_STRIP_VERTICAL_GAP,
                RISK_STRIP_WIDTH,
                max(0, option.rect.height() - RISK_STRIP_VERTICAL_GAP * 2),
            )
            painter.save()
            painter.fillRect(strip_rect, color)
            painter.restore()

            checkbox = QStyleOptionButton()
            checkbox.state = QStyle.StateFlag.State_Active
            if not index.data(CHECKBOX_ENABLED_ROLE):
                checkbox.state &= ~QStyle.StateFlag.State_Enabled
            else:
                checkbox.state |= QStyle.StateFlag.State_Enabled
            if self.is_checked(index.data(Qt.ItemDataRole.CheckStateRole)):
                checkbox.state |= QStyle.StateFlag.State_On
            else:
                checkbox.state |= QStyle.StateFlag.State_Off
            indicator = style.subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, checkbox)
            checkbox.rect = QRect(
                option.rect.x() + (option.rect.width() - indicator.width()) // 2,
                option.rect.y() + (option.rect.height() - indicator.height()) // 2,
                indicator.width(),
                indicator.height(),
            )
            style.drawControl(QStyle.ControlElement.CE_CheckBox, checkbox, painter)
            return

        if risk_color and index.column() == COL_RISK:
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            text = opt.text
            opt.text = ""
            style = opt.widget.style() if opt.widget else QApplication.style()
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter)

            color = QColor(risk_color)
            foreground = index.data(Qt.ItemDataRole.ForegroundRole)
            text_color = QColor("#111827")
            if isinstance(foreground, QBrush):
                text_color = foreground.color()

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setFont(opt.font)
            metrics = QFontMetrics(opt.font)
            badge_width = min(
                option.rect.width() - 12,
                metrics.horizontalAdvance(text) + RISK_BADGE_HORIZONTAL_PADDING * 2,
            )
            badge_rect = QRect(
                option.rect.x() + (option.rect.width() - badge_width) // 2,
                option.rect.y() + (option.rect.height() - RISK_BADGE_HEIGHT) // 2,
                badge_width,
                RISK_BADGE_HEIGHT,
            )
            badge_fill = QColor(color)
            badge_fill.setAlpha(64)
            painter.setPen(color.darker(125))
            painter.setBrush(badge_fill)
            painter.drawRoundedRect(badge_rect, 6, 6)
            painter.setPen(text_color)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)
            painter.restore()
            return

        super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index) -> bool:
        if index.column() == COL_SELECT and index.data(Qt.ItemDataRole.CheckStateRole) is not None:
            if not index.data(CHECKBOX_ENABLED_ROLE):
                return False
            if event.type() in {QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick}:
                next_state = (
                    Qt.CheckState.Unchecked
                    if self.is_checked(index.data(Qt.ItemDataRole.CheckStateRole))
                    else Qt.CheckState.Checked
                )
                return model.setData(index, next_state, Qt.ItemDataRole.CheckStateRole)
            if event.type() == QEvent.Type.KeyPress and event.key() in {
                Qt.Key.Key_Space,
                Qt.Key.Key_Select,
            }:
                next_state = (
                    Qt.CheckState.Unchecked
                    if self.is_checked(index.data(Qt.ItemDataRole.CheckStateRole))
                    else Qt.CheckState.Checked
                )
                return model.setData(index, next_state, Qt.ItemDataRole.CheckStateRole)
        return super().editorEvent(event, model, option, index)


class ScannerThread(QThread):
    finished_scan = Signal(object)
    progress = Signal(str, int)

    def __init__(self, scanner: CleanupScanner) -> None:
        super().__init__()
        self.scanner = scanner

    def run(self) -> None:
        report = self.scanner.scan(
            include_high_risk=True,
            progress_callback=self._on_progress,
        )
        self.finished_scan.emit(report)

    def _on_progress(self, stage: str, count: int) -> None:
        self.progress.emit(stage, count)


class SizeEstimationThread(QThread):
    batch_ready = Signal()
    finished = Signal()

    def __init__(self, scanner: CleanupScanner, items: list[CleanupItem]) -> None:
        super().__init__()
        self.scanner = scanner
        self.items = items

    def run(self) -> None:
        count = 0
        for item in self.items:
            if self.scanner.cancelled:
                return
            if item.is_file_system_item and item.size_bytes == 0:
                item.size_bytes = estimate_size(Path(item.path))
                count += 1
                if count % 20 == 0:
                    self.batch_ready.emit()
        self.finished.emit()


class ExecutorThread(QThread):
    finished_execute = Signal(object)

    def __init__(self, executor: CleanupExecutor, items: list[CleanupItem]) -> None:
        super().__init__()
        self.executor = executor
        self.items = items

    def run(self) -> None:
        self.finished_execute.emit(self.executor.execute(self.items))


class SettingsDialog(QDialog):
    def __init__(self, settings: UserSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.settings = settings
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.min_age_spin = QSpinBox()
        self.min_age_spin.setRange(1, 720)
        self.min_age_spin.setValue(settings.min_age_hours)
        self.min_age_spin.setSuffix(" 小时")
        form.addRow("最小文件年龄:", self.min_age_spin)

        self.max_depth_spin = QSpinBox()
        self.max_depth_spin.setRange(3, 15)
        self.max_depth_spin.setValue(settings.max_scan_depth)
        form.addRow("最大扫描深度:", self.max_depth_spin)

        self.max_dirs_spin = QSpinBox()
        self.max_dirs_spin.setRange(1000, 100000)
        self.max_dirs_spin.setSingleStep(1000)
        self.max_dirs_spin.setValue(settings.max_dirs_per_drive)
        form.addRow("最大扫描目录数:", self.max_dirs_spin)

        self.auto_select_check = QCheckBox("自动选择低风险项")
        self.auto_select_check.setChecked(settings.auto_select_low_risk)
        form.addRow("", self.auto_select_check)

        layout.addLayout(form)

        paths_label = QLabel("排除路径（每行一个）:")
        layout.addWidget(paths_label)
        self.paths_list = QTextEdit()
        self.paths_list.setPlainText("\n".join(settings.excluded_paths))
        self.paths_list.setMaximumHeight(120)
        layout.addWidget(self.paths_list)

        update_label = QLabel("更新设置")
        update_label.setStyleSheet("font-weight: 700; margin-top: 8px;")
        layout.addWidget(update_label)

        self.auto_update_check = QCheckBox("启动时自动检查更新")
        self.auto_update_check.setChecked(settings.auto_check_updates)
        layout.addWidget(self.auto_update_check)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self) -> UserSettings:
        paths = [line.strip() for line in self.paths_list.toPlainText().split("\n") if line.strip()]
        return UserSettings(
            min_age_hours=self.min_age_spin.value(),
            max_scan_depth=self.max_depth_spin.value(),
            max_dirs_per_drive=self.max_dirs_spin.value(),
            excluded_paths=paths,
            auto_select_low_risk=self.auto_select_check.isChecked(),
            auto_check_updates=self.auto_update_check.isChecked(),
        )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("严谨清理 - Windows 安全清理与软件残留检查中心")
        self.resize(1320, 820)
        self.setMinimumSize(1120, 720)

        icon_path = self._get_icon_path()
        if icon_path and icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.settings = UserSettings.load()
        self.safety_guard = SafetyGuard(settings=self.settings)
        self.scanner = CleanupScanner(self.safety_guard, self.settings)
        self.executor = CleanupExecutor(self.safety_guard)
        self.items: list[CleanupItem] = []
        self.current_category = ALL_CATEGORIES
        self.scanner_thread: ScannerThread | None = None
        self.executor_thread: ExecutorThread | None = None
        self.size_thread: SizeEstimationThread | None = None
        self.restore_records: list[QuarantineRecord] = []

        self.update_checker = UpdateChecker()
        self.update_check_thread: UpdateCheckThread | None = None
        self.pending_update = None
        self._manual_update_check = False

        self.nav = QListWidget()
        self.nav.currentTextChanged.connect(self.on_nav_changed)

        self.status_label = QLabel("准备就绪")
        self.scan_button = QPushButton("开始扫描")
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setVisible(False)
        self.clean_button = QPushButton("清理已勾选")
        self.clean_button.setEnabled(False)
        self.export_button = QPushButton("导出")
        self.export_button.setEnabled(False)
        self.settings_button = QPushButton("设置")
        self.about_button = QPushButton("关于")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索项目、来源、路径")
        self.search_box.textChanged.connect(self.refresh_table)

        self.risk_filter = QComboBox()
        self.risk_filter.addItems(list(RISK_FILTERS.keys()))
        self.risk_filter.currentTextChanged.connect(self.refresh_table)

        self.select_all_low_button = QPushButton("全选低风险")
        self.select_all_low_button.clicked.connect(self.select_all_low_risk)
        self.deselect_all_button = QPushButton("取消全选")
        self.deselect_all_button.clicked.connect(self.deselect_all)

        self.table_model = CleanupTableModel()
        self.table_model.dataChanged.connect(self.on_model_data_changed)
        self.table = QTableView()
        self.table.setModel(self.table_model)
        delegate = RiskRowDelegate(self.table)
        self.table.setItemDelegate(delegate)
        self.table.horizontalHeader().setSectionResizeMode(COL_SELECT, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(COL_RISK, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(COL_SUMMARY, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_SIZE, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(COL_GUIDANCE, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(COL_SELECT, 58)
        self.table.setColumnWidth(COL_RISK, 90)
        self.table.setColumnWidth(COL_SIZE, 88)
        self.table.setColumnWidth(COL_GUIDANCE, 340)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setWordWrap(True)
        self.table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.table.setShowGrid(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.clicked.connect(self.show_item_detail)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setObjectName("detailPanel")

        self.guide = QTextEdit()
        self.guide.setReadOnly(True)
        self.guide.setObjectName("guidePanel")
        self.guide.setText(self.guide_text())

        self.restore_list = QListWidget()
        self.restore_list.setObjectName("restoreList")
        self.restore_list.currentRowChanged.connect(self.on_restore_selection_changed)

        self.restore_detail = QTextEdit()
        self.restore_detail.setReadOnly(True)
        self.restore_detail.setObjectName("guidePanel")
        self.restore_detail.setText(self.restore_text())

        self.restore_refresh_button = QPushButton("刷新隔离区")
        self.restore_button = QPushButton("恢复选中")
        self.restore_button.setEnabled(False)
        self.restore_refresh_button.clicked.connect(self.refresh_restore_center)
        self.restore_button.clicked.connect(self.restore_selected_quarantine_item)

        self.metric_cards: dict[str, QLabel] = {}
        self.scan_button.clicked.connect(self.start_scan)
        self.cancel_button.clicked.connect(self.cancel_scan)
        self.clean_button.clicked.connect(self.confirm_and_clean)
        self.export_button.clicked.connect(self.export_results)
        self.settings_button.clicked.connect(self.open_settings_dialog)
        self.about_button.clicked.connect(self.show_about_dialog)

        self.update_bar = UpdateNotificationBar()
        self.update_bar.view_update.connect(self.show_update_dialog)
        self.update_bar.skip_version.connect(self.skip_current_update)

        self.setCentralWidget(self.build_shell())
        self.apply_theme()
        self.populate_nav()
        self.refresh_restore_center()
        self.update_metrics()
        self._maybe_check_for_updates()

    def build_shell(self) -> QWidget:
        root = QWidget()
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(238)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(18, 18, 18, 18)
        side_layout.setSpacing(14)

        brand = QLabel("严谨清理")
        brand.setObjectName("brand")
        tagline = QLabel("安全清理 · 残留检查 · 可恢复")
        tagline.setObjectName("tagline")
        side_layout.addWidget(brand)
        side_layout.addWidget(tagline)
        side_layout.addSpacing(12)
        side_layout.addWidget(self.nav, stretch=1)
        side_layout.addWidget(self.build_sidebar_status())

        version_label = QLabel(f"v{__version__}")
        version_label.setObjectName("sidebarVersion")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_layout.addWidget(version_label)

        content = QFrame()
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 22, 24, 22)
        content_layout.setSpacing(16)
        content_layout.addLayout(self.build_topbar())
        content_layout.addWidget(self.update_bar)
        content_layout.addWidget(self.progress_bar)
        content_layout.addLayout(self.build_metrics())
        content_layout.addWidget(self.build_workspace(), stretch=1)

        shell.addWidget(sidebar)
        shell.addWidget(content, stretch=1)
        return root

    def build_sidebar_status(self) -> QWidget:
        box = QFrame()
        box.setObjectName("sidebarCard")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 12, 14, 12)
        title = QLabel("安全策略")
        title.setObjectName("sidebarCardTitle")
        text = QLabel("默认回收站/隔离区\n高风险只检查\n保护用户文件夹")
        text.setObjectName("sidebarCardText")
        layout.addWidget(title)
        layout.addWidget(text)
        return box

    def build_topbar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("清理工作台")
        title.setObjectName("pageTitle")
        subtitle = QLabel("先扫描，再解释，再确认。低/中风险可清理，高风险默认只作为核对线索。")
        subtitle.setObjectName("pageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box, stretch=1)
        self.status_label.setMaximumWidth(260)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.status_label)
        layout.addWidget(self.about_button)
        layout.addWidget(self.settings_button)
        layout.addWidget(self.export_button)
        layout.addWidget(self.cancel_button)
        layout.addWidget(self.scan_button)
        layout.addWidget(self.clean_button)
        return layout

    def build_metrics(self) -> QGridLayout:
        layout = QGridLayout()
        layout.setSpacing(12)
        for index, (key, title) in enumerate(
            (
                ("total", "发现项目"),
                ("selected", "已勾选"),
                ("space", "预计释放"),
                ("high", "高风险线索"),
            )
        ):
            card = self.metric_card(title, "0")
            layout.addWidget(card, 0, index)
        return layout

    def metric_card(self, title: str, value: str) -> QWidget:
        card = QFrame()
        card.setObjectName("metricCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        label = QLabel(title)
        label.setObjectName("metricTitle")
        number = QLabel(value)
        number.setObjectName("metricValue")
        layout.addWidget(label)
        layout.addWidget(number)
        self.metric_cards[title] = number
        return card

    def build_workspace(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("workspace")

        left = QFrame()
        left.setObjectName("tablePanel")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)
        filter_bar = QHBoxLayout()
        filter_bar.addWidget(self.search_box, stretch=1)
        filter_bar.addWidget(self.risk_filter)
        filter_bar.addWidget(self.select_all_low_button)
        filter_bar.addWidget(self.deselect_all_button)
        left_layout.addLayout(filter_bar)
        left_layout.addWidget(self.table, stretch=1)

        right = QFrame()
        right.setObjectName("sidePanel")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)

        tabs = QTabWidget()
        tabs.setObjectName("sideTabs")

        detail_tab = QWidget()
        detail_layout = QVBoxLayout(detail_tab)
        detail_layout.setContentsMargins(0, 8, 0, 0)
        detail_layout.addWidget(self.detail)

        guide_tab = QWidget()
        guide_layout = QVBoxLayout(guide_tab)
        guide_layout.setContentsMargins(0, 8, 0, 0)
        guide_layout.addWidget(self.guide)

        restore_tab = QWidget()
        restore_layout = QVBoxLayout(restore_tab)
        restore_layout.setContentsMargins(0, 8, 0, 0)
        restore_actions = QHBoxLayout()
        restore_actions.addWidget(self.restore_refresh_button)
        restore_actions.addWidget(self.restore_button)
        restore_layout.addLayout(restore_actions)
        restore_layout.addWidget(self.restore_list, stretch=1)
        restore_layout.addWidget(self.restore_detail, stretch=1)

        tabs.addTab(detail_tab, "详情与说明")
        tabs.addTab(guide_tab, "清理边界")
        tabs.addTab(restore_tab, "恢复中心")

        right_layout.addWidget(tabs, stretch=1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 2)
        return splitter

    def populate_nav(self) -> None:
        self.nav.clear()
        labels = [ALL_CATEGORIES, "安全垃圾", "已卸载软件残留", "浏览器隐私", "启动项管理", "服务检查", "计划任务检查"]
        for label in labels:
            item = QListWidgetItem(label)
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
            self.nav.addItem(item)
        self.nav.setCurrentRow(0)

    def start_scan(self) -> None:
        self.scanner.reset()
        self.scan_button.setEnabled(False)
        self.clean_button.setEnabled(False)
        self.cancel_button.setVisible(True)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.status_label.setText("正在扫描...")
        self.detail.setText("正在扫描规则库指定位置、浏览器缓存、已卸载软件残留和高风险系统线索。")
        self.scanner_thread = ScannerThread(self.scanner)
        self.scanner_thread.finished_scan.connect(self.on_scan_finished)
        self.scanner_thread.progress.connect(self.on_scan_progress)
        self.scanner_thread.start()

    def cancel_scan(self) -> None:
        self.scanner.cancel()
        self.cancel_button.setEnabled(False)
        self.status_label.setText("正在取消...")

    def on_scan_progress(self, stage: str, count: int) -> None:
        self.status_label.setText(f"{stage}（{count} 项）")

    def on_scan_finished(self, report: CleanupReport) -> None:
        self.progress_bar.setVisible(False)
        self.cancel_button.setVisible(False)
        self.items = report.items
        if self.scanner.cancelled:
            self.status_label.setText(f"扫描已取消：已发现 {report.scanned_count} 项")
        else:
            self.status_label.setText(f"扫描完成：{report.scanned_count} 项")
        self.scan_button.setEnabled(True)
        self.clean_button.setEnabled(any(item.selected for item in self.items))
        self.export_button.setEnabled(bool(self.items))
        self.sync_nav_with_categories()
        self.update_metrics()
        self.refresh_table()
        self._start_size_estimation()

    def _start_size_estimation(self) -> None:
        if self.size_thread and self.size_thread.isRunning():
            self.scanner.cancel()
            self.size_thread.wait()
        self.scanner.reset()
        self.size_thread = SizeEstimationThread(self.scanner, self.items)
        self.size_thread.batch_ready.connect(self._on_size_batch)
        self.size_thread.finished.connect(self._on_size_finished)
        self.size_thread.start()

    def _on_size_batch(self) -> None:
        self.table_model.update_sizes()
        self.update_metrics()

    def _on_size_finished(self) -> None:
        self.table_model.update_sizes()
        self.update_metrics()

    def sync_nav_with_categories(self) -> None:
        existing = {self.nav.item(index).text() for index in range(self.nav.count())}
        for category in sorted({item.category for item in self.items}):
            if category not in existing:
                self.nav.addItem(category)

    def on_nav_changed(self, text: str) -> None:
        self.current_category = text or ALL_CATEGORIES
        self.refresh_table()

    def refresh_table(self) -> None:
        visible = self.filtered_items()
        self.table_model.set_items(visible)
        self.table.resizeRowsToContents()
        self.update_detail_summary(visible)
        self.update_metrics()

    def on_model_data_changed(self, top_left, bottom_right, roles) -> None:
        if Qt.ItemDataRole.CheckStateRole in roles:
            self.clean_button.setEnabled(any(item.selected for item in self.items))
            self.update_metrics()

    def filtered_items(self) -> list[CleanupItem]:
        query = self.search_box.text().strip().lower()
        risk = RISK_FILTERS[self.risk_filter.currentText()]
        result = []
        for item in self.items:
            if self.current_category != ALL_CATEGORIES and item.category != self.current_category:
                continue
            if risk is not None and item.risk != risk:
                continue
            if query and query not in " ".join(
                [item.title, item.vendor, item.category, item.path, item.description]
            ).lower():
                continue
            result.append(item)
        return result

    def select_all_low_risk(self) -> None:
        for item in self.items:
            if item.risk == RiskLevel.LOW and item.can_execute:
                item.selected = True
        self.refresh_table()

    def deselect_all(self) -> None:
        for item in self.items:
            item.selected = False
        self.refresh_table()

    def update_metrics(self) -> None:
        selected = [item for item in self.items if item.selected]
        high_count = sum(1 for item in self.items if item.risk == RiskLevel.HIGH)
        self.metric_cards["发现项目"].setText(str(len(self.items)))
        self.metric_cards["已勾选"].setText(str(len(selected)))
        self.metric_cards["预计释放"].setText(format_bytes(sum(item.size_bytes for item in selected)))
        self.metric_cards["高风险线索"].setText(str(high_count))

    def show_item_detail(self, index: QModelIndex) -> None:
        item = self.table_model.item_at(index.row())
        if item:
            self.detail.setText(item_detail_text(item))

    def update_detail_summary(self, visible: list[CleanupItem]) -> None:
        if not self.items:
            self.detail.setText('点击"开始扫描"后，这里会显示每个项目的来源、风险、路径和处理建议。')
            return
        if not visible:
            self.detail.setText("当前筛选条件下没有项目。")
            return
        grouped = Counter(item.risk.label for item in visible)
        by_category: dict[str, int] = defaultdict(int)
        for item in visible:
            by_category[item.category] += 1
        lines = ["当前视图概览", ""]
        lines.extend(f"{risk}: {count} 项" for risk, count in grouped.items())
        lines.append("")
        lines.append("分类分布")
        lines.extend(f"{category}: {count} 项" for category, count in sorted(by_category.items()))
        lines.append("")
        lines.append("点击表格中的项目查看详细说明。")
        self.detail.setText("\n".join(lines))

    def confirm_and_clean(self) -> None:
        selected = [item for item in self.items if item.selected]
        if not selected:
            QMessageBox.information(self, "没有选择项目", "请先勾选要清理的低/中风险项目。")
            return
        blocked = [item for item in selected if not item.can_execute]
        if blocked:
            QMessageBox.warning(
                self,
                "包含不可执行项目",
                "已选择项目中包含高风险或受保护项目，请取消这些项目后再清理。",
            )
            return
        message = (
            f"将清理 {len(selected)} 项，预计释放 {format_bytes(sum(i.size_bytes for i in selected))}。\n\n"
            "默认移入回收站；如果回收站组件不可用，则移入应用隔离区。\n"
            "不会永久删除，也不会处理高风险服务、注册表或计划任务。"
        )
        result = QMessageBox.question(
            self,
            "确认清理",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        self.executor.reset()
        self.scan_button.setEnabled(False)
        self.clean_button.setEnabled(False)
        self.status_label.setText("正在清理...")
        self.executor_thread = ExecutorThread(self.executor, self.items)
        self.executor_thread.finished_execute.connect(self.on_execute_finished)
        self.executor_thread.start()

    def on_execute_finished(self, report: CleanupReport) -> None:
        self.scan_button.setEnabled(True)
        self.clean_button.setEnabled(False)
        self.status_label.setText(f"清理完成：释放约 {report.freed_label}，失败 {len(report.errors)} 项")
        self.refresh_table()
        self.refresh_restore_center()
        lines = [
            f"清理完成：释放约 {report.freed_label}",
            f"日志目录：{self.executor.logs_dir}",
            f"隔离区：{self.executor.quarantine_dir}",
        ]
        if report.errors:
            lines.append("")
            lines.append("失败项目")
            lines.extend(f"- {error}" for error in report.errors[:20])
        self.detail.setText("\n".join(lines))

    def refresh_restore_center(self) -> None:
        self.restore_records = self.executor.list_quarantine_records()
        self.restore_list.clear()
        self.restore_button.setEnabled(False)
        if not self.restore_records:
            self.restore_detail.setText(self.restore_text())
            return
        for record in self.restore_records:
            item = QListWidgetItem(self.quarantine_record_list_text(record))
            item.setData(RESTORE_MANIFEST_ROLE, str(record.manifest_path))
            item.setData(RESTORE_VALID_ROLE, record.valid)
            self.restore_list.addItem(item)
        self.restore_list.setCurrentRow(0)

    def on_restore_selection_changed(self, row: int) -> None:
        if row < 0 or row >= len(self.restore_records):
            self.restore_button.setEnabled(False)
            self.restore_detail.setText(self.restore_text())
            return
        record = self.restore_records[row]
        can_restore = record.valid and record.source is not None and not record.source.exists()
        self.restore_button.setEnabled(can_restore)
        self.restore_detail.setText(self.quarantine_record_detail_text(record))

    def restore_selected_quarantine_item(self) -> None:
        current = self.restore_list.currentItem()
        if current is None:
            return
        manifest_text = current.data(RESTORE_MANIFEST_ROLE)
        if not manifest_text:
            self.restore_detail.setText("未找到选中隔离项的清单路径。")
            self.restore_button.setEnabled(False)
            return
        ok, message = self.executor.restore_quarantine_item(Path(str(manifest_text)))
        if ok:
            QMessageBox.information(self, "恢复完成", message)
        else:
            QMessageBox.warning(self, "恢复失败", message)
        self.refresh_restore_center()
        self.restore_detail.setText(message)

    @staticmethod
    def quarantine_record_list_text(record: QuarantineRecord) -> str:
        prefix = "可恢复" if record.valid else "需检查"
        return f"{prefix}｜{record.title}｜{record.created_label}"

    @staticmethod
    def quarantine_record_detail_text(record: QuarantineRecord) -> str:
        lines = [
            f"项目：{record.title}",
            f"状态：{'可恢复' if record.valid else '需检查'}",
            f"隔离时间：{record.created_label}",
            f"原路径：{record.source_label}",
            f"隔离路径：{record.quarantined_label}",
            f"清单：{record.manifest_path}",
        ]
        if record.source and record.source.exists():
            lines.extend(["", "恢复已暂停：原路径已存在，程序不会覆盖现有文件或目录。"])
        if record.message:
            lines.extend(["", f"提示：{record.message}"])
        elif record.valid:
            lines.extend(["", "恢复会把隔离文件移回原路径；如果原路径已被重新创建，会阻止覆盖。"])
        return "\n".join(lines)

    def guide_text(self) -> str:
        protected = "\n".join(f"- {path}" for path in self.safety_guard.explain_protected_paths())
        return (
            "可以清理\n"
            "- 临时文件、缓存、日志、崩溃转储。\n"
            "- 浏览器缓存，不删除书签、密码和历史数据库。\n"
            "- 已卸载软件的缓存、日志和残留文件。\n\n"
            "谨慎清理\n"
            "- 软件主程序目录、插件、快捷方式、启动项。\n"
            "- 安全软件、驱动、服务、计划任务。\n\n"
            "禁止自动清理\n"
            "- 系统目录、用户文档、桌面、下载、图片、视频。\n"
            "- 注册表关键项、正在运行的软件目录、未知个人文件。\n\n"
            "受保护路径\n"
            f"{protected}"
        )

    def restore_text(self) -> str:
        return (
            "恢复方式\n"
            "- 移入回收站的文件可从 Windows 回收站还原。\n"
            "- 隔离文件和日志位于 %LOCALAPPDATA%\\严谨清理。\n"
            "- 首次使用建议只清理默认勾选项。\n\n"
            "处理已卸载软件\n"
            "- 优先使用官方卸载器。\n"
            "- 再扫描残留目录。\n"
            "- 高风险线索只作为人工核对依据。"
        )

    def apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background: #f4f7fb; }
            #sidebar { background: #111827; }
            #brand { color: #f9fafb; font-size: 26px; font-weight: 800; }
            #tagline { color: #9ca3af; font-size: 12px; }
            #sidebarCard { background: #1f2937; border: 1px solid #374151; border-radius: 8px; }
            #sidebarCardTitle { color: #f9fafb; font-weight: 700; }
            #sidebarCardText { color: #cbd5e1; line-height: 1.4; }
            QListWidget { background: transparent; color: #cbd5e1; border: none; outline: 0; }
            QListWidget::item { padding: 11px 12px; border-radius: 7px; margin: 2px 0; }
            QListWidget::item:selected { background: #2563eb; color: white; }
            QListWidget::item:hover { background: #1f2937; }
            #restoreList {
                background: #fbfdff; color: #1f2937; border: 1px solid #e5e7eb;
                border-radius: 7px;
            }
            #restoreList::item { padding: 8px; border-radius: 6px; margin: 2px; color: #1f2937; }
            #restoreList::item:selected { background: #dbeafe; color: #0f172a; }
            #restoreList::item:hover { background: #eef4fb; color: #0f172a; }
            #content { background: #f4f7fb; }
            #pageTitle { color: #111827; font-size: 24px; font-weight: 800; }
            #pageSubtitle { color: #667085; }
            QLabel { color: #1f2937; }
            QPushButton {
                background: #2563eb; color: white; border: none; border-radius: 7px;
                padding: 9px 15px; font-weight: 700;
            }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton:disabled { background: #cbd5e1; color: #64748b; }
            QLineEdit, QComboBox {
                background: white; border: 1px solid #d0d5dd; border-radius: 7px;
                padding: 8px 10px; color: #111827;
            }
            #metricCard, #tablePanel, #sidePanel {
                background: white; border: 1px solid #e5e7eb; border-radius: 8px;
            }
            #metricTitle { color: #667085; font-size: 12px; }
            #metricValue { color: #111827; font-size: 24px; font-weight: 800; }
            QTableView {
                background: white; alternate-background-color: #f8fafc;
                border: 1px solid #d9e1ec; border-radius: 8px; gridline-color: #dfe7f1;
                selection-background-color: #bfdbfe; selection-color: #0f172a;
                font-size: 13px;
            }
            QHeaderView::section {
                background: #eef4fb; color: #334155; border: none; border-bottom: 1px solid #d9e1ec;
                padding: 10px 8px; font-weight: 800;
            }
            QTableView::item {
                padding: 8px 6px;
                border-bottom: 1px solid #e6edf5;
            }
            QTextEdit {
                background: #fbfdff; border: 1px solid #e5e7eb; border-radius: 7px;
                padding: 10px; color: #1f2937;
            }
            QTabWidget::pane {
                border: 1px solid #e5e7eb; border-radius: 7px; background: white;
            }
            QTabBar::tab {
                background: #eef4fb; color: #334155; padding: 8px 14px;
                border: 1px solid #e5e7eb; border-bottom: none; border-radius: 6px 6px 0 0;
                margin-right: 2px;
            }
            QTabBar::tab:selected { background: white; color: #111827; font-weight: 700; }
            QProgressBar { background: #e5e7eb; border: none; border-radius: 2px; }
            QProgressBar::chunk { background: #2563eb; border-radius: 2px; }
            #updateBar {
                background: #dbeafe; border: 1px solid #93c5fd; border-radius: 8px;
            }
            #updateBarLabel { color: #1e40af; font-weight: 700; }
            #updateBarViewBtn {
                background: #2563eb; color: white; padding: 6px 12px;
                border-radius: 5px; font-weight: 700;
            }
            #updateBarViewBtn:hover { background: #1d4ed8; }
            #updateBarSkipBtn {
                background: transparent; color: #6b7280; padding: 6px 12px;
                border: 1px solid #d1d5db; border-radius: 5px;
            }
            #updateBarSkipBtn:hover { background: #f3f4f6; }
            #sidebarVersion { color: #6b7280; font-size: 11px; }
            """
        )


    def open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings = dialog.get_settings()
            self.settings.save()
            self.safety_guard = SafetyGuard(settings=self.settings)
            self.scanner = CleanupScanner(self.safety_guard, self.settings)
            QMessageBox.information(self, "设置已保存", "设置已保存，下次扫描将使用新配置。")

    def _maybe_check_for_updates(self) -> None:
        if not self.settings.auto_check_updates:
            return
        if self.settings.last_update_check:
            try:
                last = datetime.fromisoformat(self.settings.last_update_check)
                if (datetime.now(timezone.utc) - last).total_seconds() < 3600:
                    return
            except ValueError:
                pass
        self._run_update_check()

    def _run_update_check(self) -> None:
        self.update_check_thread = UpdateCheckThread(self.update_checker, self)
        self.update_check_thread.result.connect(self._on_update_check_result)
        self.update_check_thread.start()

    def _on_update_check_result(self, info) -> None:
        self.settings.last_update_check = datetime.now(timezone.utc).isoformat()
        self.settings.save()
        manual = self._manual_update_check
        self._manual_update_check = False

        if info is None:
            if manual:
                QMessageBox.information(self, "检查更新", "当前已是最新版本。")
            return
        if self.settings.skipped_version == info.version:
            if manual:
                QMessageBox.information(self, "检查更新", f"新版本 {info.version} 之前已被忽略，可在设置中重置。")
            return
        self.pending_update = info
        self.update_bar.show_update(info.version)
        if manual:
            self.show_update_dialog()

    def show_update_dialog(self) -> None:
        if self.pending_update is None:
            QMessageBox.information(self, "检查更新", "当前已是最新版本。")
            return
        dialog = UpdateDialog(self.pending_update, self)
        dialog.exec()

    def skip_current_update(self) -> None:
        if self.pending_update:
            self.settings.skipped_version = self.pending_update.version
            self.settings.save()
        self.update_bar.hide_update()
        self.pending_update = None

    def show_about_dialog(self) -> None:
        dialog = AboutDialog(self)
        dialog.check_update.connect(dialog.accept)
        dialog.check_update.connect(self._manual_check_update)
        dialog.exec()

    def _manual_check_update(self) -> None:
        self._manual_update_check = True
        self.update_checker._cached = None
        self.update_checker._cache_time = None
        self._run_update_check()

    def show_backup_restore_dialog(self) -> None:
        dialog = BackupRestoreDialog(self)
        dialog.exec()

    def export_results(self) -> None:
        if not self.items:
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "导出扫描结果",
            "",
            "JSON (*.json);;CSV (*.csv)",
        )
        if not path:
            return
        try:
            if selected_filter == "JSON (*.json)" or path.endswith(".json"):
                data = [
                    {
                        "item_id": item.item_id,
                        "title": item.title,
                        "path": item.path,
                        "kind": item.kind.label,
                        "risk": item.risk.label,
                        "category": item.category,
                        "vendor": item.vendor,
                        "size_bytes": item.size_bytes,
                        "selected": item.selected,
                        "description": item.description,
                    }
                    for item in self.items
                ]
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                with open(path, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["ID", "标题", "路径", "类型", "风险", "分类", "来源", "大小", "已选择", "说明"])
                    for item in self.items:
                        writer.writerow([
                            item.item_id,
                            item.title,
                            item.path,
                            item.kind.label,
                            item.risk.label,
                            item.category,
                            item.vendor,
                            item.size_bytes,
                            "是" if item.selected else "否",
                            item.description,
                        ])
            QMessageBox.information(self, "导出成功", f"已导出 {len(self.items)} 项到 {path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"导出失败：{e}")

    def _get_icon_path(self) -> Path | None:
        """获取图标文件路径，支持开发和打包后的环境"""
        if getattr(sys, 'frozen', False):
            base = Path(sys._MEIPASS)
        else:
            base = Path(__file__).parent.parent
        icon_path = base / 'icon.ico'
        return icon_path if icon_path.exists() else None


def item_summary(item: CleanupItem) -> str:
    return (
        f"{item.title}\n"
        f"{item.category} · {item.vendor} · {item.kind.label}\n"
        f"路径：{item.path}\n"
        f"识别原因：{item.description}"
    )


def deletion_guidance(item: CleanupItem) -> str:
    if item.risk == RiskLevel.LOW:
        return "可以清理\n后果：仅删缓存/日志，可重新生成"
    if item.risk == RiskLevel.MEDIUM:
        return "确认后清理\n后果：可能移除残留或安装包"
    if item.risk == RiskLevel.HIGH:
        return "不建议自动删除\n后果：可能影响启动、服务或安全组件"
    return "不能清理\n后果：程序会阻止，避免误删系统/个人文件"


def deletion_consequence(item: CleanupItem) -> str:
    if item.risk == RiskLevel.LOW:
        return "通常只会丢失临时缓存、日志或崩溃报告；软件需要时会重新生成。"
    if item.risk == RiskLevel.MEDIUM:
        return "可能清掉软件缓存、临时安装包或卸载残留；如果仍在使用该软件，建议取消勾选。"
    if item.risk == RiskLevel.HIGH:
        return "可能影响软件启动、更新、安全组件、服务或计划任务；本版本默认不执行删除。"
    return "该项位于受保护范围或不是可安全清理对象，程序会阻止执行。"


def item_detail_text(item: CleanupItem) -> str:
    return "\n".join(
        [
            f"项目：{item.title}",
            f"来源：{item.vendor}",
            f"类别：{item.category}",
            f"类型：{item.kind.label}",
            f"风险：{item.risk.label}",
            f"大小：{item.size_label}",
            f"路径/对象：{item.path}",
            "",
            f"为什么识别：{item.description}",
            f"处理建议：{item.safe_reason}",
            f"能不能删：{deletion_guidance(item).replace(chr(10), '；')}",
            f"删除后果：{deletion_consequence(item)}",
            f"当前状态：{item.status.label}",
            f"提示：{item.message or '低/中风险文件系统项目可勾选清理；高风险项目仅供核对。'}",
        ]
    )


def run_app() -> int:
    app = QApplication([])
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()
