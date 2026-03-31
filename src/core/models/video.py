"""Video information models."""

from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class FormatInfo(BaseModel):
    """Information about a specific video format."""
    
    format_id: str
    resolution: Optional[str] = None
    fps: Optional[float] = None
    codec: Optional[str] = None
    bitrate: Optional[int] = None
    filesize: Optional[int] = None
    url: Optional[str] = None


class SubtitleInfo(BaseModel):
    """Information about a subtitle track."""
    
    language: str
    code: str
    url: Optional[str] = None
    is_srt: bool = True


class AudioTrackInfo(BaseModel):
    """Information about an audio track."""
    
    language: str
    code: str
    bitrate: Optional[int] = None
    channels: Optional[int] = None


class VideoInfo(BaseModel):
    """Complete video information."""
    
    title: str
    duration: Optional[int] = None  # seconds
    thumbnail: Optional[str] = None
    description: Optional[str] = None
    uploader: Optional[str] = None
    upload_date: Optional[str] = None
    
    # Available formats
    resolutions: List[str] = Field(default_factory=list)
    formats: List[FormatInfo] = Field(default_factory=list)
    audio_tracks: List[AudioTrackInfo] = Field(default_factory=list)
    subtitles: List[SubtitleInfo] = Field(default_factory=list)
    
    # Raw data from extractor
    raw_data: Optional[Dict] = None
    
    @property
    def best_format(self) -> Optional[FormatInfo]:
        """Get the best quality format."""
        if not self.formats:
            return None
        # Sort by resolution (assuming format_id contains resolution info)
        # For simplicity, return the first
        return self.formats[0]
    
    @property
    def duration_formatted(self) -> str:
        """Get formatted duration."""
        if not self.duration:
            return "Unknown"
        minutes, seconds = divmod(self.duration, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"