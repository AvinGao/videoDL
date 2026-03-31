"""Data models for Video Downloader."""

from .download import DownloadOptions, DownloadResult, TaskInfo
from .link import LinkCategory, HeaderSuggestion
from .headers import RequestHeaders
from .video import VideoInfo

__all__ = [
    "DownloadOptions",
    "DownloadResult",
    "TaskInfo",
    "LinkCategory",
    "HeaderSuggestion",
    "RequestHeaders",
    "VideoInfo",
]