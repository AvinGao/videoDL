"""Command-line interface commands using click."""

import asyncio
import sys
from pathlib import Path
from typing import Optional
import logging

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from ..core.scheduler import DownloadScheduler
from ..core.models.download import DownloadOptions, DownloadResult
from ..core.models.headers import RequestHeaders
from ..core.utils.config import ConfigManager, HistoryManager
from ..core.utils.link_detector import LinkDetector
from ..core.headers.manager import HeaderManager
from ..core.headers.cookie_import import CookieImporter
from ..core.utils.progress import ProgressDisplay

console = Console()
logger = logging.getLogger(__name__)


class DownloadProgressHandler:
    """Handle download progress for CLI."""
    
    def __init__(self):
        self.progress = ProgressDisplay()
        self.current_task = None
    
    def on_progress(self, percent: float, current: int, total: int):
        """Handle progress update."""
        if self.current_task:
            self.progress.update_task(self.current_task, completed=int(percent))
    
    def on_speed(self, speed: float):
        """Handle speed update."""
        pass
    
    def start_task(self, task_id: str, description: str):
        """Start tracking a task."""
        self.current_task = self.progress.add_task(task_id, description)
        self.progress.start()
    
    def stop_task(self):
        """Stop tracking current task."""
        if self.current_task:
            self.progress.remove_task(self.current_task)
            self.current_task = None
        self.progress.stop()


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Video Downloader - Download videos from various sources.
    
    Supports M3U8/HLS, DASH/MPD, direct links, magnet links, torrents, and websites.
    """
    pass


@cli.command()
@click.argument("url")
@click.option("-o", "--output", type=click.Path(), help="Save directory")
@click.option("-n", "--name", help="Save filename (without extension)")
@click.option("-t", "--threads", type=int, default=8, help="Number of threads")
@click.option("-f", "--format", "output_format", default="mp4", 
              type=click.Choice(["mp4", "mkv", "original"]), help="Output format")
@click.option("-q", "--quality", default="best", help="Video quality (best/high/medium/low)")
@click.option("-r", "--retry", type=int, default=3, help="Retry count")
@click.option("--user-agent", help="Custom User-Agent")
@click.option("--referer", help="Custom Referer")
@click.option("--cookie", help="Custom Cookie")
@click.option("--header", "headers", multiple=True, help="Custom header (key:value)")
@click.option("--import-cookie", "import_cookie", type=click.Choice(["chrome", "firefox", "edge"]),
              help="Import cookies from browser")
@click.option("--auto-referer/--no-auto-referer", default=True, help="Auto set Referer")
@click.option("--live-limit", help="Live recording limit (HH:MM:SS)")
@click.option("--overwrite", is_flag=True, help="Overwrite existing file")
def download(
    url: str,
    output: Optional[str],
    name: Optional[str],
    threads: int,
    output_format: str,
    quality: str,
    retry: int,
    user_agent: Optional[str],
    referer: Optional[str],
    cookie: Optional[str],
    headers: tuple,
    import_cookie: Optional[str],
    auto_referer: bool,
    live_limit: Optional[str],
    overwrite: bool,
):
    """Download video from URL."""
    
    # Build headers
    request_headers = RequestHeaders(
        user_agent=user_agent,
        referer=referer,
        cookie=cookie,
    )
    
    # Add custom headers
    for header in headers:
        if ':' in header:
            key, value = header.split(':', 1)
            request_headers.custom[key.strip()] = value.strip()
    
    # Import cookies from browser if requested
    if import_cookie:
        imported_cookie = CookieImporter.import_from_browser(import_cookie)
        if imported_cookie:
            request_headers.cookie = imported_cookie
            console.print(f"[green]Cookies imported from {import_cookie}[/green]")
        else:
            console.print(f"[yellow]Failed to import cookies from {import_cookie}[/yellow]")
    
    # Build options
    save_dir = Path(output) if output else Path.cwd() / "downloads"
    
    options = DownloadOptions(
        save_dir=save_dir,
        save_name=name,
        thread_count=threads,
        retry_count=retry,
        output_format=output_format,
        quality=quality,
        auto_referer=auto_referer,
        live_duration_limit=live_limit,
        overwrite=overwrite,
    )
    
    # Create scheduler and progress handler
    scheduler = DownloadScheduler()
    progress = DownloadProgressHandler()
    
    # Set up callbacks
    def on_progress(percent, current, total):
        progress.on_progress(percent, current, total)
    
    # Run download
    console.print(f"[cyan]Downloading: {url}[/cyan]")
    console.print(f"[dim]Save to: {save_dir}[/dim]")
    
    try:
        result = asyncio.run(scheduler.download(url, options, request_headers))
        
        if result.success:
            console.print(f"[green]✓ Download completed![/green]")
            console.print(f"[dim]File: {result.file_path}[/dim]")
            console.print(f"[dim]Size: {result.file_size_mb:.2f} MB[/dim]")
            console.print(f"[dim]Time: {result.duration_formatted}[/dim]")
        else:
            console.print(f"[red]✗ Download failed: {result.error_message}[/red]")
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Download cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("-l", "--limit", type=int, default=20, help="Number of records to show")
def history(limit: int):
    """Show download history."""
    config = ConfigManager()
    history_manager = HistoryManager(config)
    
    records = history_manager.get_all(limit)
    
    if not records:
        console.print("[yellow]No download history found[/yellow]")
        return
    
    table = Table(title="Download History")
    table.add_column("Time", style="cyan")
    table.add_column("URL", style="white", max_width=50)
    table.add_column("Status", justify="center")
    table.add_column("Size", justify="right")
    
    for record in records:
        status = "[green]Success[/green]" if record.get("success") else "[red]Failed[/red]"
        size = f"{record.get('file_size_bytes', 0) / (1024*1024):.1f} MB" if record.get("file_size_bytes") else "-"
        
        table.add_row(
            record.get("timestamp", "")[:19],
            record.get("url", "")[:50],
            status,
            size
        )
    
    console.print(table)


@cli.command()
@click.argument("key", required=False)
@click.argument("value", required=False)
def config(key: Optional[str], value: Optional[str]):
    """View or set configuration."""
    config_manager = ConfigManager()
    
    if key is None:
        # Show all config
        console.print(Panel("Configuration", style="bold cyan"))
        
        download_config = config_manager.get_download_config()
        headers_config = config_manager.get_headers_config()
        
        console.print("\n[bold]Download Settings:[/bold]")
        console.print(f"  Default directory: {download_config.get('default_dir')}")
        console.print(f"  Default threads: {download_config.get('default_threads')}")
        console.print(f"  Default format: {download_config.get('default_format')}")
        console.print(f"  Retry count: {download_config.get('retry_count')}")
        
        console.print("\n[bold]Headers Settings:[/bold]")
        console.print(f"  Default User-Agent: {headers_config.get('default_user_agent')[:60]}...")
        console.print(f"  Auto Referer: {headers_config.get('auto_referer')}")
        
    elif value is None:
        # Show specific key
        val = config_manager.get(key)
        console.print(f"{key} = {val}")
    else:
        # Set value
        try:
            # Try to parse as number
            if value.isdigit():
                value = int(value)
            elif value.lower() in ('true', 'false'):
                value = value.lower() == 'true'
            
            config_manager.set(key, value)
            console.print(f"[green]Set {key} = {value}[/green]")
        except Exception as e:
            console.print(f"[red]Error setting config: {e}[/red]")


@cli.command()
@click.argument("url")
@click.option("--import-cookie", "import_cookie", type=click.Choice(["chrome", "firefox", "edge"]),
              help="Import cookies from browser for testing")
def test(url: str, import_cookie: Optional[str]):
    """Test if URL is accessible and detect video type."""
    # Detect link type
    category = LinkDetector.detect_category(url)
    suggestion = LinkDetector.get_header_suggestion(url, category)
    
    console.print(f"\n[bold]URL:[/bold] {url}")
    console.print(f"[bold]Category:[/bold] {category.value}")
    
    if suggestion.required_headers:
        console.print(f"[bold]Required headers:[/bold] {', '.join(suggestion.required_headers)}")
    if suggestion.suggested_headers:
        console.print(f"[bold]Suggested headers:[/bold] {', '.join(suggestion.suggested_headers)}")
    if suggestion.warning:
        console.print(f"[yellow]Warning: {suggestion.warning}[/yellow]")
    
    # Test with HEAD request
    import httpx
    
    headers = {}
    if import_cookie:
        cookie = CookieImporter.import_from_browser(import_cookie)
        if cookie:
            headers['Cookie'] = cookie
            console.print(f"[green]Cookies imported from {import_cookie}[/green]")
    
    try:
        response = httpx.head(url, headers=headers, timeout=10, follow_redirects=True)
        console.print(f"\n[bold]HTTP Status:[/bold] {response.status_code}")
        
        if response.status_code == 200:
            console.print("[green]✓ URL is accessible[/green]")
            
            content_type = response.headers.get('content-type', '')
            if content_type:
                console.print(f"  Content-Type: {content_type}")
            
            content_length = response.headers.get('content-length')
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                console.print(f"  Size: {size_mb:.2f} MB")
                
        elif response.status_code in (403, 401):
            console.print("[red]✗ Access denied[/red] - Check headers or cookies")
        elif response.status_code == 404:
            console.print("[red]✗ URL not found[/red]")
        else:
            console.print(f"[yellow]? Response: {response.status_code}[/yellow]")
            
    except httpx.TimeoutException:
        console.print("[red]✗ Connection timeout[/red]")
    except httpx.ConnectError:
        console.print("[red]✗ Connection error[/red]")
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")


@cli.command()
def clear_history():
    """Clear download history."""
    config = ConfigManager()
    history_manager = HistoryManager(config)
    history_manager.clear()
    console.print("[green]History cleared[/green]")


def main():
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()