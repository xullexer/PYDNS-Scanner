"""Standalone utility functions used across the scanner package."""

from __future__ import annotations

import functools
import platform
import subprocess
import sys
import threading

from .constants import _ANSI_ESCAPE_RE, logger


# ---------------------------------------------------------------------------
# Slipstream synchronous runner (designed for asyncio.to_thread)
# ---------------------------------------------------------------------------

def _run_tunnel_sync(
    cmd: list, timeout: float = 8.0, ready_string: str = "Connection ready"
) -> tuple:
    """Start a tunnel binary and block-read stdout until *ready_string* or timeout.

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
                if ready_string in clean:
                    connection_ready = True
                    return
        except Exception:
            pass

    reader = threading.Thread(target=_reader, daemon=True)
    reader.start()
    reader.join(timeout=timeout)
    return proc, connection_ready, lines



# ---------------------------------------------------------------------------
# Bell / notification sound
# ---------------------------------------------------------------------------

def _play_bell_sound() -> None:
    """Play a single coin/sparkle sound with error handling.

    On Windows the blocking ``winsound.Beep`` is offloaded to a daemon
    thread so it never stalls the event loop.
    """

    def _beep_blocking():
        try:
            if platform.system() == "Windows":
                import winsound
                winsound.Beep(1400, 60)
            elif platform.system() == "Darwin":
                try:
                    subprocess.run(
                        ["afplay", "/System/Library/Sounds/Tink.aiff"],
                        check=False,
                        timeout=1,
                    )
                except (FileNotFoundError, subprocess.SubprocessError, subprocess.TimeoutExpired):
                    print("\a", end="", flush=True)
            else:
                print("\a", end="", flush=True)
        except (ImportError, OSError, AttributeError):
            try:
                print("\a", end="", flush=True)
            except OSError:
                pass

    threading.Thread(target=_beep_blocking, daemon=True).start()


# ---------------------------------------------------------------------------
# Response-time formatter (with colour markup)
# ---------------------------------------------------------------------------

def _format_time(response_time: float) -> str:
    """Format response time with Rich colour markup."""
    ms = round(response_time * 1000)
    return _format_time_ms(ms)


@functools.lru_cache(maxsize=1024)
def _format_time_ms(ms: int) -> str:
    """Cached formatter for integer-ms values."""
    if ms < 100:
        return f"[green]{ms}ms[/green]"
    elif ms < 300:
        return f"[yellow]{ms}ms[/yellow]"
    return f"[red]{ms}ms[/red]"

