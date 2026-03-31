"""Live stream recording engine using FFmpeg."""

import asyncio
import sys
from pathlib import Path
from typing import Optional, List
import logging
import time
import re
from datetime import datetime

from .base import BaseEngine
from ..models.download import DownloadOptions, DownloadResult
from ..models.headers import RequestHeaders
from ..models.link import LinkCategory
from ..utils.tool_manager import tool_manager
from .base import CREATE_NO_WINDOW  # 导入常量

logger = logging.getLogger(__name__)


class LiveEngine(BaseEngine):
    """Live stream recording engine."""
    
    def __init__(self, ffmpeg_path: Optional[Path] = None):
        super().__init__()
        self._ffmpeg_path = ffmpeg_path
        self._tool_checked = False
        self._process: Optional[asyncio.subprocess.Process] = None
        self._record_start_time: Optional[datetime] = None
    
    def _ensure_tool(self):
        """确保工具存在（延迟初始化）"""
        if self._tool_checked:
            return
        
        if self._ffmpeg_path:
            if self._ffmpeg_path.exists():
                self._tool_checked = True
                return
            else:
                raise FileNotFoundError(f"FFmpeg not found: {self._ffmpeg_path}")
        
        tool = tool_manager.ensure_tool("ffmpeg", auto_download=True)
        if tool:
            self._ffmpeg_path = tool
            self._tool_checked = True
            print(f"[LiveEngine] 已获取工具: {tool}")
        else:
            raise FileNotFoundError(
                "ffmpeg.exe not found. Please download it from https://ffmpeg.org/download.html\n"
                "The program will automatically download it when needed."
            )
    
    def _get_ffmpeg_path(self) -> Path:
        """获取 FFmpeg 路径（触发延迟初始化）"""
        self._ensure_tool()
        return self._ffmpeg_path
    
    def _headers_to_ffmpeg(self, headers: RequestHeaders) -> str:
        headers_dict = headers.to_dict()
        if not headers_dict:
            return ""
        
        header_parts = []
        for key, value in headers_dict.items():
            header_parts.append(f"{key}: {value}")
        
        return "\r\n".join(header_parts)
    
    def _options_to_args(self, options: DownloadOptions, is_live: bool = True) -> List[str]:
        args = []
        
        if is_live:
            args.extend(['-re', '-i'])
        else:
            args.extend(['-i'])
        
        if options.auto_referer:
            args.extend(['-headers', self._headers_to_ffmpeg(RequestHeaders())])
        
        args.extend(['-c', 'copy'])
        
        if options.output_format == 'mp4':
            args.extend(['-f', 'mp4'])
        elif options.output_format == 'mkv':
            args.extend(['-f', 'matroska'])
        
        if options.output_format == 'mp4':
            args.extend(['-movflags', 'faststart'])
        
        args.append('-y')
        
        return args
    
    async def record(
        self,
        url: str,
        options: DownloadOptions,
        headers: Optional[RequestHeaders] = None,
        duration_limit: Optional[int] = None
    ) -> DownloadResult:
        start_time = time.time()
        self._record_start_time = datetime.now()
        self.reset_cancel()
        
        ffmpeg_path = self._get_ffmpeg_path()
        
        output_path = self._get_output_path(url, options, "live_recording")
        
        cmd = [str(ffmpeg_path)]
        
        if headers:
            cmd.extend(['-headers', self._headers_to_ffmpeg(headers)])
        
        cmd.append('-i')
        cmd.append(url)
        cmd.extend(self._options_to_args(options, is_live=True))
        cmd.append(str(output_path))
        
        logger.debug(f"Running command: {' '.join(cmd)}")
        
        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW  # 添加这行
            )
            
            if duration_limit:
                asyncio.create_task(self._stop_after_duration(duration_limit))
            
            async for line in self._process.stderr:
                if self._cancelled:
                    self._process.terminate()
                    break
                
                line_str = line.decode('utf-8', errors='ignore').strip()
                logger.debug(line_str)
            
            await self._process.wait()
            
            if self._process.returncode == 0 or (self._cancelled and output_path.exists()):
                duration = time.time() - start_time
                file_size = output_path.stat().st_size if output_path.exists() else 0
                
                return DownloadResult(
                    success=True,
                    file_path=output_path,
                    file_size_bytes=file_size,
                    duration_seconds=duration,
                    url=url,
                    category=LinkCategory.LIVE
                )
            else:
                stderr = await self._process.stderr.read()
                error_msg = stderr.decode('utf-8', errors='ignore')[:500]
                
                return DownloadResult(
                    success=False,
                    error_message=f"FFmpeg failed (code {self._process.returncode}): {error_msg}",
                    duration_seconds=time.time() - start_time,
                    url=url,
                    category=LinkCategory.LIVE
                )
                
        except asyncio.CancelledError:
            if self._process:
                self._process.terminate()
            return DownloadResult(
                success=output_path.exists(),
                file_path=output_path if output_path.exists() else None,
                error_message="Recording cancelled" if not output_path.exists() else None,
                duration_seconds=time.time() - start_time,
                url=url,
                category=LinkCategory.LIVE
            )
        except Exception as e:
            logger.exception("Live recording failed")
            return DownloadResult(
                success=False,
                error_message=str(e),
                duration_seconds=time.time() - start_time,
                url=url,
                category=LinkCategory.LIVE
            )
    
    async def _stop_after_duration(self, duration_seconds: int):
        await asyncio.sleep(duration_seconds)
        if self._process and self._process.returncode is None:
            self._process.terminate()
    
    def _get_output_path(self, url: str, options: DownloadOptions, default_name: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if options.save_name:
            name = f"{options.save_name}_{timestamp}"
        else:
            name = f"{default_name}_{timestamp}"
        
        ext = f".{options.output_format}" if options.output_format != "original" else ".ts"
        
        return options.save_dir / f"{name}{ext}"
    
    async def download(
        self,
        url: str,
        options: DownloadOptions,
        headers: Optional[RequestHeaders] = None,
        task_id: Optional[str] = None
    ) -> DownloadResult:
        self._current_task_id = task_id
        
        duration = None
        if options.live_duration_limit:
            parts = options.live_duration_limit.split(':')
            if len(parts) == 3:
                duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        
        return await self.record(url, options, headers, duration)
    
    def supported_categories(self) -> List[LinkCategory]:
        return [LinkCategory.LIVE]
    
    def cancel(self, task_id: Optional[str] = None):
        super().cancel(task_id)
        if self._process:
            self._process.terminate()