"""Settings tab for configuring the application."""

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QSpinBox,
    QComboBox, QCheckBox, QFileDialog, QMessageBox
)

# 修改：使用绝对导入
from src.core.utils.config import ConfigManager


class SettingsTab(QWidget):
    """Settings tab for configuration."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = ConfigManager()
        
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        
        # Download settings
        download_group = QGroupBox("下载设置")
        download_layout = QVBoxLayout(download_group)
        
        # Default directory
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("默认保存目录:"))
        self.default_dir = QLineEdit()
        dir_layout.addWidget(self.default_dir)
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.clicked.connect(self.browse_directory)
        dir_layout.addWidget(self.browse_btn)
        download_layout.addLayout(dir_layout)
        
        # Threads
        thread_layout = QHBoxLayout()
        thread_layout.addWidget(QLabel("默认线程数:"))
        self.default_threads = QSpinBox()
        self.default_threads.setRange(1, 32)
        thread_layout.addWidget(self.default_threads)
        thread_layout.addStretch()
        download_layout.addLayout(thread_layout)
        
        # Format
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("默认输出格式:"))
        self.default_format = QComboBox()
        self.default_format.addItems(["mp4", "mkv", "original"])
        format_layout.addWidget(self.default_format)
        format_layout.addStretch()
        download_layout.addLayout(format_layout)
        
        # Quality
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("默认画质:"))
        self.default_quality = QComboBox()
        self.default_quality.addItems(["best", "1080p", "720p", "480p", "360p", "worst"])
        quality_layout.addWidget(self.default_quality)
        quality_layout.addStretch()
        download_layout.addLayout(quality_layout)
        
        # Max concurrent
        concurrent_layout = QHBoxLayout()
        concurrent_layout.addWidget(QLabel("最大并发下载数:"))
        self.max_concurrent = QSpinBox()
        self.max_concurrent.setRange(1, 10)
        concurrent_layout.addWidget(self.max_concurrent)
        concurrent_layout.addStretch()
        download_layout.addLayout(concurrent_layout)
        
        # Retry
        retry_layout = QHBoxLayout()
        retry_layout.addWidget(QLabel("重试次数:"))
        self.retry_count = QSpinBox()
        self.retry_count.setRange(0, 10)
        retry_layout.addWidget(self.retry_count)
        retry_layout.addStretch()
        download_layout.addLayout(retry_layout)
        
        layout.addWidget(download_group)
        
        # Headers settings
        headers_group = QGroupBox("请求头设置")
        headers_layout = QVBoxLayout(headers_group)
        
        self.auto_referer_cb = QCheckBox("自动设置 Referer")
        headers_layout.addWidget(self.auto_referer_cb)
        
        # User-Agent
        ua_layout = QHBoxLayout()
        ua_layout.addWidget(QLabel("默认 User-Agent:"))
        self.default_ua = QLineEdit()
        self.default_ua.setPlaceholderText("留空使用默认")
        ua_layout.addWidget(self.default_ua)
        headers_layout.addLayout(ua_layout)
        
        layout.addWidget(headers_group)
        
        # History settings
        history_group = QGroupBox("历史记录")
        history_layout = QVBoxLayout(history_group)
        
        max_records_layout = QHBoxLayout()
        max_records_layout.addWidget(QLabel("最大保存记录数:"))
        self.max_records = QSpinBox()
        self.max_records.setRange(10, 1000)
        max_records_layout.addWidget(self.max_records)
        max_records_layout.addStretch()
        history_layout.addLayout(max_records_layout)
        
        layout.addWidget(history_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.save_btn = QPushButton("保存设置")
        self.save_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(self.save_btn)
        
        self.reset_btn = QPushButton("重置为默认")
        self.reset_btn.clicked.connect(self.reset_settings)
        btn_layout.addWidget(self.reset_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
    
    def browse_directory(self):
        """Browse for default directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "选择默认保存目录", self.default_dir.text()
        )
        if directory:
            self.default_dir.setText(directory)
    
    def load_settings(self):
        """Load settings from config."""
        download = self.config.get_download_config()
        headers = self.config.get_headers_config()
        history = self.config.get_history_config()
        
        self.default_dir.setText(download.get('default_dir', str(Path.home() / "Downloads")))
        self.default_threads.setValue(download.get('default_threads', 8))
        self.default_format.setCurrentText(download.get('default_format', 'mp4'))
        self.default_quality.setCurrentText(download.get('quality', 'best'))
        self.max_concurrent.setValue(download.get('max_concurrent', 3))
        self.retry_count.setValue(download.get('retry_count', 3))
        
        self.auto_referer_cb.setChecked(headers.get('auto_referer', True))
        self.default_ua.setText(headers.get('default_user_agent', ''))
        
        self.max_records.setValue(history.get('max_records', 100))
    
    def save_settings(self):
        """Save settings to config."""
        self.config.set('download.default_dir', self.default_dir.text())
        self.config.set('download.default_threads', self.default_threads.value())
        self.config.set('download.default_format', self.default_format.currentText())
        self.config.set('download.quality', self.default_quality.currentText())
        self.config.set('download.max_concurrent', self.max_concurrent.value())
        self.config.set('download.retry_count', self.retry_count.value())
        
        self.config.set('headers.auto_referer', self.auto_referer_cb.isChecked())
        if self.default_ua.text():
            self.config.set('headers.default_user_agent', self.default_ua.text())
        
        self.config.set('history.max_records', self.max_records.value())
        
        QMessageBox.information(self, "成功", "设置已保存")
        
        # Reload settings in download tab
        if self.parent_window:
            self.parent_window.load_settings()
    
    def reset_settings(self):
        """Reset settings to defaults."""
        reply = QMessageBox.question(
            self, "确认", "确定要重置所有设置为默认值吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.reset_to_defaults()
            self.load_settings()
            QMessageBox.information(self, "成功", "设置已重置")
            
            if self.parent_window:
                self.parent_window.load_settings()