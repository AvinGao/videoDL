#!/usr/bin/env python3
"""Video Downloader GUI - Main entry point."""

import sys
import asyncio

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