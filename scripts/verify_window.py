from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify that the main PyQt window can be created.")
    parser.add_argument("--duration-ms", type=int, default=1200)
    parser.add_argument("--no-show", action="store_true")
    args = parser.parse_args()

    repo_root = _repo_root()
    os.chdir(repo_root)
    sys.path.insert(0, str(repo_root))

    from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR, QTimer, qInstallMessageHandler
    from PyQt5.QtWidgets import QApplication

    from src.app.m1_app import MainWindow, _qt_message_handler

    qInstallMessageHandler(_qt_message_handler)
    app = QApplication.instance() or QApplication([str(repo_root / "src" / "app" / "m1_app.py")])
    window = MainWindow()

    if not args.no_show:
        window.show()
        app.processEvents()

    QTimer.singleShot(max(args.duration_ms, 0), app.quit)
    exit_code = app.exec_()

    size = window.size()
    print(f"python={sys.executable}")
    print(f"pyqt={PYQT_VERSION_STR} qt={QT_VERSION_STR}")
    print(f"window_title={window.windowTitle()}")
    print(f"window_size={size.width()}x{size.height()}")
    print(f"stack_pages={window.stack.count()} current_index={window.stack.currentIndex()}")
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
