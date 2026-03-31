"""DASH (MPD) download engine using yt-dlp."""

import asyncio
import subprocess
import json
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging
import time
import re

from .base import BaseEngine
from ..models.download import DownloadOptions, DownloadResult
from ..models.headers import RequestHeaders
from ..models.link import LinkCategory
from ..models.video import VideoInfo, FormatInfo
from ..utils.tool_manager import tool_manager
from .base import CREATE_NO_WINDOW  # 导入常量

logger = logging.getLogger(__name__)


class DashEngine(BaseEngine):
    """DASH stream download engine using yt-dlp."""
    
    def __init__(self, tool_path: Optional[Path] = None):
        super().__init__()
        self._tool_path = tool_path
        self._tool_checked = False
        self._process: Optional[asyncio.subprocess.Process] = None
    
    def _ensure_tool(self):
        """确保工具存在（延迟初始化）"""
        if self._tool_checked:
            return
        
        if self._tool_path:
            if self._tool_path.exists():
                self._tool_checked = True
                return
            else:
                raise FileNotFoundError(f"Tool not found: {self._tool_path}")
        
        tool = tool_manager.ensure_tool("yt-dlp", auto_download=True)
        if tool:
            self._tool_path = tool
            self._tool_checked = True
            print(f"[DashEngine] 已获取工具: {tool}")
        else:
            raise FileNotFoundError(
                "yt-dlp.exe not found. Please download it from https://github.com/yt-dlp/yt-dlp/releases\n"
                "The program will automatically download it when needed."
            )
    
    def _get_tool_path(self) -> Path:
        """获取工具路径（触发延迟初始化）"""
        self._ensure_tool()
        return self._tool_path
    
    def _headers_to_args(self, headers: RequestHeaders) -> List[str]:
        args = []
        headers_dict = headers.to_dict()
        
        for key, value in headers_dict.items():
            args.extend(['--headers', f'{key}: {value}'])
        
        return args
    
    def _options_to_args(self, options: DownloadOptions) -> List[str]:
        args = []
        
        if options.save_name:
            template = str(options.save_dir / options.save_name)
        else:
            template = str(options.save_dir / '%(title)s.%(ext)s')
        args.extend(['-o', template])
        
        if options.quality == 'best':
            args.extend(['-f', 'bestvideo+bestaudio/best'])
        elif options.quality == 'worst':
            args.extend(['-f', 'worst'])
        elif options.quality == '1080p':
            args.extend(['-f', 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'])
        elif options.quality == '720p':
            args.extend(['-f', 'bestvideo[height<=720]+bestaudio/best[height<=720]'])
        elif options.quality == '480p':
            args.extend(['-f', 'bestvideo[height<=480]+bestaudio/best[height<=480]'])
        
        if options.output_format == 'mp4':
            args.extend(['--merge-output-format', 'mp4'])
        elif options.output_format == 'mkv':
            args.extend(['--merge-output-format', 'mkv'])
        
        args.extend(['--retries', str(options.retry_count)])
        args.extend(['--socket-timeout', str(options.timeout_seconds)])
        
        if not options.overwrite:
            args.append('--no-overwrites')
        
        args.extend(['--fragment-retries', str(options.retry_count)])
        
        return args
    
    async def extract_manifest_info(self, url: str, headers: Optional[RequestHeaders] = None) -> Optional[VideoInfo]:
        tool_path = self._get_tool_path()
        cmd = [str(tool_path), '-J', url]
        
        if headers:
            cmd.extend(self._headers_to_args(headers))
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW  # 添加这行
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                data = json.loads(stdout.decode('utf-8', errors='ignore'))
                return self._parse_manifest_info(data)
            else:
                logger.error(f"yt-dlp failed: {stderr.decode()}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to extract manifest info: {e}")
            return None
    
    def _parse_manifest_info(self, data: Dict[str, Any]) -> VideoInfo:
        formats = []
        
        for fmt in data.get('formats', []):
            formats.append(FormatInfo(
                format_id=fmt.get('format_id', ''),
                resolution=fmt.get('resolution'),
                fps=fmt.get('fps'),
                codec=fmt.get('vcodec') or fmt.get('acodec'),
                bitrate=fmt.get('tbr'),
                filesize=fmt.get('filesize'),
                url=fmt.get('url')
            ))
        
        resolutions = sorted(set(
            f.resolution for f in formats if f.resolution
        ), key=self._resolution_sort_key, reverse=True)
        
        return VideoInfo(
            title=data.get('title', 'DASH Stream'),
            duration=data.get('duration'),
            thumbnail=data.get('thumbnail'),
            resolutions=resolutions,
            formats=formats,
            raw_data=data
        )
    
    def _resolution_sort_key(self, resolution: str) -> int:
        if not resolution:
            return 0
        match = re.search(r'(\d+)$', resolution)
        if match:
            return int(match.group(1))
        return 0
    
    async def _parse_progress(self, line: str) -> Optional[float]:
        match = re.search(r'\[download\]\s+([\d.]+)%', line)
        if match:
            return float(match.group(1))
        return None
    
    async def download(
        self,
        url: str,
        options: DownloadOptions,
        headers: Optional[RequestHeaders] = None,
        task_id: Optional[str] = None
    ) -> DownloadResult:
        start_time = time.time()
        self._current_task_id = task_id
        self.reset_cancel()
        
        tool_path = self._get_tool_path()
        
        cmd = [str(tool_path)]
        cmd.append(url)
        
        if headers:
            cmd.extend(self._headers_to_args(headers))
        
        cmd.extend(self._options_to_args(options))
        cmd.append('--progress')
        cmd.append('--quiet')
        cmd.append('--no-warnings')
        
        logger.debug(f"Running DASH download: {' '.join(cmd)}")
        
        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=options.save_dir,
                creationflags=CREATE_NO_WINDOW  # 添加这行
            )
            
            last_progress = 0
            async for line in self._process.stdout:
                if self._cancelled:
                    self._process.terminate()
                    return DownloadResult(
                        success=False,
                        error_message="Download cancelled",
                        duration_seconds=time.time() - start_time,
                        url=url,
                        category=LinkCategory.DASH,
                        task_id=task_id
                    )
                
                line_str = line.decode('utf-8', errors='ignore').strip()
                progress = await self._parse_progress(line_str)
                
                if progress is not None and progress > last_progress:
                    last_progress = progress
                    self._report_progress(progress, int(progress), 100)
                
                logger.debug(line_str)
            
            await self._process.wait()
            
            if self._process.returncode == 0:
                output_path = self._find_output_file(options)
                duration = time.time() - start_time
                file_size = output_path.stat().st_size if output_path and output_path.exists() else 0
                
                return DownloadResult(
                    success=True,
                    file_path=output_path,
                    file_size_bytes=file_size,
                    duration_seconds=duration,
                    url=url,
                    category=LinkCategory.DASH,
                    task_id=task_id
                )
            else:
                stderr = await self._process.stderr.read()
                error_msg = stderr.decode('utf-8', errors='ignore')[:500]
                
                return DownloadResult(
                    success=False,
                    error_message=f"DASH download failed: {error_msg}",
                    duration_seconds=time.time() - start_time,
                    url=url,
                    category=LinkCategory.DASH,
                    task_id=task_id
                )
                
        except asyncio.CancelledError:
            if self._process:
                self._process.terminate()
            return DownloadResult(
                success=False,
                error_message="Download cancelled",
                duration_seconds=time.time() - start_time,
                url=url,
                category=LinkCategory.DASH,
                task_id=task_id
            )
        except Exception as e:
            logger.exception("DASH download failed")
            return DownloadResult(
                success=False,
                error_message=str(e),
                duration_seconds=time.time() - start_time,
                url=url,
                category=LinkCategory.DASH,
                task_id=task_id
            )
    
    def _find_output_file(self, options: DownloadOptions) -> Optional[Path]:
        if options.save_name:
            for ext in ['mp4', 'mkv', 'webm']:
                candidate = options.save_dir / f"{options.save_name}.{ext}"
                if candidate.exists():
                    return candidate
        
        video_extensions = {'.mp4', '.mkv', '.webm'}
        files = list(options.save_dir.glob('*'))
        video_files = [f for f in files if f.suffix.lower() in video_extensions]
        
        if video_files:
            return max(video_files, key=lambda p: p.stat().st_mtime)
        
        return None
    
    def supported_categories(self) -> List[LinkCategory]:
        return [LinkCategory.DASH, LinkCategory.WEBSITE]
    
    def cancel(self, task_id: Optional[str] = None):
        super().cancel(task_id)
        if self._process:
            self._process.terminate()