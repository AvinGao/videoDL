"""Download engines for different video types."""

from .base import BaseEngine
from .direct import DirectDownloadEngine
from .hls import HlsEngine
from .dash import DashEngine
from .p2p import P2pEngine
from .live import LiveEngine
from .website import WebsiteEngine  # 新增

__all__ = [
    "BaseEngine",
    "DirectDownloadEngine",
    "HlsEngine",
    "DashEngine",
    "P2pEngine",
    "LiveEngine",
    "WebsiteEngine",  # 新增
]