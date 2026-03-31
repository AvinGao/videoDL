"""Base download engine with common functionality."""

import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Callable, List
from pathlib import Path
import logging
import sys

from ..models.download import DownloadOptions, DownloadResult
from ..models.headers import RequestHeaders
from ..models.link import LinkCategory

logger = logging.getLogger(__name__)

# Windows 下隐藏控制台窗口的标志
if sys.platform == 'win32':
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0


class BaseEngine(ABC):
    """Base class for all download engines."""
    
    def __init__(self):
        self._progress_callback: Optional[Callable] = None
        self._speed_callback: Optional[Callable] = None
        self._cancelled = False
        self._current_task_id: Optional[str] = None
    
    @abstractmethod
    async def download(
        self,
        url: str,
        options: DownloadOptions,
        headers: Optional[RequestHeaders] = None,
        task_id: Optional[str] = None,
    ) -> DownloadResult:
        """Execute download operation.
        
        Args:
            url: URL or path to download
            options: Download options
            headers: Optional custom headers
            task_id: Optional task identifier
            
        Returns:
            DownloadResult with download outcome
        """
        pass
    
    @abstractmethod
    def supported_categories(self) -> List[LinkCategory]:
        """Return list of supported link categories."""
        pass
    
    def set_progress_callback(self, callback: Callable):
        """Set callback for progress updates."""
        self._progress_callback = callback
    
    def set_speed_callback(self, callback: Callable):
        """Set callback for speed updates."""
        self._speed_callback = callback
    
    def cancel(self, task_id: Optional[str] = None):
        """Cancel current or specified download."""
        if task_id is None or task_id == self._current_task_id:
            self._cancelled = True
    
    def reset_cancel(self):
        """Reset cancellation flag."""
        self._cancelled = False
    
    def _report_progress(self, percent: float, current: int, total: int):
        """Report download progress."""
        if self._progress_callback and not self._cancelled:
            try:
                self._progress_callback(self._current_task_id, percent, current, total)
            except Exception as e:
                logger.debug(f"Progress callback error: {e}")
    
    def _report_speed(self, speed: float):
        """Report download speed (bytes per second)."""
        if self._speed_callback and not self._cancelled:
            try:
                self._speed_callback(speed)
            except Exception as e:
                logger.debug(f"Speed callback error: {e}")
    
    def _check_cancelled(self):
        """Check if download has been cancelled."""
        if self._cancelled:
            raise asyncio.CancelledError("Download cancelled by user")
    
    @staticmethod
    def _get_output_path(
        url: str,
        options: DownloadOptions,
        default_name: str = "video"
    ) -> Path:
        """Generate output file path."""
        if options.save_name:
            name = options.save_name
        else:
            # Extract from URL or use default
            import re
            from urllib.parse import urlparse
            
            parsed = urlparse(url)
            path = parsed.path
            if path:
                name = path.split('/')[-1].split('?')[0]
                if not name or '.' not in name:
                    name = default_name
            else:
                name = default_name
        
        # Remove invalid characters
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        
        # Add extension if needed
        if options.output_format != "original":
            ext = f".{options.output_format}"
            if not name.lower().endswith(ext):
                name = name.rsplit('.', 1)[0] + ext
        
        return options.save_dir / name
    
    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Remove invalid characters from filename."""
        import re
        return re.sub(r'[<>:"/\\|?*]', '_', filename)