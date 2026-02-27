#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import csv
import gc
import ipaddress
import json
import mmap
import os
import platform
import random
import secrets
import socket
import stat
import struct
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Set, AsyncGenerator, Optional

import aiodns
import httpx
from loguru import logger
from rich.markup import escape as markup_escape
from rich.text import Text

# ---------------------------------------------------------------------------
# Platform detection — Android/Termux cannot use compiled C extensions
# such as google-re2.  All other platforms try to use the fast version first.
# ---------------------------------------------------------------------------
def _is_android() -> bool:
    """Detect Android/Termux environment."""
    return (
        os.path.exists("/data/data/com.termux") or
        os.path.exists("/data/data/com.termux.fdroid") or
        "com.termux" in os.environ.get("PREFIX", "") or
        "ANDROID_ROOT" in os.environ or
        "ANDROID_DATA" in os.environ
    )

_ANDROID = _is_android()

try:
    if _ANDROID:
        raise ImportError("Skipping google-re2 on Android/Termux")
    import re2 as re  # type: ignore  # noqa: F401
except ImportError:
    import re  # type: ignore  # noqa: F401

try:
    if _ANDROID:
        raise ImportError("Skipping pyperclip on Android/Termux")
    import pyperclip as _pyperclip_mod
    def _copy_to_clipboard(text: str) -> bool:
        try:
            _pyperclip_mod.copy(text)
            return True
        except Exception:
            return False
except ImportError:
    def _copy_to_clipboard(text: str) -> bool:  # type: ignore
        return False

if sys.platform == "win32":
    # Required for aiodns/pycares to work on Windows
    # They don't support ProactorEventLoop (default on Py3.8+)
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
    Checkbox as TextualCheckbox,
    Select,
    DirectoryTree,
)
from textual.widgets._directory_tree import DirEntry


class Checkbox(TextualCheckbox):
    """Custom Checkbox using a checkmark instead of X."""

    BUTTON = "✓"


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


# Configure logging
logger.remove()  # Remove default handler to disable all logging
os.makedirs("logs", exist_ok=True)
logger.add(
    "logs/dnsscanner_{time}.log",
    rotation="50 MB",
    compression="zip",
    level="DEBUG",
)


# Pre-compiled regex for stripping ANSI escape codes (used in proxy test output)
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def _run_slipstream_sync(
    cmd: list, timeout: float = 15.0
) -> tuple:
    """Start slipstream and block-read stdout until 'Connection ready' or timeout.

    Designed to run in a background thread (via asyncio.to_thread) because
    asyncio.create_subprocess_exec is not supported on Windows with the Selector
    event loop that aiodns requires.

    Returns:
        (process, connection_ready: bool, lines: list[str])
        The process is NOT killed here; caller handles cleanup.
    """
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )

    lines: list[str] = []
    connection_ready = False

    def _reader():
        nonlocal connection_ready
        try:
            for raw in proc.stdout:
                clean = _ANSI_ESCAPE_RE.sub(
                    "", raw.decode("utf-8", "ignore")
                ).strip()
                lines.append(clean)
                if "Connection ready" in clean:
                    connection_ready = True
                    return  # Stop reading; leave process running for proxy use
        except Exception:
            pass

    reader = threading.Thread(target=_reader, daemon=True)
    reader.start()
    reader.join(timeout=timeout)
    # If the reader is still alive after timeout: connection_ready is still False.
    # The caller will kill the process (which closes stdout → _reader exits).
    return proc, connection_ready, lines


class SlipstreamManager:
    """Manages slipstream client download and execution across platforms."""

    DOWNLOAD_URLS = {
        "Darwin-arm64": "https://github.com/Fox-Fig/slipstream-rust-plus-deploy/releases/latest/download/slipstream-client-darwin-arm64",
        "Darwin-x86_64": "https://github.com/Fox-Fig/slipstream-rust-plus-deploy/releases/latest/download/slipstream-client-darwin-amd64",
        "Windows": "https://github.com/Fox-Fig/slipstream-rust-plus-deploy/releases/latest/download/slipstream-client-windows-amd64.exe",
        "Linux-x86_64": "https://github.com/Fox-Fig/slipstream-rust-plus-deploy/releases/latest/download/slipstream-client-linux-amd64",
        "Linux-arm64": "https://github.com/Fox-Fig/slipstream-rust-plus-deploy/releases/latest/download/slipstream-client-linux-arm64",
        "Android": "https://github.com/Fox-Fig/slipstream-rust-plus-deploy/releases/latest/download/slipstream-client-linux-arm64",
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
        "Linux-x86_64": "slipstream-client-linux-amd64",
        "Linux-arm64": "slipstream-client-linux-arm64",
        "Android": "slipstream-client-linux-arm64",
    }

    # Alternative filenames to check (for backwards compatibility)
    ALT_FILENAMES = {
        "Windows": ["slipstream-client.exe", "slipstream-client-windows-amd64.exe"],
        "Darwin-arm64": ["slipstream-client", "slipstream-client-darwin-arm64"],
        "Darwin-x86_64": ["slipstream-client", "slipstream-client-darwin-amd64"],
        "Linux-x86_64": ["slipstream-client", "slipstream-client-linux-amd64"],
        "Linux-arm64": ["slipstream-client", "slipstream-client-linux-arm64"],
        "Android": ["slipstream-client", "slipstream-client-linux-arm64"],
    }

    PLATFORM_DIRS = {
        "Darwin": "mac",
        "Windows": "windows",
        "Linux": "linux",
        "Android": "android",
    }

    def __init__(self):
        self.base_dir = Path(__file__).parent / "slipstream-client"
        self.system = self._detect_system()
        self.machine = platform.machine()
        self._cached_executable_path: Optional[Path] = None

        # Normalize machine architecture
        if self.machine in ("x86_64", "AMD64", "i386", "i686", "x86"):
            self.machine = "x86_64"
        elif self.machine in ("aarch64", "arm64", "armv8l"):
            self.machine = "arm64"
        elif self.machine.startswith("arm"):
            # For other ARM variants (armv7l, etc.), use arm64 binary
            self.machine = "arm64"

    @staticmethod
    def _detect_system() -> str:
        """Detect the operating system, including Android."""
        # Check for Android first (before Linux check)
        if os.environ.get("ANDROID_ROOT") or os.environ.get("ANDROID_DATA"):
            return "Android"
        
        # Check for Termux (common Android terminal emulator)
        if os.environ.get("TERMUX_VERSION") or Path("/data/data/com.termux").exists():
            return "Android"
        
        # Check for Android build.prop
        if Path("/system/build.prop").exists():
            return "Android"
        
        # Fall back to standard platform detection
        return platform.system()

    def get_platform_key(self) -> str:
        """Get the platform key for download URLs."""
        # Windows uses a single key (no architecture differentiation)
        if self.system == "Windows":
            return "Windows"
        elif self.system == "Android":
            # Android always uses ARM64 binary (most Android devices are ARM)
            return "Android"
        elif self.system == "Linux":
            # Linux differentiates between x86_64 and ARM64
            return f"Linux-{self.machine}"
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
    """PYDNS-Scanner with Textual TUI."""

    TITLE = "PYDNS-Scanner"
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
    
    .form-row {
        width: 100%;
        height: auto;
        min-height: 3;
        margin: 1 0;
        align: left middle;
    }
    
    .form-label {
        width: 20;
        padding: 0 1;
        color: #c9d1d9;
        content-align: left middle;
        align: left middle;
    }

    .field-label {
        width: 100%;
        text-align: center;
        content-align: center middle;
        color: #8b949e;
        padding: 0 0 1 0;
    }

    .form-field {
        width: 1fr;
        height: auto;
        padding: 0 1;
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
        width: 1fr;
        height: 100%;
        border: solid #238636;
        background: #161b22;
        padding: 1;
        margin: 1;
        color: #c9d1d9;
    }

    #stats-logs-container {
        width: 100%;
        height: 14;
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

    #results {
        width: 100%;
        height: 1fr;
        background: #161b22;
        margin: 0 1;
        padding: 1;
    }

    #logs {
        width: 1fr;
        height: 100%;
        border: solid #d29922;
        background: #161b22;
        margin: 1;
        padding: 1;
    }

    #log-display {
        height: 100%;
    }
    
    .hidden {
        display: none;
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
        scrollbar-size: 0 1;
    }
    
    Checkbox {
        background: transparent;
        color: #8b949e;
        margin-right: 2;
    }

    Checkbox > .toggle--button {
        background: transparent;
        border: solid #30363d;
        color: #8b949e;
        width: 3;
    }

    Checkbox.-on {
        color: #c9d1d9;
    }

    Checkbox.-on > .toggle--button {
        background: #238636;
        border: solid #238636;
        color: #ffffff;
    }

    Checkbox:focus > .toggle--button {
        border: solid #58a6ff;
    }
    
    .checkbox-row {
        align: center middle;
        height: auto;
        padding: 1 0;
    }

    .domain-row {
        height: 6;
    }

    .domain-checkboxes {
        width: auto;
        height: 100%;
        align: left middle;
        padding: 0 2;
        margin-top: 2;
    }

    .domain-field {
        align: center top;
    }
    """

    BINDINGS = [
        ("s", "start_scan", "Start"),
        ("q", "quit", "Quit"),
        ("c", "save_results", "Save"),
        ("p", "pause_scan", "Pause"),
        ("r", "resume_scan", "Resume"),
        ("x", "shuffle_ips", "Shuffle"),
        ("l", "toggle_logs", "Logs"),
    ]

    def __init__(self):
        super().__init__()
        self.subnet_file = ""
        self.selected_cidr_file = ""  # Track custom selected file
        self.domain = ""
        self.dns_type = "A"
        self.dns_test_method = "udp"  # "udp" (port 53)
        # Calculate default concurrency as 70% of optimal
        optimal = self._get_optimal_concurrency()
        self.concurrency = int(optimal * 0.3)
        self.random_subdomain = False
        self.test_slipstream = False
        self.bell_sound_enabled = False  # Bell sound on pass
        self.proxy_auth_enabled = False  # Proxy authentication
        self.proxy_username = ""  # Proxy username
        self.proxy_password = ""  # Proxy password

        # Scan preset settings
        self.scan_preset = "fast"  # "fast", "deep", "full"
        self.preset_max_ips = 0  # 0 = unlimited
        self.preset_shuffle_threshold = 0  # Auto-shuffle after N IPs with no find
        self.preset_auto_shuffle = False
        self.ips_since_last_found = 0  # Counter for auto-shuffle logic
        self.auto_shuffle_count = 0  # How many auto-shuffles performed
        # Apply fast preset defaults
        self._apply_scan_preset()

        # General settings - advanced tests
        self.security_test_enabled = True  # DNS hijacking, DNSSEC, open resolver
        self.ipv6_test_enabled = True  # IPv6 DNS test
        self.resolve_results: dict[str, str] = {}  # IP -> resolved IP address string
        self.edns0_test_enabled = True  # EDNS0 support test
        self.isp_info_enabled = True  # AS/ISP information lookup

        # Advanced test results storage
        self.security_results: dict[str, dict] = {}  # IP -> {dnssec, hijacked, open, filtered}
        self.protocol_results: dict[str, dict] = {}  # IP -> {ipv6, edns0}
        self.isp_results: dict[str, dict] = {}  # IP -> {asn, org, country}
        self.tcp_udp_results: dict[str, str] = {}  # IP -> "TCP/UDP", "TCP only", "UDP only"
        self.extra_test_tasks: set = set()  # Track running extra test tasks
        self.extra_test_semaphore: asyncio.Semaphore | None = None  # Limits concurrent extra tests

        # Incremental pass/fail counters (avoids O(n) scans of proxy_results)
        self._passed_count = 0
        self._failed_count = 0

        # Cached widget references (populated in on_mount)
        self._stats_widget: "StatsWidget | None" = None
        self._progress_bar_widget: "CustomProgressBar | None" = None

        # Config file for caching settings
        self.config_dir = Path.home() / ".pydns-scanner"
        self.config_file = self.config_dir / "config.json"

        self.slipstream_manager = SlipstreamManager()
        self.slipstream_path = str(self.slipstream_manager.get_executable_path())
        self.slipstream_domain = ""

        # whether to perform the full HTTP/SOCKS check after slipstream starts

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

        # Shuffle support - memory efficient
        self.remaining_ips: list = []  # Legacy, kept for compat
        self.shuffle_signal: asyncio.Event | None = None  # Signal to reshuffle during scan
        self.tested_subnets: set[str] = set()  # Track completed /24 blocks (memory-efficient)

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header(show_clock=False)

        # Start Screen
        with Container(id="start-screen"):
            with Vertical(id="start-form"):
                with Horizontal(classes="form-row"):
                    with Vertical(classes="form-field"):
                        yield Label("CIDR File:", classes="field-label")
                        yield Select(
                            [("Iran IPs (~10M IPs)", "iran"), ("Custom File...", "custom")],
                            value="iran",
                            allow_blank=False,
                            id="input-cidr-select",
                        )
                    with Vertical(classes="form-field"):
                        yield Label("Scan Mode:", classes="field-label")
                        yield Select(
                            [
                                ("Fast Scan (25K, shuffle/500)", "fast"),
                                ("Deep Scan (50k, shuffle/1K)", "deep"),
                                ("Full Scan (shuffle/3K)", "full"),
                            ],
                            value="fast",
                            allow_blank=False,
                            id="input-preset",
                        )

                with Container(id="file-browser-container"):
                    yield PlainDirectoryTree(".", id="file-browser")

                with Horizontal(classes="form-row domain-row"):
                    with Vertical(classes="form-field domain-field"):
                        yield Label("Domain:", classes="field-label")
                        yield Input(
                            placeholder="e.g., google.com",
                            id="input-domain",
                        )
                    with Horizontal(classes="domain-checkboxes"):
                        yield Checkbox("Random Subdomain", id="input-random")
                        yield Checkbox("Proxy Auth", id="input-proxy-auth")

                with Container(id="proxy-auth-container"):
                    with Horizontal(classes="form-row"):
                        yield Input(
                            placeholder="proxy username",
                            id="input-proxy-user",
                            classes="form-input",
                        )
                        yield Input(
                            placeholder="proxy password",
                            id="input-proxy-pass",
                            classes="form-input",
                            password=True,
                        )

                with Horizontal(classes="form-row"):
                    with Vertical(classes="form-field"):
                        yield Label("DNS Type:", classes="field-label")
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
                        )

                with Horizontal(classes="form-row"):
                    with Vertical(classes="form-field"):
                        yield Label("Concurrency:", classes="field-label")
                        yield Input(
                            placeholder="70% of optimal",
                            id="input-concurrency",
                            value=str(self.concurrency),
                        )

                with Horizontal(classes="form-row checkbox-row"):
                    yield Checkbox("Proxy Test", id="input-slipstream")
                    yield Checkbox("Bell on Pass", id="input-bell")

                with Horizontal(id="start-buttons"):
                    yield Button("Start Scan", id="start-scan-btn", variant="success")
                    yield Button("Exit", id="exit-btn", variant="error")

        # Scan Screen (initially hidden)
        with Container(id="scan-screen"):
            with Horizontal(id="stats-logs-container"):
                yield StatsWidget(id="stats")
                with Container(id="logs", classes="hidden"):
                    yield RichLog(id="log-display", highlight=True, markup=True)
            with Container(id="progress-container"):
                yield CustomProgressBar(id="progress-bar")
            with Container(id="results"):
                yield DataTable(id="results-table")
            with Horizontal(id="controls"):
                yield Button("⏸  Pause", id="pause-btn", variant="warning")
                yield Button("🔀 Shuffle", id="shuffle-btn", variant="default")
                yield Button("▶  Resume", id="resume-btn", variant="primary")
                yield Button("Save Results", id="save-btn", variant="success")
                yield Button("Quit", id="quit-btn", variant="error")

        yield Footer()

    def _load_cached_domain(self) -> str:
        """Load last used domain from config file (legacy compatibility)."""
        config = self._load_config()
        return config.get("domain", "")

    def _load_config(self) -> dict:
        """Load complete configuration from file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"Config file corrupted or invalid, ignoring: {e}")
        except (OSError, IOError) as e:
            logger.debug(f"Failed to read config file: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error loading config: {e}")
        return {}

    def _save_domain_cache(self, domain: str) -> None:
        """Save domain to config (legacy method, use _save_config instead)."""
        config = self._load_config()
        config["domain"] = domain
        self._save_config(config)

    def _save_config(self, config: dict) -> None:
        """Save complete configuration to file."""
        try:
            # Create config directory if it doesn't exist
            self.config_dir.mkdir(parents=True, exist_ok=True)

            # Save config
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except (OSError, IOError) as e:
            logger.debug(f"Failed to save config (permission/IO error): {e}")
        except Exception as e:
            logger.warning(f"Unexpected error saving config: {e}")

    def on_mount(self) -> None:
        """Initialize when app is mounted."""
        # Set dark theme (GitHub dark)
        self.dark = True

        # Initialize keybindings for start screen
        self._update_keybinding_visibility(scanning=False, paused=False)

        # Hide scan screen initially
        self.query_one("#scan-screen").display = False

        # Load configuration and populate form
        config = self._load_config()
        try:
            # Domain
            if config.get("domain"):
                domain_input = self.query_one("#input-domain", Input)
                domain_input.value = config["domain"]

            # Concurrency
            if config.get("concurrency"):
                concurrency_input = self.query_one("#input-concurrency", Input)
                concurrency_input.value = str(config["concurrency"])

            # DNS Type
            if config.get("dns_type"):
                type_select = self.query_one("#input-type", Select)
                type_select.value = config["dns_type"]

            # Scan Preset
            if config.get("scan_preset"):
                preset_select = self.query_one("#input-preset", Select)
                preset_select.value = config["scan_preset"]

            # Proxy Auth
            if config.get("proxy_auth_enabled"):
                proxy_auth_checkbox = self.query_one("#input-proxy-auth", Checkbox)
                proxy_auth_checkbox.value = config["proxy_auth_enabled"]
                # Show proxy auth container
                self.query_one("#proxy-auth-container").display = True

                # Proxy credentials
                if config.get("proxy_username"):
                    proxy_user_input = self.query_one("#input-proxy-user", Input)
                    proxy_user_input.value = config["proxy_username"]

                if config.get("proxy_password"):
                    # Decode password from base64
                    import base64
                    try:
                        decoded_pass = base64.b64decode(config["proxy_password"]).decode("utf-8")
                        proxy_pass_input = self.query_one("#input-proxy-pass", Input)
                        proxy_pass_input.value = decoded_pass
                    except Exception:
                        pass

            # slipstream settings
            if config.get("slipstream_enabled") is not None:
                slip_checkbox = self.query_one("#input-slipstream", Checkbox)
                slip_checkbox.value = config.get("slipstream_enabled")

        except Exception as e:
            logger.debug(f"Could not set cached config values: {e}")

        # Setup both results tables
        self._setup_table_columns()

        # Cache frequently accessed widget references
        try:
            self._stats_widget = self.query_one("#stats", StatsWidget)
            self._progress_bar_widget = self.query_one("#progress-bar", CustomProgressBar)
        except Exception as e:
            logger.debug(f"Could not cache widget refs: {e}")

        # Hide pause/resume/shuffle buttons initially
        try:
            self.query_one("#pause-btn", Button).display = False
            self.query_one("#resume-btn", Button).display = False
            self.query_one("#shuffle-btn", Button).display = False
        except Exception as e:
            logger.debug(f"Could not hide buttons during mount: {e}")

    def _get_table_columns(self) -> list[tuple[str, str, int | None]]:
        """Return list of (label, key, width) for unified results table."""
        cols: list[tuple[str, str, int | None]] = [
            ("IP Address", "ip", None),
            ("Ping", "time", None),
        ]
        if self.test_slipstream:
            cols.append(("Proxy Test", "proxy", None))
        cols.append(("IPv4/IPv6", "ipver", None))
        cols.append(("Security", "security", None))
        cols.append(("TCP/UDP", "tcpudp", None))
        cols.append(("EDNS0", "edns0", None))
        cols.append(("Resolved IP", "resolved", None))
        cols.append(("ISP", "isp", 50))
        return cols

    def _setup_table_columns(self) -> None:
        """Setup unified results table with proper columns."""
        try:
            table = self.query_one("#results-table", DataTable)
            table.clear(columns=True)
            for label, key, width in self._get_table_columns():
                table.add_column(label, key=key, width=width)
            table.cursor_type = "row"
        except Exception as e:
            logger.debug(f"Could not setup table columns: {e}")

    def action_quit(self) -> None:
        """Gracefully quit the application with proper cleanup."""
        # Signal shutdown to stop any running scans
        if self._shutdown_event:
            self._shutdown_event.set()
        if self.shuffle_signal:
            self.shuffle_signal.set()  # Unblock any shuffle wait

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
            for task in list(self.active_scan_tasks):
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

        # Cancel all extra test tasks
        if hasattr(self, "extra_test_tasks"):
            for task in list(self.extra_test_tasks):
                try:
                    if not task.done():
                        task.cancel()
                except Exception as e:
                    logger.debug(f"Could not cancel extra test task: {e}")
            self.extra_test_tasks.clear()

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
            # Rebuild table when paused so user sees sorted results
            self.table_needs_rebuild = True
            self._rebuild_table()

    def action_resume_scan(self) -> None:
        """Keybinding action to resume scan."""
        if self.scan_started and self.is_paused:
            self._resume_scan()
            self._update_keybinding_visibility(scanning=True, paused=False)

    def action_shuffle_ips(self) -> None:
        """Keybinding action to shuffle IPs - instant, no pause needed."""
        if self.scan_started and not (self._shutdown_event and self._shutdown_event.is_set()):
            if self.shuffle_signal:
                self.shuffle_signal.set()
                self._log("[cyan]Shuffle requested - reshuffling IP order...[/cyan]")
                self.notify("Shuffling IP order...", severity="information", timeout=2)
                # Force immediate yield to process shuffle signal
                self.call_later(lambda: None)
    
    def action_toggle_logs(self) -> None:
        """Toggle log panel visibility with 'L' key."""
        try:
            logs_container = self.query_one("#logs")
            if "hidden" in logs_container.classes:
                logs_container.remove_class("hidden")
            else:
                logs_container.add_class("hidden")
        except Exception as e:
            logger.debug(f"Could not toggle logs: {e}")

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
                # Rebuild table when paused so user sees sorted results
                self.table_needs_rebuild = True
                self._rebuild_table()
                self._update_keybinding_visibility(scanning=True, paused=True)
            elif event.button.id == "resume-btn":
                self._resume_scan()
                self._update_keybinding_visibility(scanning=True, paused=False)
            elif event.button.id == "shuffle-btn":
                # Instant shuffle - no pause needed
                self.action_shuffle_ips()
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

        # Update dropdown to add selected file as third option
        cidr_select = self.query_one("#input-cidr-select", Select)
        file_name = Path(selected_file).name
        cidr_select.set_options([
            ("Iran IPs (~10M IPs)", "iran"),
            ("Custom File...", "custom"),
            (file_name, "selected_file"),
        ])
        cidr_select.value = "selected_file"

        # Hide browser after selection
        self.query_one("#file-browser-container").display = False

        # Notify user which file was selected
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

        # Update button visibility with explicit refresh for immediate UI update
        try:
            pause_btn = self.query_one("#pause-btn", Button)
            resume_btn = self.query_one("#resume-btn", Button)
            shuffle_btn = self.query_one("#shuffle-btn", Button)
            
            pause_btn.display = False
            resume_btn.display = True
            shuffle_btn.display = True
            
            # Force immediate refresh to update UI even during heavy load
            pause_btn.refresh()
            resume_btn.refresh()
            shuffle_btn.refresh()
            
            # Refresh parent container to ensure layout updates
            try:
                self.query_one("#controls").refresh()
            except Exception:
                pass
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

        # Update button visibility with explicit refresh for immediate UI update
        try:
            pause_btn = self.query_one("#pause-btn", Button)
            resume_btn = self.query_one("#resume-btn", Button)
            shuffle_btn = self.query_one("#shuffle-btn", Button)
            
            pause_btn.display = True
            resume_btn.display = False
            shuffle_btn.display = False
            
            # Force immediate refresh to update UI even during heavy load
            pause_btn.refresh()
            resume_btn.refresh()
            shuffle_btn.refresh()
            
            # Refresh parent container to ensure layout updates
            try:
                self.query_one("#controls").refresh()
            except Exception:
                pass
        except Exception as e:
            logger.debug(f"Could not update button visibility on resume: {e}")

        # Update keybinding visibility
        self._update_keybinding_visibility(scanning=True, paused=False)

    def _get_optimal_concurrency(self) -> int:
        """Calculate optimal concurrency based on system resources."""
        try:
            cpu_count = os.cpu_count() or 2
            # Try to detect available memory
            try:
                import shutil
                total, used, free = shutil.disk_usage("/")
                # Use a simple heuristic based on CPU count
                if cpu_count >= 8:
                    return 500
                elif cpu_count >= 4:
                    return 200
                else:
                    return 100
            except Exception:
                pass

            # Fallback: scale based on CPU count
            if cpu_count >= 8:
                return 500
            elif cpu_count >= 4:
                return 200
            else:
                return 100
        except Exception:
            return 100

    def _apply_scan_preset(self) -> None:
        """Apply scan preset settings."""
        if self.scan_preset == "fast":
            self.preset_max_ips = 25000
            self.preset_shuffle_threshold = 500
            self.preset_auto_shuffle = True
        elif self.scan_preset == "deep":
            self.preset_max_ips = 50000  # 50K max for deep scan
            self.preset_shuffle_threshold = 1000
            self.preset_auto_shuffle = True
        elif self.scan_preset == "full":
            self.preset_max_ips = 0  # Unlimited
            self.preset_shuffle_threshold = 3000
            self.preset_auto_shuffle = True
        else:  # Default to fast
            self.preset_max_ips = 25000
            self.preset_shuffle_threshold = 500
            self.preset_auto_shuffle = True

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
            # User selected "Custom File..." but hasn't picked a file yet
            self.notify(
                "Please select a CIDR file from the file browser!",
                severity="warning",
            )
            return
        elif cidr_value == "selected_file":
            # Use the previously selected custom file
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

        # Get scan preset
        preset_select = self.query_one("#input-preset", Select)
        self.scan_preset = str(preset_select.value) if preset_select.value else "fast"
        self._apply_scan_preset()

        # Get concurrency (auto or manual)
        concurrency_str = concurrency_input.value.strip().lower()
        if concurrency_str == "auto" or not concurrency_str:
            # Calculate 70% of optimal
            optimal = self._get_optimal_concurrency()
            self.concurrency = int(optimal * 0.7)
        else:
            try:
                self.concurrency = int(concurrency_str)
            except ValueError:
                optimal = self._get_optimal_concurrency()
                self.concurrency = int(optimal * 0.7)

        # Get general settings (NOT saved - user selects each time)
        # All general settings are now always enabled

        # Rebuild table columns based on enabled tests
        self._setup_table_columns()

        if not self.domain:
            self.notify("Please enter a domain!", severity="error")
            return

        # Save configuration for next session
        import base64
        config = {
            "domain": self.domain,
            "dns_type": self.dns_type,
            "scan_preset": self.scan_preset,
            "concurrency": self.concurrency,
            "proxy_auth_enabled": self.proxy_auth_enabled,
            "proxy_username": self.proxy_username if self.proxy_auth_enabled else "",
            "proxy_password": base64.b64encode(self.proxy_password.encode("utf-8")).decode("utf-8") if self.proxy_auth_enabled and self.proxy_password else "",
            # slipstream-related flags
            "slipstream_enabled": self.test_slipstream,
        }
        self._save_config(config)

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

        # Setup log display AFTER switching to scan screen
        log_widget = self.query_one("#log-display", RichLog)
        log_widget.write("[bold cyan]PYDNS Scanner Log[/bold cyan]")
        log_widget.write(f"[yellow]Subnet file:[/yellow] {self.subnet_file}")
        log_widget.write(f"[yellow]Domain:[/yellow] {self.domain}")
        log_widget.write(f"[yellow]DNS Type:[/yellow] {self.dns_type}")
        log_widget.write(f"[yellow]Concurrency:[/yellow] {self.concurrency}")
        log_widget.write(f"[yellow]Scan Preset:[/yellow] {self.scan_preset}")
        log_widget.write(
            f"[yellow]Slipstream Test:[/yellow] {'Enabled' if self.test_slipstream else 'Disabled'}"
        )
        # Log enabled extra tests
        enabled_tests = []
        if self.security_test_enabled:
            enabled_tests.append("Security")
        if self.ipv6_test_enabled:
            enabled_tests.append("IPv6")
        if self.edns0_test_enabled:
            enabled_tests.append("EDNS0")
        if self.isp_info_enabled:
            enabled_tests.append("ISP")
        if enabled_tests:
            log_widget.write(f"[yellow]Extra Tests:[/yellow] {', '.join(enabled_tests)}")
        log_widget.write("[green]Starting scan...[/green]\n")

        # Start scanning
        self.scan_started = True

        # Update keybinding visibility for scan mode
        self._update_keybinding_visibility(scanning=True, paused=False)

        self.run_worker(self._scan_async(), exclusive=True)

    async def _check_update_and_start_scan(self) -> None:
        """Check for slipstream updates and then start the scan."""
        # Rebuild table columns (test toggles already read)
        self._setup_table_columns()

        # Switch to scan screen to show progress
        self.query_one("#start-screen").display = False
        self.query_one("#scan-screen").display = True

        # Get log widget AFTER switching to scan screen
        log_widget = self.query_one("#log-display", RichLog)
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
        log_widget.write(f"[yellow]Scan Preset:[/yellow] {self.scan_preset}")
        log_widget.write("[yellow]Slipstream Test:[/yellow] Enabled")
        # Log enabled extra tests
        enabled_tests = []
        if self.security_test_enabled:
            enabled_tests.append("Security")
        if self.ipv6_test_enabled:
            enabled_tests.append("IPv6")
        if self.edns0_test_enabled:
            enabled_tests.append("EDNS0")
        if self.isp_info_enabled:
            enabled_tests.append("ISP")
        if enabled_tests:
            log_widget.write(f"[yellow]Extra Tests:[/yellow] {', '.join(enabled_tests)}")
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
        """Async scanning logic with instant shuffle support."""
        # Reset state for re-scanning
        self.found_servers.clear()
        self.server_times.clear()
        self.proxy_results.clear()
        self.current_scanned = 0
        self.table_needs_rebuild = False
        self.remaining_ips.clear()
        self.tested_subnets.clear()
        self.total_ips_yielded = 0  # Track IPs yielded across all stream instances (survives shuffles)

        # Reset extra test state
        self.security_results.clear()
        self.protocol_results.clear()
        self.isp_results.clear()
        self.resolve_results.clear()
        self.tcp_udp_results.clear()
        self.extra_test_tasks.clear()
        self.extra_test_semaphore = asyncio.Semaphore(5)  # Max 5 concurrent extra tests
        self._isp_rate_lock = asyncio.Lock()  # Serialize ip-api.com requests
        self._isp_last_request: float = 0.0   # Monotonic time of last ip-api request
        self.ips_since_last_found = 0
        self.auto_shuffle_count = 0
        self._passed_count = 0
        self._failed_count = 0

        # Shared HTTP client for extra tests (avoids per-request connection overhead)
        self._http_client = httpx.AsyncClient(
            verify=False,
            timeout=5.0,
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=10),
        )

        # Force garbage collection after clearing large structures
        gc.collect()

        # Reset pause state
        self.is_paused = False
        self.pause_event = asyncio.Event()
        self.pause_event.set()  # Not paused initially

        # Initialize shuffle signal
        self.shuffle_signal = asyncio.Event()

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

        # Start periodic sort refresh timer (every 3 seconds)
        self._sort_refresh_timer = self.set_interval(3.0, self._periodic_sort_refresh)

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

        # Use preset limit as effective total if set
        effective_total = total_ips
        if self.preset_max_ips > 0:
            effective_total = min(total_ips, self.preset_max_ips)
            self._log(f"[cyan]Found {total_ips:,} IPs in file. {self.scan_preset.title()} scan limited to {effective_total:,} IPs.[/cyan]")
        else:
            self._log(f"[cyan]Found {total_ips:,} total IPs to scan. Starting...[/cyan]")
        await asyncio.sleep(0)

        try:
            stats = self._stats_widget
            if stats is not None:
                stats.total = effective_total
            pb = self._progress_bar_widget
            if pb is not None:
                pb.update_progress(0, effective_total)
        except Exception as e:
            logger.debug(f"Could not initialize stats widget: {e}")

        logger.info(f"Starting chunked scan with concurrency {self.concurrency}")
        self._log("[cyan]Scan mode: Streaming chunks (no pre-loading)[/cyan]")
        self._log(f"[cyan]Concurrency: {self.concurrency} workers[/cyan]")
        await asyncio.sleep(0)

        self._log("[cyan]DNS method: Standard UDP (port 53)[/cyan]")
        await asyncio.sleep(0)

        self.notify("Scanning in real-time...", severity="information", timeout=3)

        # Create semaphore
        sem = asyncio.Semaphore(self.concurrency)

        # Windows Selector event loop caps socket monitoring at 64 — warn if over limit
        import sys as _sys
        if _sys.platform == "win32" and self.concurrency > 64:
            self._log(
                f"[yellow]⚠ Windows select() limit: effective concurrency capped at ~64 sockets "
                f"(requested {self.concurrency}). Consider lowering concurrency for reliability.[/yellow]"
            )

        self._log("[green]Starting memory-efficient streaming scan...[/green]")
        await asyncio.sleep(0)

        max_outstanding = self.concurrency * 2  # Cap outstanding tasks
        active_tasks: set = set()
        scan_complete = False

        # Outer loop: restarts streaming when shuffle is signaled
        while not scan_complete:
            if self._shutdown_event and self._shutdown_event.is_set():
                break

            # Clear shuffle signal for this iteration
            self.shuffle_signal.clear()

            shuffled = False

            # Stream IPs efficiently without loading all into memory
            async for ip_chunk in self._stream_ips_from_file():
                # Check for shutdown
                if self._shutdown_event and self._shutdown_event.is_set():
                    break

                # Check for pause
                await self.pause_event.wait()

                # Check for shuffle signal - break to restart stream with new order
                if self.shuffle_signal.is_set():
                    shuffled = True
                    self._log("[cyan]Reshuffling IP stream order...[/cyan]")
                    break

                # Create tasks for this chunk
                for ip in ip_chunk:
                    # Stop creating tasks if preset limit reached
                    if self._shutdown_event and self._shutdown_event.is_set():
                        break
                    task = asyncio.create_task(self._test_dns_with_callback(ip, sem))
                    active_tasks.add(task)

                # Keep reference for cleanup
                self.active_scan_tasks = active_tasks

                # Process completed tasks - keep outstanding tasks capped
                while len(active_tasks) >= max_outstanding:
                    # Check for pause before processing
                    await self.pause_event.wait()

                    # Check for shutdown
                    if self._shutdown_event and self._shutdown_event.is_set():
                        break

                    # Check for shuffle signal during processing
                    if self.shuffle_signal.is_set():
                        shuffled = True
                        self._log("[cyan]Reshuffling IP stream order...[/cyan]")
                        break

                    # Wait for some tasks to complete (timeout ensures UI stays responsive)
                    done, pending = await asyncio.wait(
                        active_tasks, return_when=asyncio.FIRST_COMPLETED, timeout=0.15
                    )

                    if not done:
                        # Timeout - no tasks completed yet, just yield to UI
                        await asyncio.sleep(0)
                        continue

                    # Process completed results in small batches to prevent UI freeze
                    done_list = list(done)
                    batch_size = 5  # Process max 5 results before yielding to UI for better responsiveness
                    for i, task in enumerate(done_list):
                        try:
                            result = await task
                            await self._process_result(result)
                        except asyncio.CancelledError:
                            pass
                        except Exception as e:
                            logger.error(
                                f"Error processing DNS test result: {e}", exc_info=True
                            )
                        
                        # Yield to UI every batch_size results to keep UI responsive
                        if (i + 1) % batch_size == 0:
                            await asyncio.sleep(0)

                    active_tasks = pending  # pending is already a set
                    self.active_scan_tasks = active_tasks

                # Break out of async for if shuffle/shutdown detected in processing
                if shuffled or (self._shutdown_event and self._shutdown_event.is_set()):
                    break

            # Check if shuffle was signaled but stream ended before we caught it
            if not shuffled and self.shuffle_signal.is_set():
                shuffled = True
                self._log("[cyan]Reshuffling IP stream order (post-stream)...[/cyan]")

            if not shuffled:
                # Stream completed normally (no shuffle interrupt)
                scan_complete = True
            else:
                # Shuffle was requested - drain active tasks quickly then restart stream
                if active_tasks:
                    self._log(f"[dim]Draining {len(active_tasks)} active tasks before reshuffle...[/dim]")
                    done, pending = await asyncio.wait(active_tasks, timeout=5.0)
                    # Process in batches to prevent UI freeze
                    done_list = list(done)
                    for i, task in enumerate(done_list):
                        try:
                            result = await task
                            await self._process_result(result)
                        except (asyncio.CancelledError, Exception):
                            pass
                        # Yield every 5 results for better responsiveness
                        if (i + 1) % 5 == 0:
                            await asyncio.sleep(0)
                    # Cancel remaining tasks that didn't finish in time
                    for task in pending:
                        task.cancel()
                    active_tasks = set()
                    self.active_scan_tasks = []

                self._log(
                    f"[cyan]Restarting stream (skipping {len(self.tested_subnets)} completed /24 blocks)[/cyan]"
                )
                gc.collect()
                await asyncio.sleep(0)

        # Check if we're shutting down
        if self._shutdown_event and self._shutdown_event.is_set():
            self._log("[yellow]Scan interrupted - cleaning up...[/yellow]")
            # Stop sort refresh timer
            if hasattr(self, "_sort_refresh_timer") and self._sort_refresh_timer:
                self._sort_refresh_timer.stop()
                self._sort_refresh_timer = None
            # Cancel remaining tasks
            for task in active_tasks:
                if not task.done():
                    task.cancel()
            return

        # Wait for all remaining tasks
        self._log("[cyan]Finishing remaining scans...[/cyan]")
        if active_tasks:
            done, _ = await asyncio.wait(active_tasks)
            # Process in batches to prevent UI freeze
            done_list = list(done)
            for i, task in enumerate(done_list):
                try:
                    result = await task
                    await self._process_result(result)
                except asyncio.CancelledError:
                    pass  # Task was cancelled
                except Exception as e:
                    logger.error(
                        f"Error processing final task result: {e}", exc_info=True
                    )
                # Yield every 5 results for better responsiveness
                if (i + 1) % 5 == 0:
                    await asyncio.sleep(0)

        self._log(
            f"[cyan]Scan complete. Scanned: {self.current_scanned}, Found: {len(self.found_servers)}[/cyan]"
        )
        logger.info(
            f"Scan complete. Scanned: {self.current_scanned}, Found: {len(self.found_servers)}"
        )

        # Stop the periodic sort refresh timer
        if hasattr(self, "_sort_refresh_timer") and self._sort_refresh_timer:
            self._sort_refresh_timer.stop()
            self._sort_refresh_timer = None

        # Rebuild table at end to show final sorted results
        self.table_needs_rebuild = True
        self._rebuild_table()

        # Full garbage collection after scan completes
        gc.collect()

        # Update final statistics
        try:
            stats = self._stats_widget
            if stats is not None:
                stats.scanned = self.current_scanned
                stats.found = len(self.found_servers)
                stats.passed = self._passed_count
                stats.failed = self._failed_count
                elapsed = time.time() - self.start_time
                stats.elapsed = elapsed
                stats.speed = self.current_scanned / elapsed if elapsed > 0 else 0
                stats.total = self.current_scanned  # Set total to actual scanned count

            pb = self._progress_bar_widget
            if pb is not None:
                pb.update_progress(self.current_scanned, self.current_scanned)  # Force 100%
        except Exception as e:
            logger.debug(f"Could not update final statistics: {e}")

        # Final table rebuild
        self.table_needs_rebuild = True
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
            self.table_needs_rebuild = True
            self._rebuild_table()  # Rebuild after all tests complete
            # Collect garbage after proxy tests complete
            gc.collect()

        # Wait for extra test tasks to complete
        if self.extra_test_tasks:
            num_extra = len(self.extra_test_tasks)
            self._log(
                f"[cyan]Waiting for {num_extra} extra tests to complete (max 30s)...[/cyan]"
            )
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.extra_test_tasks, return_exceptions=True),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                self._log("[yellow]Timeout waiting for extra tests[/yellow]")
            self.table_needs_rebuild = True
            self._rebuild_table()

        # Auto-save results
        self._auto_save_results()

        self.notify("Scan complete! Results auto-saved.", severity="information")

        # Close shared HTTP client
        try:
            await self._http_client.aclose()
        except Exception:
            pass

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

        Memory-efficient streaming approach. Skips /24 blocks already in
        self.tested_subnets so reshuffled streams don't re-scan completed blocks.
        Each yielded chunk comes from a single /24 block which is marked as tested.
        """
        chunk = []
        chunk_size = 500  # Yield 500 IPs at a time
        max_ips = self.preset_max_ips  # 0 = unlimited
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
                                pass
            except (OSError, IOError) as e:
                logger.error(f"Failed to read subnet file: {e}")
            return subnets

        # Read subnets (small list, not individual IPs)
        subnets = await loop.run_in_executor(None, read_and_process)
        rng.shuffle(subnets)

        # Generate IPs from subnets - stream them efficiently
        for net in subnets:
            # Stop streaming if shutdown was requested (preset limit reached)
            if self._shutdown_event and self._shutdown_event.is_set():
                break

            # Split into /24 chunks
            if net.prefixlen >= 24:
                chunks_24 = [net]
            else:
                chunks_24 = list(net.subnets(new_prefix=24))

            rng.shuffle(chunks_24)

            for subnet_chunk in chunks_24:
                # Skip already-tested /24 blocks (from previous shuffle iterations)
                subnet_key = str(subnet_chunk.network_address)
                if subnet_key in self.tested_subnets:
                    continue

                # Generate IPs for this /24
                if subnet_chunk.num_addresses == 1:
                    chunk.append(str(subnet_chunk.network_address))
                    self.total_ips_yielded += 1
                else:
                    # Integer-range shuffle — no IPv4Address object allocation per host
                    net_int = int(subnet_chunk.network_address)
                    if subnet_chunk.prefixlen >= 31:
                        # /31: both addresses are valid hosts; /32 is handled above
                        addr_count = subnet_chunk.num_addresses
                        indices = list(range(addr_count))
                        rng.shuffle(indices)
                        for idx in indices:
                            chunk.append(str(ipaddress.IPv4Address(net_int + idx)))
                            self.total_ips_yielded += 1
                            if max_ips > 0 and self.total_ips_yielded >= max_ips:
                                break
                    else:
                        host_count = subnet_chunk.num_addresses - 2  # exclude network + broadcast
                        start_int = net_int + 1
                        for idx in rng.sample(range(host_count), host_count):
                            chunk.append(str(ipaddress.IPv4Address(start_int + idx)))
                            self.total_ips_yielded += 1
                            # Stop generating if preset limit reached
                            if max_ips > 0 and self.total_ips_yielded >= max_ips:
                                break

                # Mark this /24 as tested
                self.tested_subnets.add(subnet_key)

                # Yield chunk when it reaches size
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []
                    await asyncio.sleep(0)  # Yield to event loop

                # Stop streaming if preset limit reached
                if max_ips > 0 and self.total_ips_yielded >= max_ips:
                    if chunk:
                        yield chunk
                    return

            # Check preset limit at subnet level too
            if max_ips > 0 and self.total_ips_yielded >= max_ips:
                if chunk:
                    yield chunk
                return

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
                # Reset auto-shuffle counter when DNS found
                self.ips_since_last_found = 0

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

                # Queue extra tests if enabled (non-blocking)
                self._queue_extra_tests(ip)
            else:
                # Increment counter for auto-shuffle logic
                self.ips_since_last_found += 1

                # Auto-shuffle logic for presets - instant, no pause needed
                if (
                    self.preset_auto_shuffle
                    and self.preset_shuffle_threshold > 0
                    and self.ips_since_last_found >= self.preset_shuffle_threshold
                    and not self.is_paused
                ):
                    # For fast preset: also check proxy pass if proxy test is on
                    should_shuffle = True
                    if self.scan_preset == "fast" and self.test_slipstream:
                        if self._passed_count > self.auto_shuffle_count:
                            should_shuffle = False

                    # For full preset: skip shuffle if ANY DNS was found in this cycle
                    if self.scan_preset == "full" and len(self.found_servers) > self.auto_shuffle_count:
                        should_shuffle = False
                        self.auto_shuffle_count = len(self.found_servers)

                    if should_shuffle:
                        self.auto_shuffle_count += 1
                        self.ips_since_last_found = 0
                        self._log(
                            f"[yellow]Auto-shuffle ({self.scan_preset}): "
                            f"No DNS in {self.preset_shuffle_threshold} IPs[/yellow]"
                        )
                        # Signal instant reshuffle - no pause needed
                        if self.shuffle_signal:
                            self.shuffle_signal.set()

            # Check preset max IPs limit (fast and deep) - outside if/else so it always fires
            if (
                self.preset_max_ips > 0
                and self.current_scanned >= self.preset_max_ips
            ):
                self._log(
                    f"[yellow]{self.scan_preset.title()} scan limit reached ({self.preset_max_ips} IPs). Stopping.[/yellow]"
                )
                if self._shutdown_event:
                    self._shutdown_event.set()

            # Update UI periodically with time-based throttling to prevent UI freeze
            current_time = time.time()
            # Update every 10 IPs OR every 0.1 seconds, whichever comes first
            should_update = (
                self.current_scanned % 10 == 0 or
                (current_time - self.last_update_time) >= 0.1
            )

            if should_update:
                elapsed = current_time - self.start_time
                self.last_update_time = current_time

                try:
                    stats = self._stats_widget
                    if stats is not None:
                        # Direct update (batch_update context manager not available on Static)
                        stats.scanned = self.current_scanned
                        stats.elapsed = elapsed
                        stats.speed = self.current_scanned / elapsed if elapsed > 0 else 0
                        stats.found = len(self.found_servers)
                        stats.passed = self._passed_count
                        stats.failed = self._failed_count

                    pb = self._progress_bar_widget
                    if pb is not None:
                        pb.update_progress(self.current_scanned, stats.total if stats else 0)
                except Exception as e:
                    logger.debug(f"Could not update stats during scan: {e}")

            # Yield to UI event loop after each result to keep UI responsive
            await asyncio.sleep(0)

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
                    prefix = random.randbytes(4).hex()
                    domain = f"{prefix}.{domain}"

                # 2 second timeout for DNS servers
                resolver = aiodns.DNSResolver(nameservers=[ip], timeout=2.0, tries=1)

                start = time.time()
                try:
                    # Use query method instead of query_dns for better compatibility
                    result = await resolver.query(domain, self.dns_type)
                    elapsed = time.time() - start

                    # If we got a result (even empty list means valid server response) and it's under 2000ms
                    # An empty list [] means "No records found" but the server DID respond successfully.
                    if (result is not None) and elapsed < 2.0:
                        logger.debug(
                            f"{ip}: DNS responded - {type(result)} in {elapsed*1000:.0f}ms"
                        )
                        return (ip, True, elapsed)
                    elif result is not None:
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
        """Add a found server to the unified result table immediately."""
        self.found_servers.add(ip)
        self.server_times[ip] = response_time

        try:
            time_str = self._format_time(response_time)

            # Build unified row
            row = [ip, time_str]
            if self.test_slipstream:
                row.append(self._get_proxy_str(ip))
            row.extend([
                self._get_ipver_column(ip),
                self._get_security_column(ip), self._get_tcp_udp_column(ip),
                self._get_edns0_column(ip),
                self._get_resolve_column(ip),
                self._get_isp_column(ip),
            ])

            table = self.query_one("#results-table", DataTable)
            table.add_row(*row, key=ip)
        except Exception as e:
            logger.debug(f"Could not add result row to table: {e}")

    def _get_proxy_str(self, ip: str) -> str:
        """Get formatted proxy status string."""
        proxy_status = self.proxy_results.get(ip, "N/A")
        if proxy_status == "Success":
            return "[green]Passed[/green]"
        elif proxy_status == "Failed":
            return "[red]Failed[/red]"
        elif proxy_status == "Testing":
            return "[yellow]Testing...[/yellow]"
        elif proxy_status == "Pending":
            return "[dim]Queued[/dim]"
        return "[dim]N/A[/dim]"

    def _get_ipver_column(self, ip: str) -> str:
        """Get IPv4/IPv6 support for table column."""
        proto = self.protocol_results.get(ip, {})
        if ip not in self.protocol_results:
            return "[dim]Testing...[/dim]"
        if proto.get("ipv6"):
            return "[green]IPv4/IPv6[/green]"
        return "[cyan]IPv4[/cyan]"

    def _update_table_row(self, ip: str) -> None:
        """Update individual cells in the table for the given IP (no rebuild)."""
        try:
            table = self.query_one("#results-table", DataTable)
            if ip in table._row_locations:
                if self.test_slipstream:
                    table.update_cell(ip, "proxy", self._get_proxy_str(ip))
                table.update_cell(ip, "ipver", self._get_ipver_column(ip))
                table.update_cell(ip, "isp", self._get_isp_column(ip))
                table.update_cell(ip, "security", self._get_security_column(ip))
                table.update_cell(ip, "tcpudp", self._get_tcp_udp_column(ip))
                table.update_cell(ip, "resolved", self._get_resolve_column(ip))
                table.update_cell(ip, "edns0", self._get_edns0_column(ip))
        except Exception as e:
            logger.debug(f"Could not update table row for {ip}: {e}")

    def _rebuild_table(self) -> None:
        """Rebuild unified table with default sort (finalized IPs first, sorted by ping)."""
        if not self.table_needs_rebuild:
            return

        try:
            ips = list(self.server_times.keys())
            finalized = [ip for ip in ips if self._is_ip_finalized(ip)]
            testing = [ip for ip in ips if not self._is_ip_finalized(ip)]

            # Sort: 1) proxy Success first (if enabled), 2) DNSSEC, 3) ping ascending
            def _sort_key(ip):
                proxy_rank = 0 if (self.test_slipstream and self.proxy_results.get(ip) == "Success") else (1 if self.test_slipstream else 0)
                dnssec_rank = 0 if self.security_results.get(ip, {}).get("dnssec") else 1
                return (proxy_rank, dnssec_rank, self.server_times.get(ip, 9999.0))
            sorted_final = sorted(finalized, key=_sort_key)
            sorted_testing = sorted(testing, key=_sort_key)

            # Rebuild unified table
            table = self.query_one("#results-table", DataTable)
            # Save scroll position before clearing
            scroll_x = table.scroll_x
            scroll_y = table.scroll_y
            
            table.clear(columns=True)
            for label, key, width in self._get_table_columns():
                table.add_column(label, key=key, width=width)
            table.cursor_type = "row"

            for ip in sorted_final + sorted_testing:
                row = [ip, self._format_time(self.server_times[ip])]
                if self.test_slipstream:
                    row.append(self._get_proxy_str(ip))
                row.extend([
                    self._get_ipver_column(ip),
                    self._get_security_column(ip), self._get_tcp_udp_column(ip),
                    self._get_edns0_column(ip),
                    self._get_resolve_column(ip),
                    self._get_isp_column(ip),
                ])
                table.add_row(*row, key=ip)

            # Restore scroll position
            table.scroll_x = scroll_x
            table.scroll_y = scroll_y

            self.table_needs_rebuild = False
        except Exception as e:
            logger.debug(f"Could not rebuild results table: {e}")

    def _is_ip_finalized(self, ip: str) -> bool:
        """Check if all enabled extra tests have completed for this IP."""
        # TCP/UDP is always tested for found servers
        if ip not in self.tcp_udp_results:
            return False
        if self.security_test_enabled and ip not in self.security_results:
            return False
        if self.isp_info_enabled and ip not in self.isp_results:
            return False
        proto = self.protocol_results.get(ip, {})
        if self.ipv6_test_enabled and "ipv6" not in proto:
            return False
        if ip not in self.resolve_results:
            return False
        if self.edns0_test_enabled and "edns0" not in proto:
            return False
        if self.test_slipstream and self.proxy_results.get(ip) in ("Pending", "Testing"):
            return False
        return True

    def _periodic_sort_refresh(self) -> None:
        """Periodically rebuild tables to maintain sort order during active scan."""
        if self.found_servers and not self.is_paused:
            self.table_needs_rebuild = True
            self._rebuild_table()

    def _format_time(self, response_time: float) -> str:
        """Format response time with color."""
        ms = response_time * 1000
        if ms < 100:
            return f"[green]{ms:.0f}ms[/green]"
        elif ms < 300:
            return f"[yellow]{ms:.0f}ms[/yellow]"
        return f"[red]{ms:.0f}ms[/red]"

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

                # Update pass/fail counters and stats
                if result == "Success":
                    self._passed_count += 1
                elif result == "Failed":
                    self._failed_count += 1
                try:
                    stats = self._stats_widget
                    if stats is not None:
                        stats.passed = self._passed_count
                        stats.failed = self._failed_count
                except Exception as e:
                    logger.debug(f"Could not update stats after proxy test: {e}")

                if result == "Success":
                    self._log(f"[green]✓ Proxy test PASSED: {dns_ip}[/green]")
                    # Play bell sound if enabled
                    if self.bell_sound_enabled:
                        self._play_bell_sound()
                else:
                    self._log(f"[red]✗ Proxy test FAILED: {dns_ip}[/red]")
                    self.table_needs_rebuild = True  # Will rebuild on pause/completion

                self._update_table_row(dns_ip)  # Update UI with final result

            finally:
                # Return port to pool
                self.available_ports.append(port)


    async def _test_slipstream_proxy(self, dns_ip: str, port: int) -> str:
        """Test DNS server using slipstream proxy on a specific port.

        Args:
            dns_ip: The DNS IP to test
            port: The port to use for slipstream

        Returns:
            "Success" if proxy works, "Failed" otherwise
        """
        process = None
        self._log(f"[dim]Starting proxy test for {dns_ip} on port {port}…[/dim]")
        try:
            # Build slipstream command with dynamic port using the manager
            cmd = self.slipstream_manager.get_run_command(
                dns_ip, port, self.slipstream_domain
            )

            logger.info(f"[{dns_ip}] Starting slipstream on port {port}")
            logger.debug(f"[{dns_ip}] Command: {' '.join(cmd)}")

            # asyncio.create_subprocess_exec is NOT supported on Windows with
            # WindowsSelectorEventLoopPolicy (required by aiodns).  Run the
            # blocking Popen + stdout-read in a thread instead.
            process, connection_ready, output_lines = await asyncio.to_thread(
                _run_slipstream_sync, cmd, 15.0
            )

            logger.debug(f"[{dns_ip}] Slipstream thread returned, PID={process.pid}, "
                         f"connection_ready={connection_ready}, lines={len(output_lines)}")

            # Surface output lines to TUI log and file logger
            for line in output_lines:
                logger.debug(f"[{dns_ip}] Slipstream: {line}")
                if "Listening on TCP port" in line:
                    self._log(f"[dim]{dns_ip}: {markup_escape(line)}[/dim]")
                elif "WARN" in line or "ERR" in line:
                    self._log(f"[yellow]{dns_ip}: {markup_escape(line)}[/yellow]")

            # Track process for cleanup on quit
            self.slipstream_processes.append(process)

            if not connection_ready:
                if not output_lines:
                    logger.warning(f"[{dns_ip}] Slipstream produced no output")
                    self._log(f"[red]{dns_ip}: slipstream produced no output (crashed?)[/red]")
                else:
                    logger.warning(f"[{dns_ip}] Slipstream connection timeout after 15s")
                    self._log(
                        f"[yellow]{dns_ip}: No tunnel established via this DNS (15s timeout)[/yellow]"
                    )
                return "Failed"

            logger.info(f"[{dns_ip}] Connection ready detected on port {port}")
            self._log(f"[cyan]{dns_ip}: Connection ready on port {port}[/cyan]")

            # Give slipstream a moment to fully initialize the proxy listener
            # This prevents race conditions where "Connection ready" is printed
            # but the proxy isn't quite ready to accept connections yet
            logger.debug(f"[{dns_ip}] Waiting 2.5s for proxy to fully initialize")
            await asyncio.sleep(2.5)

            test_success = False

            # Build SOCKS5 URL too (for independent parallel attempt)
            if self.proxy_auth_enabled and self.proxy_username:
                from urllib.parse import quote
                encoded_user = quote(self.proxy_username, safe="")
                encoded_pass = quote(self.proxy_password, safe="")
                proxy_url = f"http://{encoded_user}:{encoded_pass}@127.0.0.1:{port}"
                proxy_url_log = f"http://{self.proxy_username}:****@127.0.0.1:{port}"
                socks5_url = f"socks5://{encoded_user}:{encoded_pass}@127.0.0.1:{port}"
                socks5_url_log = f"socks5://{self.proxy_username}:****@127.0.0.1:{port}"
            else:
                proxy_url = f"http://127.0.0.1:{port}"
                proxy_url_log = proxy_url
                socks5_url = f"socks5://127.0.0.1:{port}"
                socks5_url_log = socks5_url

            # Use HTTPS (CONNECT tunnel) — slipstream is a tunnel proxy, not a plain-HTTP forwarder.
            # CONNECT is universally supported; plain HTTP forwarding often isn't.
            TEST_URL = "https://www.google.com"

            # Try HTTP proxy (via CONNECT tunnel)
            logger.info(f"[{dns_ip}] Testing HTTP proxy (CONNECT) at {proxy_url_log}")
            try:
                async with httpx.AsyncClient(
                    proxy=proxy_url,
                    timeout=15.0,
                    follow_redirects=True,
                    verify=False,
                ) as client:
                    start_time = time.time()
                    response = await client.get(TEST_URL)
                    elapsed = time.time() - start_time
                    logger.debug(f"[{dns_ip}] HTTP proxy status={response.status_code} in {elapsed:.2f}s")
                    if response.status_code in (200, 301, 302, 307, 308):
                        test_success = True
                        logger.info(f"[{dns_ip}] HTTP proxy test PASSED (status {response.status_code}, {elapsed:.2f}s)")
                        self._log(f"[green]{dns_ip}: HTTP proxy test passed (status {response.status_code})[/green]")
                    else:
                        logger.warning(f"[{dns_ip}] HTTP proxy unexpected status: {response.status_code}")
            except Exception as http_err:
                logger.warning(f"[{dns_ip}] HTTP proxy test failed: {type(http_err).__name__}: {http_err}")

            # Try SOCKS5 proxy independently (not just as fallback)
            if not test_success:
                logger.info(f"[{dns_ip}] Testing SOCKS5 proxy at {socks5_url_log}")
                try:
                    async with httpx.AsyncClient(
                        proxy=socks5_url,
                        timeout=15.0,
                        follow_redirects=True,
                        verify=False,
                    ) as client:
                        start_time = time.time()
                        response = await client.get(TEST_URL)
                        elapsed = time.time() - start_time
                        logger.debug(f"[{dns_ip}] SOCKS5 proxy status={response.status_code} in {elapsed:.2f}s")
                        if response.status_code in (200, 301, 302, 307, 308):
                            test_success = True
                            logger.info(f"[{dns_ip}] SOCKS5 proxy test PASSED (status {response.status_code}, {elapsed:.2f}s)")
                            self._log(f"[green]{dns_ip}: SOCKS5 proxy test passed (status {response.status_code})[/green]")
                        else:
                            logger.warning(f"[{dns_ip}] SOCKS5 proxy unexpected status: {response.status_code}")
                except Exception as socks_err:
                    logger.error(f"[{dns_ip}] SOCKS5 proxy test failed: {type(socks_err).__name__}: {socks_err}")
                    self._log(f"[red]{dns_ip}: Both HTTP and SOCKS5 proxy tests failed[/red]")

            final_result = "Success" if test_success else "Failed"
            logger.info(f"[{dns_ip}] Final result: {final_result}")
            return final_result

        except Exception as e:
            logger.error(
                f"[{dns_ip}] Slipstream error: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            self._log(f"[red]Slipstream error for {dns_ip}: {type(e).__name__}: {markup_escape(str(e))}[/red]")
            return "Failed"
        finally:
            # Always kill the slipstream process
            if process:
                try:
                    process.kill()
                    await asyncio.to_thread(process.wait)
                    # Remove from tracking list
                    if process in self.slipstream_processes:
                        self.slipstream_processes.remove(process)
                except (ProcessLookupError, OSError) as e:
                    logger.debug(f"Process cleanup for {dns_ip}: {e}")

    # ── Extra Test Methods ───────────────────────────────────────────────

    def _queue_extra_tests(self, ip: str) -> None:
        """Queue enabled extra tests for a found DNS server (rate-limited to 5 concurrent)."""
        async def _run_extras(dns_ip: str) -> None:
            # Use pre-initialized semaphore (set at scan start)
            async with self.extra_test_semaphore:
                tasks: list[asyncio.Task] = []
                # Always test TCP/UDP support
                tasks.append(asyncio.create_task(self._test_tcp_udp_support(dns_ip)))

                if self.security_test_enabled:
                    tasks.append(asyncio.create_task(self._test_security(dns_ip)))
                if self.ipv6_test_enabled:
                    tasks.append(asyncio.create_task(self._test_ipv6(dns_ip)))
                tasks.append(asyncio.create_task(self._test_resolve(dns_ip)))
                if self.edns0_test_enabled:
                    tasks.append(asyncio.create_task(self._test_edns0(dns_ip)))
                if self.isp_info_enabled:
                    tasks.append(asyncio.create_task(self._test_isp_info(dns_ip)))
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                # Update table row after all extras finish
                self._update_table_row(dns_ip)

        task = asyncio.create_task(_run_extras(ip))
        self.extra_test_tasks.add(task)
        task.add_done_callback(self.extra_test_tasks.discard)

    def _get_extra_summary(self, ip: str) -> str:
        """Build a compact summary string for the Extra column."""
        parts: list[str] = []
        sec = self.security_results.get(ip)
        if sec:
            flags = []
            if sec.get("dnssec"):
                flags.append("[green]DNSSEC[/green]")
            if sec.get("hijacked"):
                flags.append("[red]Hijack[/red]")
            if sec.get("open_resolver"):
                flags.append("[yellow]Open[/yellow]")
            if flags:
                parts.extend(flags)

        proto = self.protocol_results.get(ip, {})
        if proto.get("ipv6"):
            parts.append("[cyan]v6[/cyan]")
        if proto.get("edns0"):
            parts.append("[cyan]EDNS0[/cyan]")

        isp = self.isp_results.get(ip)
        if isp:
            org = isp.get("org", "")
            if org:
                parts.append(f"[dim]{org}[/dim]")

        if not parts:
            return "[dim]…[/dim]"
        return " ".join(parts)
    
    def _get_security_column(self, ip: str) -> str:
        """Get security test results for table column."""
        sec = self.security_results.get(ip)
        if not sec:
            return "[dim]…[/dim]"
        
        flags = []
        if sec.get("dnssec"):
            flags.append("[green]DNSSEC[/green]")
        if sec.get("open_resolver"):
            flags.append("[yellow]Open[/yellow]")
        if sec.get("hijacked"):
            flags.append("[red]Hijack[/red]")
        
        if not flags:
            return "[green]Secure[/green]"
        
        # Format: "DNSSEC  Open" with spacing between items
        return "  ".join(flags)
    
    def _get_ipv6_column(self, ip: str) -> str:
        """Get IPv6 test result for table column."""
        proto = self.protocol_results.get(ip, {})
        if ip not in self.protocol_results:
            return "[dim]…[/dim]"
        return "[green]Yes[/green]" if proto.get("ipv6") else "[red]No[/red]"
    
    def _get_resolve_column(self, ip: str) -> str:
        """Get resolved IP result for table column."""
        if ip not in self.resolve_results:
            return "[dim]…[/dim]"
        result = self.resolve_results[ip]
        if result == "-":
            return "[dim]-[/dim]"
        return f"[cyan]{result}[/cyan]"

    def _get_edns0_column(self, ip: str) -> str:
        """Get EDNS0 test result for table column."""
        proto = self.protocol_results.get(ip, {})
        if ip not in self.protocol_results:
            return "[dim]…[/dim]"
        return "[green]Yes[/green]" if proto.get("edns0") else "[red]No[/red]"
    
    def _get_isp_column(self, ip: str) -> str:
        """Get ISP info for table column."""
        if ip not in self.isp_results:
            return "[dim]…[/dim]"  # Not yet tested
        isp = self.isp_results[ip]
        org = isp.get("org", "-") or "-"
        if org == "-":
            return "[dim]-[/dim]"
        return f"[cyan]{org}[/cyan]"
    
    def _get_tcp_udp_column(self, ip: str) -> str:
        """Get TCP/UDP support for table column."""
        result = self.tcp_udp_results.get(ip)
        if not result:
            return "[dim]Testing…[/dim]"
        if result == "TCP/UDP":
            return "[green]TCP/UDP[/green]"
        elif result == "TCP only":
            return "[yellow]TCP only[/yellow]"
        elif result == "UDP only":
            return "[cyan]UDP only[/cyan]"
        return "[dim]Unknown[/dim]"

    async def _test_security(self, ip: str, resolver: "aiodns.DNSResolver | None" = None) -> None:
        """Test DNS security: DNSSEC validation, hijacking, open resolver."""
        result: dict = {"dnssec": False, "hijacked": False, "open_resolver": False}
        try:
            resolver = resolver or aiodns.DNSResolver(nameservers=[ip], timeout=3.0, tries=1)
            nxdomain_test = f"nxdomain-{random.randbytes(6).hex()}.example.invalid"

            # Run DNSSEC and hijack checks in parallel to reduce total wait time
            async def _check_dnssec() -> bool:
                try:
                    return await asyncio.wait_for(self._check_dnssec_raw(ip), timeout=4.0)
                except Exception:
                    return False

            async def _check_hijack() -> bool:
                try:
                    answer = await resolver.query(nxdomain_test, "A")
                    return bool(answer)
                except aiodns.error.DNSError:
                    return False
                except Exception:
                    return False

            dnssec_ok, hijacked = await asyncio.gather(
                _check_dnssec(),
                _check_hijack(),
            )
            result["dnssec"] = dnssec_ok
            result["hijacked"] = hijacked
            # Open resolver: it answered our queries = it's open to us
            result["open_resolver"] = True

        except Exception as e:
            logger.debug(f"Security test error for {ip}: {e}")

        self.security_results[ip] = result
        if result["dnssec"]:
            self._log(f"[cyan]🔒 {ip}: DNSSEC supported[/cyan]")
        if result["hijacked"]:
            self._log(f"[red]⚠ {ip}: DNS hijacking detected[/red]")

    async def _check_dnssec_raw(self, ip: str) -> bool:
        """Send a raw DNS query with DO (DNSSEC OK) flag to check DNSSEC support."""
        # Build a minimal DNS query for example.com A record with EDNS0 DO flag
        txn_id = secrets.token_bytes(2)
        # Flags: RD=1 (recursion desired)
        flags = b"\x01\x00"
        # QDCOUNT=1, ANCOUNT=0, NSCOUNT=0, ARCOUNT=1 (for OPT)
        counts = b"\x00\x01\x00\x00\x00\x00\x00\x01"
        # Question: example.com A IN
        qname = b"\x07example\x03com\x00"
        qtype = b"\x00\x01"  # A
        qclass = b"\x00\x01"  # IN
        # OPT RR (EDNS0) with DO flag
        # NAME=0x00 (root), TYPE=OPT(41), UDP_SIZE=4096, RCODE=0, VERSION=0, FLAGS=DO(0x8000), RDLEN=0
        opt_rr = b"\x00\x00\x29\x10\x00\x00\x00\x80\x00\x00\x00"

        query = txn_id + flags + counts + qname + qtype + qclass + opt_rr

        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        sock.settimeout(0)

        try:
            await loop.sock_sendto(sock, query, (ip, 53))
            data = await asyncio.wait_for(loop.sock_recv(sock, 4096), timeout=3.0)

            if len(data) < 12:
                return False

            # Check AD (Authenticated Data) flag in response – bit 5 of byte 3
            resp_flags = data[2:4]
            ad_flag = (resp_flags[1] >> 5) & 1
            # Also check if response contains OPT record with DO flag
            # Simple heuristic: if AD flag is set, DNSSEC is validated
            if ad_flag:
                return True

            # Also look for OPT record in additional section with DO flag
            # Check ARCOUNT > 0 and scan for TYPE=41
            arcount = struct.unpack("!H", data[10:12])[0]
            if arcount > 0:
                # Simplified: search for OPT type (0x0029) in response
                if b"\x00\x29" in data[12:]:
                    return True

            return False
        except Exception:
            return False
        finally:
            sock.close()

    async def _test_ipv6(self, ip: str, resolver: "aiodns.DNSResolver | None" = None) -> None:
        """Test if the DNS server handles AAAA (IPv6) queries."""
        result = False
        try:
            resolver = resolver or aiodns.DNSResolver(nameservers=[ip], timeout=3.0, tries=1)
            try:
                answer = await resolver.query("google.com", "AAAA")
                if answer:
                    result = True
            except aiodns.error.DNSError as e:
                # NXDOMAIN / NODATA still means the server handles AAAA queries
                code = e.args[0] if e.args else 0
                if code in (1, 3, 4):
                    result = True
        except Exception as e:
            logger.debug(f"IPv6 test error for {ip}: {e}")

        self.protocol_results.setdefault(ip, {})["ipv6"] = result
        if result:
            self._log(f"[cyan]{ip}: IPv6 (AAAA) supported[/cyan]")

    async def _test_resolve(self, ip: str, resolver: "aiodns.DNSResolver | None" = None) -> None:
        """Resolve the scan domain via this DNS server and record the resulting IP."""
        # For non-A record scans (NS, AAAA, etc.) the user's domain may not have
        # accessible A records on the servers being tested, so fall back to a
        # universally-resolvable domain.  For A-record scans we use the user's own
        # domain so the column reflects that specific lookup.
        if self.dns_type == "A":
            resolve_domain = self.domain.strip() or "google.com"
        else:
            resolve_domain = "google.com"
        try:
            resolver = resolver or aiodns.DNSResolver(nameservers=[ip], timeout=3.0, tries=1)
            answer = await resolver.query(resolve_domain, "A")
            if answer:
                ips = [r.host for r in answer]
                resolved = ips[0] if len(ips) == 1 else ", ".join(ips[:2])
                self.resolve_results[ip] = resolved
                self._log(f"[cyan]{ip}: {resolve_domain} → {resolved}[/cyan]")
            else:
                self.resolve_results[ip] = "-"
        except Exception as e:
            logger.debug(f"Resolve test error for {ip}: {e}")
            self.resolve_results[ip] = "-"

    async def _test_edns0(self, ip: str) -> None:
        """Test EDNS0 support by sending OPT record and checking response."""
        result = False
        try:
            # Build DNS query with EDNS0 OPT record
            txn_id = secrets.token_bytes(2)
            flags = b"\x01\x00"  # RD=1
            # QDCOUNT=1, ANCOUNT=0, NSCOUNT=0, ARCOUNT=1 (OPT)
            counts = b"\x00\x01\x00\x00\x00\x00\x00\x01"
            qname = b"\x07example\x03com\x00"
            qtype = b"\x00\x01"  # A
            qclass = b"\x00\x01"  # IN
            # OPT RR: NAME=root, TYPE=OPT(41), UDP=4096, RCODE_EXT=0, VERSION=0, FLAGS=0, RDLEN=0
            opt_rr = b"\x00\x00\x29\x10\x00\x00\x00\x00\x00\x00\x00"

            query = txn_id + flags + counts + qname + qtype + qclass + opt_rr

            loop = asyncio.get_event_loop()
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)

            try:
                await loop.sock_sendto(sock, query, (ip, 53))
                data = await asyncio.wait_for(
                    loop.sock_recv(sock, 4096), timeout=3.0
                )

                if len(data) >= 12:
                    # Check ARCOUNT in response
                    arcount = struct.unpack("!H", data[10:12])[0]
                    if arcount > 0:
                        # Look for OPT record type (41 = 0x0029) in response
                        if b"\x00\x29" in data[12:]:
                            result = True
            finally:
                sock.close()

        except Exception as e:
            logger.debug(f"EDNS0 test error for {ip}: {e}")

        self.protocol_results.setdefault(ip, {})["edns0"] = result
        if result:
            self._log(f"[cyan]{ip}: EDNS0 supported[/cyan]")

    async def _test_isp_info(self, ip: str) -> None:
        """Look up ISP/ASN/org information for the DNS server IP."""
        info: dict = {"org": "-", "isp": "-", "asn": "", "country": ""}
        try:
            # Rate-limit ip-api.com: serialize access but release lock before sleeping
            async with self._isp_rate_lock:
                now = time.monotonic()
                wait = 1.4 - (now - self._isp_last_request)  # ~43 req/min
                self._isp_last_request = time.monotonic() + max(wait, 0)
            # Sleep OUTSIDE the lock so other coroutines aren't blocked waiting
            if wait > 0:
                await asyncio.sleep(wait)

            # Use ip-api.com (free, no key required, 45 req/min)
            url = f"http://ip-api.com/json/{ip}?fields=as,org,isp,country,countryCode"
            client = getattr(self, "_http_client", None)
            owned = client is None
            if owned:
                client = httpx.AsyncClient(timeout=5.0)
            try:
                for attempt in range(2):
                    resp = await client.get(url)
                    if resp.status_code == 429:
                        # Back off and retry once
                        logger.warning(f"ip-api.com rate-limited for {ip}, retrying after 60s")
                        await asyncio.sleep(60.0)
                        continue
                    if resp.status_code == 200:
                        data = resp.json()
                        info = {
                            "org": data.get("org", "") or "-",
                            "isp": data.get("isp", "") or "-",
                            "asn": data.get("as", ""),
                            "country": data.get("countryCode", ""),
                        }
                    break
            finally:
                if owned:
                    await client.aclose()
        except Exception as e:
            logger.debug(f"ISP info error for {ip}: {e}")

        self.isp_results[ip] = info
        if info.get("org"):
            self._log(
                f"[dim]{ip}: {info.get('org', '')} ({info.get('country', '')})[/dim]"
            )

    async def _test_tcp_udp_support(self, ip: str) -> None:
        """Test if DNS server supports TCP, UDP, or both protocols."""
        tcp_works = False
        udp_works = False
        
        # UDP was already confirmed during main scan
        udp_works = True
        
        # Test TCP (port 53)
        try:
            # Build DNS query
            txn_id = secrets.token_bytes(2)
            flags = b"\x01\x00"  # RD=1
            counts = b"\x00\x01\x00\x00\x00\x00\x00\x00"  # QDCOUNT=1
            qname = b"\x06google\x03com\x00"
            qtype = b"\x00\x01"  # A
            qclass = b"\x00\x01"  # IN
            dns_msg = txn_id + flags + counts + qname + qtype + qclass
            
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, 53), timeout=2.0
            )
            try:
                # Send length-prefixed DNS query
                length_prefix = struct.pack("!H", len(dns_msg))
                writer.write(length_prefix + dns_msg)
                await writer.drain()
                
                # Read response
                resp_len_bytes = await asyncio.wait_for(
                    reader.readexactly(2), timeout=2.0
                )
                resp_len = struct.unpack("!H", resp_len_bytes)[0]
                
                if resp_len > 0:
                    resp_data = await asyncio.wait_for(
                        reader.readexactly(resp_len), timeout=2.0
                    )
                    # Valid DNS response
                    if len(resp_data) >= 12 and resp_data[:2] == txn_id:
                        tcp_works = True
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"TCP test error for {ip}: {e}")
        
        # Determine result
        if tcp_works and udp_works:
            result = "TCP/UDP"
        elif tcp_works:
            result = "TCP only"
        elif udp_works:
            result = "UDP only"
        else:
            result = "None"
        
        self.tcp_udp_results[ip] = result
        logger.debug(f"{ip}: Protocol support = {result}")

    def _shuffle_remaining_ips(self) -> None:
        """Legacy shuffle method - now signals instant reshuffle."""
        if self.shuffle_signal:
            self.shuffle_signal.set()
            self._log("[cyan]Shuffle signal sent - reshuffling stream...[/cyan]")

    async def _shuffle_remaining_ips_async(self) -> None:
        """Async shuffle - signals instant reshuffle via shuffle_signal."""
        if self.shuffle_signal:
            self.shuffle_signal.set()
            self._log("[cyan]Shuffle signal sent - reshuffling stream...[/cyan]")

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
        """Handle double-click on DNS row to copy IP and show extra details."""
        try:
            table = event.data_table
            row_key = event.row_key

            # Check if row_key exists in table
            if row_key not in table._row_locations:
                return

            row = table.get_row(row_key)

            if row and len(row) > 0:
                # Extract IP - remove any Rich markup
                ip_raw = str(row[0])
                # Strip Rich tags if present
                ip = re.sub(r"\[.*?\]", "", ip_raw).strip()

                if ip:
                    _copy_to_clipboard(ip)
                    self.notify(f"{ip} copied!", severity="information", timeout=2)

                    # Show extra test details in log if available
                    details: list[str] = []
                    sec = self.security_results.get(ip)
                    if sec:
                        details.append(
                            f"  Security: DNSSEC={'Yes' if sec.get('dnssec') else 'No'}, "
                            f"Hijack={'Yes' if sec.get('hijacked') else 'No'}, "
                            f"OpenResolver={'Yes' if sec.get('open_resolver') else 'No'}"
                        )
                    proto = self.protocol_results.get(ip, {})
                    if proto:
                        proto_items = [
                            f"{k}={'Yes' if v else 'No'}" for k, v in proto.items()
                        ]
                        details.append(f"  Protocols: {', '.join(proto_items)}")
                    isp = self.isp_results.get(ip)
                    if isp and isp.get("org"):
                        details.append(
                            f"  ISP: {isp.get('org', '')} | AS: {isp.get('asn', '')} | "
                            f"Country: {isp.get('country', '')}"
                        )
                    if details:
                        self._log(f"[cyan]── Details for {ip} ──[/cyan]")
                        for line in details:
                            self._log(f"[dim]{line}[/dim]")
        except Exception as e:
            logger.debug(f"Row selection error: {e}")

    def _build_csv_headers_and_rows(self, servers_to_save: dict) -> tuple[list[str], list[list[str]]]:
        """Build CSV headers and row data based on enabled tests."""
        headers = ["DNS", "Ping (ms)"]
        if self.test_slipstream:
            headers.append("Proxy Test")
        headers.append("IPv4/IPv6")
        # TCP/UDP is always tested
        headers.append("TCP/UDP")
        if self.security_test_enabled:
            headers.append("Security")
        if self.edns0_test_enabled:
            headers.append("EDNS0")
        headers.append("Resolved IP")
        headers.append("ISP")

        # Sort: 1) proxy Success first (if enabled), 2) DNSSEC, 3) ping ascending
        def _csv_sort_key(item):
            ip, t = item
            proxy_rank = 0 if (self.test_slipstream and self.proxy_results.get(ip) == "Success") else (1 if self.test_slipstream else 0)
            dnssec_rank = 0 if self.security_results.get(ip, {}).get("dnssec") else 1
            return (proxy_rank, dnssec_rank, t)
        sorted_servers = sorted(servers_to_save.items(), key=_csv_sort_key)

        rows: list[list[str]] = []
        for ip, resp_time in sorted_servers:
            row = [ip, f"{resp_time * 1000:.0f}"]
            if self.test_slipstream:
                row.append(self.proxy_results.get(ip, "N/A"))
            # IPv4/IPv6
            proto = self.protocol_results.get(ip, {})
            if proto.get("ipv6"):
                row.append("IPv4/IPv6")
            elif ip in self.protocol_results:
                row.append("IPv4")
            else:
                row.append("")
            # TCP/UDP
            row.append(self.tcp_udp_results.get(ip, ""))
            # Security
            if self.security_test_enabled:
                sec = self.security_results.get(ip, {})
                if ip in self.security_results:
                    flags = []
                    if sec.get("dnssec"):
                        flags.append("DNSSEC")
                    if sec.get("open_resolver"):
                        flags.append("Open Resolver")
                    if sec.get("hijacked"):
                        flags.append("Hijacked")
                    row.append(", ".join(flags) if flags else "Secure")
                else:
                    row.append("")
            # EDNS0
            if self.edns0_test_enabled:
                if ip in self.protocol_results and "edns0" in self.protocol_results[ip]:
                    row.append("Yes" if proto.get("edns0") else "No")
                else:
                    row.append("")
            # Resolved IP
            row.append(self.resolve_results.get(ip, ""))
            # ISP (rightmost column)
            isp = self.isp_results.get(ip, {})
            org = isp.get("org", "") or ""
            row.append(org if org != "-" else "")
            rows.append(row)
        return headers, rows

    def _auto_save_results(self) -> None:
        """Auto-save results as CSV at end of scan.

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

        csv_file = output_dir / f"{timestamp}.csv"
        headers, rows = self._build_csv_headers_and_rows(servers_to_save)

        try:
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)

            self._log(f"[green]✓ Results auto-saved to: {csv_file}[/green]")
            logger.info(f"Results auto-saved to {csv_file}")
        except (OSError, IOError, PermissionError) as e:
            self._log(f"[red]Failed to save results: {e}[/red]")
            logger.error(f"Failed to auto-save results to {csv_file}: {e}")

    def action_save_results(self) -> None:
        """Save results as CSV.

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

        csv_file = output_dir / f"scan_{timestamp}.csv"
        headers, rows = self._build_csv_headers_and_rows(servers_to_save)

        try:
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)

            self.notify(
                f"Saved {len(rows)} servers: {csv_file.name}",
                severity="information",
            )
            logger.info(f"Results saved to {csv_file}")
        except (OSError, IOError, PermissionError) as e:
            self.notify(f"Failed to save results: {e}", severity="error")
            logger.error(f"Failed to save results to {csv_file}: {e}")


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
