"""P2P download engine for magnet links and torrents using aria2."""

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Optional, List
import logging
import time
import re

from .base import BaseEngine
from ..models.download import DownloadOptions, DownloadResult
from ..models.headers import RequestHeaders
from ..models.link import LinkCategory
from ..utils.tool_manager import tool_manager
from .base import CREATE_NO_WINDOW  # 导入常量

logger = logging.getLogger(__name__)


class P2pEngine(BaseEngine):
    """P2P download engine using aria2."""
    
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
        
        tool = tool_manager.ensure_tool("aria2c", auto_download=True)
        if tool:
            self._tool_path = tool
            self._tool_checked = True
            print(f"[P2pEngine] 已获取工具: {tool}")
        else:
            raise FileNotFoundError(
                "aria2c.exe not found. Please download it from https://github.com/aria2/aria2/releases\n"
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
            args.extend(['--header', f'{key}: {value}'])
        
        return args
    
    def _options_to_args(self, options: DownloadOptions) -> List[str]:
        args = []
        
        args.extend(['--dir', str(options.save_dir)])
        args.extend(['--max-connection-per-server', str(options.thread_count)])
        args.extend(['--split', str(options.thread_count)])
        args.extend(['--min-split-size', '1M'])
        args.extend(['--max-tries', str(options.retry_count + 1)])
        args.extend(['--retry-wait', '5'])
        args.extend(['--timeout', str(options.timeout_seconds)])
        args.append('--continue')
        args.append('--auto-file-renaming=false')
        args.extend(['--console-log-level', 'error'])
        args.append('--download-result=default')
        args.append('--seed-time=0')
        
        return args
    
    async def download_magnet(
        self,
        magnet_url: str,
        options: DownloadOptions,
        headers: Optional[RequestHeaders] = None
    ) -> DownloadResult:
        return await self._download(magnet_url, options, headers, is_magnet=True)
    
    async def download_torrent(
        self,
        torrent_path: Path,
        options: DownloadOptions,
        headers: Optional[RequestHeaders] = None
    ) -> DownloadResult:
        return await self._download(str(torrent_path), options, headers, is_torrent=True)
    
    async def _download(
        self,
        input_str: str,
        options: DownloadOptions,
        headers: Optional[RequestHeaders],
        is_magnet: bool = False,
        is_torrent: bool = False
    ) -> DownloadResult:
        start_time = time.time()
        self._current_task_id = None
        self.reset_cancel()
        
        tool_path = self._get_tool_path()
        
        cmd = [str(tool_path)]
        
        if is_magnet:
            cmd.append(input_str)
        elif is_torrent:
            cmd.extend(['--torrent-file', input_str])
        else:
            cmd.append(input_str)
        
        if headers:
            cmd.extend(self._headers_to_args(headers))
        
        cmd.extend(self._options_to_args(options))
        
        logger.debug(f"Running command: {' '.join(cmd)}")
        
        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=options.save_dir,
                creationflags=CREATE_NO_WINDOW  # 添加这行
            )
            
            async for line in self._process.stdout:
                if self._cancelled:
                    self._process.terminate()
                    return DownloadResult(
                        success=False,
                        error_message="Download cancelled",
                        duration_seconds=time.time() - start_time,
                        url=input_str,
                        category=LinkCategory.MAGNET if is_magnet else LinkCategory.TORRENT
                    )
                
                line_str = line.decode('utf-8', errors='ignore').strip()
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
                    url=input_str,
                    category=LinkCategory.MAGNET if is_magnet else LinkCategory.TORRENT
                )
            else:
                stderr = await self._process.stderr.read()
                error_msg = stderr.decode('utf-8', errors='ignore')[:500]
                
                return DownloadResult(
                    success=False,
                    error_message=f"aria2 failed (code {self._process.returncode}): {error_msg}",
                    duration_seconds=time.time() - start_time,
                    url=input_str,
                    category=LinkCategory.MAGNET if is_magnet else LinkCategory.TORRENT
                )
                
        except asyncio.CancelledError:
            if self._process:
                self._process.terminate()
            return DownloadResult(
                success=False,
                error_message="Download cancelled",
                duration_seconds=time.time() - start_time,
                url=input_str,
                category=LinkCategory.MAGNET if is_magnet else LinkCategory.TORRENT
            )
        except Exception as e:
            logger.exception("P2P download failed")
            return DownloadResult(
                success=False,
                error_message=str(e),
                duration_seconds=time.time() - start_time,
                url=input_str,
                category=LinkCategory.MAGNET if is_magnet else LinkCategory.TORRENT
            )
    
    def _find_output_file(self, options: DownloadOptions) -> Optional[Path]:
        files = list(options.save_dir.glob('*'))
        if files:
            return max(files, key=lambda p: p.stat().st_mtime)
        return None
    
    def get_torrent_files(self, torrent_path: Path) -> List[str]:
        import subprocess
        tool_path = self._get_tool_path()
        cmd = [str(tool_path), '--show-files', '--torrent-file', str(torrent_path)]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                files = []
                for line in result.stdout.split('\n'):
                    if '|' in line:
                        parts = line.split('|')
                        if len(parts) >= 3:
                            files.append(parts[2].strip())
                return files
        except Exception:
            pass
        return []
    
    async def download(
        self,
        url: str,
        options: DownloadOptions,
        headers: Optional[RequestHeaders] = None,
        task_id: Optional[str] = None
    ) -> DownloadResult:
        if url.startswith('magnet:'):
            return await self.download_magnet(url, options, headers)
        else:
            return await self.download_torrent(Path(url), options, headers)
    
    def supported_categories(self) -> List[LinkCategory]:
        return [LinkCategory.MAGNET, LinkCategory.TORRENT]
    
    def cancel(self, task_id: Optional[str] = None):
        super().cancel(task_id)
        if self._process:
            self._process.terminate()