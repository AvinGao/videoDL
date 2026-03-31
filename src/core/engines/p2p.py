"""P2P download engine for magnet links and torrents using aria2."""

import asyncio
import subprocess
import shutil
import tempfile
import zipfile
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


class P2pEngine(BaseEngine):
    """P2P download engine using aria2."""
    
    # aria2 GitHub release URL
    ARIA2_URL = "https://github.com/aria2/aria2/releases/latest/download/aria2-1.37.0-win-64bit-build1.zip"
    
    def __init__(self, tool_path: Optional[Path] = None):
        super().__init__()
        self._tool_path = tool_path or self._find_or_download_tool()
        self._process: Optional[asyncio.subprocess.Process] = None
    
    def _find_or_download_tool(self) -> Path:
        """Find aria2c in PATH or download it."""
        tool_name = "aria2c"
        
        if shutil.which(tool_name):
            return Path(shutil.which(tool_name))
        
        # Check in resources directory
        resource_path = Path(__file__).parent.parent.parent.parent / "resources" / f"{tool_name}.exe"
        if resource_path.exists():
            return resource_path
        
        # Check in temp directory
        temp_path = Path(tempfile.gettempdir()) / "aria2" / f"{tool_name}.exe"
        if temp_path.exists():
            return temp_path
        
        # Download the tool
        self._download_tool(temp_path)
        return temp_path
    
    def _download_tool(self, target_path: Path):
        """Download aria2 from GitHub."""
        logger.info("Downloading aria2...")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        zip_path = target_path.parent / "aria2.zip"
        
        try:
            urllib.request.urlretrieve(self.ARIA2_URL, zip_path)
            
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(target_path.parent)
            
            # Find aria2c.exe in extracted files
            for exe in target_path.parent.glob("**/aria2c.exe"):
                shutil.copy(exe, target_path)
                break
            
            zip_path.unlink()
            target_path.chmod(0o755)
            logger.info("aria2 downloaded successfully")
        except Exception as e:
            logger.error(f"Failed to download aria2: {e}")
            raise RuntimeError(f"Cannot download aria2: {e}")
    
    def _headers_to_args(self, headers: RequestHeaders) -> List[str]:
        """Convert RequestHeaders to aria2 arguments."""
        args = []
        headers_dict = headers.to_dict()
        
        for key, value in headers_dict.items():
            args.extend(['--header', f'{key}: {value}'])
        
        return args
    
    def _options_to_args(self, options: DownloadOptions) -> List[str]:
        """Convert DownloadOptions to aria2 arguments."""
        args = []
        
        # Directory
        args.extend(['--dir', str(options.save_dir)])
        
        # Connection settings
        args.extend(['--max-connection-per-server', str(options.thread_count)])
        args.extend(['--split', str(options.thread_count)])
        args.extend(['--min-split-size', '1M'])
        
        # Retry
        args.extend(['--max-tries', str(options.retry_count + 1)])
        args.extend(['--retry-wait', '5'])
        
        # Timeout
        args.extend(['--timeout', str(options.timeout_seconds)])
        
        # Continue (resume)
        args.append('--continue')
        
        # Auto file name
        args.append('--auto-file-renaming=false')
        
        # Console log level
        args.extend(['--console-log-level', 'error'])
        
        # Download result
        args.append('--download-result=default')
        
        # No seed after download
        args.append('--seed-time=0')
        
        return args
    
    async def _parse_progress(self, line: str, total_size: int) -> Optional[float]:
        """Parse progress from aria2 output."""
        # Pattern: [#1 45%] 10.2MiB/22.5MiB
        import re
        
        match = re.search(r'\[#\d+\s+(\d+)%\]', line)
        if match:
            return float(match.group(1))
        
        # Pattern with size: (10.2MiB/22.5MiB)
        match = re.search(r'\(([\d.]+)([KMGT]?iB)/([\d.]+)([KMGT]?iB)\)', line)
        if match:
            current = self._parse_size(match.group(1), match.group(2))
            total = self._parse_size(match.group(3), match.group(4))
            if total > 0:
                return (current / total) * 100
        
        return None
    
    def _parse_size(self, size: str, unit: str) -> int:
        """Parse size string to bytes."""
        size = float(size)
        multipliers = {'KiB': 1024, 'MiB': 1024**2, 'GiB': 1024**3, 'TiB': 1024**4}
        
        if unit in multipliers:
            return int(size * multipliers[unit])
        return int(size)
    
    async def download_magnet(
        self,
        magnet_url: str,
        options: DownloadOptions,
        headers: Optional[RequestHeaders] = None
    ) -> DownloadResult:
        """Download magnet link."""
        return await self._download(magnet_url, options, headers, is_magnet=True)
    
    async def download_torrent(
        self,
        torrent_path: Path,
        options: DownloadOptions,
        headers: Optional[RequestHeaders] = None
    ) -> DownloadResult:
        """Download torrent file."""
        return await self._download(str(torrent_path), options, headers, is_torrent=True)
    
    async def _download(
        self,
        input_str: str,
        options: DownloadOptions,
        headers: Optional[RequestHeaders],
        is_magnet: bool = False,
        is_torrent: bool = False
    ) -> DownloadResult:
        """Execute P2P download."""
        start_time = time.time()
        self._current_task_id = None
        self.reset_cancel()
        
        # Build command
        cmd = [str(self._tool_path)]
        
        # Input
        if is_magnet:
            cmd.append(input_str)
        elif is_torrent:
            cmd.extend(['--torrent-file', input_str])
        else:
            cmd.append(input_str)
        
        # Headers (for HTTP trackers)
        if headers:
            cmd.extend(self._headers_to_args(headers))
        
        # Options
        cmd.extend(self._options_to_args(options))
        
        logger.debug(f"Running command: {' '.join(cmd)}")
        
        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=options.save_dir
            )
            
            last_progress = 0
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
                
                progress = await self._parse_progress(line_str, 0)
                if progress is not None and progress > last_progress:
                    last_progress = progress
                    self._report_progress(progress, int(progress), 100)
                
                logger.debug(line_str)
            
            await self._process.wait()
            
            if self._process.returncode == 0:
                # Find downloaded file
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
        """Find the downloaded output file."""
        # Look for newest file in directory
        files = list(options.save_dir.glob('*'))
        if files:
            newest = max(files, key=lambda p: p.stat().st_mtime)
            return newest
        
        return None
    
    def get_torrent_files(self, torrent_path: Path) -> List[str]:
        """Get list of files in a torrent."""
        import subprocess
        
        cmd = [str(self._tool_path), '--show-files', '--torrent-file', str(torrent_path)]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                # Parse output to extract file list
                files = []
                for line in result.stdout.split('\n'):
                    if '|' in line and 'file' in line.lower():
                        parts = line.split('|')
                        if len(parts) >= 3:
                            files.append(parts[2].strip())
                return files
        except Exception as e:
            logger.debug(f"Failed to get torrent files: {e}")
        
        return []
    
    async def download(
        self,
        url: str,
        options: DownloadOptions,
        headers: Optional[RequestHeaders] = None,
        task_id: Optional[str] = None
    ) -> DownloadResult:
        """Main download method."""
        if url.startswith('magnet:'):
            return await self.download_magnet(url, options, headers)
        else:
            return await self.download_torrent(Path(url), options, headers)
    
    def supported_categories(self) -> List[LinkCategory]:
        """Return supported categories."""
        return [LinkCategory.MAGNET, LinkCategory.TORRENT]
    
    def cancel(self, task_id: Optional[str] = None):
        """Cancel download."""
        super().cancel(task_id)
        if self._process:
            self._process.terminate()