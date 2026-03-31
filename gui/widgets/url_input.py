"""URL input widget with paste button."""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QApplication
)
from PyQt6.QtCore import Qt


class UrlInputWidget(QWidget):
    """Widget for URL input with paste button."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "输入视频链接 (支持 M3U8, MPD, MP4, 网站链接, 磁力链接等)"
        )
        layout.addWidget(self.url_input)
        
        self.paste_btn = QPushButton("粘贴")
        self.paste_btn.clicked.connect(self.paste_from_clipboard)
        layout.addWidget(self.paste_btn)
        
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self.clear)
        layout.addWidget(self.clear_btn)
    
    def paste_from_clipboard(self):
        """Paste URL from clipboard."""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.url_input.setText(text)
    
    def get_url(self) -> str:
        """Get the URL text."""
        return self.url_input.text().strip()
    
    def set_url(self, url: str):
        """Set the URL text."""
        self.url_input.setText(url)
    
    def clear(self):
        """Clear the URL input."""
        self.url_input.clear()