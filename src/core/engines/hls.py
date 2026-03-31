"""HLS (M3U8) download engine using N_m3u8DL-RE."""

import asyncio
import subprocess
import shutil
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional, List, Dict
import logging
import time
import re

from .base import BaseEngine
from ..models.download import DownloadOptions, DownloadResult
from ..models.headers import RequestHeaders
from ..models.link import LinkCategory

logger = logging.getLogger(__name__)


class HlsEngine(BaseEngine):
    """HLS stream download engine using N_m3u8DL-RE."""
    
    # GitHub release URL for N_m3u8DL-RE
    N_M3U8DL_RE_URL = "https://github.com/nilaoda/N_m3u8DL-RE/releases/latest/download/N_m3u8DL-RE.exe"
    
    def __init__(self, tool_path: Optional[Path] = None):
        super().__init__()
        self._tool_path = tool_path or self._find_or_download_tool()
        self._process: Optional[asyncio.subprocess.Process] = None
    
    def _find_or_download_tool(self) -> Path:
        """Find N_m3u8DL-RE in PATH or download it."""
        tool_name = "N_m3u8DL-RE"
        
        # Check in PATH
        if shutil.which(tool_name):
            return Path(shutil.which(tool_name))
        
        # Check in resources directory
        resource_path = Path(__file__).parent.parent.parent.parent / "resources" / f"{tool_name}.exe"
        if resource_path.exists():
            return resource_path
        
        # Check in temp directory
        temp_path = Path(tempfile.gettempdir()) / tool_name / f"{tool_name}.exe"
        if temp_path.exists():
            return temp_path
        
        # Download the tool
        self._download_tool(temp_path)
        return temp_path
    
    def _download_tool(self, target_path: Path):
        """Download N_m3u8DL-RE from GitHub."""
        logger.info("Downloading N_m3u8DL-RE...")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            urllib.request.urlretrieve(self.N_M3U8DL_RE_URL, target_path)
            target_path.chmod(0o755)
            logger.info("N_m3u8DL-RE downloaded successfully")
        except Exception as e:
            logger.error(f"Failed to download N_m3u8DL-RE: {e}")
            raise RuntimeError(f"Cannot download N_m3u8DL-RE: {e}")
    
    def _headers_to_args(self, headers: RequestHeaders) -> List[str]:
        """Convert RequestHeaders to N_m3u8DL-RE arguments."""
        args = []
        headers_dict = headers.to_dict()
        
        for key, value in headers_dict.items():
            args.extend(['-H', f'{key}: {value}'])
        
        return args
    
    def _options_to_args(self, options: DownloadOptions) -> List[str]:
        """Convert DownloadOptions to N_m3u8DL-RE arguments."""
        args = []
        
        # 线程数
        args.extend(['--thread-count', str(options.thread_count)])
        
        # 重试次数
        args.extend(['--download-retry-count', str(options.retry_count)])
        
        # 超时时间
        args.extend(['--http-request-timeout', str(options.timeout_seconds)])
        
        # 临时目录
        temp_dir = options.save_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        args.extend(['--tmp-dir', str(temp_dir)])
        
        # 完成后删除临时文件
        args.append('--del-after-done')
        
        # 输出格式
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
            # Extract from URL
            from urllib.parse import urlparse
            
            parsed = urlparse(url)
            path = parsed.path
            if path:
                name = path.split('/')[-1].split('?')[0]
                if not name:
                    name = "video"
            else:
                name = "video"
        
        # Remove invalid characters
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        
        # Add extension
        ext = f".{options.output_format}" if options.output_format != "original" else ".mp4"
        if not name.lower().endswith(ext):
            name = name.rsplit('.', 1)[0] + ext
        
        return options.save_dir / name
    
    async def _parse_progress(self, line: str) -> Optional[float]:
        """Parse progress from N_m3u8DL-RE output."""
        # Pattern: [current/total]
        match = re.search(r'\[(\d+)/(\d+)\]', line)
        if match:
            current = int(match.group(1))
            total = int(match.group(2))
            if total > 0:
                return (current / total) * 100
        
        # Pattern: Progress: XX%
        match = re.search(r'Progress:\s*(\d+(?:\.\d+)?)%', line)
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
            logger.info(f"File already exists: {output_path}")
            return DownloadResult(
                success=True,
                file_path=output_path,
                file_size_bytes=output_path.stat().st_size,
                duration_seconds=0,
                url=url,
                category=LinkCategory.HLS,
                task_id=task_id
            )
        
        # 准备请求头 - 如果没有提供，创建一个默认的
        if headers is None:
            headers = RequestHeaders()
        
        # 确保有 User-Agent（如果没有）
        if not headers.user_agent:
            headers.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        # 构建命令 - 完全按照成功命令的格式
        cmd = [str(self._tool_path)]
        
        # 输入 URL
        cmd.append(url)
        
        # 请求头 - 必须在 URL 之后
        headers_args = self._headers_to_args(headers)
        cmd.extend(headers_args)
        
        # 保存目录
        cmd.extend(['--save-dir', str(options.save_dir)])
        
        # 保存文件名
        if options.save_name:
            cmd.extend(['--save-name', options.save_name])
        
        # 其他选项
        cmd.extend(self._options_to_args(options))
        
        # 打印完整命令用于调试
        logger.info(f"Running command: {' '.join(cmd)}")
        print(f"调试命令: {' '.join(cmd)}")
        
        try:
            # 创建子进程
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=options.save_dir
            )
            
            # 读取输出
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
                print(f"输出: {line_str}")
                
                # 解析进度
                progress = await self._parse_progress(line_str)
                if progress is not None:
                    if progress > last_progress:
                        last_progress = progress
                        self._report_progress(progress, int(progress), 100)
                
                logger.debug(line_str)
            
            # 等待进程完成
            await self._process.wait()
            
            if self._process.returncode == 0:
                # 查找输出文件
                save_name = options.save_name or "video"
                output_file = options.save_dir / f"{save_name}.{options.output_format}"
                
                # 尝试其他扩展名
                if not output_file.exists():
                    for ext in ['mp4', 'mkv', 'ts']:
                        candidate = options.save_dir / f"{save_name}.{ext}"
                        if candidate.exists():
                            output_file = candidate
                            break
                
                duration = time.time() - start_time
                file_size = output_file.stat().st_size if output_file.exists() else 0
                
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
                # 读取错误输出
                stderr = await self._process.stderr.read()
                error_msg = stderr.decode('utf-8', errors='ignore')[:1000]
                print(f"错误输出: {error_msg}")
                
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
        """Return supported categories."""
        return [LinkCategory.HLS, LinkCategory.LIVE]
    
    def cancel(self, task_id: Optional[str] = None):
        """Cancel download."""
        super().cancel(task_id)
        if self._process:
            self._process.terminate()