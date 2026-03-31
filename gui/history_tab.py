"""History tab for displaying download history."""

from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLineEdit, QLabel,
    QHeaderView, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal

# 修改：使用绝对导入
from src.core.utils.config import HistoryManager, ConfigManager


class HistoryTab(QWidget):
    """History tab for download records."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = ConfigManager()
        self.history = HistoryManager(self.config)
        
        self.setup_ui()
        self.load_history()
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        
        # Search bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入 URL 或文件名搜索")
        self.search_input.textChanged.connect(self.search_history)
        search_layout.addWidget(self.search_input)
        
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.load_history)
        search_layout.addWidget(self.refresh_btn)
        
        self.clear_btn = QPushButton("清空历史")
        self.clear_btn.clicked.connect(self.clear_history)
        search_layout.addWidget(self.clear_btn)
        
        layout.addLayout(search_layout)
        
        # History table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "时间", "URL", "状态", "大小", "耗时", "操作"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.setAlternatingRowColors(True)
        layout.addWidget(self.history_table)
    
    def load_history(self):
        """Load history from storage."""
        records = self.history.get_all(100)
        self.display_records(records)
    
    def search_history(self):
        """Search history."""
        query = self.search_input.text().strip()
        if query:
            records = self.history.search(query)
        else:
            records = self.history.get_all(100)
        self.display_records(records)
    
    def display_records(self, records):
        """Display records in table."""
        self.history_table.setRowCount(0)
        
        for record in records:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            
            # Time
            timestamp = record.get('timestamp', '')[:19]
            self.history_table.setItem(row, 0, QTableWidgetItem(timestamp))
            
            # URL
            url = record.get('url', '')[:80]
            self.history_table.setItem(row, 1, QTableWidgetItem(url))
            
            # Status
            success = record.get('success', False)
            status = "✓ 成功" if success else "✗ 失败"
            status_color = Qt.GlobalColor.green if success else Qt.GlobalColor.red
            item = QTableWidgetItem(status)
            item.setForeground(status_color)
            self.history_table.setItem(row, 2, item)
            
            # Size
            size_bytes = record.get('file_size_bytes', 0)
            if size_bytes < 1024 * 1024:
                size_text = f"{size_bytes / 1024:.1f} KB"
            else:
                size_text = f"{size_bytes / (1024 * 1024):.1f} MB"
            self.history_table.setItem(row, 3, QTableWidgetItem(size_text))
            
            # Duration
            duration = record.get('duration_seconds', 0)
            if duration:
                minutes, seconds = divmod(int(duration), 60)
                hours, minutes = divmod(minutes, 60)
                if hours > 0:
                    duration_text = f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    duration_text = f"{minutes}m {seconds}s"
                else:
                    duration_text = f"{seconds}s"
            else:
                duration_text = "--"
            self.history_table.setItem(row, 4, QTableWidgetItem(duration_text))
            
            # Open file button
            file_path = record.get('file_path')
            if file_path and Path(file_path).exists():
                open_btn = QPushButton("打开文件")
                open_btn.clicked.connect(lambda checked, p=file_path: self.open_file(p))
                self.history_table.setCellWidget(row, 5, open_btn)
            else:
                self.history_table.setItem(row, 5, QTableWidgetItem("--"))
    
    def open_file(self, file_path: str):
        """Open file with default application."""
        import os
        import subprocess
        
        path = Path(file_path)
        if path.exists():
            if os.name == 'nt':  # Windows
                os.startfile(str(path))
            elif os.name == 'posix':  # macOS/Linux
                subprocess.run(['open', str(path)], check=False)
    
    def add_record(self, record: dict):
        """Add a record to history."""
        self.history.add(record)
        self.load_history()
    
    def clear_history(self):
        """Clear all history."""
        reply = QMessageBox.question(
            self, "确认", "确定要清空所有下载历史吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history.clear()
            self.load_history()