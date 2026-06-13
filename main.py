from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from cleaner_app.ui import MainWindow
from cleaner_app.windows_utils import is_admin, is_windows, relaunch_as_admin


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    if is_windows() and not is_admin():
        QMessageBox.information(
            None,
            "需要管理员权限",
            "为了检查启动项、服务、计划任务和部分残留目录，本软件需要以管理员权限运行。\n\n"
            "接下来会尝试重新以管理员身份启动。",
        )
        if relaunch_as_admin():
            return 0
        QMessageBox.critical(None, "启动失败", "未获得管理员权限，程序已退出。")
        return 1

    window = MainWindow()
    window.show()
    window.center_on_screen()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
