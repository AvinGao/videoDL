"""Link type detection utilities."""

import re
from urllib.parse import urlparse
from pathlib import Path
from typing import Optional, List, Dict
import yaml

from ..models.link import LinkCategory, HeaderSuggestion


class LinkDetector:
    """Detect video link types and provide header suggestions."""
    
    # Direct video file extensions
    DIRECT_EXTENSIONS = {
        '.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.ts',
        '.mpg', '.mpeg', '.wmv', '.m4v', '.3gp', '.ogv'
    }
    
    # Default site rules
    DEFAULT_SITE_RULES: Dict[str, Dict] = {
        'bilibili.com': {
            'category': 'website',
            'required_headers': ['Referer', 'User-Agent'],
            'suggested_headers': ['Cookie'],
            'referer_template': 'https://www.bilibili.com',
            'warning': 'Some Bilibili videos may require login cookies'
        },
        'youtube.com': {
            'category': 'website',
            'required_headers': ['User-Agent'],
            'suggested_headers': ['Cookie'],
            'warning': 'YouTube may require cookies for age-restricted content'
        },
        'youtu.be': {
            'category': 'website',
            'required_headers': ['User-Agent'],
            'referer_template': 'https://www.youtube.com'
        },
        'v.qq.com': {
            'category': 'website',
            'required_headers': ['Referer', 'Cookie'],
            'suggested_headers': ['User-Agent'],
            'referer_template': 'https://v.qq.com',
            'warning': 'Tencent Video requires login and proper referer'
        },
        'iqiyi.com': {
            'category': 'website',
            'required_headers': ['Referer', 'Cookie'],
            'referer_template': 'https://www.iqiyi.com'
        },
        'youku.com': {
            'category': 'website',
            'required_headers': ['Referer', 'Cookie'],
            'referer_template': 'https://www.youku.com'
        },
        'douyin.com': {
            'category': 'website',
            'required_headers': ['User-Agent'],
            'suggested_headers': ['Referer'],
            'referer_template': 'https://www.douyin.com'
        },
        'tiktok.com': {
            'category': 'website',
            'required_headers': ['User-Agent'],
            'referer_template': 'https://www.tiktok.com'
        },
        'twitch.tv': {
            'category': 'live',
            'required_headers': ['User-Agent'],
            'suggested_headers': ['Client-ID'],
            'warning': 'Twitch may require OAuth token for high quality streams'
        },
        'huya.com': {
            'category': 'live',
            'required_headers': ['User-Agent', 'Referer'],
            'referer_template': 'https://www.huya.com'
        },
        'douyu.com': {
            'category': 'live',
            'required_headers': ['User-Agent', 'Referer'],
            'referer_template': 'https://www.douyu.com'
        },
    }
    
    _site_rules: Dict[str, Dict] = DEFAULT_SITE_RULES.copy()
    
    @classmethod
    def detect_category(cls, url: str) -> LinkCategory:
        """Detect the category of a video link."""
        url_lower = url.lower().strip()
        
        # Check for magnet links
        if url_lower.startswith('magnet:'):
            return LinkCategory.MAGNET
        
        # Check for file paths (local files)
        if url_lower.startswith(('file:', '/', '\\')) or Path(url_lower).exists():
            path = Path(url_lower)
            if path.suffix.lower() == '.torrent':
                return LinkCategory.TORRENT
            elif path.suffix.lower() in cls.DIRECT_EXTENSIONS:
                return LinkCategory.DIRECT
            elif path.suffix.lower() == '.m3u8':
                return LinkCategory.HLS
            elif path.suffix.lower() == '.mpd':
                return LinkCategory.DASH
            return LinkCategory.UNKNOWN
        
        # Check URL patterns
        parsed = urlparse(url_lower)
        
        # HLS stream
        if url_lower.endswith('.m3u8'):
            return LinkCategory.HLS
        
        # DASH stream
        if url_lower.endswith('.mpd'):
            return LinkCategory.DASH
        
        # Direct file
        path_lower = parsed.path.lower()
        for ext in cls.DIRECT_EXTENSIONS:
            if path_lower.endswith(ext):
                return LinkCategory.DIRECT
        
        # RTMP stream
        if parsed.scheme == 'rtmp':
            return LinkCategory.LIVE
        
        # Check against site rules
        for domain, rules in cls._site_rules.items():
            if domain in parsed.netloc.lower():
                category = rules.get('category', 'website')
                if category == 'live':
                    return LinkCategory.LIVE
                return LinkCategory.WEBSITE
        
        # Default to unknown if it's a URL but not recognized
        if parsed.scheme in ('http', 'https'):
            return LinkCategory.UNKNOWN
        
        return LinkCategory.UNKNOWN
    
    @classmethod
    def get_header_suggestion(cls, url: str, category: LinkCategory) -> HeaderSuggestion:
        """Get header suggestions for a given URL."""
        parsed = urlparse(url.lower() if url else "")
        domain = parsed.netloc
        
        # Check site rules
        for rule_domain, rules in cls._site_rules.items():
            if rule_domain in domain:
                return HeaderSuggestion(
                    required_headers=rules.get('required_headers', []),
                    suggested_headers=rules.get('suggested_headers', []),
                    warning=rules.get('warning'),
                    referer_template=rules.get('referer_template')
                )
        
        # Default suggestions based on category
        if category == LinkCategory.HLS:
            return HeaderSuggestion(
                required_headers=['User-Agent'],
                suggested_headers=['Referer'],
                warning='Some HLS streams require correct Referer header'
            )
        elif category == LinkCategory.DASH:
            return HeaderSuggestion(
                required_headers=['User-Agent'],
                suggested_headers=['Referer'],
                warning='DASH streams may require proper headers'
            )
        elif category == LinkCategory.DIRECT:
            return HeaderSuggestion(
                required_headers=['User-Agent'],
                suggested_headers=[],
                warning=None
            )
        elif category == LinkCategory.LIVE:
            return HeaderSuggestion(
                required_headers=['User-Agent'],
                suggested_headers=['Referer'],
                warning='Live streams may require specific headers'
            )
        
        return HeaderSuggestion(
            required_headers=[],
            suggested_headers=['User-Agent'],
            warning=None
        )
    
    @classmethod
    def is_direct_video_url(cls, url: str) -> bool:
        """Check if URL is a direct video link."""
        return cls.detect_category(url) == LinkCategory.DIRECT
    
    @classmethod
    def is_m3u8_url(cls, url: str) -> bool:
        """Check if URL is an M3U8 stream."""
        return cls.detect_category(url) == LinkCategory.HLS
    
    @classmethod
    def is_mpd_url(cls, url: str) -> bool:
        """Check if URL is an MPD stream."""
        return cls.detect_category(url) == LinkCategory.DASH
    
    @classmethod
    def is_magnet_url(cls, url: str) -> bool:
        """Check if URL is a magnet link."""
        return cls.detect_category(url) == LinkCategory.MAGNET
    
    @classmethod
    def is_website_url(cls, url: str) -> bool:
        """Check if URL is a website (YouTube, Bilibili, etc.)."""
        return cls.detect_category(url) == LinkCategory.WEBSITE
    
    @classmethod
    def is_live_stream(cls, url: str) -> bool:
        """Check if URL is a live stream."""
        return cls.detect_category(url) == LinkCategory.LIVE
    
    @classmethod
    def load_site_rules(cls, config_path: Path):
        """Load site rules from YAML file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            rules = data.get('rules', [])
            for rule in rules:
                domain = rule.get('domain')
                if domain:
                    cls._site_rules[domain] = {
                        'category': rule.get('category', 'website'),
                        'required_headers': rule.get('required_headers', []),
                        'suggested_headers': rule.get('suggested_headers', []),
                        'referer_template': rule.get('referer_template'),
                        'warning': rule.get('warning')
                    }
        except Exception as e:
            pass  # Use default rules
    
    @classmethod
    def get_site_rules(cls) -> Dict:
        """Get current site rules."""
        return cls._site_rules.copy()