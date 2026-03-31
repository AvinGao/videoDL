#!/usr/bin/env python3
"""启动 Video Downloader GUI."""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import QApplication
from qasync import QApplication as QAsyncApplication

from gui.main_window import MainWindow


def main():
    """Main entry point."""
    app = QAsyncApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    with app:
        sys.exit(app.exec_())


if __name__ == "__main__":
    main()