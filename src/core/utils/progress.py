"""Progress display utilities."""

import sys
import time
import asyncio
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum

from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
    TaskID,
    ProgressColumn,
    SpinnerColumn
)
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich import print as rprint

console = Console()


class TaskStatus(Enum):
    """Task status for display."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskDisplayInfo:
    """Information for displaying a task."""
    task_id: str
    url: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    speed: float = 0.0
    size_mb: float = 0.0
    elapsed: float = 0.0
    eta: float = 0.0
    error: Optional[str] = None


class ProgressDisplay:
    """Display download progress using rich library."""
    
    def __init__(self, enable: bool = True):
        self._enable = enable
        self._progress: Optional[Progress] = None
        self._tasks: Dict[str, TaskID] = {}
        self._task_descriptions: Dict[str, str] = {}
    
    def start(self):
        """Start progress display."""
        if not self._enable:
            return
        
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
            transient=False,
            expand=True
        )
        self._progress.start()
    
    def stop(self):
        """Stop progress display."""
        if self._progress:
            self._progress.stop()
    
    def add_task(self, task_id: str, description: str, total: int = 100) -> TaskID:
        """Add a progress task."""
        if not self._progress:
            self.start()
        
        if task_id in self._tasks:
            return self._tasks[task_id]
        
        task = self._progress.add_task(
            description=description,
            total=total
        )
        self._tasks[task_id] = task
        self._task_descriptions[task_id] = description
        return task
    
    def update_task(
        self, 
        task_id: str, 
        advance: int = None, 
        completed: int = None,
        description: str = None
    ):
        """Update task progress."""
        if not self._progress or task_id not in self._tasks:
            return
        
        task = self._tasks[task_id]
        
        if advance is not None:
            self._progress.advance(task, advance)
        elif completed is not None:
            self._progress.update(task, completed=completed)
        
        if description:
            self._progress.update(task, description=description)
    
    def remove_task(self, task_id: str):
        """Remove a task."""
        if not self._progress or task_id not in self._tasks:
            return
        
        self._progress.remove_task(self._tasks[task_id])
        del self._tasks[task_id]
        if task_id in self._task_descriptions:
            del self._task_descriptions[task_id]
    
    def complete_task(self, task_id: str, success: bool = True):
        """Mark task as completed."""
        if task_id in self._tasks:
            if success:
                self.update_task(task_id, completed=100)
            self.remove_task(task_id)
    
    def get_active_task_count(self) -> int:
        """Get number of active tasks."""
        return len(self._tasks)
    
    def clear_all(self):
        """Remove all tasks."""
        for task_id in list(self._tasks.keys()):
            self.remove_task(task_id)


class MultiTaskProgress:
    """Display multiple download tasks simultaneously."""
    
    def __init__(self, max_display: int = 10):
        self._live: Optional[Live] = None
        self._tasks: Dict[str, TaskDisplayInfo] = {}
        self._max_display = max_display
        self._console = Console()
        self._layout = Layout()
        self._running = False
    
    def start(self):
        """Start live display."""
        if self._running:
            return
        
        self._layout.split_column()
        self._live = Live(
            self._layout, 
            console=self._console, 
            refresh_per_second=4,
            transient=False
        )
        self._live.start()
        self._running = True
    
    def stop(self):
        """Stop live display."""
        if not self._running:
            return
        
        if self._live:
            self._live.stop()
        self._running = False
    
    def add_task(self, task_id: str, url: str):
        """Add a task to display."""
        self._tasks[task_id] = TaskDisplayInfo(
            task_id=task_id,
            url=url,
            status=TaskStatus.PENDING
        )
        self._refresh()
    
    def update_task(
        self, 
        task_id: str, 
        progress: float = None, 
        speed: float = None,
        size_mb: float = None,
        status: TaskStatus = None,
        elapsed: float = None,
        eta: float = None,
        error: str = None
    ):
        """Update task progress."""
        if task_id not in self._tasks:
            return
        
        task = self._tasks[task_id]
        
        if progress is not None:
            task.progress = progress
        if speed is not None:
            task.speed = speed
        if size_mb is not None:
            task.size_mb = size_mb
        if status is not None:
            task.status = status
        if elapsed is not None:
            task.elapsed = elapsed
        if eta is not None:
            task.eta = eta
        if error is not None:
            task.error = error
        
        self._refresh()
    
    def set_task_status(self, task_id: str, status: TaskStatus, error: str = None):
        """Update task status."""
        if task_id in self._tasks:
            self._tasks[task_id].status = status
            if error:
                self._tasks[task_id].error = error
            self._refresh()
    
    def remove_task(self, task_id: str):
        """Remove a task from display."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            self._refresh()
    
    def clear_all(self):
        """Clear all tasks."""
        self._tasks.clear()
        self._refresh()
    
    def _refresh(self):
        """Refresh the display."""
        if not self._live:
            return
        
        # Create table
        table = Table(show_header=True, header_style="bold cyan", border_style="dim")
        table.add_column("ID", style="dim", width=8)
        table.add_column("URL", style="white", max_width=40)
        table.add_column("Progress", justify="right", width=12)
        table.add_column("Speed", justify="right", width=12)
        table.add_column("Status", justify="center", width=12)
        
        # Add tasks (limit display)
        tasks_to_display = list(self._tasks.values())[:self._max_display]
        
        for task in tasks_to_display:
            url_display = task.url[:40] + "..." if len(task.url) > 40 else task.url
            
            if task.progress > 0:
                progress_display = f"{task.progress:.1f}%"
                bar = self._create_bar(task.progress)
                progress_full = f"{bar} {progress_display}"
            else:
                progress_full = "--"
            
            speed_display = self._format_speed(task.speed) if task.speed > 0 else "--"
            status_display = self._format_status(task.status, task.error)
            
            table.add_row(
                task.task_id[:8],
                url_display,
                progress_full,
                speed_display,
                status_display
            )
        
        # Add summary
        summary = self._create_summary()
        
        # Update layout
        self._layout.update(
            Panel(
                table,
                title=f"Download Tasks ({len(self._tasks)} active)",
                border_style="green",
                subtitle=summary
            )
        )
    
    def _create_bar(self, percent: float, width: int = 10) -> str:
        """Create a simple progress bar."""
        filled = int(width * percent / 100)
        bar = "█" * filled + "░" * (width - filled)
        return bar
    
    def _format_speed(self, speed: float) -> str:
        """Format speed in human-readable format."""
        if speed < 1024:
            return f"{speed:.0f} B/s"
        elif speed < 1024 * 1024:
            return f"{speed / 1024:.1f} KB/s"
        elif speed < 1024 * 1024 * 1024:
            return f"{speed / (1024 * 1024):.1f} MB/s"
        else:
            return f"{speed / (1024 * 1024 * 1024):.2f} GB/s"
    
    def _format_status(self, status: TaskStatus, error: Optional[str] = None) -> str:
        """Format status with color."""
        if status == TaskStatus.PENDING:
            return "[yellow]Pending[/yellow]"
        elif status == TaskStatus.DOWNLOADING:
            return "[cyan]↓ Downloading[/cyan]"
        elif status == TaskStatus.PROCESSING:
            return "[magenta]⚙ Processing[/magenta]"
        elif status == TaskStatus.COMPLETED:
            return "[green]✓ Completed[/green]"
        elif status == TaskStatus.FAILED:
            return f"[red]✗ Failed[/red]\n[dim]{error[:30] if error else ''}[/dim]"
        elif status == TaskStatus.CANCELLED:
            return "[dim]⊘ Cancelled[/dim]"
        return "Unknown"
    
    def _create_summary(self) -> str:
        """Create summary text."""
        total = len(self._tasks)
        downloading = sum(1 for t in self._tasks.values() if t.status == TaskStatus.DOWNLOADING)
        completed = sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED)
        
        parts = []
        if downloading:
            parts.append(f"[cyan]{downloading} downloading[/cyan]")
        if completed:
            parts.append(f"[green]{completed} completed[/green]")
        if failed:
            parts.append(f"[red]{failed} failed[/red]")
        
        return " | ".join(parts) if parts else f"{total} tasks"


class SpinnerDisplay:
    """Simple spinner for single task display."""
    
    def __init__(self, message: str = "Processing..."):
        self._message = message
        self._spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self._idx = 0
        self._running = False
        self._task = None
    
    async def start(self, task_name: str = None):
        """Start spinner animation."""
        self._running = True
        message = task_name or self._message
        
        if self._task is None:
            from rich.progress import Progress, SpinnerColumn, TextColumn
            self._progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=False
            )
            self._progress.start()
            self._task = self._progress.add_task(message, total=None)
        else:
            self._progress.update(self._task, description=message)
    
    def stop(self, success: bool = True):
        """Stop spinner animation."""
        if self._progress and self._task:
            if success:
                self._progress.update(self._task, description="✓ Done")
            else:
                self._progress.update(self._task, description="✗ Failed")
            self._progress.stop()
        self._running = False
    
    def update_message(self, message: str):
        """Update spinner message."""
        if self._progress and self._task:
            self._progress.update(self._task, description=message)