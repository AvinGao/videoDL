"""Link type detection models."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class LinkCategory(str, Enum):
    """Category of video link."""
    
    DIRECT = "direct"        # Direct file link (mp4, mkv, etc.)
    HLS = "hls"              # HLS stream (m3u8)
    DASH = "dash"            # DASH stream (mpd)
    MAGNET = "magnet"        # Magnet link
    TORRENT = "torrent"      # Torrent file
    WEBSITE = "website"      # Website URL (YouTube, Bilibili, etc.)
    LIVE = "live"            # Live stream
    UNKNOWN = "unknown"      # Unknown type


class HeaderSuggestion(BaseModel):
    """Suggested headers for a given link."""
    
    required_headers: List[str] = Field(default_factory=list)
    suggested_headers: List[str] = Field(default_factory=list)
    warning: Optional[str] = None
    referer_template: Optional[str] = None
    
    def has_required_headers(self, headers: List[str]) -> bool:
        """Check if required headers are present."""
        return all(req in headers for req in self.required_headers)
    
    def missing_required_headers(self, headers: List[str]) -> List[str]:
        """Return missing required headers."""
        return [req for req in self.required_headers if req not in headers]