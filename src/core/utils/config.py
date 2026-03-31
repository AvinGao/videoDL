"""Configuration management."""

import yaml
import json
from pathlib import Path
from typing import Any, Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manage application configuration."""
    
    CONFIG_DIR = Path.home() / ".video_downloader"
    CONFIG_FILE = CONFIG_DIR / "config.yaml"
    
    DEFAULT_CONFIG = {
        "download": {
            "default_dir": str(Path.home() / "Downloads"),
            "default_threads": 8,
            "default_format": "mp4",
            "max_concurrent": 3,
            "retry_count": 3,
            "timeout": 30,
            "quality": "best"
        },
        "headers": {
            "default_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "auto_referer": True,
            "default_headers": {}
        },
        "tools": {
            "n_m3u8dl_re_url": "https://github.com/nilaoda/N_m3u8DL-RE/releases/latest/download/N_m3u8DL-RE.exe",
            "yt_dlp_url": "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
            "aria2_url": "https://github.com/aria2/aria2/releases/latest/download/aria2-1.37.0-win-64bit-build1.zip",
            "ffmpeg_path": "",
            "auto_update_tools": True
        },
        "history": {
            "max_records": 100,
            "save_path": str(CONFIG_DIR / "history.json")
        },
        "logging": {
            "level": "INFO",
            "file": str(CONFIG_DIR / "download.log")
        },
        "network": {
            "proxy": None,
            "verify_ssl": True,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
        "ui": {
            "show_progress": True,
            "theme": "dark",
            "max_tasks_display": 10
        }
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self.CONFIG_FILE
        self._config: Dict[str, Any] = {}
        self.load()
    
    def load(self):
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")
                self._config = {}
        
        # Merge with defaults for missing keys
        self._config = self._merge_config(self.DEFAULT_CONFIG, self._config)
    
    def _merge_config(self, default: Dict, user: Dict) -> Dict:
        """Merge user config with defaults."""
        result = default.copy()
        
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def save(self):
        """Save configuration to file."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"Config saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot notation key."""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Set configuration value by dot notation key."""
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        self.save()
    
    def get_download_config(self) -> Dict:
        """Get download configuration."""
        return self.get('download', {})
    
    def get_headers_config(self) -> Dict:
        """Get headers configuration."""
        return self.get('headers', {})
    
    def get_tools_config(self) -> Dict:
        """Get tools configuration."""
        return self.get('tools', {})
    
    def get_history_config(self) -> Dict:
        """Get history configuration."""
        return self.get('history', {})
    
    def get_logging_config(self) -> Dict:
        """Get logging configuration."""
        return self.get('logging', {})
    
    def get_network_config(self) -> Dict:
        """Get network configuration."""
        return self.get('network', {})
    
    def get_ui_config(self) -> Dict:
        """Get UI configuration."""
        return self.get('ui', {})
    
    def reset_to_defaults(self):
        """Reset configuration to defaults."""
        self._config = self.DEFAULT_CONFIG.copy()
        self.save()
    
    def export(self, file_path: Path):
        """Export configuration to file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)
    
    def import_config(self, file_path: Path):
        """Import configuration from file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            imported = yaml.safe_load(f)
            if imported:
                self._config = self._merge_config(self._config, imported)
                self.save()


class HistoryManager:
    """Manage download history."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.history_path = Path(self.config.get('history.save_path', ConfigManager.CONFIG_DIR / "history.json"))
        self._history: List[Dict] = []
        self.load()
    
    def load(self):
        """Load history from file."""
        if self.history_path.exists():
            try:
                with open(self.history_path, 'r', encoding='utf-8') as f:
                    self._history = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load history: {e}")
                self._history = []
    
    def save(self):
        """Save history to file."""
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            max_records = self.config.get('history.max_records', 100)
            if len(self._history) > max_records:
                self._history = self._history[-max_records:]
            
            with open(self.history_path, 'w', encoding='utf-8') as f:
                json.dump(self._history, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")
    
    def add(self, record: Dict):
        """Add a record to history."""
        self._history.append(record)
        self.save()
    
    def get_all(self, limit: int = None) -> List[Dict]:
        """Get all history records."""
        if limit:
            return self._history[-limit:]
        return self._history
    
    def get_by_task_id(self, task_id: str) -> Optional[Dict]:
        """Get history record by task ID."""
        for record in self._history:
            if record.get('task_id') == task_id:
                return record
        return None
    
    def clear(self):
        """Clear history."""
        self._history = []
        self.save()
    
    def search(self, query: str) -> List[Dict]:
        """Search history by URL or filename."""
        query_lower = query.lower()
        results = []
        
        for record in self._history:
            url = record.get('url', '').lower()
            file_path = record.get('file_path', '').lower()
            
            if query_lower in url or query_lower in file_path:
                results.append(record)
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get history statistics."""
        total = len(self._history)
        successful = sum(1 for r in self._history if r.get('success'))
        failed = total - successful
        
        total_size = sum(r.get('file_size_bytes', 0) for r in self._history)
        
        # Count by category
        categories = {}
        for r in self._history:
            cat = r.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1
        
        return {
            "total_downloads": total,
            "successful": successful,
            "failed": failed,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "categories": categories
        }