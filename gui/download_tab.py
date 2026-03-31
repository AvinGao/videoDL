"""Download tab for the main window."""

import os
from pathlib import Path
from typing import Optional, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QSpinBox,
    QComboBox, QCheckBox, QTextEdit, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QMessageBox, QSplitter
)
from PyQt6.QtCore import pyqtSignal, Qt

from .widgets.url_input import UrlInputWidget


class DownloadTab(QWidget):
    """Download tab for managing downloads."""
    
    download_requested = pyqtSignal(str, dict, dict)  # url, options, headers
    cancel_requested = pyqtSignal(str)  # task_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.tasks: Dict[str, dict] = {}
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        
        # Splitter for input area and task list
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Input area
        input_widget = self.create_input_area()
        splitter.addWidget(input_widget)
        
        # Task list
        task_widget = self.create_task_area()
        splitter.addWidget(task_widget)
        
        splitter.setSizes([350, 500])
        layout.addWidget(splitter)
    
    def create_input_area(self) -> QWidget:
        """Create the URL input area."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # URL input group
        url_group = QGroupBox("视频链接")
        url_layout = QVBoxLayout(url_group)
        
        self.url_input = UrlInputWidget()
        url_layout.addWidget(self.url_input)
        
        # Quick test button
        test_layout = QHBoxLayout()
        test_layout.addStretch()
        self.test_btn = QPushButton("测试链接")
        self.test_btn.clicked.connect(self.test_url)
        test_layout.addWidget(self.test_btn)
        url_layout.addLayout(test_layout)
        
        layout.addWidget(url_group)
        
        # Options group
        options_group = QGroupBox("下载选项")
        options_layout = QHBoxLayout(options_group)
        
        # Left column
        left_layout = QVBoxLayout()
        
        # Save directory
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("保存目录:"))
        self.save_dir = QLineEdit()
        self.save_dir.setText(str(Path.home() / "Downloads"))
        dir_layout.addWidget(self.save_dir)
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.clicked.connect(self.browse_directory)
        dir_layout.addWidget(self.browse_btn)
        left_layout.addLayout(dir_layout)
        
        # Filename
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("文件名:"))
        self.filename = QLineEdit()
        self.filename.setPlaceholderText("留空自动识别")
        name_layout.addWidget(self.filename)
        left_layout.addLayout(name_layout)
        
        # Thread count
        thread_layout = QHBoxLayout()
        thread_layout.addWidget(QLabel("线程数:"))
        self.thread_count = QSpinBox()
        self.thread_count.setRange(1, 32)
        self.thread_count.setValue(8)
        thread_layout.addWidget(self.thread_count)
        thread_layout.addStretch()
        left_layout.addLayout(thread_layout)
        
        options_layout.addLayout(left_layout)
        
        # Right column
        right_layout = QVBoxLayout()
        
        # Format
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("输出格式:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mkv", "original"])
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        right_layout.addLayout(format_layout)
        
        # Quality
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("画质:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["best", "1080p", "720p", "480p", "360p", "worst"])
        quality_layout.addWidget(self.quality_combo)
        quality_layout.addStretch()
        right_layout.addLayout(quality_layout)
        
        # Options
        self.overwrite_cb = QCheckBox("覆盖已存在文件")
        self.auto_referer_cb = QCheckBox("自动设置 Referer")
        self.auto_referer_cb.setChecked(True)
        right_layout.addWidget(self.overwrite_cb)
        right_layout.addWidget(self.auto_referer_cb)
        
        options_layout.addLayout(right_layout)
        
        layout.addWidget(options_group)
        
        # Headers group
        headers_group = QGroupBox("HTTP 请求头 (可选)")
        headers_layout = QVBoxLayout(headers_group)
        
        # Headers input
        self.headers_input = QTextEdit()
        self.headers_input.setPlaceholderText(
            "格式: 每行一个请求头\n\n"
            "示例:\n"
            "Referer: https://example.com\n"
            "User-Agent: Mozilla/5.0\n"
            "Cookie: session=abc123"
        )
        self.headers_input.setMaximumHeight(100)
        headers_layout.addWidget(self.headers_input)
        
        # Import cookie button
        cookie_layout = QHBoxLayout()
        cookie_layout.addStretch()
        self.import_cookie_btn = QPushButton("从浏览器导入 Cookie")
        self.import_cookie_btn.clicked.connect(self.import_cookie)
        cookie_layout.addWidget(self.import_cookie_btn)
        headers_layout.addLayout(cookie_layout)
        
        layout.addWidget(headers_group)
        
        # Download button
        self.download_btn = QPushButton("开始下载")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #5cbf60;
            }
        """)
        self.download_btn.clicked.connect(self.start_download)
        layout.addWidget(self.download_btn)
        
        return widget
    
    def create_task_area(self) -> QWidget:
        """Create the task list area."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Title
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("下载任务"))
        title_layout.addStretch()
        self.clear_btn = QPushButton("清除已完成")
        self.clear_btn.clicked.connect(self.clear_completed)
        title_layout.addWidget(self.clear_btn)
        layout.addLayout(title_layout)
        
        # Task table
        self.task_table = QTableWidget()
        self.task_table.setColumnCount(6)
        self.task_table.setHorizontalHeaderLabels([
            "任务ID", "URL", "进度", "速度", "状态", "操作"
        ])
        self.task_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.task_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.task_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.task_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.task_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.task_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.task_table.setAlternatingRowColors(True)
        layout.addWidget(self.task_table)
        
        return widget
    
    def browse_directory(self):
        """Browse for save directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "选择保存目录", self.save_dir.text()
        )
        if directory:
            self.save_dir.setText(directory)
    
    def import_cookie(self):
        """Import cookies from browser."""
        from PyQt6.QtWidgets import QInputDialog
        
        browsers = ["chrome", "firefox", "edge"]
        browser, ok = QInputDialog.getItem(
            self, "导入 Cookie", "选择浏览器:", browsers, 0, False
        )
        
        if ok and browser:
            try:
                from src.core.headers.cookie_import import CookieImporter
                cookie = CookieImporter.import_from_browser(browser)
                if cookie:
                    # Add to headers
                    current = self.headers_input.toPlainText()
                    if "Cookie:" in current:
                        QMessageBox.warning(self, "提示", "已存在 Cookie 头，请手动处理")
                    else:
                        new_headers = current + f"\nCookie: {cookie}" if current else f"Cookie: {cookie}"
                        self.headers_input.setPlainText(new_headers.strip())
                        QMessageBox.information(self, "成功", f"已从 {browser} 导入 Cookie")
                else:
                    QMessageBox.warning(self, "失败", f"无法从 {browser} 导入 Cookie")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入失败: {e}")
    
    def test_url(self):
        """Test the URL."""
        url = self.url_input.get_url()
        if not url:
            QMessageBox.warning(self, "提示", "请输入视频链接")
            return
        
        self.status_message("正在测试链接...")
        
        # TODO: Implement async test
        QMessageBox.information(self, "测试", f"链接测试功能开发中\n\nURL: {url}")
    
    def start_download(self):
        """Start the download."""
        url = self.url_input.get_url()
        if not url:
            QMessageBox.warning(self, "提示", "请输入视频链接")
            return
        
        # Collect options
        options = {
            'save_dir': self.save_dir.text(),
            'save_name': self.filename.text() if self.filename.text() else None,
            'thread_count': self.thread_count.value(),
            'output_format': self.format_combo.currentText(),
            'quality': self.quality_combo.currentText(),
            'overwrite': self.overwrite_cb.isChecked(),
            'auto_referer': self.auto_referer_cb.isChecked()
        }
        
        # Parse headers
        headers = {}
        headers_text = self.headers_input.toPlainText().strip()
        if headers_text:
            for line in headers_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
        
        self.download_requested.emit(url, options, headers)
    
    def add_task(self, task_id: str, url: str):
        """Add a task to the table."""
        row = self.task_table.rowCount()
        self.task_table.insertRow(row)
        
        # Task ID
        self.task_table.setItem(row, 0, QTableWidgetItem(task_id[:8]))
        
        # URL
        self.task_table.setItem(row, 1, QTableWidgetItem(url[:50]))
        
        # Progress bar
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(0)
        self.task_table.setCellWidget(row, 2, progress)
        
        # Speed
        self.task_table.setItem(row, 3, QTableWidgetItem("--"))
        
        # Status
        self.task_table.setItem(row, 4, QTableWidgetItem("下载中"))
        
        # Cancel button
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(lambda: self.cancel_requested.emit(task_id))
        self.task_table.setCellWidget(row, 5, cancel_btn)
        
        # Store task info
        self.tasks[task_id] = {
            'row': row,
            'url': url
        }
    
    def update_progress(self, task_id: str, percent: float, current: int, total: int):
        """Update task progress."""
        if task_id not in self.tasks:
            return
        
        row = self.tasks[task_id]['row']
        progress = self.task_table.cellWidget(row, 2)
        if progress:
            progress.setValue(int(percent))
        
        # Update status text
        self.task_table.setItem(row, 4, QTableWidgetItem(f"下载中 {percent:.1f}%"))
    
    def update_speed(self, task_id: str, speed: float):
        """Update download speed."""
        if task_id not in self.tasks:
            return
        
        row = self.tasks[task_id]['row']
        if speed < 1024:
            speed_text = f"{speed:.0f} B/s"
        elif speed < 1024 * 1024:
            speed_text = f"{speed / 1024:.1f} KB/s"
        else:
            speed_text = f"{speed / (1024 * 1024):.1f} MB/s"
        
        self.task_table.setItem(row, 3, QTableWidgetItem(speed_text))
    
    def task_finished(self, task_id: str, success: bool, error: str = None):
        """Mark task as finished."""
        if task_id not in self.tasks:
            return
        
        row = self.tasks[task_id]['row']
        status = "完成" if success else f"失败: {error[:30] if error else ''}"
        self.task_table.setItem(row, 4, QTableWidgetItem(status))
        
        # Disable cancel button
        cancel_btn = self.task_table.cellWidget(row, 5)
        if cancel_btn:
            cancel_btn.setEnabled(False)
    
    def clear_completed(self):
        """Clear completed tasks from table."""
        rows_to_remove = []
        for task_id, info in self.tasks.items():
            row = info['row']
            status_item = self.task_table.item(row, 4)
            if status_item and ("完成" in status_item.text() or "失败" in status_item.text()):
                rows_to_remove.append(row)
        
        for row in sorted(rows_to_remove, reverse=True):
            self.task_table.removeRow(row)
        
        # Rebuild tasks dict
        new_tasks = {}
        for task_id, info in self.tasks.items():
            if info['row'] not in rows_to_remove:
                new_row = self.task_table.rowCount()
                new_tasks[task_id] = {'row': new_row, 'url': info['url']}
        self.tasks = new_tasks
    
    def load_settings(self, config: dict):
        """Load settings from config."""
        self.save_dir.setText(config.get('default_dir', str(Path.home() / "Downloads")))
        self.thread_count.setValue(config.get('default_threads', 8))
        self.format_combo.setCurrentText(config.get('default_format', 'mp4'))
    
    def status_message(self, message: str):
        """Show status message."""
        if self.parent_window:
            self.parent_window.status_bar.showMessage(message)