"""HTTP request headers models."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class RequestHeaders(BaseModel):
    """HTTP request headers for downloading."""
    
    user_agent: Optional[str] = None
    referer: Optional[str] = None
    cookie: Optional[str] = None
    origin: Optional[str] = None
    authorization: Optional[str] = None
    custom: Dict[str, str] = Field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary format."""
        result = {}
        
        if self.user_agent:
            result["User-Agent"] = self.user_agent
        if self.referer:
            result["Referer"] = self.referer
        if self.cookie:
            result["Cookie"] = self.cookie
        if self.origin:
            result["Origin"] = self.origin
        if self.authorization:
            result["Authorization"] = self.authorization
        
        # Add custom headers
        result.update(self.custom)
        
        return result
    
    def to_curl_headers(self) -> List[str]:
        """Convert to curl-style header list."""
        headers = []
        for key, value in self.to_dict().items():
            headers.append(f"{key}: {value}")
        return headers
    
    def to_ffmpeg_headers(self) -> str:
        """Convert to FFmpeg -headers format."""
        headers = []
        for key, value in self.to_dict().items():
            headers.append(f"{key}: {value}")
        return "\r\n".join(headers)
    
    def to_aria2_headers(self) -> List[str]:
        """Convert to aria2 --header format."""
        return [f"--header={key}: {value}" for key, value in self.to_dict().items()]
    
    def merge(self, other: "RequestHeaders") -> "RequestHeaders":
        """Merge with another RequestHeaders, other takes precedence."""
        merged = self.model_copy()
        
        if other.user_agent:
            merged.user_agent = other.user_agent
        if other.referer:
            merged.referer = other.referer
        if other.cookie:
            merged.cookie = other.cookie
        if other.origin:
            merged.origin = other.origin
        if other.authorization:
            merged.authorization = other.authorization
        
        merged.custom.update(other.custom)
        
        return merged
    
    def is_empty(self) -> bool:
        """Check if all headers are empty."""
        return not any([
            self.user_agent,
            self.referer,
            self.cookie,
            self.origin,
            self.authorization,
            self.custom,
        ])