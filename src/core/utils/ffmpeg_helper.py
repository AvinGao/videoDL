"""FFmpeg helper utilities for format conversion and video processing."""

import asyncio
import subprocess
import json
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class FFmpegHelper:
    """FFmpeg helper for video processing."""
    
    def __init__(self, ffmpeg_path: Optional[Path] = None):
        self._ffmpeg_path = ffmpeg_path or self._find_ffmpeg()
        self._ffprobe_path = self._find_ffprobe()
    
    def _find_ffmpeg(self) -> Path:
        """Find FFmpeg executable."""
        if shutil.which('ffmpeg'):
            return Path(shutil.which('ffmpeg'))
        
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
    
    def _find_ffprobe(self) -> Path:
        """Find ffprobe executable."""
        if shutil.which('ffprobe'):
            return Path(shutil.which('ffprobe'))
        
        # Try same directory as ffmpeg
        probe_path = self._ffmpeg_path.parent / 'ffprobe.exe'
        if probe_path.exists():
            return probe_path
        
        common_paths = [
            Path('C:/ffmpeg/bin/ffprobe.exe'),
            Path('/usr/local/bin/ffprobe'),
            Path('/usr/bin/ffprobe'),
        ]
        
        for path in common_paths:
            if path.exists():
                return path
        
        raise RuntimeError("ffprobe not found. Please install FFmpeg and add it to PATH.")
    
    async def get_video_info(self, file_path: Path) -> Dict:
        """Get video information using ffprobe."""
        cmd = [
            str(self._ffprobe_path),
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(file_path)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return json.loads(stdout.decode('utf-8'))
            else:
                logger.error(f"ffprobe failed: {stderr.decode()}")
                return {}
                
        except Exception as e:
            logger.error(f"Failed to get video info: {e}")
            return {}
    
    async def get_duration(self, file_path: Path) -> Optional[float]:
        """Get video duration in seconds."""
        info = await self.get_video_info(file_path)
        
        if 'format' in info and 'duration' in info['format']:
            try:
                return float(info['format']['duration'])
            except (ValueError, TypeError):
                pass
        
        return None
    
    async def get_resolution(self, file_path: Path) -> Optional[Tuple[int, int]]:
        """Get video resolution (width, height)."""
        info = await self.get_video_info(file_path)
        
        for stream in info.get('streams', []):
            if stream.get('codec_type') == 'video':
                width = stream.get('width')
                height = stream.get('height')
                if width and height:
                    return (width, height)
        
        return None
    
    async def convert_to_mp4(self, input_path: Path, output_path: Optional[Path] = None) -> Path:
        """Convert video to MP4 format."""
        if output_path is None:
            output_path = input_path.with_suffix('.mp4')
        
        return await self._convert(input_path, output_path, 'mp4')
    
    async def convert_to_mkv(self, input_path: Path, output_path: Optional[Path] = None) -> Path:
        """Convert video to MKV format."""
        if output_path is None:
            output_path = input_path.with_suffix('.mkv')
        
        return await self._convert(input_path, output_path, 'matroska')
    
    async def convert_to_mov(self, input_path: Path, output_path: Optional[Path] = None) -> Path:
        """Convert video to MOV format."""
        if output_path is None:
            output_path = input_path.with_suffix('.mov')
        
        return await self._convert(input_path, output_path, 'mov')
    
    async def convert_to_webm(self, input_path: Path, output_path: Optional[Path] = None) -> Path:
        """Convert video to WebM format."""
        if output_path is None:
            output_path = input_path.with_suffix('.webm')
        
        return await self._convert(input_path, output_path, 'webm')
    
    async def _convert(self, input_path: Path, output_path: Path, format_name: str) -> Path:
        """Internal conversion method."""
        cmd = [
            str(self._ffmpeg_path),
            '-i', str(input_path),
            '-c', 'copy',  # Copy codec without re-encoding
            '-f', format_name,
            '-y',  # Overwrite output
            str(output_path)
        ]
        
        logger.debug(f"Running: {' '.join(cmd)}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"Converted {input_path} to {output_path}")
                return output_path
            else:
                error_msg = stderr.decode('utf-8', errors='ignore')[:500]
                raise RuntimeError(f"Conversion failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Conversion error: {e}")
            raise
    
    async def extract_audio(self, input_path: Path, output_format: str = "mp3") -> Path:
        """Extract audio from video."""
        output_path = input_path.with_suffix(f'.{output_format}')
        
        cmd = [
            str(self._ffmpeg_path),
            '-i', str(input_path),
            '-vn',  # No video
            '-acodec', self._get_audio_codec(output_format),
            '-y',
            str(output_path)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"Extracted audio to {output_path}")
                return output_path
            else:
                error_msg = stderr.decode('utf-8', errors='ignore')[:500]
                raise RuntimeError(f"Audio extraction failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Audio extraction error: {e}")
            raise
    
    def _get_audio_codec(self, format_name: str) -> str:
        """Get audio codec for given format."""
        codecs = {
            'mp3': 'libmp3lame',
            'aac': 'aac',
            'm4a': 'aac',
            'wav': 'pcm_s16le',
            'flac': 'flac',
            'ogg': 'libvorbis',
        }
        return codecs.get(format_name, 'copy')
    
    async def embed_subtitle(self, input_path: Path, subtitle_path: Path) -> Path:
        """Embed subtitle into video."""
        output_path = input_path.with_suffix('.subbed.mp4')
        
        cmd = [
            str(self._ffmpeg_path),
            '-i', str(input_path),
            '-i', str(subtitle_path),
            '-c', 'copy',
            '-c:s', 'mov_text',
            '-metadata:s:s:0', 'language=eng',
            '-y',
            str(output_path)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"Embedded subtitle to {output_path}")
                return output_path
            else:
                error_msg = stderr.decode('utf-8', errors='ignore')[:500]
                raise RuntimeError(f"Subtitle embedding failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Subtitle embedding error: {e}")
            raise
    
    async def merge_audio_video(self, video_path: Path, audio_path: Path) -> Path:
        """Merge separate audio and video files."""
        output_path = video_path.with_suffix('.merged.mp4')
        
        cmd = [
            str(self._ffmpeg_path),
            '-i', str(video_path),
            '-i', str(audio_path),
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-y',
            str(output_path)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"Merged to {output_path}")
                return output_path
            else:
                error_msg = stderr.decode('utf-8', errors='ignore')[:500]
                raise RuntimeError(f"Merge failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Merge error: {e}")
            raise
    
    async def compress(self, input_path: Path, output_path: Optional[Path] = None, crf: int = 23) -> Path:
        """Compress video using H.264 with specified CRF."""
        if output_path is None:
            output_path = input_path.with_suffix('.compressed.mp4')
        
        cmd = [
            str(self._ffmpeg_path),
            '-i', str(input_path),
            '-c:v', 'libx264',
            '-crf', str(crf),
            '-preset', 'medium',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-y',
            str(output_path)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"Compressed to {output_path}")
                return output_path
            else:
                error_msg = stderr.decode('utf-8', errors='ignore')[:500]
                raise RuntimeError(f"Compression failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Compression error: {e}")
            raise