#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import gc
import ipaddress
import json
import mmap
import os
import platform
import secrets
import stat
import subprocess
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Set, AsyncGenerator, Optional

import aiodns
import httpx
import orjson
import pyperclip
from loguru import logger
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Static,
    RichLog,
    Input,
    Label,
    Checkbox,
    Select,
    DirectoryTree,
)
from textual.widgets._directory_tree import DirEntry


class PlainDirectoryTree(DirectoryTree):
    """Custom DirectoryTree that uses plain text icons instead of emojis for Linux compatibility."""

    # Override class-level icon constants
    ICON_FOLDER = "[DIR]  "
    ICON_FOLDER_OPEN = "[DIR]  "
    ICON_FILE = "[FILE] "

    def render_label(self, node, base_style, style):
        """Override render to ensure plain icons are used."""
        node_label = node._label
        icon = self.ICON_FILE

        if isinstance(node.data, DirEntry):
            if node.data.path.is_dir():
                icon = self.ICON_FOLDER_OPEN if node.is_expanded else self.ICON_FOLDER

        label = Text(icon, style=base_style + style) if icon else Text()
        label.append(node_label.plain, base_style + style)
        return label


# Configure logging (disabled by default)
logger.remove()  # Remove default handler to disable all logging
# Uncomment below to enable file logging for debugging
# logger.add(
#     "logs/dnsscanner_{time}.log",
#     rotation="50 MB",
#     compression="zip",
#     level="DEBUG",
# )


class SlipstreamManager:
    """Manages slipstream client download and execution across platforms."""

    DOWNLOAD_URLS = {
        "Darwin-arm64": "https://github.com/AliRezaBeigy/slipstream-rust-deploy/releases/latest/download/slipstream-client-darwin-arm64",
        "Darwin-x86_64": "https://github.com/AliRezaBeigy/slipstream-rust-deploy/releases/latest/download/slipstream-client-darwin-amd64",
        "Windows": "https://github.com/AliRezaBeigy/slipstream-rust-deploy/releases/latest/download/slipstream-client-windows-amd64.exe",
        "Linux": "https://github.com/AliRezaBeigy/slipstream-rust-deploy/releases/latest/download/slipstream-client-linux-amd64",
    }

    # Windows DLL dependencies (required for slipstream-client on Windows)
    WINDOWS_DLLS = {
        "libcrypto-3-x64.dll": "https://raw.githubusercontent.com/xullexer/PYDNS-Scanner/main/slipstream-client/windows/libcrypto-3-x64.dll",
        "libssl-3-x64.dll": "https://raw.githubusercontent.com/xullexer/PYDNS-Scanner/main/slipstream-client/windows/libssl-3-x64.dll",
    }

    # Primary filenames (for new downloads)
    FILENAMES = {
        "Darwin-arm64": "slipstream-client-darwin-arm64",
        "Darwin-x86_64": "slipstream-client-darwin-amd64",
        "Windows": "slipstream-client-windows-amd64.exe",
        "Linux": "slipstream-client-linux-amd64",
    }

    # Alternative filenames to check (for backwards compatibility)
    ALT_FILENAMES = {
        "Windows": ["slipstream-client.exe", "slipstream-client-windows-amd64.exe"],
        "Darwin-arm64": ["slipstream-client", "slipstream-client-darwin-arm64"],
        "Darwin-x86_64": ["slipstream-client", "slipstream-client-darwin-amd64"],
        "Linux": ["slipstream-client", "slipstream-client-linux-amd64"],
    }

    PLATFORM_DIRS = {
        "Darwin": "mac",
        "Windows": "windows",
        "Linux": "linux",
    }

    def __init__(self):
        self.base_dir = Path(__file__).parent / "slipstream-client"
        self.system = platform.system()
        self.machine = platform.machine()
        self._cached_executable_path: Optional[Path] = None

        # Normalize machine architecture
        if self.machine in ("x86_64", "AMD64", "i386", "i686", "x86"):
            self.machine = "x86_64"
        elif self.machine == "aarch64":
            self.machine = "arm64"

    def get_platform_key(self) -> str:
        """Get the platform key for download URLs."""
        # Windows uses a single key (no architecture differentiation)
        if self.system == "Windows":
            return "Windows"
        elif self.system == "Linux":
            return "Linux"
        elif self.system == "Darwin":
            # macOS differentiates between ARM and Intel
            return f"Darwin-{self.machine}"
        else:
            raise RuntimeError(f"Unsupported platform: {self.system}")

    def get_platform_dir(self) -> Path:
        """Get the platform-specific directory."""
        dir_name = self.PLATFORM_DIRS.get(self.system, self.system.lower())
        return self.base_dir / dir_name

    def get_executable_path(self) -> Path:
        """Get the path to the slipstream executable.

        First checks for any existing executable (including legacy names),
        then falls back to the primary filename for new downloads.
        """
        # Return cached path if already found
        if self._cached_executable_path and self._cached_executable_path.exists():
            return self._cached_executable_path

        platform_key = self.get_platform_key()
        platform_dir = self.get_platform_dir()

        # Check for alternative filenames first (existing installations)
        alt_filenames = self.ALT_FILENAMES.get(platform_key, [])
        for filename in alt_filenames:
            exe_path = platform_dir / filename
            if exe_path.exists():
                self._cached_executable_path = exe_path
                return exe_path

        # Fall back to primary filename (for new downloads)
        filename = self.FILENAMES.get(platform_key)
        if not filename:
            raise RuntimeError(f"Unsupported platform: {self.system} {self.machine}")

        return platform_dir / filename

    def is_installed(self) -> bool:
        """Check if slipstream is already installed."""
        platform_key = self.get_platform_key()
        platform_dir = self.get_platform_dir()

        # Check all possible filenames
        alt_filenames = self.ALT_FILENAMES.get(platform_key, [])
        for filename in alt_filenames:
            if (platform_dir / filename).exists():
                return True

        # Also check primary filename
        primary_filename = self.FILENAMES.get(platform_key)
        if primary_filename and (platform_dir / primary_filename).exists():
            return True

        return False

    def ensure_executable(self) -> bool:
        """Ensure the slipstream executable has proper permissions.

        On Linux/macOS, this sets the executable bit.
        On Windows, no action is needed.

        Returns:
            True if permissions were set successfully or not needed, False on error.
        """
        try:
            exe_path = self.get_executable_path()
            if not exe_path.exists():
                return False

            if self.system in ("Linux", "Darwin"):
                # Set executable bit for user, group, and others
                current_mode = exe_path.stat().st_mode
                exe_path.chmod(
                    current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
                )
                logger.info(f"Set executable permissions on {exe_path}")

            return True
        except Exception as e:
            logger.error(f"Failed to set executable permissions: {e}")
            return False

    async def ensure_installed(self, log_callback=None) -> tuple[bool, str]:
        """Ensure slipstream is installed. Download if not present.

        Args:
            log_callback: Optional callback(message) for status updates

        Returns:
            Tuple of (success, message)
        """

        def log(msg):
            if log_callback:
                log_callback(msg)
            logger.info(msg)

        # Check if already installed
        if self.is_installed():
            log("[green]✓ Slipstream client found[/green]")
            return (True, "Already installed")

        # Not installed, download it
        log("[cyan]Slipstream client not found, downloading...[/cyan]")
        success = await self.download()

        if success:
            log("[green]✓ Slipstream client downloaded successfully[/green]")
            return (True, "Downloaded successfully")
        else:
            log("[red]✗ Failed to download Slipstream client[/red]")
            return (False, "Download failed")

    def get_download_url(self) -> Optional[str]:
        """Get the download URL for current platform."""
        try:
            platform_key = self.get_platform_key()
            return self.DOWNLOAD_URLS.get(platform_key)
        except RuntimeError:
            return None

    async def download(
        self, progress_callback=None, max_retries: int = 5, retry_delay: float = 2.0
    ) -> bool:
        """Download slipstream for the current platform with resume and retry support.

        Args:
            progress_callback: Optional callback(downloaded, total, status) for progress updates
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            True if download successful, False otherwise
        """
        url = self.get_download_url()
        if not url:
            return False

        exe_path = self.get_executable_path()
        temp_path = exe_path.with_suffix(exe_path.suffix + ".partial")
        platform_dir = self.get_platform_dir()

        # Create directory if it doesn't exist
        platform_dir.mkdir(parents=True, exist_ok=True)

        for attempt in range(1, max_retries + 1):
            try:
                # Check if we have a partial download to resume
                downloaded = 0
                if temp_path.exists():
                    downloaded = temp_path.stat().st_size

                headers = {}
                if downloaded > 0:
                    headers["Range"] = f"bytes={downloaded}-"
                    if progress_callback:
                        progress_callback(
                            downloaded,
                            0,
                            f"Resuming from {downloaded / (1024*1024):.1f} MB...",
                        )

                async with httpx.AsyncClient(
                    follow_redirects=True,
                    timeout=httpx.Timeout(30.0, read=60.0, connect=30.0),
                    verify=True,  # Enable SSL verification
                    limits=httpx.Limits(
                        max_keepalive_connections=5, max_connections=10
                    ),
                ) as client:
                    async with client.stream("GET", url, headers=headers) as response:
                        # Check if server supports resume
                        if response.status_code == 206:  # Partial content
                            content_range = response.headers.get("content-range", "")
                            if "/" in content_range:
                                total = int(content_range.split("/")[1])
                            else:
                                total = downloaded + int(
                                    response.headers.get("content-length", 0)
                                )
                            mode = "ab"  # Append mode
                        elif response.status_code == 200:
                            # Server doesn't support resume, start fresh
                            total = int(response.headers.get("content-length", 0))
                            downloaded = 0
                            mode = "wb"  # Write mode (overwrite)
                        else:
                            response.raise_for_status()
                            continue

                        if progress_callback:
                            progress_callback(downloaded, total, "Downloading...")

                        with open(temp_path, mode) as f:
                            async for chunk in response.aiter_bytes(chunk_size=32768):
                                f.write(chunk)
                                downloaded += len(chunk)
                                if progress_callback:
                                    progress_callback(
                                        downloaded, total, "Downloading..."
                                    )

                # Download complete - rename temp file to final
                if temp_path.exists():
                    if exe_path.exists():
                        exe_path.unlink()
                    temp_path.rename(exe_path)

                # Make executable on Unix-like systems
                if self.system in ("Linux", "Darwin"):
                    exe_path.chmod(
                        exe_path.stat().st_mode
                        | stat.S_IXUSR
                        | stat.S_IXGRP
                        | stat.S_IXOTH
                    )
                    logger.info(f"Set executable permissions on {exe_path}")

                # Download Windows DLLs if on Windows
                if self.system == "Windows":
                    await self._download_windows_dlls()

                return True

            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.HTTPStatusError,
                httpx.ConnectError,
            ) as e:
                error_msg = f"{type(e).__name__}"
                if hasattr(e, "__cause__") and e.__cause__:
                    error_msg += f": {str(e.__cause__)}"

                if progress_callback:
                    progress_callback(
                        downloaded, 0, f"Retry {attempt}/{max_retries}: {error_msg}"
                    )

                if attempt < max_retries:
                    await asyncio.sleep(retry_delay * attempt)  # Exponential backoff
                    continue
                else:
                    # Max retries reached, keep partial file for next attempt
                    return False
            except Exception as e:
                # Unexpected error - clean up partial download
                logger.error(f"Unexpected download error: {e}", exc_info=True)
                if temp_path.exists():
                    temp_path.unlink()
                return False

        return False

    async def _download_windows_dlls(self, log_callback=None) -> bool:
        """Download required Windows DLL dependencies.

        Args:
            log_callback: Optional callback(message) for status updates

        Returns:
            True if all DLLs downloaded successfully, False otherwise
        """
        if self.system != "Windows":
            return True

        platform_dir = self.get_platform_dir()
        platform_dir.mkdir(parents=True, exist_ok=True)

        def log(msg):
            if log_callback:
                log_callback(msg)
            logger.info(msg)

        all_success = True
        for dll_name, dll_url in self.WINDOWS_DLLS.items():
            dll_path = platform_dir / dll_name

            # Skip if DLL already exists
            if dll_path.exists():
                log(f"[dim]DLL already exists: {dll_name}[/dim]")
                continue

            try:
                log(f"[cyan]Downloading {dll_name}...[/cyan]")
                async with httpx.AsyncClient(
                    follow_redirects=True,
                    timeout=httpx.Timeout(30.0, read=60.0, connect=30.0),
                    verify=True,
                ) as client:
                    response = await client.get(dll_url)
                    response.raise_for_status()

                    with open(dll_path, "wb") as f:
                        f.write(response.content)

                    log(f"[green]✓ Downloaded {dll_name}[/green]")
            except Exception as e:
                log(f"[red]Failed to download {dll_name}: {e}[/red]")
                all_success = False

        return all_success

    async def download_with_ui(
        self, progress_bar, log_widget, max_retries: int = 5, retry_delay: float = 2.0
    ) -> bool:
        """Download slipstream with UI updates for progress bar and log.

        This method handles UI updates directly in the async context without using call_from_thread.

        Args:
            progress_bar: CustomProgressBar widget to update
            log_widget: RichLog widget to write status messages
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            True if download successful, False otherwise
        """
        url = self.get_download_url()
        if not url:
            log_widget.write("[red]No download URL available for this platform[/red]")
            return False

        exe_path = self.get_executable_path()
        temp_path = exe_path.with_suffix(exe_path.suffix + ".partial")
        platform_dir = self.get_platform_dir()

        # Create directory if it doesn't exist
        platform_dir.mkdir(parents=True, exist_ok=True)

        last_logged_percent = -1

        for attempt in range(1, max_retries + 1):
            try:
                # Check if we have a partial download to resume
                downloaded = 0
                if temp_path.exists():
                    downloaded = temp_path.stat().st_size

                headers = {}
                if downloaded > 0:
                    headers["Range"] = f"bytes={downloaded}-"
                    log_widget.write(
                        f"[cyan]Resuming from {downloaded / (1024*1024):.1f} MB...[/cyan]"
                    )

                async with httpx.AsyncClient(
                    follow_redirects=True,
                    timeout=httpx.Timeout(30.0, read=60.0, connect=30.0),
                    verify=True,
                    limits=httpx.Limits(
                        max_keepalive_connections=5, max_connections=10
                    ),
                ) as client:
                    async with client.stream("GET", url, headers=headers) as response:
                        # Check if server supports resume
                        if response.status_code == 206:  # Partial content
                            content_range = response.headers.get("content-range", "")
                            if "/" in content_range:
                                total = int(content_range.split("/")[1])
                            else:
                                total = downloaded + int(
                                    response.headers.get("content-length", 0)
                                )
                            mode = "ab"  # Append mode
                        elif response.status_code == 200:
                            # Server doesn't support resume, start fresh
                            total = int(response.headers.get("content-length", 0))
                            downloaded = 0
                            mode = "wb"  # Write mode (overwrite)
                        else:
                            response.raise_for_status()
                            continue

                        log_widget.write(
                            f"[cyan]Downloading...[/cyan] Total: {total / (1024*1024):.1f} MB"
                        )

                        with open(temp_path, mode) as f:
                            async for chunk in response.aiter_bytes(chunk_size=32768):
                                f.write(chunk)
                                downloaded += len(chunk)

                                # Update progress bar
                                if total > 0:
                                    progress_bar.update_progress(downloaded, total)

                                    # Log progress at 10% intervals
                                    current_percent = (
                                        int((downloaded / total) * 10) * 10
                                    )
                                    if current_percent > last_logged_percent:
                                        last_logged_percent = current_percent
                                        mb_downloaded = downloaded / (1024 * 1024)
                                        mb_total = total / (1024 * 1024)
                                        log_widget.write(
                                            f"[dim]Progress: {mb_downloaded:.1f}/{mb_total:.1f} MB ({current_percent}%)[/dim]"
                                        )

                # Download complete - rename temp file to final
                if temp_path.exists():
                    if exe_path.exists():
                        exe_path.unlink()
                    temp_path.rename(exe_path)

                # Make executable on Unix-like systems
                if self.system in ("Linux", "Darwin"):
                    exe_path.chmod(
                        exe_path.stat().st_mode
                        | stat.S_IXUSR
                        | stat.S_IXGRP
                        | stat.S_IXOTH
                    )
                    log_widget.write(
                        "[green]✓ Set executable permissions on slipstream client[/green]"
                    )

                # Download Windows DLLs if on Windows
                if self.system == "Windows":
                    log_widget.write(
                        "[cyan]Downloading required Windows DLLs...[/cyan]"
                    )
                    await self._download_windows_dlls_with_ui(log_widget)

                return True

            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.HTTPStatusError,
                httpx.ConnectError,
            ) as e:
                error_msg = f"{type(e).__name__}"
                if hasattr(e, "__cause__") and e.__cause__:
                    error_msg += f": {str(e.__cause__)}"

                log_widget.write(
                    f"[yellow]Retry {attempt}/{max_retries}: {error_msg}[/yellow]"
                )

                if attempt < max_retries:
                    log_widget.write(
                        f"[dim]Waiting {retry_delay * attempt:.0f}s before retry...[/dim]"
                    )
                    await asyncio.sleep(retry_delay * attempt)  # Exponential backoff
                    continue
                else:
                    # Max retries reached, keep partial file for next attempt
                    return False
            except Exception as e:
                log_widget.write(
                    f"[red]Unexpected error: {type(e).__name__}: {e}[/red]"
                )
                # Unexpected error - clean up partial download
                if temp_path.exists():
                    temp_path.unlink()
                return False

        return False

    async def _download_windows_dlls_with_ui(self, log_widget) -> bool:
        """Download required Windows DLL dependencies with UI updates.

        Args:
            log_widget: RichLog widget to write status messages

        Returns:
            True if all DLLs downloaded successfully, False otherwise
        """
        if self.system != "Windows":
            return True

        platform_dir = self.get_platform_dir()
        platform_dir.mkdir(parents=True, exist_ok=True)

        all_success = True
        for dll_name, dll_url in self.WINDOWS_DLLS.items():
            dll_path = platform_dir / dll_name

            # Skip if DLL already exists
            if dll_path.exists():
                log_widget.write(f"[dim]DLL already exists: {dll_name}[/dim]")
                continue

            try:
                log_widget.write(f"[cyan]Downloading {dll_name}...[/cyan]")
                async with httpx.AsyncClient(
                    follow_redirects=True,
                    timeout=httpx.Timeout(30.0, read=60.0, connect=30.0),
                    verify=True,
                ) as client:
                    response = await client.get(dll_url)
                    response.raise_for_status()

                    with open(dll_path, "wb") as f:
                        f.write(response.content)

                    log_widget.write(f"[green]✓ Downloaded {dll_name}[/green]")
            except Exception as e:
                log_widget.write(f"[red]Failed to download {dll_name}: {e}[/red]")
                all_success = False

        return all_success

    def get_run_command(self, dns_ip: str, port: int, domain: str) -> list:
        """Get the command to run slipstream (same args for all platforms).

        Args:
            dns_ip: DNS server IP
            port: TCP listen port
            domain: Domain for slipstream

        Returns:
            List of command arguments
        """
        exe_path = self.get_executable_path()

        # Ensure executable permissions are set (important for Linux/macOS)
        self.ensure_executable()

        return [
            str(exe_path),
            "--resolver",
            f"{dns_ip}:53",
            "--resolver",
            "8.8.4.4:53",
            "--tcp-listen-port",
            str(port),
            "--domain",
            domain,
        ]


class StatsWidget(Static):
    """Display scan statistics."""

    found = reactive(0)
    passed = reactive(0)
    failed = reactive(0)
    scanned = reactive(0)
    total = reactive(0)
    speed = reactive(0.0)
    elapsed = reactive(0.0)

    def render(self) -> str:
        """Render the stats."""
        return f"""[b cyan]PYDNS Scanner Statistics[/b cyan]

[yellow]Total IPs:[/yellow] {self.total:,}
[yellow]Scanned:[/yellow] {self.scanned:,}
[white]Found:[/white] {self.found}
[green]Pass:[/green] {self.passed}
[red]Fail:[/red] {self.failed}
[yellow]Speed:[/yellow] {self.speed:.1f} IPs/sec
[yellow]Elapsed:[/yellow] {self.elapsed:.1f}s
"""


class CustomProgressBar(Static):
    """Custom progress bar with ▓▒ style and float percentage."""

    progress = reactive(0.0)
    total = reactive(100.0)
    bar_width = 40  # Width of the bar in characters

    def render(self) -> str:
        """Render the custom progress bar."""
        if self.total <= 0:
            percent = 0.0
        else:
            percent = (self.progress / self.total) * 100

        # Calculate filled portion
        filled = int((percent / 100) * self.bar_width)
        empty = self.bar_width - filled

        # Build the bar with ▓ for filled and ▒ for empty
        bar = "▓" * filled + "▒" * empty

        # Color: green for filled, dim for empty
        return f"[green]{bar[:filled]}[/green][dim]{bar[filled:]}[/dim] [cyan]{percent:.2f}%[/cyan]"

    def update_progress(self, progress: float, total: float) -> None:
        """Update progress values."""
        self.progress = progress
        self.total = total


class DNSScannerTUI(App):
    """PYDNS Scanner with Textual TUI."""

    # Set Dracula theme as default
    ENABLE_COMMAND_PALETTE = False  # Disable command palette

    CSS = """
    Screen {
        background: #0d1117;
    }
    
    /* Dark theme colors */
    Header {
        background: #161b22;
        color: #58a6ff;
    }
    
    Footer {
        background: #161b22;
        color: #8b949e;
    }
    
    Footer > .footer--key {
        background: #21262d;
        color: #58a6ff;
    }
    
    Footer > .footer--description {
        color: #c9d1d9;
    }
    
    /* Start Screen Styles */
    #start-screen {
        width: 100%;
        height: 100%;
        background: #0d1117;
        padding: 1;
    }
    
    #start-form {
        width: 100%;
        height: auto;
        max-height: 100%;
        border: solid #30363d;
        background: #161b22;
        padding: 2;
        overflow-y: auto;
    }
    
    #start-title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: #58a6ff;
        padding: 1;
    }
    
    .form-row {
        width: 100%;
        height: auto;
        min-height: 3;
        margin: 1 0;
    }
    
    .form-label {
        width: 20;
        padding: 0 1;
        color: #c9d1d9;
    }
    
    .form-input {
        width: 1fr;
    }
    
    Input {
        background: #21262d;
        border: solid #30363d;
        color: #c9d1d9;
        height: 3;
    }
    
    Input:focus {
        border: solid #58a6ff;
    }
    
    #file-browser-container {
        width: 100%;
        height: 10;
        max-height: 15;
        border: solid #238636;
        background: #161b22;
        margin: 1 0;
        display: none;
    }
    
    DirectoryTree {
        height: 100%;
        background: #161b22;
        color: #c9d1d9;
    }
    
    DirectoryTree:focus > .directory-tree--folder {
        color: #58a6ff;
    }
    
    Select {
        width: 1fr;
        background: #21262d;
        border: solid #30363d;
    }
    
    Select.-expanded {
        height: auto;
    }
    
    SelectCurrent {
        background: #21262d;
        color: #c9d1d9;
        padding: 0 1;
    }
    
    Select > SelectOverlay {
        background: #161b22;
        border: solid #58a6ff;
        width: 100%;
    }
    
    Select > SelectOverlay > OptionList {
        background: #161b22;
        color: #c9d1d9;
        padding: 0;
        height: auto;
    }
    
    Select > SelectOverlay > OptionList > .option-list--option {
        padding: 0 1;
        background: #161b22;
        color: #c9d1d9;
    }
    
    Select > SelectOverlay > OptionList > .option-list--option-highlighted {
        background: #30363d;
        color: #58a6ff;
    }
    
    Select > SelectOverlay > OptionList > .option-list--option-hover {
        background: #21262d;
    }
    
    #progress-container {
        width: 100%;
        height: 3;
        margin: 0 1;
        border: solid #30363d;
        background: #161b22;
        padding: 0 1;
    }

    #start-buttons {
        width: 100%;
        height: auto;
        align: center middle;
        margin-top: 2;
    }
    
    #proxy-auth-container {
        width: 100%;
        height: auto;
        display: none;
        padding: 0;
        margin: 0;
    }
    
    /* Scan Screen Styles */
    #scan-screen {
        width: 100%;
        height: 100%;
        background: #0d1117;
    }

    #stats {
        width: 100%;
        height: auto;
        border: solid #238636;
        background: #161b22;
        padding: 1;
        margin: 1;
        color: #c9d1d9;
    }

    #progress-bar {
        width: 100%;
        max-width: 100%;
        height: 1;
        content-align: center middle;
    }
    
    ProgressBar > .bar--bar {
        color: #238636;
        background: #21262d;
    }
    
    ProgressBar > .bar--complete {
        color: #238636;
    }

    #main-content {
        width: 100%;
        height: 1fr;
    }

    #results {
        width: 60%;
        height: 100%;
        border: solid #58a6ff;
        background: #161b22;
        margin: 1;
    }

    #logs {
        width: 40%;
        height: 100%;
        border: solid #d29922;
        background: #161b22;
        margin: 1;
    }

    #controls {
        width: 100%;
        height: auto;
        margin: 1;
        align: center middle;
    }

    Button {
        margin: 0 1;
        background: #21262d;
        color: #c9d1d9;
        border: solid #30363d;
    }
    
    Button:hover {
        background: #30363d;
        color: #58a6ff;
    }
    
    Button:focus {
        border: solid #58a6ff;
    }
    
    Button.-primary {
        background: #238636;
        color: #ffffff;
        border: solid #238636;
    }
    
    Button.-primary:hover {
        background: #2ea043;
    }

    DataTable {
        height: 100%;
        background: #161b22;
    }
    
    DataTable > .datatable--header {
        background: #21262d;
        color: #58a6ff;
        text-style: bold;
    }
    
    DataTable > .datatable--cursor {
        background: #30363d;
        color: #c9d1d9;
    }
    
    DataTable > .datatable--hover {
        background: #21262d;
    }

    RichLog {
        height: 100%;
        background: #161b22;
        color: #c9d1d9;
    }
    
    Checkbox {
        background: transparent;
        color: #c9d1d9;
        margin-right: 2;
    }
    
    Checkbox:focus > .toggle--button {
        background: #58a6ff;
    }
    
    .checkbox-row {
        align: center middle;
        height: auto;
        padding: 1 0;
    }
    """

    BINDINGS = [
        ("s", "start_scan", "Start"),
        ("q", "quit", "Quit"),
        ("c", "save_results", "Save"),
        ("p", "pause_scan", "Pause"),
        ("r", "resume_scan", "Resume"),
        ("x", "shuffle_ips", "Shuffle"),
    ]

    def __init__(self):
        super().__init__()
        self.subnet_file = ""
        self.selected_cidr_file = ""  # Track custom selected file
        self.domain = ""
        self.dns_type = "A"
        self.concurrency = 100
        self.random_subdomain = False
        self.test_slipstream = False
        self.bell_sound_enabled = False  # Bell sound on pass
        self.proxy_auth_enabled = False  # Proxy authentication
        self.proxy_username = ""  # Proxy username
        self.proxy_password = ""  # Proxy password

        # Config file for caching settings
        self.config_dir = Path.home() / ".pydns-scanner"
        self.config_file = self.config_dir / "config.json"

        self.slipstream_manager = SlipstreamManager()
        self.slipstream_path = str(self.slipstream_manager.get_executable_path())
        self.slipstream_domain = ""
        self.found_servers: Set[str] = set()  # Keep found servers for results
        self.server_times: dict[str, float] = {}
        self.proxy_results: dict[str, str] = (
            {}
        )  # IP -> "Success", "Failed", or "Testing"
        self.start_time = 0.0
        self.last_update_time = 0.0
        self.last_table_update_time = 0.0
        self.current_scanned = 0
        self.table_needs_rebuild = False
        self.scan_started = False
        self.is_paused = False
        self.pause_event = asyncio.Event()
        self.pause_event.set()  # Not paused initially

        # Button spam protection
        self._processing_button = False

        # Slipstream parallel testing config
        self.slipstream_max_concurrent = 5
        self.slipstream_base_port = 10800  # Base port, will use 10800-10804
        self.available_ports: deque = deque()  # Available ports for testing
        self.slipstream_semaphore: asyncio.Semaphore = (
            None  # Will be created in async context
        )
        self.pending_slipstream_tests: deque = deque()  # Queue for pending tests
        self.slipstream_tasks: set = set()  # Track running slipstream tasks
        self.active_scan_tasks: list = []  # Track active DNS scan tasks for cleanup
        self._shutdown_event: asyncio.Event = None  # Signal for graceful shutdown
        self.slipstream_processes: list = (
            []
        )  # Track all slipstream processes for cleanup

        # Shuffle support
        self.remaining_ips: list = []  # Track remaining IPs for shuffle feature
        # Note: tested_ips removed for better memory management - only used temporarily during shuffle

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header(show_clock=False)

        # Start Screen
        with Container(id="start-screen"):
            with Vertical(id="start-form"):
                yield Static(
                    "[b cyan]PYDNS Scanner Configuration[/b cyan]", id="start-title"
                )

                with Horizontal(classes="form-row"):
                    yield Label("CIDR File:", classes="form-label")
                    yield Select(
                        [("Iran IPs (~10M IPs)", "iran"), ("Custom File...", "custom")],
                        value="iran",
                        allow_blank=False,
                        id="input-cidr-select",
                        classes="form-input",
                    )

                with Container(id="file-browser-container"):
                    yield PlainDirectoryTree(".", id="file-browser")

                with Horizontal(classes="form-row"):
                    yield Label("Domain:", classes="form-label")
                    yield Input(
                        placeholder="e.g., google.com",
                        id="input-domain",
                        classes="form-input",
                    )

                with Horizontal(classes="form-row"):
                    yield Label("Proxy Auth:", classes="form-label")
                    yield Checkbox("Enable", id="input-proxy-auth")

                with Container(id="proxy-auth-container"):
                    with Horizontal(classes="form-row"):
                        yield Label("Username:", classes="form-label")
                        yield Input(
                            placeholder="proxy username",
                            id="input-proxy-user",
                            classes="form-input",
                        )
                    with Horizontal(classes="form-row"):
                        yield Label("Password:", classes="form-label")
                        yield Input(
                            placeholder="proxy password",
                            id="input-proxy-pass",
                            classes="form-input",
                            password=True,
                        )

                with Horizontal(classes="form-row"):
                    yield Label("DNS Type:", classes="form-label")
                    yield Select(
                        [
                            ("A (IPv4)", "A"),
                            ("AAAA (IPv6)", "AAAA"),
                            ("MX (Mail)", "MX"),
                            ("TXT", "TXT"),
                            ("NS", "NS"),
                        ],
                        value="A",
                        allow_blank=False,
                        id="input-type",
                        classes="form-input",
                    )

                with Horizontal(classes="form-row"):
                    yield Label("Concurrency:", classes="form-label")
                    yield Input(
                        placeholder="100",
                        id="input-concurrency",
                        classes="form-input",
                        value="100",
                    )

                with Horizontal(classes="form-row checkbox-row"):
                    yield Checkbox("Random Subdomain", id="input-random")
                    yield Checkbox("Proxy Test", id="input-slipstream")
                    yield Checkbox("Bell on Pass", id="input-bell")

                with Horizontal(id="start-buttons"):
                    yield Button("Start Scan", id="start-scan-btn", variant="success")
                    yield Button("Exit", id="exit-btn", variant="error")

        # Scan Screen (initially hidden)
        with Container(id="scan-screen"):
            yield StatsWidget(id="stats")
            with Container(id="progress-container"):
                yield CustomProgressBar(id="progress-bar")
            with Horizontal(id="main-content"):
                with Container(id="results"):
                    yield DataTable(id="results-table")
                with Container(id="logs"):
                    yield RichLog(id="log-display", highlight=True, markup=True)
            with Horizontal(id="controls"):
                yield Button("⏸  Pause", id="pause-btn", variant="warning")
                yield Button("🔀 Shuffle", id="shuffle-btn", variant="default")
                yield Button("▶  Resume", id="resume-btn", variant="primary")
                yield Button("Save Results", id="save-btn", variant="success")
                yield Button("Quit", id="quit-btn", variant="error")

        yield Footer()

    def _load_cached_domain(self) -> str:
        """Load last used domain from config file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    return config.get("last_domain", "")
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"Config file corrupted or invalid, ignoring: {e}")
        except (OSError, IOError) as e:
            logger.debug(f"Failed to read config file: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error loading cached domain: {e}")
        return ""

    def _save_domain_cache(self, domain: str) -> None:
        """Save domain to config file for next session."""
        try:
            # Create config directory if it doesn't exist
            self.config_dir.mkdir(parents=True, exist_ok=True)

            # Load existing config or create new
            config = {}
            if self.config_file.exists():
                try:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        config = json.load(f)
                except (json.JSONDecodeError, OSError):
                    # Start fresh if config is corrupted
                    config = {}

            # Update domain
            config["last_domain"] = domain

            # Save config
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except (OSError, IOError) as e:
            logger.debug(f"Failed to save domain cache (permission/IO error): {e}")
        except Exception as e:
            logger.warning(f"Unexpected error saving domain cache: {e}")

    def on_mount(self) -> None:
        """Initialize when app is mounted."""
        # Set dark theme (GitHub dark)
        self.dark = True

        # Initialize keybindings for start screen
        self._update_keybinding_visibility(scanning=False, paused=False)

        # Hide scan screen initially
        self.query_one("#scan-screen").display = False

        # Load cached domain and set it
        cached_domain = self._load_cached_domain()
        try:
            domain_input = self.query_one("#input-domain", Input)
            domain_input.value = cached_domain
        except Exception as e:
            logger.debug(f"Could not set cached domain (widget may not be ready): {e}")

        # Setup results table
        table = self.query_one("#results-table", DataTable)
        table.add_columns("IP Address", "Response Time", "Status", "Proxy Test")
        table.cursor_type = "row"

        # Hide pause/resume/shuffle buttons initially
        try:
            self.query_one("#pause-btn", Button).display = False
            self.query_one("#resume-btn", Button).display = False
            self.query_one("#shuffle-btn", Button).display = False
        except Exception as e:
            logger.debug(f"Could not hide buttons during mount: {e}")

    def action_quit(self) -> None:
        """Gracefully quit the application with proper cleanup."""
        # Signal shutdown to stop any running scans
        if self._shutdown_event:
            self._shutdown_event.set()

        # Kill all slipstream processes immediately
        if hasattr(self, "slipstream_processes"):
            for process in self.slipstream_processes[:]:
                try:
                    if process and hasattr(process, "kill"):
                        process.kill()
                except (ProcessLookupError, OSError) as e:
                    logger.debug(f"Process already terminated or inaccessible: {e}")
            self.slipstream_processes.clear()

        # Cancel all active scan tasks
        if hasattr(self, "active_scan_tasks"):
            for task in self.active_scan_tasks[:]:
                try:
                    if not task.done():
                        task.cancel()
                except Exception as e:
                    logger.debug(f"Could not cancel scan task: {e}")
            self.active_scan_tasks.clear()

        # Cancel all slipstream test tasks
        if hasattr(self, "slipstream_tasks"):
            for task in list(self.slipstream_tasks):
                try:
                    if not task.done():
                        task.cancel()
                except Exception as e:
                    logger.debug(f"Could not cancel slipstream task: {e}")
            self.slipstream_tasks.clear()

        # Cancel all Textual workers
        try:
            self.workers.cancel_all()
        except Exception as e:
            logger.debug(f"Could not cancel workers: {e}")

        # Force garbage collection
        gc.collect()

        # Restore terminal state before force exit
        try:
            # Stop the Textual driver to restore terminal
            if hasattr(self, "_driver") and self._driver:
                self._driver.stop_application_mode()
        except Exception as e:
            logger.debug(f"Could not stop application mode: {e}")

        # Reset terminal on different platforms
        if platform.system() == "Windows":
            # Windows: reset console mode
            try:
                import ctypes

                kernel32 = ctypes.windll.kernel32
                # Get stdout handle
                handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
                # Enable virtual terminal processing and restore defaults
                kernel32.SetConsoleMode(handle, 0x0001 | 0x0002 | 0x0004)
                # Also restore stdin
                stdin_handle = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
                kernel32.SetConsoleMode(stdin_handle, 0x0080 | 0x0001 | 0x0002 | 0x0004)
                # Show cursor
                print("\033[?25h", end="", flush=True)
            except (ImportError, AttributeError, OSError) as e:
                logger.debug(f"Windows terminal reset failed: {e}")
        else:
            # Unix: reset terminal with stty
            try:
                subprocess.run(["stty", "sane"], check=False, capture_output=True)
                print("\033[?25h", end="", flush=True)  # Show cursor
            except (FileNotFoundError, subprocess.SubprocessError) as e:
                logger.debug(f"Unix terminal reset failed: {e}")

        # Force exit
        os._exit(0)

    def _update_keybinding_visibility(
        self, scanning: bool = False, paused: bool = False
    ) -> None:
        """Update keybinding visibility based on app state - now shows all bindings."""
        # All bindings are always visible in footer
        pass

    def action_pause_scan(self) -> None:
        """Keybinding action to pause scan."""
        if self.scan_started and not self.is_paused:
            self._pause_scan()
            self._update_keybinding_visibility(scanning=True, paused=True)

    def action_resume_scan(self) -> None:
        """Keybinding action to resume scan."""
        if self.scan_started and self.is_paused:
            self._resume_scan()
            self._update_keybinding_visibility(scanning=True, paused=False)

    def action_shuffle_ips(self) -> None:
        """Keybinding action to shuffle IPs (only when paused)."""
        if self.scan_started and self.is_paused:
            self.run_worker(self._shuffle_remaining_ips_async(), exclusive=False)

    def action_start_scan(self) -> None:
        """Keybinding action to start scan from config screen."""
        if not self.scan_started:
            try:
                start_screen = self.query_one("#start-screen")
                if start_screen.display:
                    self._start_scan_from_form()
            except Exception as e:
                logger.debug(f"Could not start scan via keybinding: {e}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        # Prevent button spam crashes
        if event.button.id in [
            "start-scan-btn",
            "pause-btn",
            "resume-btn",
            "shuffle-btn",
        ]:
            if self._processing_button:
                return
            self._processing_button = True

        try:
            if event.button.id == "start-scan-btn":
                self._start_scan_from_form()
            elif event.button.id == "exit-btn":
                self.action_quit()
            elif event.button.id == "pause-btn":
                self._pause_scan()
            elif event.button.id == "resume-btn":
                self._resume_scan()
            elif event.button.id == "shuffle-btn":
                # Run async shuffle in worker
                self.run_worker(self._shuffle_remaining_ips_async(), exclusive=False)
            elif event.button.id == "save-btn":
                self.action_save_results()
            elif event.button.id == "quit-btn":
                self.action_quit()
        finally:
            if event.button.id in [
                "start-scan-btn",
                "pause-btn",
                "resume-btn",
                "shuffle-btn",
            ]:
                self._processing_button = False

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle CIDR dropdown selection changes."""
        if event.select.id == "input-cidr-select":
            browser = self.query_one("#file-browser-container")
            if event.value == "custom":
                # Show file browser when Custom is selected
                browser.display = True
            else:
                # Hide browser for other selections
                browser.display = False

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox state changes."""
        if event.checkbox.id == "input-proxy-auth":
            try:
                container = self.query_one("#proxy-auth-container")
                container.display = event.value
            except Exception as e:
                logger.debug(f"Could not toggle proxy auth container: {e}")

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """Handle file selection from directory tree."""
        selected_file = str(event.path)

        # Store the selected file path
        self.selected_cidr_file = selected_file

        # Keep dropdown at "custom" value without adding new option
        cidr_select = self.query_one("#input-cidr-select", Select)
        cidr_select.value = "custom"

        # Hide browser after selection
        self.query_one("#file-browser-container").display = False

        # Notify user which file was selected
        file_name = Path(selected_file).name
        self.notify(f"Selected: {file_name}", severity="information", timeout=3)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key press in input fields on start screen."""
        # Only handle inputs on start screen
        if event.input.id in ["input-domain", "input-concurrency"]:
            # Check if start screen is visible
            try:
                start_screen = self.query_one("#start-screen")
                if start_screen.display:
                    # Start the scan when Enter is pressed
                    self._start_scan_from_form()
            except Exception as e:
                logger.debug(f"Could not handle input submit: {e}")

    def _pause_scan(self) -> None:
        """Pause the current scan."""
        if not self.scan_started or self.is_paused:
            return

        self.is_paused = True
        self.pause_event.clear()
        self._log("[yellow]⏸  Scan paused[/yellow]")
        self.notify("Scan paused", severity="warning")

        # Update button visibility
        try:
            self.query_one("#pause-btn", Button).display = False
            self.query_one("#resume-btn", Button).display = True
            self.query_one("#shuffle-btn", Button).display = True
        except Exception as e:
            logger.debug(f"Could not update button visibility on pause: {e}")

        # Update keybinding visibility
        self._update_keybinding_visibility(scanning=True, paused=True)

    def _resume_scan(self) -> None:
        """Resume the paused scan."""
        if not self.scan_started or not self.is_paused:
            return

        # If user shuffled IPs, we need to switch to memory mode for remaining scan
        if self.remaining_ips:
            self._log("[cyan]Resuming with shuffled IP order...[/cyan]")
            # The scan loop will handle the shuffled order appropriately

        self.is_paused = False
        self.pause_event.set()
        self._log("[green]▶  Scan resumed[/green]")
        self.notify("Scan resumed", severity="information")

        # Update button visibility
        try:
            self.query_one("#pause-btn", Button).display = True
            self.query_one("#resume-btn", Button).display = False
            self.query_one("#shuffle-btn", Button).display = False
        except Exception as e:
            logger.debug(f"Could not update button visibility on resume: {e}")

        # Update keybinding visibility
        self._update_keybinding_visibility(scanning=True, paused=False)

    def _start_scan_from_form(self) -> None:
        """Get values from form and start scanning."""
        # Get form values
        cidr_select = self.query_one("#input-cidr-select", Select)
        domain_input = self.query_one("#input-domain", Input)
        type_select = self.query_one("#input-type", Select)
        concurrency_input = self.query_one("#input-concurrency", Input)
        random_checkbox = self.query_one("#input-random", Checkbox)
        slipstream_checkbox = self.query_one("#input-slipstream", Checkbox)
        bell_checkbox = self.query_one("#input-bell", Checkbox)

        # Determine CIDR file based on dropdown selection
        cidr_value = str(cidr_select.value) if cidr_select.value else "iran"

        if cidr_value == "iran":
            # Use bundled Iran CIDR file as default
            iran_cidr_path = Path(__file__).parent / "iran-ipv4.cidrs"
            if not iran_cidr_path.exists():
                self.notify(
                    "Iran CIDR file not found! Please reinstall or select a custom file.",
                    severity="error",
                )
                return
            self.subnet_file = str(iran_cidr_path)
        elif cidr_value == "custom":
            # Use the custom selected file
            if not self.selected_cidr_file:
                self.notify(
                    "Please select a CIDR file from the file browser!",
                    severity="warning",
                )
                return
            if not Path(self.selected_cidr_file).exists():
                self.notify(
                    f"File not found: {self.selected_cidr_file}", severity="error"
                )
                return
            self.subnet_file = self.selected_cidr_file
        else:
            # Fallback to Iran default
            iran_cidr_path = Path(__file__).parent / "iran-ipv4.cidrs"
            self.subnet_file = str(iran_cidr_path)

        self.domain = domain_input.value.strip()
        self.slipstream_domain = self.domain
        self.dns_type = str(type_select.value) if type_select.value else "A"
        self.random_subdomain = random_checkbox.value
        self.test_slipstream = slipstream_checkbox.value
        self.bell_sound_enabled = bell_checkbox.value

        # Get proxy auth settings
        proxy_auth_checkbox = self.query_one("#input-proxy-auth", Checkbox)
        self.proxy_auth_enabled = proxy_auth_checkbox.value
        if self.proxy_auth_enabled:
            proxy_user_input = self.query_one("#input-proxy-user", Input)
            proxy_pass_input = self.query_one("#input-proxy-pass", Input)
            self.proxy_username = proxy_user_input.value.strip()
            self.proxy_password = proxy_pass_input.value
            if not self.proxy_username:
                self.notify("Please enter proxy username!", severity="error")
                return

        try:
            self.concurrency = int(concurrency_input.value.strip() or "100")
        except ValueError:
            self.concurrency = 100

        if not self.domain:
            self.notify("Please enter a domain!", severity="error")
            return

        # Save domain for next session
        self._save_domain_cache(self.domain)

        # Check slipstream version and update if needed
        if self.test_slipstream:
            self.notify(
                "Checking Slipstream client...", severity="information", timeout=2
            )
            self.run_worker(self._check_update_and_start_scan(), exclusive=True)
            return

        # Switch to scan screen
        self.query_one("#start-screen").display = False
        self.query_one("#scan-screen").display = True

        # Show pause button, hide resume button
        try:
            self.query_one("#pause-btn", Button).display = True
            self.query_one("#resume-btn", Button).display = False
        except Exception as e:
            logger.debug(f"Could not update button visibility after form submit: {e}")

        # Setup log display
        log_widget = self.query_one("#log-display", RichLog)
        log_widget.write("[bold cyan]PYDNS Scanner Log[/bold cyan]")
        log_widget.write(f"[yellow]Subnet file:[/yellow] {self.subnet_file}")
        log_widget.write(f"[yellow]Domain:[/yellow] {self.domain}")
        log_widget.write(f"[yellow]DNS Type:[/yellow] {self.dns_type}")
        log_widget.write(f"[yellow]Concurrency:[/yellow] {self.concurrency}")
        log_widget.write(
            f"[yellow]Slipstream Test:[/yellow] {'Enabled' if self.test_slipstream else 'Disabled'}"
        )
        log_widget.write("[green]Starting scan...[/green]\n")

        # Start scanning
        self.scan_started = True

        # Update keybinding visibility for scan mode
        self._update_keybinding_visibility(scanning=True, paused=False)

        self.run_worker(self._scan_async(), exclusive=True)

    async def _check_update_and_start_scan(self) -> None:
        """Check for slipstream updates and then start the scan."""
        log_widget = self.query_one("#log-display", RichLog)

        # Switch to scan screen to show progress
        self.query_one("#start-screen").display = False
        self.query_one("#scan-screen").display = True

        log_widget.write("[bold cyan]PYDNS Scanner Log[/bold cyan]")
        log_widget.write("[cyan]Checking Slipstream client...[/cyan]")

        # Ensure slipstream is installed (download only if not present)
        def log_callback(msg):
            log_widget.write(msg)

        success, message = await self.slipstream_manager.ensure_installed(log_callback)

        # Verify we have a working slipstream
        if not self.slipstream_manager.is_installed():
            log_widget.write("[red]✗ Failed to get Slipstream client![/red]")
            log_widget.write(
                "[yellow]Please download manually or check your network connection.[/yellow]"
            )
            self.notify("Slipstream not available", severity="error")
            return

        # Ensure executable permissions
        self.slipstream_manager.ensure_executable()
        self.slipstream_path = str(self.slipstream_manager.get_executable_path())

        # Continue with scan setup
        log_widget.write(f"[yellow]Subnet file:[/yellow] {self.subnet_file}")
        log_widget.write(f"[yellow]Domain:[/yellow] {self.domain}")
        log_widget.write(f"[yellow]DNS Type:[/yellow] {self.dns_type}")
        log_widget.write(f"[yellow]Concurrency:[/yellow] {self.concurrency}")
        log_widget.write("[yellow]Slipstream Test:[/yellow] Enabled")
        log_widget.write("[green]Starting scan...[/green]\n")

        # Show pause button, hide resume button
        try:
            self.query_one("#pause-btn", Button).display = True
            self.query_one("#resume-btn", Button).display = False
        except Exception as e:
            logger.debug(
                f"Could not update button visibility after slipstream check: {e}"
            )

        self.scan_started = True

        # Update keybinding visibility for scan mode
        self._update_keybinding_visibility(scanning=True, paused=False)

        await self._scan_async()

    async def _download_and_start_scan(self) -> None:
        """Download slipstream and then start the scan."""
        log_widget = self.query_one("#log-display", RichLog)
        progress_bar = self.query_one("#progress-bar", CustomProgressBar)

        # Switch to scan screen to show progress
        self.query_one("#start-screen").display = False
        self.query_one("#scan-screen").display = True

        log_widget.write("[bold cyan]PYDNS Scanner Log[/bold cyan]")
        log_widget.write(
            f"[yellow]Platform:[/yellow] {self.slipstream_manager.system} {self.slipstream_manager.machine}"
        )
        log_widget.write("[cyan]Downloading Slipstream client...[/cyan]")
        log_widget.write(
            f"[dim]URL: {self.slipstream_manager.get_download_url()}[/dim]"
        )

        success = await self.slipstream_manager.download_with_ui(
            progress_bar=progress_bar,
            log_widget=log_widget,
        )

        if success:
            log_widget.write("[green]✓ Slipstream downloaded successfully![/green]")
            progress_bar.update_progress(100, 100)  # Show 100%
            self.slipstream_path = str(self.slipstream_manager.get_executable_path())

            # Continue with the scan
            log_widget.write(f"[yellow]Subnet file:[/yellow] {self.subnet_file}")
            log_widget.write(f"[yellow]Domain:[/yellow] {self.domain}")
            log_widget.write(f"[yellow]DNS Type:[/yellow] {self.dns_type}")
            log_widget.write(f"[yellow]Concurrency:[/yellow] {self.concurrency}")
            log_widget.write("[yellow]Slipstream Test:[/yellow] Enabled")
            log_widget.write("[green]Starting scan...[/green]\n")

            self.scan_started = True

            # Update keybinding visibility for scan mode
            self._update_keybinding_visibility(scanning=True, paused=False)

            await self._scan_async()
        else:
            log_widget.write(
                "[red]✗ Failed to download Slipstream after multiple retries![/red]"
            )
            log_widget.write(
                f"[yellow]Expected path: {self.slipstream_manager.get_executable_path()}[/yellow]"
            )
            log_widget.write(
                "[yellow]Partial download saved. Run again to resume.[/yellow]"
            )
            log_widget.write(
                "[yellow]Or download manually and place in the path above.[/yellow]"
            )
            self.notify(
                "Failed to download Slipstream. Run again to resume.", severity="error"
            )

    async def _scan_async(self) -> None:
        """Async scanning logic."""
        # Reset state for re-scanning
        self.found_servers.clear()
        self.server_times.clear()
        self.proxy_results.clear()
        self.current_scanned = 0
        self.table_needs_rebuild = False
        self.remaining_ips.clear()
        # tested_ips removed for better memory management

        # Force garbage collection after clearing large structures
        gc.collect()

        # Reset pause state
        self.is_paused = False
        self.pause_event = asyncio.Event()
        self.pause_event.set()  # Not paused initially

        # Initialize shutdown event for graceful cleanup
        self._shutdown_event = asyncio.Event()
        self.active_scan_tasks = []

        # Initialize slipstream parallel testing
        self.slipstream_semaphore = asyncio.Semaphore(self.slipstream_max_concurrent)
        self.available_ports = deque(
            range(
                self.slipstream_base_port,
                self.slipstream_base_port + self.slipstream_max_concurrent,
            )
        )
        self.pending_slipstream_tests.clear()
        self.slipstream_tasks.clear()

        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.last_table_update_time = self.start_time

        # Notify user about CIDR loading
        self.notify("Reading CIDR file...", severity="information", timeout=3)
        self._log("[cyan]Analyzing CIDR file...[/cyan]")
        await asyncio.sleep(0)

        # Fast count of total IPs (not lines) for accurate progress
        loop = asyncio.get_event_loop()
        total_ips = await loop.run_in_executor(
            None, self._count_total_ips_fast, self.subnet_file
        )

        if total_ips == 0:
            self._log("[red]ERROR: No valid IPs found in CIDR file![/red]")
            self.notify("No valid IPs! Check CIDR file format.", severity="error")
            return

        self._log(f"[cyan]Found {total_ips:,} total IPs to scan. Starting...[/cyan]")
        await asyncio.sleep(0)

        try:
            stats = self.query_one("#stats", StatsWidget)
            stats.total = total_ips
            progress_bar = self.query_one("#progress-bar", CustomProgressBar)
            progress_bar.update_progress(0, total_ips)
        except Exception as e:
            logger.debug(f"Could not initialize stats widget: {e}")

        logger.info(f"Starting chunked scan with concurrency {self.concurrency}")
        self._log("[cyan]Scan mode: Streaming chunks (no pre-loading)[/cyan]")
        self._log(f"[cyan]Concurrency: {self.concurrency} workers[/cyan]")
        await asyncio.sleep(0)

        self.notify("Scanning in real-time...", severity="information", timeout=3)

        # Create semaphore
        sem = asyncio.Semaphore(self.concurrency)

        # Use memory-efficient streaming by default
        self._log("[green]Starting memory-efficient streaming scan...[/green]")
        await asyncio.sleep(0)

        chunk_size = 500  # Process 500 IPs at a time
        active_tasks = []
        chunk_num = 0

        # Stream IPs efficiently without loading all into memory
        async for ip_chunk in self._stream_ips_from_file():
            # Check for shutdown
            if self._shutdown_event and self._shutdown_event.is_set():
                break

            # Check for pause
            await self.pause_event.wait()

            # After resume, if user shuffled, switch to shuffled mode
            if self.remaining_ips:
                self._log("[cyan]Switching to shuffled IP scanning mode...[/cyan]")
                break  # Exit streaming loop to handle shuffled IPs below

            chunk_num += 1

            # Create tasks for this chunk
            for ip in ip_chunk:
                task = asyncio.create_task(self._test_dns_with_callback(ip, sem))
                active_tasks.append(task)

            # Keep reference for cleanup
            self.active_scan_tasks = active_tasks

            # Process completed tasks periodically
            if len(active_tasks) >= chunk_size:
                # Check for pause before processing
                await self.pause_event.wait()

                # Check for shutdown
                if self._shutdown_event and self._shutdown_event.is_set():
                    break

                # Wait for some tasks to complete
                done, active_tasks = await asyncio.wait(
                    active_tasks, return_when=asyncio.FIRST_COMPLETED
                )

                # Process completed results
                for task in done:
                    try:
                        result = await task
                        await self._process_result(result)
                    except asyncio.CancelledError:
                        pass  # Task was cancelled during shutdown
                    except Exception as e:
                        logger.error(
                            f"Error processing DNS test result: {e}", exc_info=True
                        )

                active_tasks = list(active_tasks)
                self.active_scan_tasks = active_tasks
                await asyncio.sleep(0)  # Yield to UI

        # Handle shuffled IPs if user shuffled during pause
        if self.remaining_ips:
            self._log(
                f"[cyan]Scanning {len(self.remaining_ips)} shuffled IPs...[/cyan]"
            )

            # Process shuffled IPs in chunks
            shuffled_index = 0
            while shuffled_index < len(self.remaining_ips):
                # Check for shutdown
                if self._shutdown_event and self._shutdown_event.is_set():
                    break

                # Check for pause
                await self.pause_event.wait()

                # Get next chunk of shuffled IPs
                chunk_end = min(shuffled_index + chunk_size, len(self.remaining_ips))
                shuffled_chunk = self.remaining_ips[shuffled_index:chunk_end]
                shuffled_index = chunk_end

                # Create tasks for this shuffled chunk
                for ip in shuffled_chunk:
                    # remaining_ips already contains only untested IPs
                    task = asyncio.create_task(self._test_dns_with_callback(ip, sem))
                    active_tasks.append(task)

                # Process completed tasks
                if len(active_tasks) >= chunk_size or shuffled_index >= len(
                    self.remaining_ips
                ):
                    await self.pause_event.wait()

                    if self._shutdown_event and self._shutdown_event.is_set():
                        break

                    done, active_tasks = await asyncio.wait(
                        active_tasks, return_when=asyncio.FIRST_COMPLETED
                    )

                    for task in done:
                        try:
                            result = await task
                            await self._process_result(result)
                        except asyncio.CancelledError:
                            pass  # Task was cancelled during shuffle transition
                        except Exception as e:
                            logger.error(
                                f"Error processing shuffled IP result: {e}",
                                exc_info=True,
                            )

                    active_tasks = list(active_tasks)
                    await asyncio.sleep(0)

        # Clear shuffled IPs from memory after processing for better memory management
        if self.remaining_ips:
            shuffled_count = len(self.remaining_ips)
            self.remaining_ips.clear()  # Free memory
            gc.collect()  # Force garbage collection
            self._log(
                f"[dim]Cleared {shuffled_count} shuffled IPs from memory (GC triggered)[/dim]"
            )

        # Check if we're shutting down
        if self._shutdown_event and self._shutdown_event.is_set():
            self._log("[yellow]Scan interrupted - cleaning up...[/yellow]")
            # Cancel remaining tasks
            for task in active_tasks:
                if not task.done():
                    task.cancel()
            return

        # Wait for all remaining tasks
        self._log("[cyan]Finishing remaining scans...[/cyan]")
        if active_tasks:
            done, _ = await asyncio.wait(active_tasks)
            for task in done:
                try:
                    result = await task
                    await self._process_result(result)
                except asyncio.CancelledError:
                    pass  # Task was cancelled
                except Exception as e:
                    logger.error(
                        f"Error processing final task result: {e}", exc_info=True
                    )

        self._log(
            f"[cyan]Scan complete. Scanned: {self.current_scanned}, Found: {len(self.found_servers)}[/cyan]"
        )
        logger.info(
            f"Scan complete. Scanned: {self.current_scanned}, Found: {len(self.found_servers)}"
        )

        # Full garbage collection after scan completes
        gc.collect()

        # Update final statistics
        try:
            stats = self.query_one("#stats", StatsWidget)
            stats.scanned = self.current_scanned
            stats.found = len(self.found_servers)
            stats.passed = len(
                [ip for ip, r in self.proxy_results.items() if r == "Success"]
            )
            stats.failed = len(
                [ip for ip, r in self.proxy_results.items() if r == "Failed"]
            )
            elapsed = time.time() - self.start_time
            stats.elapsed = elapsed
            stats.speed = self.current_scanned / elapsed if elapsed > 0 else 0
            stats.total = self.current_scanned  # Set total to actual scanned count

            progress_bar = self.query_one("#progress-bar", CustomProgressBar)
            progress_bar.update_progress(
                self.current_scanned, self.current_scanned
            )  # Force 100%
        except Exception as e:
            logger.debug(f"Could not update final statistics: {e}")

        # Final table rebuild
        self._rebuild_table()

        # Wait for all pending slipstream tests to complete (with timeout)
        if self.test_slipstream and self.slipstream_tasks:
            num_tasks = len(self.slipstream_tasks)
            self._log(
                f"[cyan]Waiting for {num_tasks} slipstream tests to complete (max 60s)...[/cyan]"
            )
            try:
                # Wait maximum 60 seconds for all tests
                await asyncio.wait_for(
                    asyncio.gather(*self.slipstream_tasks, return_exceptions=True),
                    timeout=60.0,
                )
            except asyncio.TimeoutError:
                self._log(
                    "[yellow]Timeout waiting for slipstream tests - continuing anyway[/yellow]"
                )
            self._rebuild_table()  # Rebuild after all tests complete
            # Collect garbage after proxy tests complete
            gc.collect()

        # Auto-save results
        self._auto_save_results()

        self.notify("Scan complete! Results auto-saved.", severity="information")

    def _count_total_ips_fast(self, filepath: str) -> int:
        """Fast counting of total IPs in CIDR file without loading into memory.

        This provides an accurate count for progress tracking without memory overhead.
        """
        total_ips = 0
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        try:
                            network = ipaddress.IPv4Network(line, strict=False)
                            # Count actual host IPs (excluding network/broadcast for subnets)
                            if network.prefixlen >= 31:  # /31 or /32
                                total_ips += network.num_addresses
                            else:
                                total_ips += (
                                    network.num_addresses - 2
                                )  # Exclude network & broadcast
                        except (
                            ipaddress.AddressValueError,
                            ipaddress.NetmaskValueError,
                            ValueError,
                        ):
                            logger.debug(f"Skipping invalid CIDR line: {line[:50]}")
        except (OSError, IOError) as e:
            logger.error(f"Failed to read CIDR file '{filepath}': {e}")
            return 0
        except Exception as e:
            logger.error(
                f"Unexpected error counting IPs in file '{filepath}': {e}",
                exc_info=True,
            )
            return 0

        return total_ips

    def _count_file_lines(self, filepath: str) -> int:
        """Fast line counting for CIDR file."""
        count = 0
        try:
            with open(filepath, "rb") as f:
                for line in f:
                    line_str = line.strip()
                    if line_str and not line_str.startswith(b"#"):
                        count += 1
        except (OSError, IOError) as e:
            logger.debug(f"Failed to count lines in '{filepath}': {e}")
        return count

    def _load_subnets(self) -> list[ipaddress.IPv4Network]:
        """Load subnets from file using fast mmap-based reading."""
        subnets = []
        logger.info(f"Loading subnets from {self.subnet_file}")
        try:
            # Fast reading using mmap for large files
            with open(self.subnet_file, "r+b") as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmapped:
                    for line in iter(mmapped.readline, b""):
                        try:
                            line_str = line.decode("utf-8", errors="ignore").strip()
                            if line_str and not line_str.startswith("#"):
                                subnets.append(
                                    ipaddress.IPv4Network(line_str, strict=False)
                                )
                        except (
                            ipaddress.AddressValueError,
                            ipaddress.NetmaskValueError,
                            ValueError,
                        ) as e:
                            logger.debug(
                                f"Skipping invalid CIDR: {line_str[:50]} - {e}"
                            )
        except (ValueError, OSError, mmap.error) as e:
            logger.warning(
                f"mmap failed for '{self.subnet_file}': {e}, falling back to regular reading"
            )
            # Fallback to regular reading if mmap fails (e.g., empty file)
            try:
                with open(self.subnet_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            try:
                                subnets.append(
                                    ipaddress.IPv4Network(line, strict=False)
                                )
                            except (
                                ipaddress.AddressValueError,
                                ipaddress.NetmaskValueError,
                                ValueError,
                            ) as e:
                                logger.debug(
                                    f"Skipping invalid CIDR: {line[:50]} - {e}"
                                )
            except (OSError, IOError) as e:
                logger.error(f"Failed to read subnet file '{self.subnet_file}': {e}")

        logger.info(f"Loaded {len(subnets)} subnets")
        return subnets

    async def _stream_ips_from_file(self) -> AsyncGenerator[list[str], None]:
        """Stream IPs from CIDR file in chunks without loading everything into memory.

        Memory-efficient streaming approach that only loads IPs into remaining_ips
        when shuffle functionality is actually needed.
        """
        chunk = []
        chunk_size = 500  # Yield 500 IPs at a time
        rng = secrets.SystemRandom()

        loop = asyncio.get_event_loop()

        def read_and_process():
            """Blocking function to read file and yield subnet chunks."""
            subnets = []
            try:
                with open(self.subnet_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            try:
                                subnet = ipaddress.IPv4Network(line, strict=False)
                                subnets.append(subnet)
                            except (
                                ipaddress.AddressValueError,
                                ipaddress.NetmaskValueError,
                                ValueError,
                            ):
                                # Invalid CIDR - skip it silently (common in user-provided files)
                                pass
            except (OSError, IOError) as e:
                logger.error(f"Failed to read subnet file: {e}")
            return subnets

        # Read subnets
        subnets = await loop.run_in_executor(None, read_and_process)
        rng.shuffle(subnets)

        # Generate IPs from subnets - stream them efficiently
        for net in subnets:
            # Split into /24 chunks
            if net.prefixlen >= 24:
                chunks = [net]
            else:
                chunks = list(net.subnets(new_prefix=24))

            rng.shuffle(chunks)

            for subnet_chunk in chunks:
                if subnet_chunk.num_addresses == 1:
                    ip_str = str(subnet_chunk.network_address)
                    chunk.append(ip_str)
                else:
                    ips = list(subnet_chunk.hosts())
                    rng.shuffle(ips)
                    for ip in ips:
                        ip_str = str(ip)
                        chunk.append(ip_str)

                        # Yield chunk when it reaches size
                        if len(chunk) >= chunk_size:
                            yield chunk
                            chunk = []
                            await asyncio.sleep(0)  # Yield to event loop

        # Yield remaining IPs
        if chunk:
            yield chunk

    async def _test_dns_with_callback(
        self, ip: str, sem: asyncio.Semaphore
    ) -> tuple[str, bool, float]:
        """Test DNS and return result tuple."""
        # Wait if paused
        await self.pause_event.wait()
        return await self._test_dns(ip, sem)

    async def _process_result(self, result: tuple[str, bool, float]) -> None:
        """Process a single DNS test result."""
        if isinstance(result, tuple):
            ip, is_valid, response_time = result

            # Update scanned count (no longer tracking tested_ips for memory efficiency)
            self.current_scanned += 1

            if is_valid:
                # Add to found servers and table immediately
                self._add_result(ip, response_time)
                self._log(
                    f"[green]✓ Found DNS: {ip} ({response_time*1000:.0f}ms)[/green]"
                )

                # Queue slipstream test if enabled (non-blocking)
                if self.test_slipstream:
                    self.proxy_results[ip] = "Pending"
                    task = asyncio.create_task(self._queue_slipstream_test(ip))
                    self.slipstream_tasks.add(task)
                    task.add_done_callback(self.slipstream_tasks.discard)

            # Update UI periodically
            if self.current_scanned % 10 == 0:
                current_time = time.time()
                elapsed = current_time - self.start_time

                try:
                    stats = self.query_one("#stats", StatsWidget)
                    stats.scanned = self.current_scanned
                    stats.elapsed = elapsed
                    stats.speed = self.current_scanned / elapsed if elapsed > 0 else 0
                    stats.found = len(self.found_servers)
                    stats.passed = len(
                        [ip for ip, r in self.proxy_results.items() if r == "Success"]
                    )
                    stats.failed = len(
                        [ip for ip, r in self.proxy_results.items() if r == "Failed"]
                    )

                    progress_bar = self.query_one("#progress-bar", CustomProgressBar)
                    progress_bar.update_progress(self.current_scanned, stats.total)
                except Exception as e:
                    logger.debug(f"Could not update stats during scan: {e}")

                # Periodic garbage collection every 1000 scans to prevent memory buildup
                if self.current_scanned % 1000 == 0:
                    gc.collect(generation=0)  # Fast generation-0 collection

    def _collect_ips(self, subnets: list[ipaddress.IPv4Network]) -> list[str]:
        """Collect all IPs from subnets in random order using CSPRNG."""
        logger.info(f"Collecting IPs from {len(subnets)} subnets")
        all_ips = []
        rng = secrets.SystemRandom()  # Cryptographically secure RNG

        # Shuffle subnets first for randomization
        subnets_copy = list(subnets)
        rng.shuffle(subnets_copy)

        for net in subnets_copy:
            # Split into /24 chunks
            if net.prefixlen >= 24:
                chunks = [net]
            else:
                chunks = list(net.subnets(new_prefix=24))

            # Shuffle chunks for random order
            rng.shuffle(chunks)

            for chunk in chunks:
                # For /32 (single IP), just use the network address
                if chunk.num_addresses == 1:
                    all_ips.append(str(chunk.network_address))
                else:
                    # Get usable IPs (skip network and broadcast)
                    ips = list(chunk.hosts())
                    # Shuffle IPs within each chunk
                    rng.shuffle(ips)
                    all_ips.extend([str(ip) for ip in ips])

        logger.info(f"Collected {len(all_ips)} IPs to scan")
        return all_ips

    async def _test_dns(
        self, ip: str, sem: asyncio.Semaphore
    ) -> tuple[str, bool, float]:
        """Test if IP is a DNS server that responds (even if answer is empty)."""
        async with sem:
            try:
                domain = self.domain
                if self.random_subdomain:
                    prefix = secrets.token_hex(4)
                    domain = f"{prefix}.{domain}"

                # 2 second timeout for DNS servers
                resolver = aiodns.DNSResolver(nameservers=[ip], timeout=2.0, tries=1)

                start = time.time()
                try:
                    # Use query method instead of query_dns for better compatibility
                    result = await resolver.query(domain, self.dns_type)
                    elapsed = time.time() - start

                    # If we got a result and it's under 2000ms, it's a valid DNS server
                    if result and elapsed < 2.0:
                        logger.debug(
                            f"{ip}: DNS responded - {type(result)} in {elapsed*1000:.0f}ms"
                        )
                        return (ip, True, elapsed)
                    elif result:
                        # Too slow, reject it
                        logger.debug(f"{ip}: DNS too slow - {elapsed*1000:.0f}ms")
                        return (ip, False, 0)

                    # No response
                    return (ip, False, 0)

                except aiodns.error.DNSError as dns_err:
                    elapsed = time.time() - start
                    # DNS errors like NXDOMAIN, NODATA, etc. mean the DNS server IS working
                    # Only connection/timeout errors mean it's not a valid DNS server
                    error_code = dns_err.args[0] if dns_err.args else 0

                    # Error codes that indicate a working DNS server:
                    # 1 = NXDOMAIN (domain doesn't exist - but DNS is working!)
                    # 4 = NODATA (no records found - but DNS is working!)
                    # 3 = NXRRSET (RR type doesn't exist - but DNS is working!)
                    if error_code in (1, 3, 4) and elapsed < 2.0:
                        logger.info(
                            f"{ip}: DNS working with error code {error_code} in {elapsed*1000:.0f}ms"
                        )
                        return (ip, True, elapsed)
                    elif error_code in (1, 3, 4):
                        # Working but too slow
                        return (ip, False, 0)

                    # Other DNS errors = not a valid/working DNS server
                    return (ip, False, 0)

            except asyncio.TimeoutError:
                return (ip, False, 0)
            except Exception as e:
                # Log unexpected errors but don't crash the scan
                logger.debug(f"Unexpected error testing DNS {ip}: {e}")
                return (ip, False, 0)

    def _add_result(self, ip: str, response_time: float) -> None:
        """Add a found server to results immediately, resort periodically."""
        self.found_servers.add(ip)
        self.server_times[ip] = response_time

        # Add to table immediately for instant feedback
        try:
            table = self.query_one("#results-table", DataTable)

            server_ms = response_time * 1000
            if server_ms < 100:
                server_time_str = f"[green]{server_ms:.0f}ms[/green]"
            elif server_ms < 300:
                server_time_str = f"[yellow]{server_ms:.0f}ms[/yellow]"
            else:
                server_time_str = f"[red]{server_ms:.0f}ms[/red]"

            # Get proxy status
            proxy_status = self.proxy_results.get(ip, "N/A")
            if proxy_status == "Success":
                proxy_str = "[green]✓ Passed[/green]"
            elif proxy_status == "Failed":
                proxy_str = "[red]✗ Failed[/red]"
            elif proxy_status == "Testing":
                proxy_str = "[yellow]Testing...[/yellow]"
            elif proxy_status == "Pending":
                proxy_str = "[dim]Queued[/dim]"
            else:
                proxy_str = "[dim]N/A[/dim]"

            table.add_row(
                ip,
                server_time_str,
                "[green]Active[/green]",
                proxy_str,
            )
        except Exception as e:
            logger.debug(f"Could not add result row to table: {e}")

        # Mark table for periodic resort
        self.table_needs_rebuild = True

        # Resort table every 2 seconds to maintain sorted order
        current_time = time.time()
        if current_time - self.last_table_update_time >= 2.0:
            self._rebuild_table()
            self.last_table_update_time = current_time

    def _rebuild_table(self) -> None:
        """Rebuild the entire table with sorted results."""
        if not self.table_needs_rebuild:
            return

        try:
            table = self.query_one("#results-table", DataTable)

            # Clear and rebuild table with smart sorting:
            # 1. Passed proxy tests (lowest ping first)
            # 2. Testing status
            # 3. Queued/Pending
            # 4. N/A status
            # 5. Failed tests (at the end)
            table.clear()

            def sort_key(item):
                server_ip, server_time = item
                proxy_status = self.proxy_results.get(server_ip, "N/A")

                # Priority order: Success=0, Testing=1, Pending=2, N/A=3, Failed=4
                if proxy_status == "Success":
                    priority = 0
                elif proxy_status == "Testing":
                    priority = 1
                elif proxy_status == "Pending":
                    priority = 2
                elif proxy_status == "N/A":
                    priority = 3
                else:  # Failed
                    priority = 4

                # Sort by priority first, then by response time
                return (priority, server_time)

            # Show all servers including failed ones
            sorted_servers = sorted(self.server_times.items(), key=sort_key)

            for server_ip, server_time in sorted_servers:
                server_ms = server_time * 1000
                if server_ms < 100:
                    server_time_str = f"[green]{server_ms:.0f}ms[/green]"
                elif server_ms < 300:
                    server_time_str = f"[yellow]{server_ms:.0f}ms[/yellow]"
                else:
                    server_time_str = f"[red]{server_ms:.0f}ms[/red]"

                # Get proxy status
                proxy_status = self.proxy_results.get(server_ip, "N/A")
                if proxy_status == "Success":
                    proxy_str = "[green]✓ Passed[/green]"
                elif proxy_status == "Failed":
                    proxy_str = "[red]✗ Failed[/red]"
                elif proxy_status == "Testing":
                    proxy_str = "[yellow]Testing...[/yellow]"
                elif proxy_status == "Pending":
                    proxy_str = "[dim]Queued[/dim]"
                else:
                    proxy_str = "[dim]N/A[/dim]"

                table.add_row(
                    server_ip,
                    server_time_str,
                    "[green]Active[/green]",
                    proxy_str,
                )

            self.table_needs_rebuild = False
        except Exception as e:
            logger.debug(f"Could not rebuild results table: {e}")

    async def _queue_slipstream_test(self, dns_ip: str) -> None:
        """Queue and run slipstream test with semaphore for max concurrent tests."""
        async with self.slipstream_semaphore:
            # Get an available port
            while not self.available_ports:
                await asyncio.sleep(0.1)  # Wait for a port to become available

            port = self.available_ports.popleft()

            try:
                self.proxy_results[dns_ip] = "Testing"
                self._update_table_row(dns_ip)  # Update UI to show testing status
                self._log(
                    f"[cyan]Testing {dns_ip} with slipstream on port {port}...[/cyan]"
                )

                result = await self._test_slipstream_proxy(dns_ip, port)
                self.proxy_results[dns_ip] = result

                # Update stats
                try:
                    stats = self.query_one("#stats", StatsWidget)
                    if result == "Success":
                        stats.passed = len(
                            [
                                ip
                                for ip, r in self.proxy_results.items()
                                if r == "Success"
                            ]
                        )
                    else:
                        stats.failed = len(
                            [
                                ip
                                for ip, r in self.proxy_results.items()
                                if r == "Failed"
                            ]
                        )
                except Exception as e:
                    logger.debug(f"Could not update stats after proxy test: {e}")

                if result == "Success":
                    self._log(f"[green]✓ Proxy test PASSED: {dns_ip}[/green]")
                    # Play bell sound if enabled
                    if self.bell_sound_enabled:
                        self._play_bell_sound()
                else:
                    self._log(f"[red]✗ Proxy test FAILED: {dns_ip}[/red]")
                    # Keep failed in list but at the end (handled by sort_key in _rebuild_table)
                    self.table_needs_rebuild = True
                    self._rebuild_table()

                self._update_table_row(dns_ip)  # Update UI with final result

            finally:
                # Return port to pool
                self.available_ports.append(port)

    def _update_table_row(self, ip: str) -> None:
        """Update a single row in the table for the given IP."""
        self.table_needs_rebuild = True
        self._rebuild_table()

    async def _test_slipstream_proxy(self, dns_ip: str, port: int) -> str:
        """Test DNS server using slipstream proxy on a specific port.

        Args:
            dns_ip: The DNS IP to test
            port: The port to use for slipstream

        Returns:
            "Success" if proxy works, "Failed" otherwise
        """
        process = None
        try:
            # Build slipstream command with dynamic port using the manager
            cmd = self.slipstream_manager.get_run_command(
                dns_ip, port, self.slipstream_domain
            )

            logger.info(f"[{dns_ip}] Starting slipstream on port {port}")
            logger.debug(f"[{dns_ip}] Command: {' '.join(cmd)}")

            # Start slipstream process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                ),
            )

            logger.debug(f"[{dns_ip}] Process started with PID {process.pid}")

            # Track process for cleanup on quit
            self.slipstream_processes.append(process)

            # Wait for "Connection ready" message (15 second timeout)
            connection_ready = False
            try:

                async def wait_for_connection_ready():
                    nonlocal connection_ready
                    line_count = 0
                    while True:
                        line = await process.stdout.readline()
                        if not line:
                            logger.warning(
                                f"[{dns_ip}] Slipstream process ended without output"
                            )
                            break

                        line_str = line.decode("utf-8", errors="ignore").strip()
                        line_count += 1

                        # Log every line from slipstream for debugging
                        logger.debug(
                            f"[{dns_ip}] Slipstream output #{line_count}: {line_str}"
                        )

                        if "Connection ready" in line_str:
                            connection_ready = True
                            logger.info(
                                f"[{dns_ip}] Connection ready detected on port {port}"
                            )
                            self._log(
                                f"[cyan]{dns_ip}: Connection ready on port {port}[/cyan]"
                            )
                            return

                await asyncio.wait_for(wait_for_connection_ready(), timeout=15)
            except asyncio.TimeoutError:
                logger.warning(f"[{dns_ip}] Slipstream connection timeout after 15s")
                self._log(
                    f"[yellow]{dns_ip}: Slipstream connection timeout (15s)[/yellow]"
                )
                return "Failed"

            if not connection_ready:
                logger.error(f"[{dns_ip}] Connection not ready after waiting")
                return "Failed"

            # Give slipstream a moment to fully initialize the proxy listener
            # This prevents race conditions where "Connection ready" is printed
            # but the proxy isn't quite ready to accept connections yet
            logger.debug(f"[{dns_ip}] Waiting 1.5s for proxy to fully initialize")
            await asyncio.sleep(1.5)

            # Test the proxy with google.com using dynamic port
            # Mid-high timeout (15 seconds) as requested
            # Build proxy URL with optional authentication
            if self.proxy_auth_enabled and self.proxy_username:
                from urllib.parse import quote

                encoded_user = quote(self.proxy_username, safe="")
                encoded_pass = quote(self.proxy_password, safe="")
                proxy_url = f"http://{encoded_user}:{encoded_pass}@127.0.0.1:{port}"
                proxy_url_log = f"http://{self.proxy_username}:****@127.0.0.1:{port}"
            else:
                proxy_url = f"http://127.0.0.1:{port}"
                proxy_url_log = proxy_url
            test_success = False

            # Try HTTP proxy first
            logger.info(f"[{dns_ip}] Testing HTTP proxy at {proxy_url_log}")
            try:
                logger.debug(
                    f"[{dns_ip}] Creating HTTP client with proxy={proxy_url}, timeout=15.0"
                )
                async with httpx.AsyncClient(
                    proxy=proxy_url,
                    timeout=15.0,  # Mid-high timeout
                    follow_redirects=True,
                ) as client:
                    logger.debug(
                        f"[{dns_ip}] Sending HTTP GET to http://google.com via proxy"
                    )
                    start_time = time.time()
                    response = await client.get("http://google.com")
                    elapsed = time.time() - start_time

                    # Log detailed response information
                    logger.debug(f"[{dns_ip}] HTTP response received in {elapsed:.2f}s")
                    logger.debug(
                        f"[{dns_ip}] HTTP response status: {response.status_code}"
                    )
                    logger.debug(
                        f"[{dns_ip}] HTTP response headers: {dict(response.headers)}"
                    )
                    logger.debug(f"[{dns_ip}] HTTP response URL: {response.url}")
                    logger.debug(
                        f"[{dns_ip}] HTTP response body preview: {response.text[:200]}"
                    )

                    if response.status_code in (200, 301, 302):
                        test_success = True
                        logger.info(
                            f"[{dns_ip}] HTTP proxy test PASSED (status {response.status_code}, {elapsed:.2f}s)"
                        )
                        self._log(
                            f"[green]{dns_ip}: HTTP proxy test passed (status {response.status_code})[/green]"
                        )
                    else:
                        logger.warning(
                            f"[{dns_ip}] HTTP proxy unexpected status code: {response.status_code}"
                        )
            except Exception as http_err:
                logger.warning(
                    f"[{dns_ip}] HTTP proxy test failed: {type(http_err).__name__}: {str(http_err)}"
                )
                logger.debug(f"[{dns_ip}] HTTP error details:", exc_info=True)

                # Try SOCKS5 proxy with optional authentication
                if self.proxy_auth_enabled and self.proxy_username:
                    socks5_url = (
                        f"socks5://{encoded_user}:{encoded_pass}@127.0.0.1:{port}"
                    )
                    socks5_url_log = (
                        f"socks5://{self.proxy_username}:****@127.0.0.1:{port}"
                    )
                else:
                    socks5_url = f"socks5://127.0.0.1:{port}"
                    socks5_url_log = socks5_url
                logger.info(f"[{dns_ip}] Testing SOCKS5 proxy at {socks5_url_log}")
                try:
                    logger.debug(
                        f"[{dns_ip}] Creating SOCKS5 client with proxy={socks5_url_log}, timeout=15.0"
                    )
                    async with httpx.AsyncClient(
                        proxy=socks5_url,
                        timeout=15.0,  # Mid-high timeout
                        follow_redirects=True,
                    ) as client:
                        logger.debug(
                            f"[{dns_ip}] Sending HTTP GET to http://google.com via SOCKS5"
                        )
                        start_time = time.time()
                        response = await client.get("http://google.com")
                        elapsed = time.time() - start_time

                        # Log detailed response information
                        logger.debug(
                            f"[{dns_ip}] SOCKS5 response received in {elapsed:.2f}s"
                        )
                        logger.debug(
                            f"[{dns_ip}] SOCKS5 response status: {response.status_code}"
                        )
                        logger.debug(
                            f"[{dns_ip}] SOCKS5 response headers: {dict(response.headers)}"
                        )
                        logger.debug(f"[{dns_ip}] SOCKS5 response URL: {response.url}")
                        logger.debug(
                            f"[{dns_ip}] SOCKS5 response body preview: {response.text[:200]}"
                        )

                        if response.status_code in (200, 301, 302):
                            test_success = True
                            logger.info(
                                f"[{dns_ip}] SOCKS5 proxy test PASSED (status {response.status_code}, {elapsed:.2f}s)"
                            )
                            self._log(
                                f"[green]{dns_ip}: SOCKS5 proxy test passed (status {response.status_code})[/green]"
                            )
                        else:
                            logger.warning(
                                f"[{dns_ip}] SOCKS5 proxy unexpected status code: {response.status_code}"
                            )
                except Exception as socks_err:
                    logger.error(
                        f"[{dns_ip}] SOCKS5 proxy test failed: {type(socks_err).__name__}: {str(socks_err)}"
                    )
                    logger.debug(f"[{dns_ip}] SOCKS5 error details:", exc_info=True)
                    self._log(
                        f"[red]{dns_ip}: Both HTTP and SOCKS5 proxy tests failed[/red]"
                    )

            final_result = "Success" if test_success else "Failed"
            logger.info(f"[{dns_ip}] Final result: {final_result}")
            return final_result

        except Exception as e:
            logger.error(
                f"[{dns_ip}] Slipstream error: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            self._log(f"[red]Slipstream error for {dns_ip}: {str(e)[:50]}[/red]")
            return "Failed"
        finally:
            # Always kill the slipstream process
            if process:
                try:
                    process.kill()
                    await process.wait()
                    # Remove from tracking list
                    if process in self.slipstream_processes:
                        self.slipstream_processes.remove(process)
                except (ProcessLookupError, OSError) as e:
                    logger.debug(f"Process cleanup for {dns_ip}: {e}")

    def _shuffle_remaining_ips(self) -> None:
        """Shuffle the remaining untested IPs while preserving tested ones.

        Note: For large CIDR files, this will load remaining IPs into memory.
        This is only done when shuffle is actually requested to maintain efficiency.
        Uses temporary tested_ips tracking only during shuffle for memory efficiency.
        """
        if not self.is_paused:
            self.notify("Can only shuffle when paused!", severity="warning")
            return

        # If remaining_ips is empty, we need to build it from untested IPs
        if not self.remaining_ips:
            self._log(
                "[yellow]Loading remaining IPs for shuffle (this may use memory for large files)...[/yellow]"
            )
            self.notify("Loading IPs for shuffle...", severity="information", timeout=3)

            # Temporarily build tested_ips set from found_servers for shuffle logic
            # This is memory-intensive but only done when shuffle is requested
            temp_tested_ips = set(
                self.found_servers
            )  # Only IPs that were found (much smaller set)

            try:
                # Re-read the file to get all IPs
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def build_remaining():
                    all_ips = []
                    async for ip_chunk in self._stream_ips_from_file():
                        all_ips.extend(ip_chunk)
                    return [ip for ip in all_ips if ip not in temp_tested_ips]

                self.remaining_ips = loop.run_until_complete(build_remaining())
                loop.close()

                # Clear temporary set to free memory
                del temp_tested_ips

            except (OSError, IOError) as e:
                self._log(
                    f"[red]Failed to load IPs for shuffle (file error): {e}[/red]"
                )
                logger.error(f"Failed to load IPs for shuffle: {e}")
                self.notify("Shuffle failed - unable to load IPs", severity="error")
                return
            except Exception as e:
                self._log(f"[red]Failed to load IPs for shuffle: {e}[/red]")
                logger.error(f"Unexpected error during shuffle: {e}", exc_info=True)
                self.notify("Shuffle failed - unexpected error", severity="error")
                return

        untested_count = len(self.remaining_ips)

        if untested_count == 0:
            self.notify("All IPs have been tested!", severity="information")
            return

        # Warn about memory usage for large lists
        if untested_count > 100000:  # > 100k IPs
            self._log(
                f"[yellow]Warning: Shuffling {untested_count} IPs may use significant memory[/yellow]"
            )

        # Shuffle the remaining untested IPs
        rng = secrets.SystemRandom()
        rng.shuffle(self.remaining_ips)

        # Force garbage collection after shuffle
        gc.collect()

        self._log(
            f"[cyan]🔀 Shuffled {untested_count} untested IPs (optimized memory usage)[/cyan]"
        )
        self.notify(f"Shuffled {untested_count} untested IPs", severity="information")

    async def _shuffle_remaining_ips_async(self) -> None:
        """Async version of shuffle to avoid event loop conflicts."""
        if not self.is_paused:
            self.notify("Can only shuffle when paused!", severity="warning")
            return

        # If remaining_ips is empty, we need to build it from untested IPs
        if not self.remaining_ips:
            self._log(
                "[yellow]Loading remaining IPs for shuffle (this may use memory for large files)...[/yellow]"
            )
            self.notify("Loading IPs for shuffle...", severity="information", timeout=3)

            # Temporarily build tested_ips set from found_servers for shuffle logic
            temp_tested_ips = set(self.found_servers)

            try:
                # Re-read the file to get all IPs using the existing async generator
                all_ips = []
                async for ip_chunk in self._stream_ips_from_file():
                    all_ips.extend(ip_chunk)

                # Filter out already found servers
                self.remaining_ips = [ip for ip in all_ips if ip not in temp_tested_ips]

                # Clear temporary set to free memory
                del temp_tested_ips

            except (OSError, IOError) as e:
                self._log(
                    f"[red]Failed to load IPs for shuffle (file error): {e}[/red]"
                )
                logger.error(f"Async shuffle failed to load IPs: {e}")
                self.notify("Shuffle failed - unable to load IPs", severity="error")
                return
            except Exception as e:
                self._log(f"[red]Failed to load IPs for shuffle: {e}[/red]")
                logger.error(
                    f"Unexpected error during async shuffle: {e}", exc_info=True
                )
                self.notify("Shuffle failed - unexpected error", severity="error")
                return

        untested_count = len(self.remaining_ips)

        if untested_count == 0:
            self.notify("All IPs have been tested!", severity="information")
            return

        # Warn about memory usage for large lists
        if untested_count > 100000:
            self._log(
                f"[yellow]Warning: Shuffling {untested_count} IPs may use significant memory[/yellow]"
            )

        # Shuffle the remaining untested IPs
        rng = secrets.SystemRandom()
        rng.shuffle(self.remaining_ips)

        # Force garbage collection after shuffle
        gc.collect()

        self._log(
            f"[cyan]🔀 Shuffled {untested_count} untested IPs (optimized memory usage)[/cyan]"
        )
        self.notify(f"Shuffled {untested_count} untested IPs", severity="information")

    def _play_bell_sound(self) -> None:
        """Play a single coin/sparkle sound with error handling for systems without sound support."""
        try:
            if platform.system() == "Windows":
                # Windows - single high-pitched coin sparkle sound
                import winsound

                winsound.Beep(1400, 60)  # Single bright coin-like tone
            elif platform.system() == "Darwin":
                # macOS - try system coin sound
                try:
                    import subprocess

                    subprocess.run(
                        ["afplay", "/System/Library/Sounds/Tink.aiff"],
                        check=False,
                        timeout=1,
                    )
                except (
                    FileNotFoundError,
                    subprocess.SubprocessError,
                    subprocess.TimeoutExpired,
                ):
                    print("\a", end="", flush=True)
            else:
                # Linux/Unix - single terminal bell
                print("\a", end="", flush=True)
        except ImportError:
            # winsound not available on non-Windows
            try:
                print("\a", end="", flush=True)
            except OSError:
                pass  # Terminal doesn't support bell
        except (OSError, AttributeError) as e:
            logger.debug(f"Bell sound failed: {e}")

    def _log(self, message: str) -> None:
        """Add message to log display."""
        try:
            log_widget = self.query_one("#log-display", RichLog)
            log_widget.write(message)
        except Exception as e:
            # Widget might not be ready or mounted yet - this is expected during startup
            logger.debug(f"Log widget not available: {e}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle double-click on DNS row to copy IP to clipboard."""
        try:
            table = self.query_one("#results-table", DataTable)
            row_key = event.row_key

            # Check if row_key exists in table
            if row_key not in table._row_locations:
                return

            row = table.get_row(row_key)

            if row and len(row) > 0:
                # Extract IP - remove any Rich markup
                ip_raw = str(row[0])
                # Strip Rich tags if present
                import re

                ip = re.sub(r"\[.*?\]", "", ip_raw).strip()

                if ip:
                    pyperclip.copy(ip)
                    self.notify(f"{ip} copied!", severity="information", timeout=2)
        except Exception as e:
            logger.debug(f"Row selection error: {e}")

    def _auto_save_results(self) -> None:
        """Auto-save results at end of scan.

        When slipstream testing is enabled, only save DNS servers that passed the proxy test.
        """
        # Filter servers based on test mode
        if self.test_slipstream:
            # Only save servers that passed proxy test
            passed_servers = {
                ip: time
                for ip, time in self.server_times.items()
                if self.proxy_results.get(ip) == "Success"
            }
            if not passed_servers:
                self._log(
                    "[yellow]No DNS servers passed proxy test - nothing to save.[/yellow]"
                )
                self._log(
                    f"[yellow]Total DNS found: {len(self.found_servers)}, Passed proxy: 0[/yellow]"
                )
                logger.warning(
                    f"No servers passed proxy test. Total found: {len(self.found_servers)}"
                )
                return
            servers_to_save = passed_servers
            self._log(
                f"[cyan]Saving {len(passed_servers)}/{len(self.found_servers)} DNS servers that passed proxy test...[/cyan]"
            )
            logger.info(f"Saving {len(passed_servers)} servers that passed proxy test")
        else:
            # Save all found servers
            if not self.found_servers:
                self._log("[yellow]No DNS servers found to save.[/yellow]")
                return
            servers_to_save = self.server_times

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = Path("results")

        try:
            output_dir.mkdir(exist_ok=True)
        except (OSError, PermissionError) as e:
            self._log(f"[red]Failed to create results directory: {e}[/red]")
            logger.error(f"Failed to create results directory: {e}")
            return

        # Save TXT with datetime filename
        txt_file = output_dir / f"{timestamp}.txt"

        # Sort by response time for output
        sorted_servers = sorted(servers_to_save.items(), key=lambda x: x[1])

        try:
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write(f"# PYDNS Scanner Results - {timestamp}\n")
                f.write(f"# Domain: {self.domain} | Type: {self.dns_type}\n")
                if self.test_slipstream:
                    f.write("# Slipstream Test: ENABLED (only passed servers)\n")
                f.write(f"# Total Saved: {len(servers_to_save)}\n")
                f.write("#" + "=" * 50 + "\n\n")
                for server_ip, server_time in sorted_servers:
                    f.write(f"{server_ip}\n")

            self._log(f"[green]✓ Results auto-saved to: {txt_file}[/green]")
            logger.info(f"Results auto-saved to {txt_file}")
        except (OSError, IOError, PermissionError) as e:
            self._log(f"[red]Failed to save results: {e}[/red]")
            logger.error(f"Failed to auto-save results to {txt_file}: {e}")

    def action_save_results(self) -> None:
        """Save results to file.

        When slipstream testing is enabled, only save DNS servers that passed the proxy test.
        """
        # Filter servers based on test mode
        if self.test_slipstream:
            passed_servers = {
                ip: time
                for ip, time in self.server_times.items()
                if self.proxy_results.get(ip) == "Success"
            }
            if not passed_servers:
                self.notify("No servers passed proxy test!", severity="warning")
                return
            servers_to_save = passed_servers
        else:
            if not self.found_servers:
                self.notify("No results to save!", severity="warning")
                return
            servers_to_save = self.server_times

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = Path("results")

        try:
            output_dir.mkdir(exist_ok=True)
        except (OSError, PermissionError) as e:
            self.notify(f"Failed to create results directory: {e}", severity="error")
            logger.error(f"Failed to create results directory: {e}")
            return

        # Save JSON
        json_file = output_dir / f"scan_{timestamp}.json"
        elapsed = time.time() - self.start_time

        # Sort by response time
        sorted_servers = sorted(servers_to_save.items(), key=lambda x: x[1])
        servers_list = [ip for ip, _ in sorted_servers]

        data = {
            "scan_info": {
                "domain": self.domain,
                "dns_type": self.dns_type,
                "slipstream_test": self.test_slipstream,
                "total_found": len(self.found_servers),
                "total_passed_proxy": (
                    len(
                        [
                            ip
                            for ip in self.proxy_results
                            if self.proxy_results[ip] == "Success"
                        ]
                    )
                    if self.test_slipstream
                    else 0
                ),
                "total_saved": len(servers_to_save),
                "elapsed_seconds": elapsed,
                "timestamp": timestamp,
            },
            "servers": servers_list,
        }

        try:
            with open(json_file, "wb") as f:
                f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))

            # Save TXT
            txt_file = output_dir / f"scan_{timestamp}.txt"
            with open(txt_file, "w", encoding="utf-8") as f:
                for server in servers_list:
                    f.write(f"{server}\n")

            self.notify(
                f"Saved {len(servers_list)} servers: {json_file.name}",
                severity="information",
            )
            logger.info(f"Results saved to {json_file}")
        except (OSError, IOError, PermissionError) as e:
            self.notify(f"Failed to save results: {e}", severity="error")
            logger.error(f"Failed to save results to {json_file}: {e}")


def main():
    """Main entry point."""
    try:
        Path("logs").mkdir(exist_ok=True)
        Path("results").mkdir(exist_ok=True)

        logger.info("PYDNS Scanner TUI starting")

        app = DNSScannerTUI()
        app.run()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
