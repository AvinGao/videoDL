"""Main window for Video Downloader GUI."""

import sys
import asyncio
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QStatusBar, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QIcon

from qasync import QApplication as QAsyncApplication, asyncSlot

from .download_tab import DownloadTab
from .history_tab import HistoryTab
from .settings_tab import SettingsTab
from src.core.scheduler import DownloadScheduler
from src.core.utils.config import ConfigManager


class DownloadWorker(QThread):
    """Worker thread for downloads."""
    
    progress_signal = pyqtSignal(str, float, int, int)  # task_id, percent, current, total
    speed_signal = pyqtSignal(str, float)  # task_id, speed
    finished_signal = pyqtSignal(str, dict)  # task_id, result
    error_signal = pyqtSignal(str, str)  # task_id, error
    
    def __init__(self, scheduler: DownloadScheduler):
        super().__init__()
        self.scheduler = scheduler
        self._tasks = {}
        self._running = True
        
        # Connect scheduler signals
        scheduler.set_progress_callback(self._on_progress)
        scheduler.set_speed_callback(self._on_speed)
    
    def _on_progress(self, task_id: str, percent: float, current: int, total: int):
        """Handle progress update."""
        self.progress_signal.emit(task_id, percent, current, total)
    
    def _on_speed(self, task_id: str, speed: float):
        """Handle speed update."""
        self.speed_signal.emit(task_id, speed)
    
    def add_task(self, task_id: str, url: str, options: dict, headers: dict):
        """Add a download task."""
        self._tasks[task_id] = {
            'url': url,
            'options': options,
            'headers': headers
        }
    
    def run(self):
        """Run the download tasks."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            for task_id, task in self._tasks.items():
                if not self._running:
                    break
                
                result = loop.run_until_complete(
                    self.scheduler.download(
                        task['url'],
                        task['options'],
                        task['headers'],
                        task_id
                    )
                )
                
                self.finished_signal.emit(task_id, {
                    'success': result.success,
                    'file_path': str(result.file_path) if result.file_path else None,
                    'file_size_bytes': result.file_size_bytes,
                    'duration_seconds': result.duration_seconds,
                    'error': result.error_message
                })
        finally:
            loop.close()
    
    def stop(self):
        """Stop all downloads."""
        self._running = False
        self.scheduler.cancel_all()


class MainWindow(QMainWindow):
    """Main window for Video Downloader."""
    
    def __init__(self):
        super().__init__()
        
        # Initialize components
        self.config = ConfigManager()
        self.scheduler = DownloadScheduler()
        self.worker: Optional[DownloadWorker] = None
        
        self.setup_ui()
        self.setup_menu()
        self.setup_statusbar()
        self.apply_theme()
        
        self.setWindowTitle("Video Downloader")
        self.setMinimumSize(900, 700)
        self.resize(1000, 750)
    
    def setup_ui(self):
        """Setup the main UI."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.download_tab = DownloadTab(self)
        self.history_tab = HistoryTab(self)
        self.settings_tab = SettingsTab(self)
        
        # Add tabs
        self.tab_widget.addTab(self.download_tab, "📥 下载")
        self.tab_widget.addTab(self.history_tab, "📋 历史记录")
        self.tab_widget.addTab(self.settings_tab, "⚙️ 设置")
        
        layout.addWidget(self.tab_widget)
        
        # Connect signals
        self.download_tab.download_requested.connect(self.start_download)
        self.download_tab.cancel_requested.connect(self.cancel_download)
        
        # Load settings
        self.load_settings()
    
    def setup_menu(self):
        """Setup menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("文件")
        
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu("帮助")
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_statusbar(self):
        """Setup status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
    
    def apply_theme(self):
        """Apply dark theme."""
        dark_style = """
        QMainWindow {
            background-color: #2b2b2b;
        }
        QTabWidget::pane {
            border: 1px solid #3c3c3c;
            background-color: #2b2b2b;
        }
        QTabBar::tab {
            background-color: #3c3c3c;
            color: #ffffff;
            padding: 8px 16px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background-color: #4a4a4a;
        }
        QPushButton {
            background-color: #4a4a4a;
            color: #ffffff;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #5a5a5a;
        }
        QPushButton:pressed {
            background-color: #3a3a3a;
        }
        QLineEdit, QTextEdit, QComboBox {
            background-color: #3c3c3c;
            color: #ffffff;
            border: 1px solid #5a5a5a;
            border-radius: 4px;
            padding: 4px;
        }
        QLabel {
            color: #ffffff;
        }
        QGroupBox {
            color: #ffffff;
            border: 1px solid #5a5a5a;
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QSpinBox, QComboBox {
            background-color: #3c3c3c;
            color: #ffffff;
            border: 1px solid #5a5a5a;
            border-radius: 4px;
        }
        QTableWidget {
            background-color: #2b2b2b;
            color: #ffffff;
            gridline-color: #3c3c3c;
        }
        QHeaderView::section {
            background-color: #3c3c3c;
            color: #ffffff;
            padding: 4px;
        }
        QScrollBar:vertical {
            background-color: #2b2b2b;
            width: 12px;
        }
        QScrollBar::handle:vertical {
            background-color: #5a5a5a;
            border-radius: 6px;
        }
        """
        self.setStyleSheet(dark_style)
    
    def load_settings(self):
        """Load settings from config."""
        download_config = self.config.get_download_config()
        self.download_tab.load_settings(download_config)
        self.settings_tab.load_settings(self.config)
    
    @asyncSlot()
    async def start_download(self, url: str, options: dict, headers: dict):
        """Start a download task."""
        self.status_bar.showMessage(f"开始下载: {url}")
        
        if self.worker is None or not self.worker.isRunning():
            self.worker = DownloadWorker(self.scheduler)
            self.worker.progress_signal.connect(self.download_tab.update_progress)
            self.worker.speed_signal.connect(self.download_tab.update_speed)
            self.worker.finished_signal.connect(self.on_download_finished)
            self.worker.error_signal.connect(self.on_download_error)
            self.worker.start()
        
        # Add task to worker
        import uuid
        task_id = str(uuid.uuid4())
        self.worker.add_task(task_id, url, options, headers)
        
        # Add to download tab
        self.download_tab.add_task(task_id, url)
    
    def on_download_finished(self, task_id: str, result: dict):
        """Handle download finished."""
        self.status_bar.showMessage("下载完成" if result['success'] else f"下载失败: {result['error']}")
        
        # Add to history
        self.history_tab.add_record(result)
        
        # Update UI
        self.download_tab.task_finished(task_id, result['success'])
    
    def on_download_error(self, task_id: str, error: str):
        """Handle download error."""
        self.status_bar.showMessage(f"错误: {error}")
        self.download_tab.task_finished(task_id, False, error)
    
    def cancel_download(self, task_id: str):
        """Cancel a download."""
        self.scheduler.cancel_task(task_id)
        self.status_bar.showMessage(f"已取消下载: {task_id}")
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "关于 Video Downloader",
            "Video Downloader v1.0.0\n\n"
            "一个强大的视频下载工具\n\n"
            "支持格式:\n"
            "• M3U8/HLS 流媒体\n"
            "• DASH/MPD 流媒体\n"
            "• MP4, MKV, AVI 等直链\n"
            "• YouTube, Bilibili 等网站\n"
            "• 磁力链接和种子文件\n\n"
            "开源协议: MIT"
        )
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)
        event.accept()