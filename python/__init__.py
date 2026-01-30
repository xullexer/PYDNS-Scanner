"""
PYDNS Scanner - A modern, high-performance DNS scanner with a beautiful TUI.

This package provides a Terminal User Interface for scanning IP ranges
to find working DNS servers with optional Slipstream proxy testing.
"""

__version__ = "1.0.8"
__author__ = "xullexer"

from python.dnsscanner_tui import main, DNSScannerTUI

__all__ = ["main", "DNSScannerTUI", "__version__"]
