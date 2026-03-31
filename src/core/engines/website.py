"""Website video extraction engine using yt-dlp.

This engine handles website URLs like YouTube, Bilibili, etc.
It extracts video information and downloads using yt-dlp.
"""

import asyncio
import subprocess
import shutil
import tempfile
import urllib.request
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging
import time

from .base import BaseEngine
from ..models.download import DownloadOptions, DownloadResult
from ..models.headers import RequestHeaders
from ..models.link import LinkCategory
from ..models.video import VideoInfo, FormatInfo, SubtitleInfo, AudioTrackInfo

logger = logging.getLogger(__name__)


class WebsiteEngine(BaseEngine):
    """Website video extraction engine using yt-dlp.
    
    Supports:
    - YouTube
    - Bilibili
    - Youku, Tencent Video, iQiyi
    - Douyin/TikTok
    - Twitter/X
    - Twitch
    - And many more sites supported by yt-dlp
    """
    
    # yt-dlp GitHub release URL
    YT_DLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
    
    def __init__(self, tool_path: Optional[Path] = None):
        super().__init__()
        self._tool_path = tool_path or self._find_or_download_tool()
        self._process: Optional[asyncio.subprocess.Process] = None
        self._extracted_info: Optional[VideoInfo] = None
    
    def _find_or_download_tool(self) -> Path:
        """Find yt-dlp in PATH or download it."""
        tool_name = "yt-dlp"
        
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
        """Download yt-dlp from GitHub."""
        logger.info("Downloading yt-dlp...")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            urllib.request.urlretrieve(self.YT_DLP_URL, target_path)
            target_path.chmod(0o755)
            logger.info("yt-dlp downloaded successfully")
        except Exception as e:
            logger.error(f"Failed to download yt-dlp: {e}")
            raise RuntimeError(f"Cannot download yt-dlp: {e}")
    
    def _headers_to_args(self, headers: RequestHeaders) -> List[str]:
        """Convert RequestHeaders to yt-dlp arguments."""
        args = []
        headers_dict = headers.to_dict()
        
        for key, value in headers_dict.items():
            args.extend(['--headers', f'{key}: {value}'])
        
        return args
    
    def _options_to_args(self, options: DownloadOptions) -> List[str]:
        """Convert DownloadOptions to yt-dlp arguments."""
        args = []
        
        # Output template
        if options.save_name:
            template = str(options.save_dir / options.save_name)
        else:
            template = str(options.save_dir / '%(title)s.%(ext)s')
        args.extend(['-o', template])
        
        # Format selection based on quality
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
        elif options.quality == '360p':
            args.extend(['-f', 'bestvideo[height<=360]+bestaudio/best[height<=360]'])
        
        # Output format
        if options.output_format == 'mp4':
            args.extend(['--merge-output-format', 'mp4'])
        elif options.output_format == 'mkv':
            args.extend(['--merge-output-format', 'mkv'])
        elif options.output_format == 'webm':
            args.extend(['--merge-output-format', 'webm'])
        
        # Retries
        args.extend(['--retries', str(options.retry_count)])
        
        # Timeout
        args.extend(['--socket-timeout', str(options.timeout_seconds)])
        
        # Overwrite
        if not options.overwrite:
            args.append('--no-overwrites')
        
        # Fragment retries
        args.extend(['--fragment-retries', str(options.retry_count)])
        
        # Skip download if file exists
        if not options.overwrite:
            args.append('--download-archive')
            args.append(str(options.save_dir / '.archive'))
        
        # Embed metadata
        args.append('--embed-metadata')
        
        # Embed thumbnail
        args.append('--embed-thumbnail')
        
        # Subtitle download
        args.append('--write-subs')
        args.append('--write-auto-subs')
        args.append('--sub-langs', 'all')
        args.append('--embed-subs')
        
        return args
    
    async def extract_video_info(
        self,
        url: str,
        headers: Optional[RequestHeaders] = None,
        task_id: Optional[str] = None
    ) -> Optional[VideoInfo]:
        """Extract video information from website URL.
        
        Args:
            url: Website URL (YouTube, Bilibili, etc.)
            headers: Optional custom headers
            task_id: Optional task identifier
            
        Returns:
            VideoInfo object with title, formats, subtitles, etc.
        """
        self._current_task_id = task_id
        
        # Build command
        cmd = [str(self._tool_path), '-J', url]  # -J for JSON output
        
        # Add headers
        if headers:
            cmd.extend(self._headers_to_args(headers))
        
        # Add cookies from browser if not provided
        if not headers or not headers.cookie:
            cmd.append('--cookies-from-browser')
            cmd.append('chrome')  # Try Chrome first, can be configurable
        
        # Add user agent
        cmd.append('--user-agent')
        cmd.append('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        logger.debug(f"Extracting info from: {url}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                data = json.loads(stdout.decode('utf-8', errors='ignore'))
                self._extracted_info = self._parse_video_info(data)
                return self._extracted_info
            else:
                error_msg = stderr.decode('utf-8', errors='ignore')[:500]
                logger.error(f"yt-dlp extraction failed: {error_msg}")
                return None
                
        except asyncio.CancelledError:
            logger.info("Video info extraction cancelled")
            return None
        except Exception as e:
            logger.error(f"Failed to extract video info: {e}")
            return None
    
    def _parse_video_info(self, data: Dict[str, Any]) -> VideoInfo:
        """Parse yt-dlp JSON output into VideoInfo."""
        formats = []
        
        for fmt in data.get('formats', []):
            # Skip non-video formats if they have no video codec
            if fmt.get('vcodec') == 'none' and fmt.get('acodec') == 'none':
                continue
                
            formats.append(FormatInfo(
                format_id=fmt.get('format_id', ''),
                resolution=fmt.get('resolution'),
                fps=fmt.get('fps'),
                codec=fmt.get('vcodec') or fmt.get('acodec'),
                bitrate=fmt.get('tbr') or fmt.get('vbr') or fmt.get('abr'),
                filesize=fmt.get('filesize'),
                url=fmt.get('url')
            ))
        
        # Extract unique resolutions
        resolutions = sorted(set(
            f.resolution for f in formats if f.resolution
        ), key=self._resolution_sort_key)
        
        # Parse subtitles
        subtitles = []
        for lang, sub_data in data.get('subtitles', {}).items():
            for sub in sub_data:
                subtitles.append(SubtitleInfo(
                    language=sub.get('name', lang),
                    code=lang,
                    url=sub.get('url'),
                    is_srt=sub.get('ext') == 'vtt'  # VTT or SRT
                ))
        
        # Parse automatic captions
        for lang, sub_data in data.get('automatic_captions', {}).items():
            for sub in sub_data:
                subtitles.append(SubtitleInfo(
                    language=f"{lang} (auto)",
                    code=lang,
                    url=sub.get('url'),
                    is_srt=sub.get('ext') == 'vtt'
                ))
        
        # Parse audio tracks
        audio_tracks = []
        for fmt in data.get('formats', []):
            if fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
                audio_tracks.append(AudioTrackInfo(
                    language=fmt.get('language', 'unknown'),
                    codec=fmt.get('acodec', 'unknown'),
                    bitrate=fmt.get('abr'),
                    channels=fmt.get('audio_channels')
                ))
        
        return VideoInfo(
            title=data.get('title', 'Unknown'),
            duration=data.get('duration'),
            thumbnail=data.get('thumbnail'),
            description=data.get('description', '')[:500],  # Limit description length
            uploader=data.get('uploader'),
            upload_date=data.get('upload_date'),
            resolutions=resolutions,
            formats=formats,
            audio_tracks=audio_tracks,
            subtitles=subtitles,
            raw_data=data
        )
    
    def _resolution_sort_key(self, resolution: str) -> int:
        """Sort key for resolutions."""
        if not resolution:
            return 0
        
        # Extract numeric height from resolution string (e.g., "1920x1080" -> 1080)
        match = re.search(r'(\d+)$', resolution)
        if match:
            return int(match.group(1))
        
        # Handle special cases
        if '4k' in resolution.lower():
            return 2160
        if '8k' in resolution.lower():
            return 4320
        
        return 0
    
    async def get_available_formats(self, url: str) -> List[Dict[str, Any]]:
        """Get list of available formats with details.
        
        Returns:
            List of format dictionaries with format_id, resolution, codec, filesize
        """
        info = await self.extract_video_info(url)
        if not info:
            return []
        
        formats = []
        for fmt in info.formats:
            formats.append({
                'format_id': fmt.format_id,
                'resolution': fmt.resolution or 'audio only',
                'codec': fmt.codec,
                'filesize': fmt.filesize,
                'filesize_mb': fmt.filesize / (1024 * 1024) if fmt.filesize else None
            })
        
        return formats
    
    async def download_format(
        self,
        url: str,
        format_id: str,
        options: DownloadOptions,
        headers: Optional[RequestHeaders] = None,
        task_id: Optional[str] = None
    ) -> DownloadResult:
        """Download a specific format by ID."""
        self._current_task_id = task_id
        self.reset_cancel()
        
        # Build command
        cmd = [str(self._tool_path)]
        
        # Input URL
        cmd.append(url)
        
        # Specific format
        cmd.extend(['-f', format_id])
        
        # Headers
        if headers:
            cmd.extend(self._headers_to_args(headers))
        
        # Options
        cmd.extend(self._options_to_args(options))
        
        # Progress
        cmd.append('--progress')
        
        # Quiet mode
        cmd.append('--quiet')
        cmd.append('--no-warnings')
        
        logger.debug(f"Downloading format {format_id} from: {url}")
        
        start_time = time.time()
        
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
                        url=url,
                        category=LinkCategory.WEBSITE
                    )
                
                line_str = line.decode('utf-8', errors='ignore').strip()
                
                # Parse progress
                progress = self._parse_progress(line_str)
                if progress is not None and progress > last_progress:
                    last_progress = progress
                    self._report_progress(progress, int(progress), 100)
                
                logger.debug(line_str)
            
            await self._process.wait()
            
            if self._process.returncode == 0:
                # Find output file
                output_path = self._find_output_file(options)
                
                duration = time.time() - start_time
                file_size = output_path.stat().st_size if output_path and output_path.exists() else 0
                
                return DownloadResult(
                    success=True,
                    file_path=output_path,
                    file_size_bytes=file_size,
                    duration_seconds=duration,
                    url=url,
                    category=LinkCategory.WEBSITE
                )
            else:
                stderr = await self._process.stderr.read()
                error_msg = stderr.decode('utf-8', errors='ignore')[:500]
                
                return DownloadResult(
                    success=False,
                    error_message=f"yt-dlp failed (code {self._process.returncode}): {error_msg}",
                    duration_seconds=time.time() - start_time,
                    url=url,
                    category=LinkCategory.WEBSITE
                )
                
        except asyncio.CancelledError:
            if self._process:
                self._process.terminate()
            return DownloadResult(
                success=False,
                error_message="Download cancelled",
                duration_seconds=time.time() - start_time,
                url=url,
                category=LinkCategory.WEBSITE
            )
        except Exception as e:
            logger.exception("Website download failed")
            return DownloadResult(
                success=False,
                error_message=str(e),
                duration_seconds=time.time() - start_time,
                url=url,
                category=LinkCategory.WEBSITE
            )
    
    def _parse_progress(self, line: str) -> Optional[float]:
        """Parse progress from yt-dlp output."""
        # Pattern: [download] 45.5% of 50.23MiB at  2.34MiB/s ETA 00:12
        match = re.search(r'\[download\]\s+([\d.]+)%', line)
        if match:
            return float(match.group(1))
        
        # Pattern for fragment downloads
        match = re.search(r'\[download\]\s+Downloading\s+(\d+)%\s+of\s+', line)
        if match:
            return float(match.group(1))
        
        return None
    
    def _find_output_file(self, options: DownloadOptions) -> Optional[Path]:
        """Find the downloaded output file."""
        if options.save_name:
            # Try common extensions
            for ext in ['mp4', 'mkv', 'webm', 'm4a', 'mp3']:
                candidate = options.save_dir / f"{options.save_name}.{ext}"
                if candidate.exists():
                    return candidate
        
        # Look for newest file in directory
        video_extensions = {'.mp4', '.mkv', '.webm', '.flv', '.avi', '.mov'}
        files = list(options.save_dir.glob('*'))
        
        # Filter to video files
        video_files = [f for f in files if f.suffix.lower() in video_extensions]
        
        if video_files:
            newest = max(video_files, key=lambda p: p.stat().st_mtime)
            return newest
        
        return None
    
    async def download(
        self,
        url: str,
        options: DownloadOptions,
        headers: Optional[RequestHeaders] = None,
        task_id: Optional[str] = None
    ) -> DownloadResult:
        """Main download method for website URLs.
        
        This method will:
        1. Extract video info
        2. Automatically select best quality
        3. Download the video
        """
        # First extract video info to get best format
        info = await self.extract_video_info(url, headers, task_id)
        
        if not info:
            return DownloadResult(
                success=False,
                error_message="Failed to extract video information",
                url=url,
                category=LinkCategory.WEBSITE
            )
        
        # Log extracted info
        logger.info(f"Extracted video: {info.title}")
        logger.info(f"Available resolutions: {', '.join(info.resolutions)}")
        
        # Find best format based on quality preference
        best_format_id = self._find_best_format_id(info, options.quality)
        
        if best_format_id:
            logger.info(f"Downloading format: {best_format_id}")
            return await self.download_format(url, best_format_id, options, headers, task_id)
        else:
            return DownloadResult(
                success=False,
                error_message="No suitable format found",
                url=url,
                category=LinkCategory.WEBSITE
            )
    
    def _find_best_format_id(self, info: VideoInfo, quality: str) -> Optional[str]:
        """Find best format ID based on quality preference."""
        if not info.formats:
            return None
        
        # Parse quality preference
        target_height = None
        if quality == 'best':
            target_height = 99999
        elif quality == 'worst':
            target_height = 0
        elif quality == '1080p':
            target_height = 1080
        elif quality == '720p':
            target_height = 720
        elif quality == '480p':
            target_height = 480
        elif quality == '360p':
            target_height = 360
        
        # Filter formats with video
        video_formats = [f for f in info.formats if f.resolution and f.resolution != 'audio only']
        
        if not video_formats:
            # No video formats, return first format (probably audio)
            return info.formats[0].format_id if info.formats else None
        
        # Sort by resolution
        if target_height == 0:  # worst quality
            video_formats.sort(key=lambda f: self._resolution_sort_key(f.resolution))
        else:  # best quality
            video_formats.sort(key=lambda f: self._resolution_sort_key(f.resolution), reverse=True)
        
        # Find format with resolution <= target_height
        for fmt in video_formats:
            height = self._resolution_sort_key(fmt.resolution)
            if target_height == 99999 or height <= target_height:
                return fmt.format_id
        
        # Fallback to first format
        return video_formats[0].format_id if video_formats else None
    
    def get_extracted_info(self) -> Optional[VideoInfo]:
        """Get the last extracted video info."""
        return self._extracted_info
    
    def supported_categories(self) -> List[LinkCategory]:
        """Return supported categories."""
        return [LinkCategory.WEBSITE]
    
    def cancel(self, task_id: Optional[str] = None):
        """Cancel download."""
        super().cancel(task_id)
        if self._process:
            self._process.terminate()