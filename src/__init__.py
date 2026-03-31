"""Video Downloader - A powerful video download tool."""

__version__ = "1.0.0"
__author__ = "Video Downloader Team"
__license__ = "MIT"

from .core.scheduler import DownloadScheduler
from .core.models.download import DownloadOptions, DownloadResult
from .core.models.headers import RequestHeaders
from .core.utils.config import ConfigManager

__all__ = [
    "DownloadScheduler",
    "DownloadOptions",
    "DownloadResult",
    "RequestHeaders",
    "ConfigManager",
    "__version__",
]