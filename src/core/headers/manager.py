"""HTTP headers manager."""

import re
from urllib.parse import urlparse
from typing import Optional, List, Dict
from ..models.headers import RequestHeaders
from .presets import UserAgentPresets


class HeaderManager:
    """Manage HTTP request headers."""
    
    @staticmethod
    def create_default() -> RequestHeaders:
        """Create default request headers."""
        return RequestHeaders(
            user_agent=UserAgentPresets.get_default(),
            referer=None,
            cookie=None,
            custom={}
        )
    
    @staticmethod
    def from_url(url: str, with_referer: bool = True) -> RequestHeaders:
        """Create request headers from URL, optionally setting Referer."""
        headers = HeaderManager.create_default()
        
        if with_referer:
            # Extract domain from URL for Referer
            parsed = urlparse(url)
            referer = f"{parsed.scheme}://{parsed.netloc}"
            headers.referer = referer
        
        return headers
    
    @staticmethod
    def merge(base: RequestHeaders, override: RequestHeaders) -> RequestHeaders:
        """Merge two header sets, override takes precedence."""
        return base.merge(override)
    
    @staticmethod
    def validate(headers: RequestHeaders, required: List[str]) -> List[str]:
        """Validate headers against required list. Return missing headers."""
        existing = set(headers.to_dict().keys())
        required_set = set(required)
        
        # Normalize header names for comparison
        existing_lower = {k.lower() for k in existing}
        required_lower = {r.lower() for r in required_set}
        
        missing = []
        for req in required_set:
            if req.lower() not in existing_lower:
                missing.append(req)
        
        return missing
    
    @staticmethod
    def from_dict(data: Dict[str, str]) -> RequestHeaders:
        """Create RequestHeaders from dictionary."""
        headers = RequestHeaders(custom={})
        
        # Map common headers to their fields
        header_map = {
            "user-agent": "user_agent",
            "referer": "referer",
            "cookie": "cookie",
            "origin": "origin",
            "authorization": "authorization",
        }
        
        for key, value in data.items():
            key_lower = key.lower()
            if key_lower in header_map:
                setattr(headers, header_map[key_lower], value)
            else:
                headers.custom[key] = value
        
        return headers
    
    @staticmethod
    def parse_cookie_string(cookie_str: str) -> Dict[str, str]:
        """Parse cookie string into dictionary."""
        cookies = {}
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                cookies[key.strip()] = value.strip()
        return cookies
    
    @staticmethod
    def to_cookie_string(cookies: Dict[str, str]) -> str:
        """Convert cookie dictionary to string."""
        return '; '.join(f"{k}={v}" for k, v in cookies.items())
    
    @staticmethod
    def suggest_for_domain(domain: str) -> RequestHeaders:
        """Suggest headers for a specific domain."""
        headers = HeaderManager.create_default()
        
        domain_lower = domain.lower()
        
        # Bilibili
        if "bilibili.com" in domain_lower:
            headers.referer = "https://www.bilibili.com"
        
        # YouTube
        elif "youtube.com" in domain_lower or "youtu.be" in domain_lower:
            # YouTube doesn't require Referer
            pass
        
        # Tencent Video
        elif "v.qq.com" in domain_lower:
            headers.referer = "https://v.qq.com"
        
        # iQiyi
        elif "iqiyi.com" in domain_lower:
            headers.referer = "https://www.iqiyi.com"
        
        # Youku
        elif "youku.com" in domain_lower:
            headers.referer = "https://www.youku.com"
        
        # Douyin/TikTok
        elif "douyin.com" in domain_lower or "tiktok.com" in domain_lower:
            headers.referer = "https://www.douyin.com"
        
        return headers