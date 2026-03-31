"""Download scheduler that orchestrates all engines."""

import asyncio
import uuid
import json
import logging
from pathlib import Path
from typing import Dict, Optional, List, Callable, Any
from datetime import datetime

from .models.download import DownloadOptions, DownloadResult, TaskInfo
from .models.headers import RequestHeaders
from .models.link import LinkCategory
from .utils.link_detector import LinkDetector
from .utils.config import ConfigManager, HistoryManager
from .headers.manager import HeaderManager
from .engines.base import BaseEngine
from .engines.direct import DirectDownloadEngine
from .engines.direct_hls import DirectHlsEngine
from .engines.dash import DashEngine
from .engines.p2p import P2pEngine
from .engines.live import LiveEngine
from .engines.website import WebsiteEngine

logger = logging.getLogger(__name__)


class DownloadScheduler:
    """Orchestrate downloads using appropriate engines."""
    
    def __init__(self):
        self._engines: Dict[LinkCategory, BaseEngine] = {}
        self._tasks: Dict[str, TaskInfo] = {}
        self._config = ConfigManager()
        self._history = HistoryManager(self._config)
        self._progress_callback: Optional[Callable] = None
        self._speed_callback: Optional[Callable] = None
        self._max_concurrent = self._config.get('download.max_concurrent', 3)
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        
        self._init_engines()
    
    def _init_engines(self):
        """Initialize all download engines."""
        self._engines[LinkCategory.DIRECT] = DirectDownloadEngine()
        self._engines[LinkCategory.HLS] = DirectHlsEngine()
        self._engines[LinkCategory.DASH] = DashEngine()
        self._engines[LinkCategory.WEBSITE] = WebsiteEngine()
        self._engines[LinkCategory.MAGNET] = P2pEngine()
        self._engines[LinkCategory.TORRENT] = P2pEngine()
        self._engines[LinkCategory.LIVE] = LiveEngine()
    
    def set_progress_callback(self, callback: Callable):
        """Set callback for progress updates."""
        self._progress_callback = callback
        for engine in self._engines.values():
            engine.set_progress_callback(callback)
    
    def set_speed_callback(self, callback: Callable):
        """Set callback for speed updates."""
        self._speed_callback = callback
        for engine in self._engines.values():
            engine.set_speed_callback(callback)
    
    async def download(
        self,
        input_str: str,
        options: DownloadOptions,
        headers: Optional[RequestHeaders] = None,
        task_id: Optional[str] = None
    ) -> DownloadResult:
        """Execute download with appropriate engine."""
        # Generate task ID if not provided
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        # 1. Detect category
        category = LinkDetector.detect_category(input_str)
        
        if category == LinkCategory.UNKNOWN:
            return DownloadResult(
                success=False,
                error_message=f"Cannot determine video type for: {input_str}",
                url=input_str,
                category=category,
                task_id=task_id
            )
        
        # 2. Get header suggestions and merge
        suggestion = LinkDetector.get_header_suggestion(input_str, category)
        
        # Generate default headers if needed
        if headers is None:
            headers = HeaderManager.create_default()
        
        # Merge with suggested headers if auto_referer enabled
        if options.auto_referer:
            suggested = HeaderManager.from_url(input_str)
            headers = HeaderManager.merge(headers, suggested)
        
        # 3. Validate headers if strict mode
        if options.strict_headers and suggestion.required_headers:
            missing = HeaderManager.validate(headers, suggestion.required_headers)
            if missing:
                return DownloadResult(
                    success=False,
                    error_message=f"Missing required headers: {', '.join(missing)}",
                    url=input_str,
                    category=category,
                    task_id=task_id
                )
        
        # 4. Get appropriate engine
        engine = self._engines.get(category)
        if not engine:
            return DownloadResult(
                success=False,
                error_message=f"No engine available for category: {category}",
                url=input_str,
                category=category,
                task_id=task_id
            )
        
        # 5. Create task info
        self._tasks[task_id] = TaskInfo(
            task_id=task_id,
            input=input_str,
            category=category,
            status="downloading",
            start_time=datetime.now()
        )
        
        # 6. Execute download with semaphore for concurrency control
        async with self._semaphore:
            try:
                result = await engine.download(input_str, options, headers, task_id)
                
                # Update task info
                if task_id in self._tasks:
                    self._tasks[task_id].status = "completed" if result.success else "failed"
                    self._tasks[task_id].end_time = datetime.now()
                    self._tasks[task_id].output_path = result.file_path
                    self._tasks[task_id].error = result.error_message
                    self._tasks[task_id].progress = 100 if result.success else 0
                
                # Save to history
                self._save_to_history(task_id, input_str, category, result)
                
                return result
                
            except asyncio.CancelledError:
                if task_id in self._tasks:
                    self._tasks[task_id].status = "cancelled"
                    self._tasks[task_id].end_time = datetime.now()
                
                return DownloadResult(
                    success=False,
                    error_message="Download cancelled",
                    duration_seconds=0,
                    url=input_str,
                    category=category,
                    task_id=task_id
                )
            except Exception as e:
                logger.exception(f"Download failed for {input_str}")
                
                if task_id in self._tasks:
                    self._tasks[task_id].status = "failed"
                    self._tasks[task_id].error = str(e)
                    self._tasks[task_id].end_time = datetime.now()
                
                return DownloadResult(
                    success=False,
                    error_message=str(e),
                    duration_seconds=0,
                    url=input_str,
                    category=category,
                    task_id=task_id
                )
    
    def _save_to_history(self, task_id: str, url: str, category: LinkCategory, result: DownloadResult):
        """Save download result to history."""
        history_record = {
            "task_id": task_id,
            "url": url,
            "category": category.value,
            "success": result.success,
            "file_path": str(result.file_path) if result.file_path else None,
            "file_size_bytes": result.file_size_bytes,
            "duration_seconds": result.duration_seconds,
            "timestamp": datetime.now().isoformat(),
            "error": result.error_message
        }
        self._history.add(history_record)
    
    def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """Get status of a task."""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[TaskInfo]:
        """Get all tasks."""
        return list(self._tasks.values())
    
    def cancel_task(self, task_id: str):
        """Cancel a running task."""
        task = self._tasks.get(task_id)
        if task and task.is_running:
            engine = self._engines.get(task.category)
            if engine:
                engine.cancel(task_id)
            task.status = "cancelled"
            task.end_time = datetime.now()
    
    def cancel_all(self):
        """Cancel all running tasks."""
        for task_id in list(self._tasks.keys()):
            self.cancel_task(task_id)
    
    def get_active_tasks(self) -> List[TaskInfo]:
        """Get all active tasks."""
        return [t for t in self._tasks.values() if t.is_running]
    
    def get_completed_tasks(self) -> List[TaskInfo]:
        """Get all completed tasks."""
        return [t for t in self._tasks.values() if t.is_completed]
    
    def get_failed_tasks(self) -> List[TaskInfo]:
        """Get all failed tasks."""
        return [t for t in self._tasks.values() if t.is_failed]
    
    def get_history(self, limit: int = 20) -> List[Dict]:
        """Get download history."""
        return self._history.get_all(limit)
    
    def clear_history(self):
        """Clear download history."""
        self._history.clear()
    
    def search_history(self, query: str) -> List[Dict]:
        """Search history by URL or filename."""
        return self._history.search(query)
    
    async def download_batch(
        self,
        urls: List[str],
        options: DownloadOptions,
        headers: Optional[RequestHeaders] = None,
        max_concurrent: Optional[int] = None
    ) -> List[DownloadResult]:
        """Download multiple URLs concurrently."""
        concurrent = max_concurrent or self._max_concurrent
        semaphore = asyncio.Semaphore(concurrent)
        
        async def download_with_semaphore(url: str) -> DownloadResult:
            async with semaphore:
                return await self.download(url, options, headers)
        
        tasks = [download_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to DownloadResult
        final_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                final_results.append(DownloadResult(
                    success=False,
                    error_message=str(r),
                    url=urls[i],
                    category=LinkCategory.UNKNOWN
                ))
            else:
                final_results.append(r)
        
        return final_results
    
    async def download_from_file(
        self,
        file_path: Path,
        options: DownloadOptions,
        headers: Optional[RequestHeaders] = None
    ) -> List[DownloadResult]:
        """Download URLs from a file (one URL per line)."""
        with open(file_path, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        return await self.download_batch(urls, options, headers)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get download statistics."""
        completed = self.get_completed_tasks()
        failed = self.get_failed_tasks()
        active = self.get_active_tasks()
        
        total_size = sum(
            t.output_path.stat().st_size 
            for t in completed 
            if t.output_path and t.output_path.exists()
        )
        
        return {
            "total_tasks": len(self._tasks),
            "completed": len(completed),
            "failed": len(failed),
            "active": len(active),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "history_count": len(self._history.get_all())
        }
    
    def cleanup(self):
        """Clean up resources."""
        for engine in self._engines.values():
            if hasattr(engine, 'close'):
                try:
                    asyncio.create_task(engine.close())
                except Exception:
                    pass