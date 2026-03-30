"""Platform detection, logging setup, regex constants and event-loop policy."""

from __future__ import annotations

import asyncio
import os
import sys

from loguru import logger


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------
def _is_android() -> bool:
    """Detect Android/Termux environment."""
    return (
        os.path.exists("/data/data/com.termux")
        or os.path.exists("/data/data/com.termux.fdroid")
        or "com.termux" in os.environ.get("PREFIX", "")
        or "ANDROID_ROOT" in os.environ
        or "ANDROID_DATA" in os.environ
    )


_ANDROID: bool = _is_android()

# ---------------------------------------------------------------------------
# Regex engine
# ---------------------------------------------------------------------------
try:
    import re2 as re  # type: ignore[import-untyped]
except ImportError:
    import re

# ---------------------------------------------------------------------------
# Clipboard helper
# ---------------------------------------------------------------------------
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

    def _read_from_clipboard() -> str:
        try:
            text = _pyperclip_mod.paste()
            return text if isinstance(text, str) else ""
        except Exception:
            return ""
except ImportError:

    def _copy_to_clipboard(text: str) -> bool:  # type: ignore[misc]
        return False

    def _read_from_clipboard() -> str:  # type: ignore[misc]
        return ""


# ---------------------------------------------------------------------------
# Windows event-loop policy (must run before any asyncio call)
# ---------------------------------------------------------------------------
# Textual's main event loop expects SelectorEventLoop on Windows.
# DNS scanning runs inline in this same loop using dnspython's async resolver.
if sys.platform == "win32" and sys.version_info < (3, 14):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logger.remove()
os.makedirs("logs", exist_ok=True)
logger.add(
    "logs/dnsscanner_{time}.log",
    rotation="50 MB",
    compression="zip",
    level="DEBUG",
)

# ---------------------------------------------------------------------------
# Pre-compiled regex for stripping ANSI escape codes
# ---------------------------------------------------------------------------
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
