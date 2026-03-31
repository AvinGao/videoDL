"""Direct download engine for single file videos with multi-thread support."""

import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import Optional, List
import logging
import time
from urllib.parse import urlparse

from .base import BaseEngine
from ..models.download import DownloadOptions, DownloadResult
from ..models.headers import RequestHeaders
from ..models.link import LinkCategory

logger = logging.getLogger(__name__)


class DirectDownloadEngine(BaseEngine):
    """Direct download engine with multi-thread chunk download support."""
    
    def __init__(self):
        super().__init__()
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=32,           # 最大连接数
                ttl_dns_cache=300,
                enable_cleanup_closed=True
            )
            timeout = aiohttp.ClientTimeout(
                total=None,
                connect=30,
                sock_read=600
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout
            )
        return self._session
    
    async def _get_file_size(self, url: str, headers: dict) -> Optional[int]:
        """Get file size via HEAD request."""
        try:
            # 创建临时会话用于 HEAD 请求
            async with aiohttp.ClientSession() as session:
                async with session.head(url, headers=headers, allow_redirects=True) as response:
                    if response.status == 200:
                        content_length = response.headers.get('Content-Length')
                        if content_length:
                            return int(content_length)
                return None
        except Exception as e:
            print(f"[DirectEngine] 获取文件大小失败: {e}")
            return None
    
    async def _download_chunk(
        self,
        url: str,
        start: int,
        end: int,
        chunk_path: Path,
        headers: dict,
        semaphore: asyncio.Semaphore,
        retry_count: int = 3
    ) -> bool:
        """Download a single chunk with retry."""
        for attempt in range(retry_count):
            async with semaphore:
                if self._cancelled:
                    return False
                
                try:
                    # 为每个分块创建独立的会话
                    connector = aiohttp.TCPConnector(limit=1)
                    timeout = aiohttp.ClientTimeout(total=120, connect=30)
                    
                    chunk_headers = headers.copy()
                    chunk_headers['Range'] = f'bytes={start}-{end}'
                    
                    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                        async with session.get(url, headers=chunk_headers) as response:
                            if response.status in (200, 206):
                                data = await response.read()
                                
                                async with aiofiles.open(chunk_path, 'wb') as f:
                                    await f.write(data)
                                
                                # 打印进度
                                size_mb = (end - start + 1) / (1024 * 1024)
                                print(f"[DirectEngine] 分块 {start//(1024*1024)}MB 完成 ({size_mb:.1f}MB)")
                                return True
                            else:
                                print(f"[DirectEngine] 分块 {start}-{end} 失败: HTTP {response.status}")
                                return False
                                
                except asyncio.CancelledError:
                    return False
                except Exception as e:
                    print(f"[DirectEngine] 分块 {start}-{end} 尝试 {attempt+1}/{retry_count} 失败: {e}")
                    if attempt < retry_count - 1:
                        await asyncio.sleep(2)
                    continue
            
            return False
        
        return False
    
    async def _merge_chunks(self, chunk_paths: List[Path], output_path: Path) -> bool:
        """Merge downloaded chunks into final file."""
        try:
            async with aiofiles.open(output_path, 'wb') as out_file:
                for chunk_path in sorted(chunk_paths, key=lambda p: int(p.stem.split('_')[-1])):
                    async with aiofiles.open(chunk_path, 'rb') as in_file:
                        data = await in_file.read()
                        await out_file.write(data)
                    chunk_path.unlink()
            return True
        except Exception as e:
            print(f"[DirectEngine] 合并分块失败: {e}")
            return False
    
    async def _single_thread_download(
        self,
        url: str,
        output_path: Path,
        headers: dict,
        options: DownloadOptions
    ) -> bool:
        """Single thread download."""
        for attempt in range(options.retry_count + 1):
            if self._cancelled:
                return False
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        if response.status != 200:
                            if attempt < options.retry_count:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return False
                        
                        total_size = int(response.headers.get('Content-Length', 0))
                        downloaded = 0
                        last_report = time.time()
                        last_bytes = 0
                        
                        async with aiofiles.open(output_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(256 * 1024):
                                if self._cancelled:
                                    return False
                                
                                await f.write(chunk)
                                downloaded += len(chunk)
                                
                                if total_size > 0:
                                    percent = (downloaded / total_size) * 100
                                    self._report_progress(percent, downloaded, total_size)
                                
                                now = time.time()
                                if now - last_report >= 0.5:
                                    speed = (downloaded - last_bytes) / (now - last_report)
                                    self._report_speed(speed)
                                    last_report = now
                                    last_bytes = downloaded
                        
                        return True
                    
            except asyncio.CancelledError:
                return False
            except Exception as e:
                print(f"[DirectEngine] 下载尝试 {attempt+1} 失败: {e}")
                if attempt < options.retry_count:
                    await asyncio.sleep(2 ** attempt)
        
        return False
    
    async def download(
        self,
        url: str,
        options: DownloadOptions,
        headers: Optional[RequestHeaders] = None,
        task_id: Optional[str] = None
    ) -> DownloadResult:
        """Execute direct download."""
        start_time = time.time()
        self._current_task_id = task_id
        self.reset_cancel()
        
        # 生成输出路径
        if options.save_name:
            filename = options.save_name
        else:
            parsed = urlparse(url)
            filename = parsed.path.split('/')[-1] or "video"
            if '.' not in filename:
                filename += f".{options.output_format}"
        
        output_path = options.save_dir / filename
        
        # 检查文件是否已存在
        if output_path.exists() and not options.overwrite:
            return DownloadResult(
                success=True,
                file_path=output_path,
                file_size_bytes=output_path.stat().st_size,
                duration_seconds=0,
                url=url,
                category=LinkCategory.DIRECT,
                task_id=task_id
            )
        
        # 准备请求头
        headers_dict = {}
        if headers:
            headers_dict = headers.to_dict()
        elif options.auto_referer:
            parsed = urlparse(url)
            headers_dict['Referer'] = f"{parsed.scheme}://{parsed.netloc}"
        
        if 'User-Agent' not in headers_dict:
            headers_dict['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        
        print(f"[DirectEngine] 开始下载: {url}")
        
        try:
            # 获取文件大小
            file_size = await self._get_file_size(url, headers_dict)
            
            # 对于小文件或未知大小，使用单线程
            use_multi_thread = (
                file_size and 
                options.thread_count > 1 and 
                file_size > 20 * 1024 * 1024  # 大于 20MB 才用多线程
            )
            
            if use_multi_thread:
                print(f"[DirectEngine] 使用多线程下载，文件大小 {file_size/(1024*1024):.2f} MB，线程数 {options.thread_count}")
                
                # 多线程分块下载
                chunk_size = file_size // options.thread_count
                chunk_paths = []
                tasks = []
                semaphore = asyncio.Semaphore(options.thread_count)
                
                for i in range(options.thread_count):
                    start = i * chunk_size
                    end = start + chunk_size - 1 if i < options.thread_count - 1 else file_size - 1
                    chunk_path = options.save_dir / f"{output_path.stem}_chunk_{i}.part"
                    chunk_paths.append(chunk_path)
                    
                    task = self._download_chunk(url, start, end, chunk_path, headers_dict, semaphore)
                    tasks.append(task)
                
                # 并发下载所有分块
                results = await asyncio.gather(*tasks)
                success_count = sum(1 for r in results if r is True)
                
                print(f"[DirectEngine] 分块下载完成: {success_count}/{options.thread_count}")
                
                if success_count == options.thread_count:
                    # 合并分块
                    if await self._merge_chunks(chunk_paths, output_path):
                        duration = time.time() - start_time
                        file_size = output_path.stat().st_size
                        speed_mbps = (file_size / (1024 * 1024)) / duration if duration > 0 else 0
                        print(f"[DirectEngine] 多线程下载完成: {file_size/(1024*1024):.2f} MB, "
                              f"耗时 {duration:.1f}s, 速度 {speed_mbps:.1f} MB/s")
                        
                        return DownloadResult(
                            success=True,
                            file_path=output_path,
                            file_size_bytes=file_size,
                            duration_seconds=duration,
                            url=url,
                            category=LinkCategory.DIRECT,
                            task_id=task_id
                        )
                else:
                    # 清理分块
                    for cp in chunk_paths:
                        if cp.exists():
                            cp.unlink()
            
            # 使用单线程下载
            print(f"[DirectEngine] 使用单线程下载")
            if await self._single_thread_download(url, output_path, headers_dict, options):
                duration = time.time() - start_time
                file_size = output_path.stat().st_size if output_path.exists() else 0
                speed_mbps = (file_size / (1024 * 1024)) / duration if duration > 0 else 0
                print(f"[DirectEngine] 下载完成: {file_size/(1024*1024):.2f} MB, "
                      f"耗时 {duration:.1f}s, 速度 {speed_mbps:.1f} MB/s")
                
                return DownloadResult(
                    success=True,
                    file_path=output_path,
                    file_size_bytes=file_size,
                    duration_seconds=duration,
                    url=url,
                    category=LinkCategory.DIRECT,
                    task_id=task_id
                )
            
            # 清理失败的文件
            if output_path.exists():
                output_path.unlink()
            
            return DownloadResult(
                success=False,
                error_message="Download failed",
                duration_seconds=time.time() - start_time,
                url=url,
                category=LinkCategory.DIRECT,
                task_id=task_id
            )
            
        except asyncio.CancelledError:
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            return DownloadResult(
                success=False,
                error_message="Download cancelled",
                duration_seconds=time.time() - start_time,
                url=url,
                category=LinkCategory.DIRECT,
                task_id=task_id
            )
        except Exception as e:
            logger.exception("Direct download failed")
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            return DownloadResult(
                success=False,
                error_message=str(e),
                duration_seconds=time.time() - start_time,
                url=url,
                category=LinkCategory.DIRECT,
                task_id=task_id
            )
    
    def supported_categories(self) -> List[LinkCategory]:
        return [LinkCategory.DIRECT]
    
    def cancel(self, task_id: Optional[str] = None):
        super().cancel(task_id)