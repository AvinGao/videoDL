"""Download options and result models."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from .link import LinkCategory


class DownloadOptions(BaseModel):
    """Download configuration options."""
    
    save_dir: Path = Field(default=Path("./downloads"))
    save_name: Optional[str] = None
    thread_count: int = Field(default=8, ge=1, le=32)
    retry_count: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=30, ge=5, le=300)
    output_format: str = Field(default="mp4", pattern="^(mp4|mkv|original)$")
    quality: str = Field(default="best")
    overwrite: bool = False
    auto_referer: bool = True
    strict_headers: bool = False
    live_duration_limit: Optional[str] = None  # HH:MM:SS format
    max_concurrent: int = Field(default=1, ge=1, le=10)
    
    @field_validator("save_dir", mode="before")
    @classmethod
    def validate_save_dir(cls, v):
        """Convert string to Path and ensure directory exists."""
        if isinstance(v, str):
            v = Path(v)
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    @field_validator("live_duration_limit")
    @classmethod
    def validate_duration(cls, v):
        """Validate duration format HH:MM:SS."""
        if v:
            import re
            if not re.match(r"^\d{2}:\d{2}:\d{2}$", v):
                raise ValueError("Duration must be in HH:MM:SS format")
        return v


class DownloadResult(BaseModel):
    """Result of a download operation."""
    
    success: bool
    file_path: Optional[Path] = None
    error_message: Optional[str] = None
    duration_seconds: float = 0
    file_size_bytes: int = 0
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    url: Optional[str] = None
    category: Optional[LinkCategory] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @property
    def file_size_mb(self) -> float:
        """Get file size in MB."""
        return self.file_size_bytes / (1024 * 1024)
    
    @property
    def duration_formatted(self) -> str:
        """Get formatted duration."""
        minutes, seconds = divmod(int(self.duration_seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"


class TaskInfo(BaseModel):
    """Information about a download task."""
    
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    input: str
    category: LinkCategory
    status: str = "pending"  # pending, downloading, completed, failed, cancelled
    progress: float = 0
    speed: float = 0  # bytes per second
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    output_path: Optional[Path] = None
    error: Optional[str] = None
    
    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0
    
    @property
    def is_running(self) -> bool:
        """Check if task is currently running."""
        return self.status in ("pending", "downloading")
    
    @property
    def is_completed(self) -> bool:
        """Check if task is completed."""
        return self.status == "completed"
    
    @property
    def is_failed(self) -> bool:
        """Check if task failed."""
        return self.status == "failed"