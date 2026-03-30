"""Custom Textual widgets used by the scanner TUI."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import (
    Checkbox as TextualCheckbox,
    DirectoryTree,
    Footer as TextualFooter,
    Static,
)
from textual.widgets._directory_tree import DirEntry


class Checkbox(TextualCheckbox):
    """Custom Checkbox using a checkmark instead of X."""

    BUTTON = "✓"


class PlainDirectoryTree(DirectoryTree):
    """Custom DirectoryTree that uses plain text icons for Linux compat."""

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


class VersionedFooter(TextualFooter):
    """Footer that keeps native key bindings and shows app version at right."""

    DEFAULT_CSS = (
        TextualFooter.DEFAULT_CSS
        + """
    VersionedFooter > .footer-version {
        dock: right;
        width: auto;
        height: 1;
        min-width: 8;
        padding: 0 1;
        color: $footer-foreground;
        background: $footer-background;
        text-style: bold;
    }
    """
    )

    def compose(self) -> ComposeResult:
        yield from super().compose()
        yield Static("v2.0.3", classes="footer-version")


class StatsWidget(Widget):
    """Display scan statistics.

    Composed of individual child Static rows so that tooltips can be
    attached to specific rows (DNS / SEC) without covering the whole box.
    """

    BAR_WIDTH = 38

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.found: int = 0
        self.passed: int = 0
        self.failed: int = 0
        self.secure: int = 0
        self.normal: int = 0
        self.filtered: int = 0
        self.scanned: int = 0
        self.total: int = 0
        self.speed: float = 0.0
        self.elapsed: float = 0.0
        self.current_ip: str = ""
        self.current_range: str = ""
        self._bar_progress: float = 0.0
        self._bar_total: float = 0.0

        # Pre-build child widgets so update_stats() can call .update()
        # even before they are mounted.
        self._w_header = Static("[b cyan]PYDNS Scanner Statistics[/b cyan]")
        self._w_gap = Static("")
        self._w_scan = Static("")
        self._w_now = Static("")
        self._w_dns = Static("")
        self._w_dns.tooltip = "F=Found   P=Pass   X=Fail"
        self._w_sec = Static("")
        self._w_sec.tooltip = "S=Secure   N=Normal   F=Filtered"
        self._w_speed = Static("")
        self._w_time = Static("")
        self._w_gap2 = Static("")
        self._w_bar = Static("")

    def compose(self) -> ComposeResult:
        yield self._w_header
        yield self._w_gap
        yield self._w_scan
        yield self._w_now
        yield self._w_dns
        yield self._w_sec
        yield self._w_speed
        yield self._w_time
        yield self._w_gap2
        yield self._w_bar

    def update_stats(
        self,
        *,
        scanned: int | None = None,
        found: int | None = None,
        passed: int | None = None,
        failed: int | None = None,
        secure: int | None = None,
        normal: int | None = None,
        filtered: int | None = None,
        total: int | None = None,
        speed: float | None = None,
        elapsed: float | None = None,
        current_ip: str | None = None,
        current_range: str | None = None,
        bar_progress: float | None = None,
        bar_total: float | None = None,
    ) -> None:
        """Batch-update any subset of stats, then redraw each row."""
        if scanned is not None:
            self.scanned = scanned
        if found is not None:
            self.found = found
        if passed is not None:
            self.passed = passed
        if failed is not None:
            self.failed = failed
        if secure is not None:
            self.secure = secure
        if normal is not None:
            self.normal = normal
        if filtered is not None:
            self.filtered = filtered
        if total is not None:
            self.total = total
        if speed is not None:
            self.speed = speed
        if elapsed is not None:
            self.elapsed = elapsed
        if current_ip is not None:
            self.current_ip = current_ip
        if current_range is not None:
            self.current_range = current_range
        if bar_progress is not None:
            self._bar_progress = bar_progress
        if bar_total is not None:
            self._bar_total = bar_total
        self._refresh_rows()

    def _refresh_rows(self) -> None:
        range_val = self.current_range if self.current_range else "[dim]—[/dim]"
        ip_val = self.current_ip if self.current_ip else "[dim]—[/dim]"
        scan_ratio = (
            f"{self.scanned:,} / {self.total:,}"
            if self.total > 0
            else f"{self.scanned:,} / [dim]—[/dim]"
        )

        # Progress bar
        bar_total = self._bar_total
        bar_progress = self._bar_progress
        if bar_total > 0:
            ratio = max(0.0, min(1.0, bar_progress / bar_total))
        else:
            ratio = 0.0
        percent = ratio * 100
        filled = int(ratio * self.BAR_WIDTH)
        empty = max(0, self.BAR_WIDTH - filled)
        bar_str = (
            f"[#22c55e]{'█' * filled}[/#22c55e]"
            f"[grey35]{'░' * empty}[/grey35]"
            f" [bold cyan]{percent:5.1f}%[/bold cyan]"
        )

        self._w_scan.update(f"[yellow]Scan:[/yellow]  {scan_ratio}")
        self._w_now.update(
            f"[yellow]Now:[/yellow]   {range_val}[dim] > [/dim]{ip_val}"
        )
        self._w_dns.update(
            f"[yellow]DNS:[/yellow]   "
            f"[#fbbf24]{self.found}[/#fbbf24]"
            f"[dim] / [/dim]"
            f"[#22c55e]{self.passed}[/#22c55e]"
            f"[dim] / [/dim]"
            f"[#ef4444]{self.failed}[/#ef4444]"
        )
        self._w_sec.update(
            f"[yellow]SEC:[/yellow]   "
            f"[#4ade80]{self.secure}[/#4ade80]"
            f"[dim] / [/dim]"
            f"[#60a5fa]{self.normal}[/#60a5fa]"
            f"[dim] / [/dim]"
            f"[#fb923c]{self.filtered}[/#fb923c]"
        )
        self._w_speed.update(f"[yellow]Speed:[/yellow] {self.speed:.1f} IPs/sec")
        self._w_time.update(f"[yellow]Time:[/yellow]  {self.elapsed:.1f}s")
        self._w_bar.update(bar_str)

