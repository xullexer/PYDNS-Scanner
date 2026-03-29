"""SlipNetManager — cross-platform download & execution of the SlipNet CLI binary."""

from __future__ import annotations

import asyncio
import base64
import functools
import stat
from pathlib import Path
from typing import Optional

import httpx

from .constants import logger

# Pinned to v2.4.1 — update this when a new release is needed.
_SLIPNET_VERSION = "v2.4.1"
_RELEASE_BASE = f"https://github.com/anonvector/SlipNet/releases/download/{_SLIPNET_VERSION}"


class SlipNetManager:
    """Manages SlipNet CLI client download and execution across platforms."""

    DOWNLOAD_URLS = {
        "Darwin-arm64": f"{_RELEASE_BASE}/slipnet-darwin-arm64",
        "Darwin-x86_64": f"{_RELEASE_BASE}/slipnet-darwin-amd64",
        "Windows": f"{_RELEASE_BASE}/slipnet-windows-amd64.exe",
        "Linux-x86_64": f"{_RELEASE_BASE}/slipnet-linux-amd64",
        "Linux-arm64": f"{_RELEASE_BASE}/slipnet-linux-arm64",
        "Android": f"{_RELEASE_BASE}/slipnet-linux-arm64",
    }

    FILENAMES = {
        "Darwin-arm64": "slipnet-darwin-arm64",
        "Darwin-x86_64": "slipnet-darwin-amd64",
        "Windows": "slipnet-windows-amd64.exe",
        "Linux-x86_64": "slipnet-linux-amd64",
        "Linux-arm64": "slipnet-linux-arm64",
        "Android": "slipnet-linux-arm64",
    }

    ALT_FILENAMES = {
        "Windows": ["slipnet.exe", "slipnet-windows-amd64.exe"],
        "Darwin-arm64": ["slipnet", "slipnet-darwin-arm64"],
        "Darwin-x86_64": ["slipnet", "slipnet-darwin-amd64"],
        "Linux-x86_64": ["slipnet", "slipnet-linux-amd64"],
        "Linux-arm64": ["slipnet", "slipnet-linux-arm64"],
        "Android": ["slipnet", "slipnet-linux-arm64"],
    }

    PLATFORM_DIRS = {
        "Darwin": "mac",
        "Windows": "windows",
        "Linux": "linux",
        "Android": "android",
    }

    def __init__(self):
        import platform as _platform
        import sys as _sys

        if getattr(_sys, "frozen", False) and hasattr(_sys, "_MEIPASS"):
            self.base_dir = Path(_sys._MEIPASS) / "slipnet-client"
        else:
            self.base_dir = Path(__file__).resolve().parent.parent / "slipnet-client"
        self.system = self._detect_system()
        self.machine = _platform.machine()
        self._cached_executable_path: Optional[Path] = None

        if self.machine in ("x86_64", "AMD64", "i386", "i686", "x86"):
            self.machine = "x86_64"
        elif self.machine in ("aarch64", "arm64", "armv8l"):
            self.machine = "arm64"
        elif self.machine.startswith("arm"):
            self.machine = "arm64"

    # ── Platform helpers ────────────────────────────────────────────────

    @staticmethod
    def _detect_system() -> str:
        import os
        import platform as _platform

        if os.environ.get("ANDROID_ROOT") or os.environ.get("ANDROID_DATA"):
            return "Android"
        if os.environ.get("TERMUX_VERSION") or Path("/data/data/com.termux").exists():
            return "Android"
        if Path("/system/build.prop").exists():
            return "Android"
        return _platform.system()

    @functools.lru_cache(maxsize=1)
    def get_platform_key(self) -> str:
        if self.system == "Windows":
            return "Windows"
        elif self.system == "Android":
            return "Android"
        elif self.system == "Linux":
            return f"Linux-{self.machine}"
        elif self.system == "Darwin":
            return f"Darwin-{self.machine}"
        else:
            raise RuntimeError(f"Unsupported platform: {self.system}")

    @functools.lru_cache(maxsize=1)
    def get_platform_dir(self) -> Path:
        dir_name = self.PLATFORM_DIRS.get(self.system, self.system.lower())
        return self.base_dir / dir_name

    # ── Executable path / install checks ────────────────────────────────

    def get_executable_path(self) -> Path:
        if self._cached_executable_path and self._cached_executable_path.exists():
            return self._cached_executable_path

        platform_key = self.get_platform_key()
        platform_dir = self.get_platform_dir()

        for filename in self.ALT_FILENAMES.get(platform_key, []):
            exe_path = platform_dir / filename
            if exe_path.exists():
                self._cached_executable_path = exe_path
                return exe_path

        filename = self.FILENAMES.get(platform_key)
        if not filename:
            raise RuntimeError(f"Unsupported platform: {self.system} {self.machine}")
        return platform_dir / filename

    def is_installed(self) -> bool:
        platform_key = self.get_platform_key()
        platform_dir = self.get_platform_dir()

        for filename in self.ALT_FILENAMES.get(platform_key, []):
            if (platform_dir / filename).exists():
                return True

        primary_filename = self.FILENAMES.get(platform_key)
        if primary_filename and (platform_dir / primary_filename).exists():
            return True
        return False

    def ensure_executable(self) -> bool:
        try:
            exe_path = self.get_executable_path()
            if not exe_path.exists():
                return False
            if self.system in ("Linux", "Darwin"):
                current_mode = exe_path.stat().st_mode
                exe_path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                logger.info(f"Set executable permissions on {exe_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to set executable permissions: {e}")
            return False

    # ── Download helpers ────────────────────────────────────────────────

    async def ensure_installed(self, log_callback=None) -> tuple[bool, str]:
        def log(msg):
            if log_callback:
                log_callback(msg)
            logger.info(msg)

        if self.is_installed():
            log("[green]✓ SlipNet client found[/green]")
            return (True, "Already installed")

        log("[cyan]SlipNet client not found, downloading...[/cyan]")
        success = await self.download()

        if success:
            log("[green]✓ SlipNet client downloaded successfully[/green]")
            return (True, "Downloaded successfully")
        else:
            log("[red]✗ Failed to download SlipNet client[/red]")
            return (False, "Download failed")

    def get_download_url(self) -> Optional[str]:
        try:
            platform_key = self.get_platform_key()
            return self.DOWNLOAD_URLS.get(platform_key)
        except RuntimeError:
            return None

    async def download(
        self, progress_callback=None, max_retries: int = 5, retry_delay: float = 2.0
    ) -> bool:
        url = self.get_download_url()
        if not url:
            return False

        exe_path = self.get_executable_path()
        temp_path = exe_path.with_suffix(exe_path.suffix + ".partial")
        platform_dir = self.get_platform_dir()
        platform_dir.mkdir(parents=True, exist_ok=True)

        for attempt in range(1, max_retries + 1):
            try:
                downloaded = 0
                if temp_path.exists():
                    downloaded = temp_path.stat().st_size

                headers = {}
                if downloaded > 0:
                    headers["Range"] = f"bytes={downloaded}-"
                    if progress_callback:
                        progress_callback(
                            downloaded, 0,
                            f"Resuming from {downloaded / (1024 * 1024):.1f} MB...",
                        )

                async with httpx.AsyncClient(
                    follow_redirects=True,
                    timeout=httpx.Timeout(30.0, read=60.0, connect=30.0),
                    verify=True,
                    limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                ) as client:
                    async with client.stream("GET", url, headers=headers) as response:
                        if response.status_code == 206:
                            content_range = response.headers.get("content-range", "")
                            if "/" in content_range:
                                total = int(content_range.split("/")[1])
                            else:
                                total = downloaded + int(
                                    response.headers.get("content-length", 0)
                                )
                            mode = "ab"
                        elif response.status_code == 200:
                            total = int(response.headers.get("content-length", 0))
                            downloaded = 0
                            mode = "wb"
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
                                    progress_callback(downloaded, total, "Downloading...")

                if temp_path.exists():
                    if exe_path.exists():
                        exe_path.unlink()
                    temp_path.rename(exe_path)

                if self.system in ("Linux", "Darwin"):
                    exe_path.chmod(
                        exe_path.stat().st_mode
                        | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
                    )
                    logger.info(f"Set executable permissions on {exe_path}")

                return True

            except (
                httpx.TimeoutException, httpx.NetworkError,
                httpx.HTTPStatusError, httpx.ConnectError,
            ) as e:
                error_msg = f"{type(e).__name__}"
                if hasattr(e, "__cause__") and e.__cause__:
                    error_msg += f": {str(e.__cause__)}"
                if progress_callback:
                    progress_callback(downloaded, 0, f"Retry {attempt}/{max_retries}: {error_msg}")
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay * attempt)
                    continue
                else:
                    return False
            except Exception as e:
                logger.error(f"Unexpected download error: {e}", exc_info=True)
                if temp_path.exists():
                    temp_path.unlink()
                return False

        return False

    async def download_with_ui(
        self, progress_bar, log_widget, max_retries: int = 5, retry_delay: float = 2.0
    ) -> bool:
        url = self.get_download_url()
        if not url:
            log_widget.write("[red]No download URL available for this platform[/red]")
            return False

        exe_path = self.get_executable_path()
        temp_path = exe_path.with_suffix(exe_path.suffix + ".partial")
        platform_dir = self.get_platform_dir()
        platform_dir.mkdir(parents=True, exist_ok=True)

        last_logged_percent = -1

        for attempt in range(1, max_retries + 1):
            try:
                downloaded = 0
                if temp_path.exists():
                    downloaded = temp_path.stat().st_size

                headers = {}
                if downloaded > 0:
                    headers["Range"] = f"bytes={downloaded}-"
                    log_widget.write(
                        f"[cyan]Resuming from {downloaded / (1024 * 1024):.1f} MB...[/cyan]"
                    )

                async with httpx.AsyncClient(
                    follow_redirects=True,
                    timeout=httpx.Timeout(30.0, read=60.0, connect=30.0),
                    verify=True,
                    limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                ) as client:
                    async with client.stream("GET", url, headers=headers) as response:
                        if response.status_code == 206:
                            content_range = response.headers.get("content-range", "")
                            if "/" in content_range:
                                total = int(content_range.split("/")[1])
                            else:
                                total = downloaded + int(
                                    response.headers.get("content-length", 0)
                                )
                            mode = "ab"
                        elif response.status_code == 200:
                            total = int(response.headers.get("content-length", 0))
                            downloaded = 0
                            mode = "wb"
                        else:
                            response.raise_for_status()
                            continue

                        log_widget.write(f"[cyan]Downloading SlipNet...[/cyan] Total: {total / (1024 * 1024):.1f} MB")

                        with open(temp_path, mode) as f:
                            async for chunk in response.aiter_bytes(chunk_size=32768):
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total > 0:
                                    progress_bar.update_progress(downloaded, total)
                                    current_percent = int((downloaded / total) * 10) * 10
                                    if current_percent > last_logged_percent:
                                        last_logged_percent = current_percent
                                        mb_downloaded = downloaded / (1024 * 1024)
                                        mb_total = total / (1024 * 1024)
                                        log_widget.write(
                                            f"[dim]Progress: {mb_downloaded:.1f}/{mb_total:.1f} MB ({current_percent}%)[/dim]"
                                        )

                if temp_path.exists():
                    if exe_path.exists():
                        exe_path.unlink()
                    temp_path.rename(exe_path)

                if self.system in ("Linux", "Darwin"):
                    exe_path.chmod(
                        exe_path.stat().st_mode
                        | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
                    )
                    log_widget.write("[green]✓ Set executable permissions on SlipNet client[/green]")

                return True

            except (
                httpx.TimeoutException, httpx.NetworkError,
                httpx.HTTPStatusError, httpx.ConnectError,
            ) as e:
                error_msg = f"{type(e).__name__}"
                if hasattr(e, "__cause__") and e.__cause__:
                    error_msg += f": {str(e.__cause__)}"
                log_widget.write(f"[yellow]Retry {attempt}/{max_retries}: {error_msg}[/yellow]")
                if attempt < max_retries:
                    log_widget.write(f"[dim]Waiting {retry_delay * attempt:.0f}s before retry...[/dim]")
                    await asyncio.sleep(retry_delay * attempt)
                    continue
                else:
                    return False
            except Exception as e:
                log_widget.write(f"[red]Unexpected error: {type(e).__name__}: {e}[/red]")
                if temp_path.exists():
                    temp_path.unlink()
                return False

        return False

    # ── Command builder ─────────────────────────────────────────────────

    @staticmethod
    def parse_config(slipnet_url: str) -> dict:
        """Decode a ``slipnet://BASE64...`` URI and return parsed fields.

        The base64 payload is pipe-delimited.  Known field positions:
            0  version/type
            1  name1
            2  name2
            3  domain        (the tunnel domain — used for DNS resolution)
            4  resolver      (e.g. ``8.8.8.8:53:0``)
            8  socks_port
            9  listen_addr
            12 username
            13 password

        Returns a dict with at least ``domain``, ``username``, ``socks_port``,
        ``listen_addr``.  Missing/unparseable fields default to ``""``.
        """
        result: dict = {
            "domain": "",
            "username": "",
            "password": "",
            "socks_port": "",
            "listen_addr": "",
            "resolver": "",
            "raw_fields": [],
        }
        try:
            if not slipnet_url or not slipnet_url.startswith("slipnet://"):
                return result
            b64 = slipnet_url.split("slipnet://", 1)[1]
            # Add padding if needed
            missing_pad = len(b64) % 4
            if missing_pad:
                b64 += "=" * (4 - missing_pad)
            decoded = base64.b64decode(b64).decode("utf-8", "ignore")
            fields = decoded.split("|")
            result["raw_fields"] = fields
            if len(fields) > 3:
                result["domain"] = fields[3]
            if len(fields) > 4:
                result["resolver"] = fields[4]
            if len(fields) > 8:
                result["socks_port"] = fields[8]
            if len(fields) > 9:
                result["listen_addr"] = fields[9]
            if len(fields) > 12:
                result["username"] = fields[12]
            if len(fields) > 13:
                result["password"] = fields[13]
        except Exception as e:
            logger.debug(f"Failed to parse SlipNet config: {e}")
        return result

    def get_run_command(self, dns_ip: str, port: int, slipnet_url: str, query_size: int = 0) -> list:
        """Build command to start SlipNet with a specific DNS server and port.

        Args:
            dns_ip: The DNS server IP to route through.
            port: Local SOCKS5 proxy port.
            slipnet_url: The ``slipnet://BASE64...`` config URI.
            query_size: Max DNS query payload bytes (0 = default/full capacity, min 50).
        """
        exe_path = self.get_executable_path()
        self.ensure_executable()
        cmd = [
            str(exe_path),
            "--dns", dns_ip,
            "--port", str(port),
        ]
        if query_size and query_size >= 50:
            cmd += ["--query-size", str(query_size)]
        cmd.append(slipnet_url)
        return cmd
