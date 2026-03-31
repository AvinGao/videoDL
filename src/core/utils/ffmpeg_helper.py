"""FFmpeg helper utilities for format conversion and video processing."""

import asyncio
import subprocess
import json
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import logging
import sys

from .tool_manager import tool_manager
from ..engines.base import CREATE_NO_WINDOW  # 导入常量

logger = logging.getLogger(__name__)


class FFmpegHelper:
    """FFmpeg helper for video processing."""
    
    def __init__(self, ffmpeg_path: Optional[Path] = None):
        self._ffmpeg_path = ffmpeg_path
        self._tool_checked = False
        self._ffprobe_path = None
    
    def _ensure_tool(self):
        """确保工具存在（延迟初始化）"""
        if self._tool_checked:
            return
        
        if self._ffmpeg_path:
            if self._ffmpeg_path.exists():
                self._tool_checked = True
                self._ffprobe_path = self._find_ffprobe()
                return
            else:
                raise FileNotFoundError(f"FFmpeg not found: {self._ffmpeg_path}")
        
        tool = tool_manager.ensure_tool("ffmpeg", auto_download=True)
        if tool:
            self._ffmpeg_path = tool
            self._tool_checked = True
            self._ffprobe_path = self._find_ffprobe()
        else:
            raise FileNotFoundError(
                "ffmpeg.exe not found. Please download it from https://ffmpeg.org/download.html\n"
                "The program will automatically download it when needed."
            )
    
    def _get_ffmpeg_path(self) -> Path:
        """获取 FFmpeg 路径（触发延迟初始化）"""
        self._ensure_tool()
        return self._ffmpeg_path
    
    def _get_ffprobe_path(self) -> Path:
        """获取 ffprobe 路径（触发延迟初始化）"""
        self._ensure_tool()
        return self._ffprobe_path
    
    def _find_ffprobe(self) -> Path:
        """Find ffprobe executable."""
        ffmpeg_path = self._get_ffmpeg_path()
        
        if shutil.which('ffprobe'):
            return Path(shutil.which('ffprobe'))
        
        probe_path = ffmpeg_path.parent / 'ffprobe.exe'
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
        ffprobe_path = self._get_ffprobe_path()
        cmd = [
            str(ffprobe_path),
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
                stderr=asyncio.subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW  # 添加这行
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
        info = await self.get_video_info(file_path)
        if 'format' in info and 'duration' in info['format']:
            try:
                return float(info['format']['duration'])
            except (ValueError, TypeError):
                pass
        return None
    
    async def convert_to_mp4(self, input_path: Path, output_path: Optional[Path] = None) -> Path:
        if output_path is None:
            output_path = input_path.with_suffix('.mp4')
        return await self._convert(input_path, output_path, 'mp4')
    
    async def convert_to_mkv(self, input_path: Path, output_path: Optional[Path] = None) -> Path:
        if output_path is None:
            output_path = input_path.with_suffix('.mkv')
        return await self._convert(input_path, output_path, 'matroska')
    
    async def _convert(self, input_path: Path, output_path: Path, format_name: str) -> Path:
        ffmpeg_path = self._get_ffmpeg_path()
        cmd = [
            str(ffmpeg_path),
            '-i', str(input_path),
            '-c', 'copy',
            '-f', format_name,
            '-y',
            str(output_path)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW
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
        ffmpeg_path = self._get_ffmpeg_path()
        output_path = input_path.with_suffix(f'.{output_format}')
        
        codecs = {
            'mp3': 'libmp3lame',
            'aac': 'aac',
            'wav': 'pcm_s16le',
            'flac': 'flac',
        }
        codec = codecs.get(output_format, 'copy')
        
        cmd = [
            str(ffmpeg_path),
            '-i', str(input_path),
            '-vn',
            '-acodec', codec,
            '-y',
            str(output_path)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW  # 添加这行
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