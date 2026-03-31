"""工具管理器 - 自动下载和管理外部工具"""

import sys
import os
import ssl
import urllib.request
import zipfile
import subprocess
from pathlib import Path
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class ToolManager:
    """管理所有外部工具"""
    
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
            return Path(sys.executable).parent / "tools"
        else:
            # 开发环境
            return Path(__file__).parent.parent.parent.parent / "tools"
    
    def _download_file(self, url: str, target_path: Path) -> bool:
        """下载文件"""
        try:
            print(f"正在下载: {url}")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建忽略 SSL 验证的上下文
            ssl_context = ssl._create_unverified_context()
            urllib.request.urlretrieve(url, target_path, context=ssl_context)
            print(f"下载完成: {target_path}")
            return True
        except Exception as e:
            print(f"下载失败: {e}")
            return False
    
    def _extract_zip(self, zip_path: Path, target_path: Path, entry_pattern: str) -> bool:
        """解压 ZIP 并提取指定文件"""
        try:
            import zipfile
            print(f"正在解压: {zip_path}")
            
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # 查找匹配的文件
                for file_info in zf.filelist:
                    import fnmatch
                    if fnmatch.fnmatch(file_info.filename, entry_pattern):
                        # 提取文件
                        with zf.open(file_info) as source, open(target_path, 'wb') as target:
                            target.write(source.read())
                        print(f"提取完成: {target_path}")
                        return True
            
            print(f"未在 ZIP 中找到匹配的文件: {entry_pattern}")
            return False
        except Exception as e:
            print(f"解压失败: {e}")
            return False
    
    def ensure_tool(self, tool_name: str) -> Optional[Path]:
        """确保工具存在，如果不存在则自动下载"""
        if tool_name not in self.TOOLS:
            print(f"未知工具: {tool_name}")
            return None
        
        config = self.TOOLS[tool_name]
        filename = config["filename"]
        tool_path = self.tools_dir / filename
        
        # 检查是否已存在
        if tool_path.exists():
            print(f"找到 {tool_name}: {tool_path}")
            return tool_path
        
        print(f"未找到 {tool_name}，正在自动下载...")
        
        # 下载
        temp_file = self.tools_dir / f"{tool_name}.tmp"
        
        if not self._download_file(config["url"], temp_file):
            print(f"下载 {tool_name} 失败")
            return None
        
        # 如果是 ZIP 文件，需要解压
        if config.get("is_zip"):
            if self._extract_zip(temp_file, tool_path, config["zip_entry"]):
                temp_file.unlink()
                return tool_path
            else:
                return None
        else:
            # 直接重命名
            temp_file.rename(tool_path)
            return tool_path
    
    def ensure_all_tools(self) -> Dict[str, bool]:
        """确保所有工具都存在"""
        results = {}
        for tool_name in self.TOOLS:
            result = self.ensure_tool(tool_name)
            results[tool_name] = result is not None
            if result:
                print(f"✓ {tool_name}: {result}")
            else:
                print(f"✗ {tool_name}: 下载失败")
        return results
    
    def get_tool_path(self, tool_name: str) -> Optional[Path]:
        """获取工具路径，如果不存在则返回 None"""
        config = self.TOOLS.get(tool_name)
        if not config:
            return None
        
        tool_path = self.tools_dir / config["filename"]
        if tool_path.exists():
            return tool_path
        return None


# 全局实例
tool_manager = ToolManager()