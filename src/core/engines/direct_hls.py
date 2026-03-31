"""Direct HLS download engine - calls N_m3u8DL-RE exactly like command line."""

import asyncio
import subprocess
import shutil
import tempfile
import urllib.request
import ssl
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

logger = logging.getLogger(__name__)


class DirectHlsEngine(BaseEngine):
    """HLS download engine that calls N_m3u8DL-RE exactly like command line."""
    
    # GitHub release URL for N_m3u8DL-RE
    N_M3U8DL_RE_URL = "https://github.com/nilaoda/N_m3u8DL-RE/releases/latest/download/N_m3u8DL-RE.exe"
    
    def __init__(self, tool_path: Optional[Path] = None):
        super().__init__()
        self._tool_path = tool_path or self._find_or_download_tool()
        self._process: Optional[asyncio.subprocess.Process] = None
    
    def _get_base_path(self) -> Path:
        """获取程序基础路径（支持 PyInstaller）"""
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后的临时目录
            return Path(sys._MEIPASS)
        else:
            # 开发环境
            return Path(__file__).parent.parent.parent.parent
    
    def _get_tools_dir(self) -> Path:
        """获取工具存放目录"""
        # 优先使用程序所在目录
        if getattr(sys, 'frozen', False):
            # 打包后的 exe 所在目录
            return Path(sys.executable).parent / "tools"
        else:
            # 开发环境，使用项目根目录的 tools 文件夹
            tools_dir = Path(__file__).parent.parent.parent.parent / "tools"
            tools_dir.mkdir(parents=True, exist_ok=True)
            return tools_dir
    
    def _download_file(self, url: str, target_path: Path) -> bool:
        """下载文件，支持 SSL"""
        try:
            print(f"[HlsEngine] 正在下载: {url}")
            print(f"[HlsEngine] 保存到: {target_path}")
            
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建忽略 SSL 验证的上下文（解决证书问题）
            ssl_context = ssl._create_unverified_context()
            
            urllib.request.urlretrieve(url, target_path, context=ssl_context)
            print(f"[HlsEngine] 下载完成: {target_path}")
            return True
        except Exception as e:
            print(f"[HlsEngine] 下载失败: {e}")
            return False
    
    def _find_or_download_tool(self) -> Path:
        """Find N_m3u8DL-RE in PATH or download it."""
        tool_name = "N_m3u8DL-RE.exe"
        
        # 1. 检查工具目录
        tools_dir = self._get_tools_dir()
        tool_path = tools_dir / tool_name
        if tool_path.exists():
            print(f"[HlsEngine] 找到工具: {tool_path}")
            return tool_path
        
        # 2. 检查程序所在目录
        if getattr(sys, 'frozen', False):
            exe_dir = Path(sys.executable).parent
            tool_path = exe_dir / tool_name
            if tool_path.exists():
                print(f"[HlsEngine] 找到工具: {tool_path}")
                return tool_path
        
        # 3. 检查当前目录
        if Path(tool_name).exists():
            print(f"[HlsEngine] 找到工具: {Path(tool_name).absolute()}")
            return Path(tool_name)
        
        # 4. 检查 PATH
        if shutil.which("N_m3u8DL-RE"):
            return Path(shutil.which("N_m3u8DL-RE"))
        
        # 5. 自动下载
        print(f"[HlsEngine] 未找到 {tool_name}，正在自动下载...")
        target_path = tools_dir / tool_name
        
        if self._download_file(self.N_M3U8DL_RE_URL, target_path):
            return target_path
        else:
            raise FileNotFoundError(
                f"无法下载 {tool_name}，请手动下载并放置到程序目录\n"
                f"下载地址: {self.N_M3U8DL_RE_URL}"
            )
    
    def _headers_to_args(self, headers: RequestHeaders) -> List[str]:
        """Convert RequestHeaders to N_m3u8DL-RE arguments."""
        args = []
        headers_dict = headers.to_dict()
        
        for key, value in headers_dict.items():
            # 整个 "key: value" 用引号包裹
            header_str = f'{key}: {value}'
            args.extend(['-H', f'"{header_str}"'])
        
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
        print(f"\n[HlsEngine] 执行命令:\n{' '.join(cmd)}\n")
        
        try:
            # 使用 shell=True 让 Windows 正确解析命令行
            self._process = await asyncio.create_subprocess_shell(
                ' '.join(cmd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(options.save_dir)
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
                if line_str:
                    print(line_str)
                
                # 解析进度
                progress = await self._parse_progress(line_str)
                if progress is not None:
                    if progress > last_progress:
                        last_progress = progress
                        print(f"[HlsEngine] 进度: {progress:.1f}%")
                        self._report_progress(progress, int(progress), 100)
            
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
                
                print(f"[HlsEngine] 下载完成: {output_file}")
                
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
                print(f"[HlsEngine] 错误: {error_msg}")
                
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