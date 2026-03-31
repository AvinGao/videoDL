"""Live stream recording engine using FFmpeg."""

import asyncio
import subprocess
import shutil
from pathlib import Path
from typing import Optional, List, Dict
import logging
import time
import re
from datetime import datetime, timedelta

from .base import BaseEngine
from ..models.download import DownloadOptions, DownloadResult
from ..models.headers import RequestHeaders
from ..models.link import LinkCategory

logger = logging.getLogger(__name__)


class LiveEngine(BaseEngine):
    """Live stream recording engine."""
    
    def __init__(self, ffmpeg_path: Optional[Path] = None):
        super().__init__()
        self._ffmpeg_path = ffmpeg_path or self._find_ffmpeg()
        self._process: Optional[asyncio.subprocess.Process] = None
        self._record_start_time: Optional[datetime] = None
    
    def _find_ffmpeg(self) -> Path:
        """Find FFmpeg in PATH."""
        if shutil.which('ffmpeg'):
            return Path(shutil.which('ffmpeg'))
        
        # Check common locations
        common_paths = [
            Path('C:/ffmpeg/bin/ffmpeg.exe'),
            Path('C:/Program Files/ffmpeg/bin/ffmpeg.exe'),
            Path.home() / 'ffmpeg/bin/ffmpeg.exe',
            Path('/usr/local/bin/ffmpeg'),
            Path('/usr/bin/ffmpeg'),
        ]
        
        for path in common_paths:
            if path.exists():
                return path
        
        raise RuntimeError("FFmpeg not found. Please install FFmpeg and add it to PATH.")
    
    def _headers_to_ffmpeg(self, headers: RequestHeaders) -> str:
        """Convert RequestHeaders to FFmpeg headers string."""
        headers_dict = headers.to_dict()
        if not headers_dict:
            return ""
        
        header_parts = []
        for key, value in headers_dict.items():
            header_parts.append(f"{key}: {value}")
        
        return "\r\n".join(header_parts)
    
    def _options_to_args(self, options: DownloadOptions, is_live: bool = True) -> List[str]:
        """Convert DownloadOptions to FFmpeg arguments."""
        args = []
        
        # Input format for live streams
        if is_live:
            args.extend(['-re', '-i'])
        else:
            args.extend(['-i'])
        
        # Headers for HLS/HTTP streams
        if options.auto_referer:
            args.extend(['-headers', self._headers_to_ffmpeg(RequestHeaders())])
        
        # Codec copy (no re-encoding)
        args.extend(['-c', 'copy'])
        
        # Output format
        if options.output_format == 'mp4':
            args.extend(['-f', 'mp4'])
        elif options.output_format == 'mkv':
            args.extend(['-f', 'matroska'])
        
        # Fast start for MP4
        if options.output_format == 'mp4':
            args.extend(['-movflags', 'faststart'])
        
        # Overwrite output
        args.append('-y')
        
        return args
    
    async def _parse_progress(self, line: str) -> Optional[float]:
        """Parse progress from FFmpeg output."""
        # Pattern: frame= 1234 fps= 25 q=-1.0 size=  1024kB time=00:00:45.67
        import re
        
        match = re.search(r'time=(\d{2}):(\d{2}):(\d{2}\.\d+)', line)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = float(match.group(3))
            current_seconds = hours * 3600 + minutes * 60 + seconds
            
            # If we know expected duration (for VOD), calculate progress
            # For live streams, we just report elapsed time
            if self._record_start_time:
                elapsed = current_seconds
                self._report_progress(0, int(elapsed), 0)  # No max for live
                return None
        
        return None
    
    async def record(
        self,
        url: str,
        options: DownloadOptions,
        headers: Optional[RequestHeaders] = None,
        duration_limit: Optional[int] = None
    ) -> DownloadResult:
        """Record live stream."""
        start_time = time.time()
        self._record_start_time = datetime.now()
        self.reset_cancel()
        
        output_path = self._get_output_path(url, options, "live_recording")
        
        # Build command
        cmd = [str(self._ffmpeg_path)]
        
        # Add headers if provided
        if headers:
            cmd.extend(['-headers', self._headers_to_ffmpeg(headers)])
        
        # Input URL
        cmd.append('-i')
        cmd.append(url)
        
        # Output options
        cmd.extend(self._options_to_args(options, is_live=True))
        
        # Output file
        cmd.append(str(output_path))
        
        logger.debug(f"Running command: {' '.join(cmd)}")
        
        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Create task for duration limit if specified
            if duration_limit:
                asyncio.create_task(self._stop_after_duration(duration_limit))
            
            # Read stderr for progress
            async for line in self._process.stderr:
                if self._cancelled:
                    self._process.terminate()
                    break
                
                line_str = line.decode('utf-8', errors='ignore').strip()
                await self._parse_progress(line_str)
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
        """Stop recording after specified duration."""
        await asyncio.sleep(duration_seconds)
        if self._process and self._process.returncode is None:
            self._process.terminate()
    
    def _get_output_path(
        self,
        url: str,
        options: DownloadOptions,
        default_name: str
    ) -> Path:
        """Generate output path with timestamp."""
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
        """Main download method for live streams."""
        self._current_task_id = task_id
        
        # Parse duration limit if specified
        duration = None
        if options.live_duration_limit:
            parts = options.live_duration_limit.split(':')
            if len(parts) == 3:
                duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        
        return await self.record(url, options, headers, duration)
    
    def supported_categories(self) -> List[LinkCategory]:
        """Return supported categories."""
        return [LinkCategory.LIVE]
    
    def cancel(self, task_id: Optional[str] = None):
        """Cancel recording."""
        super().cancel(task_id)
        if self._process:
            self._process.terminate()