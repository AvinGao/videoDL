"""Direct HLS download engine - calls N_m3u8DL-RE exactly like command line."""

import asyncio
import sys
from pathlib import Path
from typing import Optional, List
import logging
import time
import re
import subprocess

from .base import BaseEngine
from ..models.download import DownloadOptions, DownloadResult
from ..models.headers import RequestHeaders
from ..models.link import LinkCategory
from ..utils.tool_manager import tool_manager
from .base import CREATE_NO_WINDOW # 导入常量

logger = logging.getLogger(__name__)


class DirectHlsEngine(BaseEngine):
    """HLS download engine that calls N_m3u8DL-RE exactly like command line."""
    
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
        
        # 尝试获取或下载工具
        tool = tool_manager.ensure_tool("N_m3u8DL-RE", auto_download=True)
        if tool:
            self._tool_path = tool
            self._tool_checked = True
            print(f"[DirectHlsEngine] 已获取工具: {tool}")
        else:
            raise FileNotFoundError(
                "N_m3u8DL-RE.exe not found. Please download it from https://github.com/nilaoda/N_m3u8DL-RE/releases\n"
                "The program will automatically download it when needed."
            )
    
    def _get_tool_path(self) -> Path:
        """获取工具路径（触发延迟初始化）"""
        self._ensure_tool()
        return self._tool_path
    
    def _headers_to_args(self, headers: RequestHeaders) -> List[str]:
        """Convert RequestHeaders to N_m3u8DL-RE arguments."""
        args = []
        headers_dict = headers.to_dict()
        
        for key, value in headers_dict.items():
            header_str = f'{key}: {value}'
            args.extend(['-H', header_str])
        
        return args
    
    def _options_to_args(self, options: DownloadOptions) -> List[str]:
        """Convert DownloadOptions to N_m3u8DL-RE arguments."""
        args = []
        
        args.extend(['--thread-count', str(options.thread_count)])
        args.extend(['--download-retry-count', str(options.retry_count)])
        args.extend(['--http-request-timeout', str(options.timeout_seconds)])
        
        temp_dir = options.save_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        args.extend(['--tmp-dir', str(temp_dir)])
        args.append('--del-after-done')
        
        if options.output_format == 'mp4':
            args.extend(['-M', 'format=mp4'])
        elif options.output_format == 'mkv':
            args.extend(['-M', 'format=mkv'])
        
        return args
    
    def _get_output_path(self, url: str, options: DownloadOptions) -> Path:
        """Generate output file path."""
        if options.save_name:
            name = options.save_name
        else:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path = parsed.path
            if path:
                name = path.split('/')[-1].split('?')[0]
                if not name:
                    name = "video"
            else:
                name = "video"
        
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        ext = f".{options.output_format}" if options.output_format != "original" else ".mp4"
        if not name.lower().endswith(ext):
            name = name.rsplit('.', 1)[0] + ext
        
        return options.save_dir / name
    
    async def _parse_progress(self, line: str) -> Optional[float]:
        """Parse progress from N_m3u8DL-RE output."""
        match = re.search(r'\[(\d+)/(\d+)\]', line)
        if match:
            current = int(match.group(1))
            total = int(match.group(2))
            if total > 0:
                return (current / total) * 100
        
        match = re.search(r'Progress:\s*(\d+(?:\.\d+)?)%', line)
        if match:
            return float(match.group(1))
        
        match = re.search(r'(\d+(?:\.\d+)?)%', line)
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
        """Execute HLS download."""
        start_time = time.time()
        self._current_task_id = task_id
        self.reset_cancel()
        
        # 检查输出文件是否已存在
        output_path = self._get_output_path(url, options)
        if output_path.exists() and not options.overwrite:
            return DownloadResult(
                success=True,
                file_path=output_path,
                file_size_bytes=output_path.stat().st_size,
                duration_seconds=0,
                url=url,
                category=LinkCategory.HLS,
                task_id=task_id
            )
        
        # 准备请求头
        if headers is None:
            headers = RequestHeaders()
        
        if not headers.user_agent:
            headers.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        # 获取工具路径（触发延迟初始化）
        tool_path = self._get_tool_path()
        
        # 构建命令
        cmd = [str(tool_path)]
        cmd.append(url)
        cmd.extend(self._headers_to_args(headers))
        cmd.extend(['--save-dir', str(options.save_dir)])
        
        if options.save_name:
            cmd.extend(['--save-name', options.save_name])
        
        cmd.extend(self._options_to_args(options))
        
        cmd_str = ' '.join(cmd)
        logger.info(f"Running command: {cmd_str}")
        print(f"\n[DirectHlsEngine] 执行命令:\n{cmd_str}\n")
        
        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(options.save_dir),
                creationflags=CREATE_NO_WINDOW
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
                        category=LinkCategory.HLS,
                        task_id=task_id
                    )
                
                line_str = line.decode('utf-8', errors='ignore').strip()
                if line_str:
                    print(line_str)
                
                progress = await self._parse_progress(line_str)
                if progress is not None and progress > last_progress:
                    last_progress = progress
                    self._report_progress(progress, int(progress), 100)
            
            await self._process.wait()
            
            if self._process.returncode == 0:
                save_name = options.save_name or "video"
                output_file = options.save_dir / f"{save_name}.{options.output_format}"
                
                if not output_file.exists():
                    for ext in ['mp4', 'mkv', 'ts']:
                        candidate = options.save_dir / f"{save_name}.{ext}"
                        if candidate.exists():
                            output_file = candidate
                            break
                
                duration = time.time() - start_time
                file_size = output_file.stat().st_size if output_file.exists() else 0
                
                print(f"[DirectHlsEngine] 下载完成: {output_file}")
                
                return DownloadResult(
                    success=True,
                    file_path=output_file,
                    file_size_bytes=file_size,
                    duration_seconds=duration,
                    url=url,
                    category=LinkCategory.HLS,
                    task_id=task_id
                )
            else:
                stderr = await self._process.stderr.read()
                error_msg = stderr.decode('utf-8', errors='ignore')[:1000]
                print(f"[DirectHlsEngine] 错误: {error_msg}")
                
                return DownloadResult(
                    success=False,
                    error_message=f"N_m3u8DL-RE failed (code {self._process.returncode}): {error_msg}",
                    duration_seconds=time.time() - start_time,
                    url=url,
                    category=LinkCategory.HLS,
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
                category=LinkCategory.HLS,
                task_id=task_id
            )
        except Exception as e:
            logger.exception("HLS download failed")
            return DownloadResult(
                success=False,
                error_message=str(e),
                duration_seconds=time.time() - start_time,
                url=url,
                category=LinkCategory.HLS,
                task_id=task_id
            )
    
    def supported_categories(self) -> List[LinkCategory]:
        return [LinkCategory.HLS, LinkCategory.LIVE]
    
    def cancel(self, task_id: Optional[str] = None):
        super().cancel(task_id)
        if self._process:
            self._process.terminate()