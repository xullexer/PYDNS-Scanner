"""SlipstreamManager — cross-platform download & execution of the slipstream proxy binary."""

from __future__ import annotations

import asyncio
import functools
import stat
from pathlib import Path
from typing import Optional

import httpx

from .constants import logger


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

    WINDOWS_DLLS = {
        "libcrypto-3-x64.dll": "https://raw.githubusercontent.com/xullexer/PYDNS-Scanner/main/slipstream-client/windows/libcrypto-3-x64.dll",
        "libssl-3-x64.dll": "https://raw.githubusercontent.com/xullexer/PYDNS-Scanner/main/slipstream-client/windows/libssl-3-x64.dll",
    }

    FILENAMES = {
        "Darwin-arm64": "slipstream-client-darwin-arm64",
        "Darwin-x86_64": "slipstream-client-darwin-amd64",
        "Windows": "slipstream-client-windows-amd64.exe",
        "Linux-x86_64": "slipstream-client-linux-amd64",
        "Linux-arm64": "slipstream-client-linux-arm64",
        "Android": "slipstream-client-linux-arm64",
    }

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
        import os
        import platform as _platform
        import sys as _sys

        # When running as a PyInstaller one-file frozen EXE, data files are
        # extracted to sys._MEIPASS.  Otherwise use the source tree layout.
        if getattr(_sys, "frozen", False) and hasattr(_sys, "_MEIPASS"):
            self.base_dir = Path(_sys._MEIPASS) / "slipstream-client"
        else:
            self.base_dir = Path(__file__).resolve().parent.parent / "slipstream-client"
        self.system = self._detect_system()
        self.machine = _platform.machine()
        self._cached_executable_path: Optional[Path] = None

        # Normalize machine architecture
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
            log("[green]✓ Slipstream client found[/green]")
            return (True, "Already installed")

        log("[cyan]Slipstream client not found, downloading...[/cyan]")
        success = await self.download()

        if success:
            log("[green]✓ Slipstream client downloaded successfully[/green]")
            return (True, "Downloaded successfully")
        else:
            log("[red]✗ Failed to download Slipstream client[/red]")
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

                if self.system == "Windows":
                    await self._download_windows_dlls()

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

    async def _download_windows_dlls(self, log_callback=None) -> bool:
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

                        log_widget.write(f"[cyan]Downloading...[/cyan] Total: {total / (1024 * 1024):.1f} MB")

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
                    log_widget.write("[green]✓ Set executable permissions on slipstream client[/green]")

                if self.system == "Windows":
                    log_widget.write("[cyan]Downloading required Windows DLLs...[/cyan]")
                    await self._download_windows_dlls_with_ui(log_widget)

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

    async def _download_windows_dlls_with_ui(self, log_widget) -> bool:
        if self.system != "Windows":
            return True

        platform_dir = self.get_platform_dir()
        platform_dir.mkdir(parents=True, exist_ok=True)

        all_success = True
        for dll_name, dll_url in self.WINDOWS_DLLS.items():
            dll_path = platform_dir / dll_name
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

    # ── Command builder ─────────────────────────────────────────────────

    def get_run_command(self, dns_ip: str, port: int, domain: str) -> list:
        exe_path = self.get_executable_path()
        self.ensure_executable()
        cmd = [
            str(exe_path),
            "--resolver", f"{dns_ip}:53",
            "--resolver", "8.8.4.4:53",
            "--tcp-listen-port", str(port),
            "--domain", domain,
        ]
        return cmd
