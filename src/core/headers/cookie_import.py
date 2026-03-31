"""Browser cookie import functionality."""

import os
import sqlite3
import shutil
from pathlib import Path
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class CookieImporter:
    """Import cookies from browsers."""
    
    # Common cookie file paths
    BROWSER_PATHS = {
        "chrome": {
            "windows": os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Cookies"),
            "mac": os.path.expanduser("~/Library/Application Support/Google/Chrome/Default/Cookies"),
            "linux": os.path.expanduser("~/.config/google-chrome/Default/Cookies"),
        },
        "firefox": {
            "windows": os.path.expandvars(r"%APPDATA%\Mozilla\Firefox\Profiles"),
            "mac": os.path.expanduser("~/Library/Application Support/Firefox/Profiles"),
            "linux": os.path.expanduser("~/.mozilla/firefox"),
        },
        "edge": {
            "windows": os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Cookies"),
            "mac": os.path.expanduser("~/Library/Application Support/Microsoft Edge/Default/Cookies"),
            "linux": os.path.expanduser("~/.config/microsoft-edge/Default/Cookies"),
        },
    }
    
    @classmethod
    def _get_platform(cls) -> str:
        """Get current platform."""
        import sys
        if sys.platform == "win32":
            return "windows"
        elif sys.platform == "darwin":
            return "mac"
        return "linux"
    
    @classmethod
    def _find_firefox_profile(cls) -> Optional[Path]:
        """Find Firefox profile directory."""
        platform = cls._get_platform()
        profiles_dir = cls.BROWSER_PATHS["firefox"][platform]
        
        if not os.path.exists(profiles_dir):
            return None
        
        # 查找默认 profile
        profiles_ini = Path(profiles_dir) / "profiles.ini"
        if profiles_ini.exists():
            import configparser
            config = configparser.ConfigParser()
            config.read(profiles_ini)
            
            for section in config.sections():
                if section.startswith("Profile"):
                    is_default = config.get(section, "Default", fallback="0") == "1"
                    profile_path = config.get(section, "Path")
                    if profile_path:
                        full_path = Path(profiles_dir) / profile_path
                        if full_path.exists():
                            return full_path
        
        # 查找最近的 profile
        for item in Path(profiles_dir).iterdir():
            if item.is_dir() and (item / "cookies.sqlite").exists():
                return item
        
        return None
    
    @classmethod
    def from_chrome(cls, domain: Optional[str] = None) -> Optional[str]:
        """Import cookies from Chrome browser."""
        platform = cls._get_platform()
        cookie_path = cls.BROWSER_PATHS["chrome"][platform]
        
        if not os.path.exists(cookie_path):
            # 尝试查找其他 Chrome 路径
            chrome_paths = [
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Cookies"),
                os.path.expandvars(r"%LOCALAPPDATA%\Chromium\User Data\Default\Cookies"),
                os.path.expandvars(r"%USERPROFILE%\AppData\Local\Google\Chrome\User Data\Default\Cookies"),
            ]
            for path in chrome_paths:
                if os.path.exists(path):
                    cookie_path = path
                    break
            else:
                logger.warning(f"Chrome cookie file not found")
                return None
        
        return cls._read_chrome_cookies(Path(cookie_path), domain)
    
    @classmethod
    def _read_chrome_cookies(cls, cookie_path: Path, domain: Optional[str] = None) -> Optional[str]:
        """Read cookies from Chrome SQLite database."""
        temp_cookie = None
        try:
            import tempfile
            
            # 复制数据库到临时文件（避免锁定）
            temp_cookie = Path(tempfile.gettempdir()) / f"cookies_{os.getpid()}.db"
            shutil.copy2(cookie_path, temp_cookie)
            
            conn = sqlite3.connect(str(temp_cookie))
            cursor = conn.cursor()
            
            # Chrome cookies table structure
            if domain:
                query = """
                    SELECT name, value FROM cookies
                    WHERE host_key LIKE ?
                    ORDER BY last_access_utc DESC
                """
                cursor.execute(query, (f"%{domain}%",))
            else:
                query = """
                    SELECT name, value FROM cookies
                    ORDER BY last_access_utc DESC
                    LIMIT 50
                """
                cursor.execute(query)
            
            cookies = {}
            for name, value in cursor.fetchall():
                cookies[name] = value
            
            conn.close()
            
            if cookies:
                return '; '.join(f"{k}={v}" for k, v in cookies.items())
            else:
                logger.warning("No cookies found")
                return None
            
        except sqlite3.OperationalError as e:
            logger.error(f"SQLite error: {e}. Make sure Chrome is closed.")
            return None
        except Exception as e:
            logger.error(f"Failed to read cookies: {e}")
            return None
        finally:
            if temp_cookie and Path(temp_cookie).exists():
                try:
                    Path(temp_cookie).unlink()
                except:
                    pass
    
    @classmethod
    def from_firefox(cls, domain: Optional[str] = None) -> Optional[str]:
        """Import cookies from Firefox browser."""
        profile_path = cls._find_firefox_profile()
        if not profile_path:
            logger.warning("Firefox profile not found")
            return None
        
        cookie_path = profile_path / "cookies.sqlite"
        if not cookie_path.exists():
            logger.warning(f"Firefox cookie file not found: {cookie_path}")
            return None
        
        return cls._read_firefox_cookies(cookie_path, domain)
    
    @classmethod
    def _read_firefox_cookies(cls, cookie_path: Path, domain: Optional[str] = None) -> Optional[str]:
        """Read cookies from Firefox SQLite database."""
        temp_cookie = None
        try:
            import tempfile
            
            temp_cookie = Path(tempfile.gettempdir()) / f"cookies_{os.getpid()}.db"
            shutil.copy2(cookie_path, temp_cookie)
            
            conn = sqlite3.connect(str(temp_cookie))
            cursor = conn.cursor()
            
            if domain:
                query = """
                    SELECT name, value FROM moz_cookies
                    WHERE host LIKE ?
                    ORDER BY lastAccessed DESC
                """
                cursor.execute(query, (f"%{domain}%",))
            else:
                query = """
                    SELECT name, value FROM moz_cookies
                    ORDER BY lastAccessed DESC
                    LIMIT 50
                """
                cursor.execute(query)
            
            cookies = {}
            for name, value in cursor.fetchall():
                cookies[name] = value
            
            conn.close()
            
            if cookies:
                return '; '.join(f"{k}={v}" for k, v in cookies.items())
            else:
                return None
            
        except sqlite3.OperationalError as e:
            logger.error(f"SQLite error: {e}. Make sure Firefox is closed.")
            return None
        except Exception as e:
            logger.error(f"Failed to read Firefox cookies: {e}")
            return None
        finally:
            if temp_cookie and Path(temp_cookie).exists():
                try:
                    Path(temp_cookie).unlink()
                except:
                    pass
    
    @classmethod
    def from_edge(cls, domain: Optional[str] = None) -> Optional[str]:
        """Import cookies from Edge browser."""
        platform = cls._get_platform()
        cookie_path = cls.BROWSER_PATHS["edge"][platform]
        
        if not os.path.exists(cookie_path):
            logger.warning(f"Edge cookie file not found: {cookie_path}")
            return None
        
        return cls._read_chrome_cookies(Path(cookie_path), domain)
    
    @classmethod
    def import_from_browser(cls, browser: str, domain: Optional[str] = None) -> Optional[str]:
        """Import cookies from specified browser."""
        import_methods = {
            "chrome": cls.from_chrome,
            "firefox": cls.from_firefox,
            "edge": cls.from_edge,
        }
        
        method = import_methods.get(browser.lower())
        if method:
            # 先提示关闭浏览器
            print(f"提示: 请先关闭 {browser} 浏览器，否则无法读取 Cookie")
            return method(domain)
        
        return None