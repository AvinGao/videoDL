"""工具管理器 - 统一管理所有外部工具"""

import sys
import os
import shutil
import urllib.request
import ssl
import zipfile
import tempfile
from pathlib import Path
from typing import Optional, Dict
import logging
import fnmatch

logger = logging.getLogger(__name__)


class ToolManager:
    """统一管理所有外部工具"""
    
    # 工具配置
    TOOLS = {
        "N_m3u8DL-RE": {
            "url": "https://github.com/nilaoda/N_m3u8DL-RE/releases/latest/download/N_m3u8DL-RE.exe",
            "filename": "N_m3u8DL-RE.exe",
            "description": "M3U8/HLS 下载工具"
        },
        "yt-dlp": {
            "url": "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
            "filename": "yt-dlp.exe",
            "description": "DASH/网站视频下载工具"
        },
        "aria2c": {
            "url": "https://github.com/aria2/aria2/releases/latest/download/aria2-1.37.0-win-64bit-build1.zip",
            "filename": "aria2c.exe",
            "description": "磁力/BT 下载工具",
            "is_zip": True,
            "zip_entry": "aria2-1.37.0-win-64bit-build1/aria2c.exe"
        },
        "ffmpeg": {
            "url": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
            "filename": "ffmpeg.exe",
            "description": "视频格式转换工具",
            "is_zip": True,
            "zip_entry": "ffmpeg-*/bin/ffmpeg.exe"
        }
    }
    
    def __init__(self):
        self.tools_dir = self._get_tools_dir()
        self.tools_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_tools_dir(self) -> Path:
        """获取工具存放目录"""
        if getattr(sys, 'frozen', False):
            # 打包后的 exe 所在目录
            exe_dir = Path(sys.executable).parent
            # 优先使用 tools 文件夹
            tools_dir = exe_dir / "tools"
            if tools_dir.exists():
                return tools_dir
            # 如果没有 tools 文件夹，直接使用 exe 所在目录
            return exe_dir
        else:
            # 开发环境，使用项目根目录的 tools 文件夹
            return Path(__file__).parent.parent.parent.parent / "tools"
    
    def get_tool_path(self, tool_name: str) -> Optional[Path]:
        """获取工具路径，如果不存在返回 None"""
        config = self.TOOLS.get(tool_name)
        if not config:
            return None
        
        # 1. 检查 tools 目录
        tool_path = self.tools_dir / config["filename"]
        if tool_path.exists():
            return tool_path
        
        # 2. 检查 exe 同级目录（兼容旧版本）
        if getattr(sys, 'frozen', False):
            exe_dir = Path(sys.executable).parent
            alt_path = exe_dir / config["filename"]
            if alt_path.exists():
                return alt_path
        
        # 3. 检查当前工作目录
        current_path = Path.cwd() / config["filename"]
        if current_path.exists():
            return current_path
        
        # 4. 检查 PATH 环境变量
        if shutil.which(config["filename"]):
            return Path(shutil.which(config["filename"]))
        
        return None
    
    def ensure_tool(self, tool_name: str, auto_download: bool = True) -> Optional[Path]:
        """确保指定的工具存在，必要时自动下载"""
        # 先检查是否已存在
        tool_path = self.get_tool_path(tool_name)
        if tool_path:
            print(f"[ToolManager] 找到 {tool_name}: {tool_path}")
            return tool_path
        
        if not auto_download:
            return None
        
        # 自动下载
        config = self.TOOLS.get(tool_name)
        if not config:
            print(f"[ToolManager] 未知工具: {tool_name}")
            return None
        
        print(f"[ToolManager] 未找到 {tool_name}，正在自动下载...")
        return self._download_tool(tool_name)
    
    def _download_tool(self, tool_name: str) -> Optional[Path]:
        """下载工具"""
        config = self.TOOLS[tool_name]
        target_path = self.tools_dir / config["filename"]
        
        try:
            print(f"[ToolManager] 下载: {config['url']}")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建忽略 SSL 验证的上下文
            ssl_context = ssl._create_unverified_context()
            
            # 如果是 ZIP 文件，先下载到临时文件
            if config.get("is_zip"):
                temp_file = Path(tempfile.gettempdir()) / f"{tool_name}.tmp.zip"
                urllib.request.urlretrieve(config["url"], temp_file, context=ssl_context)
                
                # 解压并提取
                with zipfile.ZipFile(temp_file, 'r') as zf:
                    for file_info in zf.filelist:
                        if fnmatch.fnmatch(file_info.filename, config["zip_entry"]):
                            with zf.open(file_info) as source, open(target_path, 'wb') as target:
                                target.write(source.read())
                            break
                
                temp_file.unlink()
            else:
                # 直接下载 exe
                urllib.request.urlretrieve(config["url"], target_path, context=ssl_context)
            
            print(f"[ToolManager] 下载完成: {target_path}")
            return target_path
            
        except Exception as e:
            print(f"[ToolManager] 下载失败: {e}")
            return None


# 全局实例
tool_manager = ToolManager()