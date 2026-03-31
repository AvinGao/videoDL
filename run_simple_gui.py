#!/usr/bin/env python3
"""Video Downloader GUI - 完整版"""

import sys
import os
import asyncio
import uuid
import time
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton, QSpinBox,
    QComboBox, QCheckBox, QTextEdit, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QMessageBox,
    QStatusBar, QGroupBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor

# 导入下载引擎
from src.core.scheduler import DownloadScheduler
from src.core.models.download import DownloadOptions
from src.core.models.headers import RequestHeaders
from src.core.utils.link_detector import LinkDetector
from src.core.utils.config import ConfigManager, HistoryManager


def get_base_path():
    """获取程序基础路径（支持 PyInstaller）"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))


class DownloadWorker(QThread):
    """Worker thread for downloads."""
    
    progress_signal = pyqtSignal(str, float, int, int)
    finished_signal = pyqtSignal(str, bool, str, str)
    log_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.scheduler = DownloadScheduler()
        self.tasks: Dict[str, dict] = {}
        self._running = True
        self._current_task = None
        self._loop = None
        
        print("[Worker] 初始化，设置回调")
        self.scheduler.set_progress_callback(self._on_progress)
    
    def _on_progress(self, task_id: str, percent: float, current: int, total: int):
        """Handle progress update."""
        print(f"[Worker] 进度回调: task_id={task_id}, percent={percent:.1f}%")
        self.progress_signal.emit(task_id, percent, current, total)
    
    def _options_to_model(self, options_dict: dict) -> DownloadOptions:
        """Convert dict to DownloadOptions."""
        return DownloadOptions(
            save_dir=Path(options_dict.get('save_dir', './downloads')),
            save_name=options_dict.get('save_name'),
            thread_count=options_dict.get('thread_count', 8),
            retry_count=options_dict.get('retry_count', 3),
            output_format=options_dict.get('output_format', 'mp4'),
            quality=options_dict.get('quality', 'best'),
            overwrite=options_dict.get('overwrite', False),
            auto_referer=options_dict.get('auto_referer', True)
        )
    
    def _headers_to_model(self, headers_dict: dict) -> RequestHeaders:
        """Convert dict to RequestHeaders."""
        headers = RequestHeaders()
        for key, value in headers_dict.items():
            key_lower = key.lower()
            if key_lower == 'user-agent':
                headers.user_agent = value
            elif key_lower == 'referer':
                headers.referer = value
            elif key_lower == 'cookie':
                headers.cookie = value
            elif key_lower == 'origin':
                headers.origin = value
            elif key_lower == 'authorization':
                headers.authorization = value
            else:
                headers.custom[key] = value
        return headers
    
    def add_task(self, task_id: str, url: str, options: dict, headers: dict):
        """Add a download task."""
        self.tasks[task_id] = {
            'url': url,
            'options': options,
            'headers': headers
        }
        print(f"[Worker] 添加任务: {task_id} - {url[:50]}...")
    
    def run(self):
        """Run downloads in thread."""
        print(f"[Worker] 线程启动，任务数: {len(self.tasks)}")
        
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            tasks_to_process = list(self.tasks.items())
            
            for task_id, task in tasks_to_process:
                if not self._running:
                    break
                
                if task_id not in self.tasks:
                    print(f"[Worker] 任务 {task_id} 已被取消，跳过")
                    continue
                
                self._current_task = task_id
                print(f"[Worker] 开始下载: {task_id} - {task['url'][:50]}...")
                self.log_signal.emit(f"开始下载: {task['url']}")
                
                try:
                    result = self._loop.run_until_complete(
                        self.scheduler.download(
                            task['url'],
                            self._options_to_model(task['options']),
                            self._headers_to_model(task['headers']),
                            task_id
                        )
                    )
                    
                    print(f"[Worker] 下载完成: {task_id} - success={result.success}")
                    self.finished_signal.emit(
                        task_id,
                        result.success,
                        result.error_message or '',
                        str(result.file_path) if result.file_path else ''
                    )
                    
                    if task_id in self.tasks:
                        del self.tasks[task_id]
                    
                except Exception as e:
                    print(f"[Worker] 下载异常: {task_id} - {e}")
                    self.finished_signal.emit(task_id, False, str(e), '')
                    if task_id in self.tasks:
                        del self.tasks[task_id]
            
        except Exception as e:
            print(f"[Worker] 错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._loop.close()
            print("[Worker] 线程结束")
    
    def stop(self):
        """Stop downloads."""
        self._running = False
        if self.scheduler:
            self.scheduler.cancel_all()
        self.tasks.clear()
        print("[Worker] 停止请求，任务队列已清空")


class MainWindow(QMainWindow):
    """Main window."""
    
    def __init__(self):
        super().__init__()
        
        # 设置窗口图标
        self.setWindowIcon(self.get_window_icon())
        
        self.config = ConfigManager()
        self.history = HistoryManager(self.config)
        self.worker = DownloadWorker()
        self.current_task_id = None
        
        # 连接信号
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.on_download_finished)
        self.worker.log_signal.connect(self.add_log)
        
        print("[GUI] Worker 信号已连接")
        
        self.setup_ui()
        self.load_settings()
        
        self.setWindowTitle("Video Downloader")
        self.setMinimumSize(900, 700)
        self.resize(1000, 750)
    
    def get_window_icon(self):
        """获取窗口图标"""
        base_path = get_base_path()
        
        icon_paths = [
            os.path.join(base_path, "resources", "icon.ico"),
            os.path.join(base_path, "resources", "icon.png"),
            os.path.join(base_path, "icon.ico"),
        ]
        
        for path in icon_paths:
            if os.path.exists(path):
                print(f"[GUI] 加载图标: {path}")
                return QIcon(path)
        
        # 创建简单的图标
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(76, 175, 80))
        return QIcon(pixmap)
    
    def setup_ui(self):
        """Setup UI."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Tab widget
        tabs = QTabWidget()
        
        # Download tab
        download_tab = QWidget()
        self.setup_download_tab(download_tab)
        tabs.addTab(download_tab, "📥 下载")
        
        # History tab
        history_tab = QWidget()
        self.setup_history_tab(history_tab)
        tabs.addTab(history_tab, "📋 历史记录")
        
        # Log tab
        log_tab = QWidget()
        self.setup_log_tab(log_tab)
        tabs.addTab(log_tab, "📝 日志")
        
        layout.addWidget(tabs)
        
        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪")
    
    def setup_download_tab(self, widget):
        """Setup download tab."""
        layout = QVBoxLayout(widget)
        
        # URL input
        url_group = QGroupBox("视频链接")
        url_layout = QVBoxLayout(url_group)
        
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText(
            "输入视频链接 (每行一个，支持批量下载)\n\n"
            "支持格式:\n"
            "• M3U8/HLS: https://example.com/video.m3u8\n"
            "• DASH/MPD: https://example.com/manifest.mpd\n"
            "• 直链: https://example.com/video.mp4\n"
            "• 网站: https://youtube.com/watch?v=xxx\n"
            "• 磁力链接: magnet:?xt=urn:btih:..."
        )
        self.url_input.setMaximumHeight(120)
        url_layout.addWidget(self.url_input)
        
        # URL buttons
        url_btn_layout = QHBoxLayout()
        paste_btn = QPushButton("粘贴")
        paste_btn.clicked.connect(self.paste_url)
        url_btn_layout.addWidget(paste_btn)
        
        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(lambda: self.url_input.clear())
        url_btn_layout.addWidget(clear_btn)
        
        test_btn = QPushButton("测试链接")
        test_btn.clicked.connect(self.test_url)
        url_btn_layout.addWidget(test_btn)
        
        url_btn_layout.addStretch()
        url_layout.addLayout(url_btn_layout)
        
        layout.addWidget(url_group)
        
        # Options
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
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self.browse_dir)
        dir_layout.addWidget(browse_btn)
        left_layout.addLayout(dir_layout)
        
        # Filename
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("文件名:"))
        self.filename = QLineEdit()
        self.filename.setPlaceholderText("留空自动识别")
        name_layout.addWidget(self.filename)
        left_layout.addLayout(name_layout)
        
        # Right column
        right_layout = QVBoxLayout()
        
        # Threads
        thread_layout = QHBoxLayout()
        thread_layout.addWidget(QLabel("线程数:"))
        self.thread_count = QSpinBox()
        self.thread_count.setRange(1, 32)
        self.thread_count.setValue(8)
        thread_layout.addWidget(self.thread_count)
        thread_layout.addStretch()
        right_layout.addLayout(thread_layout)
        
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
        
        options_layout.addLayout(left_layout)
        options_layout.addLayout(right_layout)
        
        layout.addWidget(options_group)
        
        # Checkboxes
        checkbox_layout = QHBoxLayout()
        self.overwrite_cb = QCheckBox("覆盖已存在文件")
        self.auto_referer_cb = QCheckBox("自动设置 Referer")
        self.auto_referer_cb.setChecked(True)
        checkbox_layout.addWidget(self.overwrite_cb)
        checkbox_layout.addWidget(self.auto_referer_cb)
        checkbox_layout.addStretch()
        layout.addLayout(checkbox_layout)
        
        # Headers
        headers_group = QGroupBox("HTTP 请求头 (可选)")
        headers_layout = QVBoxLayout(headers_group)
        self.headers_input = QTextEdit()
        self.headers_input.setPlaceholderText(
            "每行一个请求头\n\n"
            "示例:\n"
            "Referer: https://example.com\n"
            "User-Agent: Mozilla/5.0\n"
            "Cookie: session=abc123"
        )
        self.headers_input.setMaximumHeight(100)
        headers_layout.addWidget(self.headers_input)
        
        # Import cookie button
        import_btn = QPushButton("从浏览器导入 Cookie")
        import_btn.clicked.connect(self.import_cookie)
        headers_layout.addWidget(import_btn)
        
        layout.addWidget(headers_group)
        
        # Progress section
        progress_group = QGroupBox("下载进度")
        progress_layout = QVBoxLayout(progress_group)
        
        self.current_file_label = QLabel("等待下载...")
        progress_layout.addWidget(self.current_file_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_layout.addWidget(self.progress_bar)
        
        self.speed_label = QLabel("速度: --")
        progress_layout.addWidget(self.speed_label)
        
        layout.addWidget(progress_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.download_btn = QPushButton("开始下载")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #5cbf60;
            }
        """)
        self.download_btn.clicked.connect(self.start_download)
        btn_layout.addWidget(self.download_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #ff5555;
            }
        """)
        self.cancel_btn.clicked.connect(self.cancel_download)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
    
    def setup_history_tab(self, widget):
        """Setup history tab."""
        layout = QVBoxLayout(widget)
        
        # Search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入关键词搜索")
        self.search_input.textChanged.connect(self.search_history)
        search_layout.addWidget(self.search_input)
        
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.load_history)
        search_layout.addWidget(refresh_btn)
        
        clear_history_btn = QPushButton("清空历史")
        clear_history_btn.clicked.connect(self.clear_history)
        search_layout.addWidget(clear_history_btn)
        
        layout.addLayout(search_layout)
        
        # History table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "时间", "URL", "状态", "大小", "耗时", "文件"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.setAlternatingRowColors(False)
        self.history_table.setStyleSheet("""
            QTableWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                gridline-color: #3c3c3c;
            }
            QTableWidget::item {
                background-color: #2b2b2b;
            }
        """)
        layout.addWidget(self.history_table)
        
        self.load_history()
    
    def setup_log_tab(self, widget):
        """Setup log tab."""
        layout = QVBoxLayout(widget)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self.log_text)
        
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        layout.addWidget(clear_log_btn)
    
    def paste_url(self):
        """Paste URL from clipboard."""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.url_input.setText(text)
            self.add_log(f"粘贴 URL: {text[:50]}...")
    
    def browse_dir(self):
        """Browse for save directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "选择保存目录", self.save_dir.text()
        )
        if directory:
            self.save_dir.setText(directory)
            self.add_log(f"保存目录: {directory}")
    
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
                    current = self.headers_input.toPlainText()
                    new_headers = current + f"\nCookie: {cookie}" if current else f"Cookie: {cookie}"
                    self.headers_input.setPlainText(new_headers.strip())
                    self.add_log(f"已从 {browser} 导入 Cookie")
                    QMessageBox.information(self, "成功", f"已从 {browser} 导入 Cookie")
                else:
                    QMessageBox.warning(self, "失败", f"无法从 {browser} 导入 Cookie，请确保浏览器已关闭")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入失败: {e}")
    
    def test_url(self):
        """Test the URL."""
        url = self.url_input.toPlainText().strip().split('\n')[0]
        if not url:
            QMessageBox.warning(self, "提示", "请输入视频链接")
            return
        
        self.add_log(f"测试链接: {url}")
        
        try:
            category = LinkDetector.detect_category(url)
            suggestion = LinkDetector.get_header_suggestion(url, category)
            
            msg = f"链接类型: {category.value}\n"
            if suggestion.required_headers:
                msg += f"需要的请求头: {', '.join(suggestion.required_headers)}\n"
            if suggestion.warning:
                msg += f"提示: {suggestion.warning}"
            
            QMessageBox.information(self, "链接检测结果", msg)
            self.add_log(f"链接类型: {category.value}")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"检测失败: {e}")
    
    def start_download(self):
        """Start download."""
        urls = self.url_input.toPlainText().strip().split('\n')
        urls = [u.strip() for u in urls if u.strip()]
        
        if not urls:
            QMessageBox.warning(self, "提示", "请输入视频链接")
            return
        
        # 停止旧的 worker
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.quit()
            self.worker.wait(2000)
        
        # 创建新的 worker
        self.worker = DownloadWorker()
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.on_download_finished)
        self.worker.log_signal.connect(self.add_log)
        
        # 解析请求头
        headers = {}
        headers_text = self.headers_input.toPlainText().strip()
        if headers_text:
            for line in headers_text.split('\n'):
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
        
        # 添加默认的 User-Agent
        if 'User-Agent' not in headers and 'user-agent' not in headers:
            headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            self.add_log("添加默认 User-Agent")
        
        # 自动设置 Referer
        if self.auto_referer_cb.isChecked():
            if 'Referer' not in headers and 'referer' not in headers:
                first_url = urls[0]
                from urllib.parse import urlparse
                parsed = urlparse(first_url)
                if parsed.netloc:
                    headers['Referer'] = f"https://{parsed.netloc}"
                    self.add_log(f"自动添加 Referer: {headers['Referer']}")
        
        # 构建选项
        options = {
            'save_dir': self.save_dir.text(),
            'save_name': self.filename.text() if self.filename.text() else None,
            'thread_count': self.thread_count.value(),
            'output_format': self.format_combo.currentText(),
            'quality': self.quality_combo.currentText(),
            'overwrite': self.overwrite_cb.isChecked(),
            'auto_referer': self.auto_referer_cb.isChecked(),
            'retry_count': 3
        }
        
        # 打印调试信息
        self.add_log("=" * 60)
        self.add_log("开始下载任务")
        self.add_log(f"URL: {urls[0]}")
        self.add_log("请求头:")
        for key, value in headers.items():
            display_value = value[:100] + "..." if len(value) > 100 else value
            self.add_log(f"  {key}: {display_value}")
        self.add_log(f"保存目录: {options['save_dir']}")
        self.add_log(f"线程数: {options['thread_count']}")
        self.add_log("=" * 60)
        
        # 添加所有任务
        for url in urls:
            task_id = str(uuid.uuid4())[:8]
            self.current_task_id = task_id
            self.worker.add_task(task_id, url, options, headers)
        
        # 更新 UI
        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.speed_label.setText("速度: --")
        self.current_file_label.setText(f"下载中: {urls[0][:50]}...")
        self.statusBar.showMessage(f"开始下载 {len(urls)} 个任务...")
        
        # 启动下载
        self.worker.start()
    
    def cancel_download(self):
        """Cancel download."""
        self.worker.stop()
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.statusBar.showMessage("已取消")
        self.add_log("下载已取消")
    
    def update_progress(self, task_id: str, percent: float, current: int, total: int):
        """Update progress bar."""
        print(f"[GUI] 更新进度: {task_id} - {percent:.1f}%")
        self.progress_bar.setValue(int(percent))
        self.statusBar.showMessage(f"下载进度: {percent:.1f}%")
    
    def on_download_finished(self, task_id: str, success: bool, error: str, file_path: str):
        """Handle download finished."""
        print(f"[GUI] 下载完成: {task_id} - success={success}")
        
        if success:
            self.progress_bar.setValue(100)
            self.statusBar.showMessage("下载完成!")
            self.add_log(f"下载完成: {file_path}")
            
            self.history.add({
                'task_id': task_id,
                'url': self.url_input.toPlainText().strip().split('\n')[0],
                'success': success,
                'file_path': file_path,
                'timestamp': datetime.now().isoformat()
            })
            self.load_history()
            
            QMessageBox.information(self, "成功", f"视频下载完成!\n保存位置: {file_path}")
        else:
            self.statusBar.showMessage(f"下载失败: {error}")
            self.add_log(f"下载失败: {error}")
            QMessageBox.critical(self, "失败", f"下载失败:\n{error}")
        
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.current_file_label.setText("等待下载...")
    
    def add_log(self, message: str):
        """Add log message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        print(f"[LOG] {message}")
    
    def load_settings(self):
        """Load settings from config."""
        download = self.config.get_download_config()
        self.save_dir.setText(download.get('default_dir', str(Path.home() / "Downloads")))
        self.thread_count.setValue(download.get('default_threads', 8))
        self.format_combo.setCurrentText(download.get('default_format', 'mp4'))
        self.quality_combo.setCurrentText(download.get('quality', 'best'))
        self.auto_referer_cb.setChecked(download.get('auto_referer', True))
    
    def load_history(self):
        """Load history from storage."""
        records = self.history.get_all(100)
        self.display_history(records)
    
    def search_history(self):
        """Search history."""
        query = self.search_input.text().strip()
        if query:
            records = self.history.search(query)
        else:
            records = self.history.get_all(100)
        self.display_history(records)
    
    def display_history(self, records):
        """Display history in table."""
        self.history_table.setRowCount(0)
        
        for record in records:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            
            timestamp = record.get('timestamp', '')[:19]
            self.history_table.setItem(row, 0, QTableWidgetItem(timestamp))
            
            url = record.get('url', '')[:80]
            self.history_table.setItem(row, 1, QTableWidgetItem(url))
            
            success = record.get('success', False)
            status = "✓ 成功" if success else "✗ 失败"
            self.history_table.setItem(row, 2, QTableWidgetItem(status))
            
            size_bytes = record.get('file_size_bytes', 0)
            if size_bytes:
                if size_bytes < 1024 * 1024:
                    size_text = f"{size_bytes / 1024:.1f} KB"
                else:
                    size_text = f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                size_text = "--"
            self.history_table.setItem(row, 3, QTableWidgetItem(size_text))
            
            duration = record.get('duration_seconds', 0)
            if duration:
                minutes, seconds = divmod(int(duration), 60)
                duration_text = f"{minutes}m {seconds}s"
            else:
                duration_text = "--"
            self.history_table.setItem(row, 4, QTableWidgetItem(duration_text))
            
            file_path = record.get('file_path', '')
            if file_path:
                self.history_table.setItem(row, 5, QTableWidgetItem(Path(file_path).name))
            else:
                self.history_table.setItem(row, 5, QTableWidgetItem("--"))
    
    def clear_history(self):
        """Clear history."""
        reply = QMessageBox.question(
            self, "确认", "确定要清空所有下载历史吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history.clear()
            self.load_history()
            self.add_log("历史记录已清空")


def main():
    """Main entry point."""
    # 解决 Windows 任务栏图标问题
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VideoDownloader.1.0")
    except Exception:
        pass
    
    app = QApplication(sys.argv)
    
    # 设置应用程序图标（任务栏）
    base_path = get_base_path()
    icon_paths = [
        os.path.join(base_path, "resources", "icon.ico"),
        os.path.join(base_path, "resources", "icon.png"),
    ]
    
    for path in icon_paths:
        if os.path.exists(path):
            app.setWindowIcon(QIcon(path))
            print(f"[GUI] 设置任务栏图标: {path}")
            break
    
    # 设置应用样式
    app.setStyle('Fusion')
    
    # 设置暗色主题
    app.setStyleSheet("""
        QMainWindow {
            background-color: #2b2b2b;
        }
        QLabel {
            color: #ffffff;
        }
        QCheckBox {
            color: #ffffff;
            spacing: 8px;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
        }
        QCheckBox::indicator:unchecked {
            border: 1px solid #5a5a5a;
            background-color: #3c3c3c;
            border-radius: 3px;
        }
        QCheckBox::indicator:checked {
            border: 1px solid #4caf50;
            background-color: #4caf50;
            border-radius: 3px;
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
        QLineEdit, QTextEdit, QComboBox, QSpinBox {
            background-color: #3c3c3c;
            color: #ffffff;
            border: 1px solid #5a5a5a;
            border-radius: 4px;
            padding: 4px;
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
        QProgressBar {
            background-color: #3c3c3c;
            border: 1px solid #5a5a5a;
            border-radius: 4px;
            text-align: center;
            color: #ffffff;
        }
        QProgressBar::chunk {
            background-color: #4caf50;
            border-radius: 3px;
        }
        QStatusBar {
            background-color: #3c3c3c;
            color: #ffffff;
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
        QMessageBox {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QMessageBox QLabel {
            color: #ffffff;
        }
        QMessageBox QPushButton {
            background-color: #4a4a4a;
            color: #ffffff;
            min-width: 80px;
            padding: 5px;
        }
        QInputDialog {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QInputDialog QLabel {
            color: #ffffff;
        }
        QInputDialog QLineEdit {
            background-color: #3c3c3c;
            color: #ffffff;
            border: 1px solid #5a5a5a;
        }
    """)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()