#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PYDNS-Scanner TUI — main application module.

All reusable helpers, widgets, mixins and the SlipstreamManager live in the
``scanner`` sub-package.  This file contains only the Textual App subclass
(``DNSScannerTUI``) and the ``main()`` entry-point.
"""

from __future__ import annotations

import asyncio
import gc
import os
import platform
import random
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from typing import Set


def _resource_path(relative: str) -> Path:
    """Resolve a bundled resource path.

    When running as a PyInstaller one-file executable, data files are
    extracted to ``sys._MEIPASS``.  In normal (source) mode falls back to
    the directory that contains this module.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).parent / relative

import dns.asyncresolver
import dns.exception
import dns.resolver
import httpx

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    DirectoryTree,
    Header,
    RichLog,
    Input,
    Label,
    Select,
)

# ── Scanner package imports ─────────────────────────────────────────────────
try:
    from .scanner import (
        # Constants / platform
        _copy_to_clipboard,
        re,
        logger,
        # Widgets
        Checkbox,
        PlainDirectoryTree,
        StatsWidget,
        VersionedFooter,
        # Standalone classes
        SlipstreamManager,
        SlipNetManager,
        # Mixins (compose into DNSScannerTUI via multiple inheritance)
        ConfigMixin,
        ProxyTestingMixin,
        ExtraTestsMixin,
        ResultsMixin,
        ISPCacheMixin,
        IPStreamingMixin,
    )
except ImportError:
    from scanner import (
        # Constants / platform
        _copy_to_clipboard,
        re,
        logger,
        # Widgets
        Checkbox,
        PlainDirectoryTree,
        StatsWidget,
        VersionedFooter,
        # Standalone classes
        SlipstreamManager,
        SlipNetManager,
        # Mixins (compose into DNSScannerTUI via multiple inheritance)
        ConfigMixin,
        ProxyTestingMixin,
        ExtraTestsMixin,
        ResultsMixin,
        ISPCacheMixin,
        IPStreamingMixin,
    )


class DNSScannerTUI(
    ConfigMixin,
    ProxyTestingMixin,
    ExtraTestsMixin,
    ResultsMixin,
    ISPCacheMixin,
    IPStreamingMixin,
    App,
):
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

    #slipnet-fields-container {
        width: 100%;
        height: auto;
        display: none;
        padding: 0;
        margin: 0;
    }

    #slipstream-auth-sub {
        width: 100%;
        height: auto;
        padding: 0;
        margin: 0;
    }

    #socks5-auth-container {
        width: 100%;
        height: auto;
        display: none;
        padding: 0;
        margin: 0;
    }

    #ssh-auth-container {
        width: 100%;
        height: auto;
        display: none;
        padding: 0;
        margin: 0;
    }

    #protocol-auth-section {
        width: 100%;
        height: auto;
        border: solid #30363d;
        background: #0d1117;
        padding: 1 2;
        margin: 0 0 1 0;
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
        height: 18;
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

    #advanced-settings-container {
        display: none;
        height: auto;
        padding: 0 2;
        margin: 0 0 1 0;
        border: solid #30363d;
        background: #0d1117;
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
        self.dns_test_method = "udp"  # "udp" (port 53)
        # Calculate default concurrency as 90% of optimal
        optimal = self._get_optimal_concurrency()
        self.concurrency = int(optimal * 0.9)
        self.random_subdomain = False
        self.test_slipstream = False
        self.bell_sound_enabled = False  # Bell sound on pass
        self.proxy_auth_enabled = False  # Proxy authentication
        self.proxy_username = ""  # Proxy username
        self.proxy_password = ""  # Proxy password

        # Advanced settings (configurable from start form)
        self.dns_timeout: float = 2.0  # Seconds for DNS test timeout
        self.slipstream_timeout: float = 15.0  # Seconds for slipstream tunnel + HTTP test
        self.proxy_test_url: str = "https://www.google.com/gen_204"
        self.proxy_success_code: int = 204  # Expected HTTP status code for proxy test success
        self.proxy_ping_threshold: int = 800  # 0 = test all; otherwise only ping <= this ms

        # Experimental OS MTU
        self.os_mtu: int = 0                   # 0 = disabled
        self._original_mtu: int = 0            # stores MTU before we changed it
        self._mtu_interface: str = ""          # interface name we changed

        # SlipNet DNS query size (0 = default/full capacity)
        self.slipnet_query_size: int = 0

        # ISP cache file path — kept in cwd so it is always writable,
        # even when running as a frozen PyInstaller one-file EXE.
        self._isp_cache_path = Path("isp_cache.json")

        # Scan strategy: "shuffle" (random order) or "redis" (pincer from edges)
        self.scan_strategy = "redis"

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
        self.dns_types_results: dict[str, dict] = {}  # IP -> {A: bool, TXT: bool, ...}
        self.extra_test_tasks: set = set()  # Track running extra test tasks
        self.extra_test_semaphore: asyncio.Semaphore | None = None  # Limits concurrent extra tests

        # Incremental pass/fail counters (avoids O(n) scans of proxy_results)
        self._passed_count = 0
        self._failed_count = 0

        # Cached widget references (populated in on_mount)
        self._stats_widget: "StatsWidget | None" = None

        # Config file for caching settings
        self.config_dir = Path.home() / ".pydns-scanner"
        self.config_file = self.config_dir / "config.json"

        self.slipstream_manager = SlipstreamManager()
        self.slipstream_path = str(self.slipstream_manager.get_executable_path())
        self.slipstream_domain = ""

        # SlipNet protocol support
        self.slipnet_manager = SlipNetManager()
        self.active_protocol: str = "slipstream"  # "slipstream" or "slipnet"
        self.slipnet_url: str = ""
        self.auth_mode: str = "none"  # "none", "socks5", "ssh"
        self._proto_lock: bool = False
        self._auth_lock: bool = False
        self.ssh_host: str = ""
        self.ssh_port: int = 22
        self.ssh_user: str = ""
        self.ssh_pass: str = ""

        # whether to perform the full HTTP/SOCKS check after slipstream starts

        self.found_servers: Set[str] = set()  # Keep found servers for results
        self.server_times: dict[str, float] = {}
        self.proxy_results: dict[str, str] = (
            {}
        )  # IP -> "Success", "Failed", or "Testing"
        self.start_time = 0.0
        self._paused_elapsed: float = 0.0
        self._pause_started_at: float = 0.0
        self.last_update_time = 0.0
        self.last_table_update_time = 0.0
        self.current_scanned = 0
        self._current_scanning_ip: str = ""
        self._current_scanning_range: str = ""
        self.table_needs_rebuild = False
        self.scan_started = False
        self.is_paused = False
        self.pause_event = asyncio.Event()
        self.pause_event.set()  # Not paused initially

        # Button spam protection
        self._processing_button = False

        # Slipstream parallel testing config
        self.slipstream_max_concurrent = 3
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
        self.remaining_ips: list = []
        self.shuffle_signal: asyncio.Event | None = None  # Signal to reshuffle during scan
        self.tested_subnets: set[int] = set()  # Track completed /24 blocks as int(network_address)

        # Debug logging support
        self.debug_mode: bool = False
        self._debug_log_file = None

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

                with Container(id="protocol-auth-section"):
                    yield Label("Protocol:", classes="field-label")
                    with Horizontal(classes="form-row checkbox-row"):
                        yield Checkbox("Slipstream", id="proto-slipstream", value=True)
                        yield Checkbox("SlipNet (DNSTT/NoizDNS)", id="proto-slipnet")
                    with Container(id="slipstream-auth-sub"):
                        yield Label("Auth:", classes="field-label")
                        with Horizontal(classes="form-row checkbox-row"):
                            yield Checkbox("No Auth", id="auth-none", value=True)
                            yield Checkbox("SOCKS5", id="auth-socks5")
                            yield Checkbox("SSH", id="auth-ssh")

                with Horizontal(classes="form-row domain-row"):
                    with Vertical(classes="form-field domain-field"):
                        yield Label("Domain:", classes="field-label")
                        yield Input(
                            placeholder="e.g., google.com",
                            id="input-domain",
                        )
                    with Horizontal(classes="domain-checkboxes"):
                        yield Checkbox("Random Subdomain", id="input-random")

                with Container(id="slipnet-fields-container"):
                    with Horizontal(classes="form-row"):
                        with Vertical(classes="form-field"):
                            yield Label("SlipNet URL:", classes="field-label")
                            yield Input(
                                placeholder="slipnet://BASE64...",
                                id="input-slipnet-url",
                                classes="form-input",
                            )

                with Container(id="socks5-auth-container"):
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

                with Container(id="ssh-auth-container"):
                    with Horizontal(classes="form-row"):
                        yield Input(
                            placeholder="SSH Host",
                            id="input-ssh-host",
                            classes="form-input",
                        )
                        yield Input(
                            placeholder="22",
                            id="input-ssh-port",
                            classes="form-input",
                            value="22",
                        )
                    with Horizontal(classes="form-row"):
                        yield Input(
                            placeholder="SSH Username",
                            id="input-ssh-user",
                            classes="form-input",
                        )
                        yield Input(
                            placeholder="SSH Password",
                            id="input-ssh-pass",
                            classes="form-input",
                            password=True,
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
                    yield Checkbox("Advanced", id="input-show-advanced")

                with Container(id="advanced-settings-container"):
                    with Horizontal(classes="form-row"):
                        with Vertical(classes="form-field"):
                            yield Label("DNS Timeout (s):", classes="field-label")
                            yield Input(
                                placeholder="2.0",
                                id="input-dns-timeout",
                                value="2.0",
                            )
                        with Vertical(classes="form-field"):
                            yield Label("Proxy Timeout (s):", classes="field-label")
                            yield Input(
                                placeholder="15.0",
                                id="input-proxy-timeout",
                                value="15.0",
                            )
                    with Horizontal(classes="form-row"):
                        with Vertical(classes="form-field"):
                            yield Label("Proxy Test URL:", classes="field-label")
                            yield Input(
                                placeholder="https://www.google.com/gen_204",
                                id="input-test-url",
                                value="https://www.google.com/gen_204",
                            )
                        with Vertical(classes="form-field"):
                            yield Label("Expected Status Code (custom URL only):", classes="field-label")
                            yield Input(
                                placeholder="200",
                                id="input-proxy-success-code",
                                value="200",
                            )
                    with Horizontal(classes="form-row"):
                        with Vertical(classes="form-field"):
                            yield Label("Minimum Ping to Test (ms, 0=all, blank=800):", classes="field-label")
                            yield Input(
                                placeholder="0 = test all (default 800)",
                                id="input-proxy-ping-threshold",
                                value="800",
                            )
                        with Vertical(classes="form-field"):
                            yield Label("Parallel Proxy Tests (1-7):", classes="field-label")
                            yield Input(
                                placeholder="3 (default)",
                                id="input-proxy-parallel",
                                value="3",
                            )
                    with Horizontal(classes="form-row"):
                        with Vertical(classes="form-field"):
                            yield Label("Auto-Shuffle After N IPs (0=preset):", classes="field-label")
                            yield Input(
                                placeholder="0",
                                id="input-shuffle-threshold",
                                value="0",
                            )
                    with Horizontal(classes="form-row"):
                        with Vertical(classes="form-field"):
                            yield Label("!! Experimental OS Network MTU (10-1500, 0=off) [Admin/Root Required]:", classes="field-label")
                            yield Input(
                                placeholder="0 (disabled)",
                                id="input-os-mtu",
                                value="0",
                            )
                        with Container(id="slipnet-query-size-container", classes="form-field"):
                            yield Label("SlipNet Query Size (bytes, 0=default, min 50):", classes="field-label")
                            yield Input(
                                placeholder="0 (full capacity)",
                                id="input-slipnet-query-size",
                                value="0",
                            )
                            yield Label("Presets: 100 / 80 / 60 / 55 / 50", classes="field-label")

                with Horizontal(id="start-buttons"):
                    yield Button("Start Scan", id="start-scan-btn", variant="success")
                    yield Button("Exit", id="exit-btn", variant="error")

        # Scan Screen (initially hidden)
        with Container(id="scan-screen"):
            with Horizontal(id="stats-logs-container"):
                yield StatsWidget(id="stats")
                with Container(id="logs"):
                    yield RichLog(id="log-display", highlight=True, markup=True, max_lines=5000)
            with Container(id="results"):
                yield DataTable(id="results-table")
            with Horizontal(id="controls"):
                yield Button("⏸  Pause", id="pause-btn", variant="warning")
                yield Button("🔀 Shuffle", id="shuffle-btn", variant="default")
                yield Button("▶  Resume", id="resume-btn", variant="primary")
                yield Button("Save Results", id="save-btn", variant="success")
                yield Button("Quit", id="quit-btn", variant="error")

        yield VersionedFooter()

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

            # Scan Preset
            if config.get("scan_preset"):
                preset_select = self.query_one("#input-preset", Select)
                preset_select.value = config["scan_preset"]

            # Protocol selector
            if config.get("active_protocol") == "slipnet":
                try:
                    self.query_one("#proto-slipstream", Checkbox).value = False
                    self.query_one("#proto-slipnet", Checkbox).value = True
                    self.query_one("#slipnet-fields-container").display = True
                    self.query_one("#slipnet-query-size-container").display = True
                    for row in self.query(".domain-row"):
                        row.display = False
                except Exception:
                    pass
            else:
                try:
                    self.query_one("#slipnet-query-size-container").display = False
                except Exception:
                    pass

            # SlipNet URL
            if config.get("slipnet_url"):
                try:
                    self.query_one("#input-slipnet-url", Input).value = config["slipnet_url"]
                except Exception:
                    pass

            # Auth mode (Slipstream only — SlipNet uses embedded auth in URI)
            if config.get("active_protocol", "slipstream") != "slipnet":
                saved_auth = config.get("auth_mode", "none")
                if saved_auth == "socks5":
                    try:
                        self.query_one("#auth-none", Checkbox).value = False
                        self.query_one("#auth-socks5", Checkbox).value = True
                        self.query_one("#socks5-auth-container").display = True
                    except Exception:
                        pass
                elif saved_auth == "ssh":
                    try:
                        self.query_one("#auth-none", Checkbox).value = False
                        self.query_one("#auth-ssh", Checkbox).value = True
                        self.query_one("#ssh-auth-container").display = True
                    except Exception:
                        pass
                if config.get("proxy_auth_enabled"):
                    if config.get("proxy_username"):
                        try:
                            self.query_one("#input-proxy-user", Input).value = config["proxy_username"]
                        except Exception:
                            pass
                    if config.get("proxy_password"):
                        import base64
                        try:
                            decoded_pass = base64.b64decode(config["proxy_password"]).decode("utf-8")
                            self.query_one("#input-proxy-pass", Input).value = decoded_pass
                        except Exception:
                            pass
                if config.get("ssh_host"):
                    try:
                        self.query_one("#input-ssh-host", Input).value = config["ssh_host"]
                    except Exception:
                        pass
                if config.get("ssh_port"):
                    try:
                        self.query_one("#input-ssh-port", Input).value = str(config["ssh_port"])
                    except Exception:
                        pass
                if config.get("ssh_user"):
                    try:
                        self.query_one("#input-ssh-user", Input).value = config["ssh_user"]
                    except Exception:
                        pass
                if config.get("ssh_pass"):
                    import base64
                    try:
                        decoded_ssh_pass = base64.b64decode(config["ssh_pass"]).decode("utf-8")
                        self.query_one("#input-ssh-pass", Input).value = decoded_ssh_pass
                    except Exception:
                        pass

            # slipstream settings
            if config.get("slipstream_enabled") is not None:
                slip_checkbox = self.query_one("#input-slipstream", Checkbox)
                slip_checkbox.value = config.get("slipstream_enabled")

            # Advanced settings
            if config.get("dns_timeout"):
                self.query_one("#input-dns-timeout", Input).value = str(config["dns_timeout"])
            if config.get("slipstream_timeout"):
                self.query_one("#input-proxy-timeout", Input).value = str(config["slipstream_timeout"])
            if config.get("proxy_test_url"):
                self.query_one("#input-test-url", Input).value = config["proxy_test_url"]
            if config.get("proxy_success_code"):
                self.query_one("#input-proxy-success-code", Input).value = str(config["proxy_success_code"])
            if config.get("proxy_ping_threshold") is not None:
                self.query_one("#input-proxy-ping-threshold", Input).value = str(config["proxy_ping_threshold"])
            if config.get("shuffle_threshold"):
                self.query_one("#input-shuffle-threshold", Input).value = str(config["shuffle_threshold"])
            if config.get("proxy_parallel") is not None:
                self.query_one("#input-proxy-parallel", Input).value = str(config["proxy_parallel"])
            if config.get("os_mtu") is not None:
                self.query_one("#input-os-mtu", Input).value = str(config["os_mtu"])
            if config.get("slipnet_query_size") is not None:
                self.query_one("#input-slipnet-query-size", Input).value = str(config["slipnet_query_size"])

        except Exception as e:
            logger.debug(f"Could not set cached config values: {e}")

        # Setup both results tables
        self._setup_table_columns()

        # Cache frequently accessed widget references
        try:
            self._stats_widget = self.query_one("#stats", StatsWidget)
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
        cols: list[tuple[str, str, int | None]] = []
        if self.test_slipstream:
            cols.append(("Proxy", "proxy", 12))
        cols.append(("IP Address", "ip", None))
        cols.append(("Ping", "time", None))
        cols.append(("IPv4/IPv6", "ipver", None))
        cols.append(("Security", "security", None))
        cols.append(("TCP/UDP", "tcpudp", None))
        cols.append(("DNS Types", "dns_types", 20))
        cols.append(("EDNS0", "edns0", None))
        cols.append(("IP", "resolved", None))
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

        # Cancel active DNS scan tasks
        if hasattr(self, "active_scan_tasks"):
            for task in list(self.active_scan_tasks):
                try:
                    if not task.done():
                        task.cancel()
                except Exception as e:
                    logger.debug(f"Could not cancel scan task: {e}")
            if isinstance(self.active_scan_tasks, set):
                self.active_scan_tasks.clear()
            else:
                self.active_scan_tasks = []

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

        # Clear pending proxy test queue
        if hasattr(self, "pending_slipstream_tests"):
            self.pending_slipstream_tests.clear()

        # Close shared HTTP client if open
        if hasattr(self, "_http_client") and self._http_client:
            try:
                import asyncio as _aio
                loop = _aio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._http_client.aclose())
                else:
                    loop.run_until_complete(self._http_client.aclose())
            except Exception:
                pass
            self._http_client = None

        # Cancel all Textual workers
        try:
            self.workers.cancel_all()
        except Exception as e:
            logger.debug(f"Could not cancel workers: {e}")

        # Force garbage collection
        gc.collect()

        # Close debug log if still open
        self._close_debug_log()

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

        # Revert OS MTU before exit
        self._revert_os_mtu()

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
        cb_id = event.checkbox.id

        if cb_id == "input-show-advanced":
            try:
                container = self.query_one("#advanced-settings-container")
                container.display = event.value
            except Exception as e:
                logger.debug(f"Could not toggle advanced settings container: {e}")

        elif cb_id in ("proto-slipstream", "proto-slipnet"):
            if self._proto_lock:
                return
            self._proto_lock = True
            try:
                if event.value:
                    other_id = "proto-slipnet" if cb_id == "proto-slipstream" else "proto-slipstream"
                    self.query_one(f"#{other_id}", Checkbox).value = False
                    is_slipnet = (cb_id == "proto-slipnet")
                    self.query_one("#slipnet-fields-container").display = is_slipnet
                    for row in self.query(".domain-row"):
                        row.display = not is_slipnet
                    # SlipNet v2.4.1 handles auth internally; hide auth UI when SlipNet active
                    try:
                        self.query_one("#slipstream-auth-sub").display = not is_slipnet
                        if is_slipnet:
                            self.query_one("#socks5-auth-container").display = False
                            self.query_one("#ssh-auth-container").display = False
                    except Exception:
                        pass
                    # Show query-size setting only for SlipNet
                    try:
                        self.query_one("#slipnet-query-size-container").display = is_slipnet
                    except Exception:
                        pass
                else:
                    other_id = "proto-slipnet" if cb_id == "proto-slipstream" else "proto-slipstream"
                    if not self.query_one(f"#{other_id}", Checkbox).value:
                        event.checkbox.value = True
            except Exception as e:
                logger.debug(f"Protocol checkbox error: {e}")
            finally:
                self._proto_lock = False

        elif cb_id in ("auth-none", "auth-socks5", "auth-ssh"):
            if self._auth_lock:
                return
            self._auth_lock = True
            try:
                if event.value:
                    others = [i for i in ("auth-none", "auth-socks5", "auth-ssh") if i != cb_id]
                    for other_id in others:
                        self.query_one(f"#{other_id}", Checkbox).value = False
                    self.query_one("#socks5-auth-container").display = (cb_id == "auth-socks5")
                    self.query_one("#ssh-auth-container").display = (cb_id == "auth-ssh")
                else:
                    others_on = [i for i in ("auth-none", "auth-socks5", "auth-ssh")
                                 if i != cb_id and self.query_one(f"#{i}", Checkbox).value]
                    if not others_on:
                        event.checkbox.value = True
            except Exception as e:
                logger.debug(f"Auth checkbox error: {e}")
            finally:
                self._auth_lock = False

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
        self._pause_started_at = time.time()
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
        if self._pause_started_at > 0:
            self._paused_elapsed += time.time() - self._pause_started_at
            self._pause_started_at = 0.0
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
        """Calculate optimal *total* concurrency based on system resources.

        The multi-threaded worker pool distributes work across N threads,
        each with its own event loop.  We cap the total so the pool stays
        within ~6-8 threads (the sweet-spot before OS scheduling overhead
        dominates on Windows).
        """
        try:
            cpu_count = os.cpu_count() or 2

            # Try psutil for accurate memory detection
            try:
                import psutil  # type: ignore
                mem_gb = psutil.virtual_memory().available / (1024 ** 3)
                # ~50 concurrent per GB free, scaled by CPU
                mem_based = int(mem_gb * 50)
                cpu_based = cpu_count * 50
                optimal = max(100, min(mem_based, cpu_based, 600))
            except ImportError:
                # Fallback: scale based on CPU count only
                if cpu_count >= 8:
                    optimal = 400
                elif cpu_count >= 4:
                    optimal = 250
                else:
                    optimal = 150

            # Hard cap: more than ~440 on Windows (8 threads × 55) gives
            # diminishing returns due to thread scheduling overhead.
            if sys.platform == "win32":
                optimal = min(optimal, 440)

            return optimal
        except Exception:
            return 200

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
        concurrency_input = self.query_one("#input-concurrency", Input)
        random_checkbox = self.query_one("#input-random", Checkbox)
        slipstream_checkbox = self.query_one("#input-slipstream", Checkbox)
        bell_checkbox = self.query_one("#input-bell", Checkbox)

        # Determine CIDR file based on dropdown selection
        cidr_value = str(cidr_select.value) if cidr_select.value else "iran"

        if cidr_value == "iran":
            # Use bundled Iran CIDR file as default
            iran_cidr_path = _resource_path("iran-ipv4.cidrs")
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
            iran_cidr_path = _resource_path("iran-ipv4.cidrs")
            self.subnet_file = str(iran_cidr_path)

        self.domain = domain_input.value.strip()
        # When using SlipNet, the domain field may be hidden / empty.
        # Fall back to a sensible default so DNS probes still work.
        if not self.domain:
            self.domain = "google.com"
        self.slipstream_domain = self.domain
        self.dns_type = "A"
        self.random_subdomain = random_checkbox.value
        self.test_slipstream = slipstream_checkbox.value
        self.bell_sound_enabled = bell_checkbox.value
        try:
            self.debug_mode = self.query_one("#input-debug", Checkbox).value
        except Exception:
            self.debug_mode = False

        # Determine active protocol from Checkbox
        try:
            self.active_protocol = "slipnet" if self.query_one("#proto-slipnet", Checkbox).value else "slipstream"
        except Exception:
            self.active_protocol = "slipstream"

        # SlipNet-specific validation (only when proxy test is enabled)
        if self.active_protocol == "slipnet" and self.test_slipstream:
            slipnet_url_str = self.query_one("#input-slipnet-url", Input).value.strip()
            if not slipnet_url_str or not slipnet_url_str.startswith("slipnet://"):
                self.notify("Please enter a valid SlipNet URL (slipnet://...)!", severity="error")
                return
            self.slipnet_url = slipnet_url_str

            # Parse SlipNet config to extract the tunnel domain
            parsed_cfg = SlipNetManager.parse_config(self.slipnet_url)
            if parsed_cfg.get("domain"):
                self.domain = parsed_cfg["domain"]
                self.slipstream_domain = self.domain
            # v2.4.1 handles SOCKS5 auth internally via the slipnet:// URI.

        # Determine auth mode (Slipstream only; SlipNet v2.4.1 handles auth internally)
        if self.active_protocol == "slipstream":
            try:
                if self.query_one("#auth-socks5", Checkbox).value:
                    self.auth_mode = "socks5"
                elif self.query_one("#auth-ssh", Checkbox).value:
                    self.auth_mode = "ssh"
                else:
                    self.auth_mode = "none"
            except Exception:
                self.auth_mode = "none"

            if self.auth_mode == "socks5":
                proxy_user_input = self.query_one("#input-proxy-user", Input)
                proxy_pass_input = self.query_one("#input-proxy-pass", Input)
                self.proxy_username = proxy_user_input.value.strip()
                self.proxy_password = proxy_pass_input.value
                self.proxy_auth_enabled = bool(self.proxy_username)
                if not self.proxy_username:
                    self.notify("Please enter proxy username!", severity="error")
                    return
            elif self.auth_mode == "ssh":
                self.ssh_host = self.query_one("#input-ssh-host", Input).value.strip()
                self.ssh_port = 22
                try:
                    ssh_port_str = self.query_one("#input-ssh-port", Input).value.strip()
                    if ssh_port_str:
                        self.ssh_port = int(ssh_port_str)
                except (ValueError, Exception):
                    self.ssh_port = 22
                self.ssh_user = self.query_one("#input-ssh-user", Input).value.strip()
                self.ssh_pass = self.query_one("#input-ssh-pass", Input).value
                if not self.ssh_host or not self.ssh_user:
                    self.notify("Please enter SSH host and username!", severity="error")
                    return
                # SSH auth controls the remote tunnel; the local SOCKS5 proxy is no-auth.
                self.proxy_username = ""
                self.proxy_password = ""
                self.proxy_auth_enabled = False
            else:
                self.proxy_auth_enabled = False
                self.proxy_username = ""
                self.proxy_password = ""
        else:
            # SlipNet: auth is embedded in the slipnet:// URI, handled by v2.4.1
            self.auth_mode = "none"
            self.proxy_auth_enabled = False
            self.proxy_username = ""
            self.proxy_password = ""

        # Get scan preset
        preset_select = self.query_one("#input-preset", Select)
        self.scan_preset = str(preset_select.value) if preset_select.value else "fast"
        self._apply_scan_preset()

        # Get concurrency (auto or manual)
        concurrency_str = concurrency_input.value.strip().lower()
        if concurrency_str == "auto" or not concurrency_str:
            # Calculate 90% of optimal
            optimal = self._get_optimal_concurrency()
            self.concurrency = int(optimal * 0.9)
        else:
            try:
                self.concurrency = int(concurrency_str)
            except ValueError:
                optimal = self._get_optimal_concurrency()
                self.concurrency = int(optimal * 0.9)

        # Get general settings (NOT saved - user selects each time)
        # All general settings are now always enabled

        # Get advanced settings
        try:
            dns_timeout_str = self.query_one("#input-dns-timeout", Input).value.strip()
            self.dns_timeout = float(dns_timeout_str) if dns_timeout_str else 2.0
            if self.dns_timeout <= 0:
                self.dns_timeout = 2.0
        except (ValueError, Exception):
            self.dns_timeout = 2.0

        try:
            proxy_timeout_str = self.query_one("#input-proxy-timeout", Input).value.strip()
            self.slipstream_timeout = float(proxy_timeout_str) if proxy_timeout_str else 15.0
            if self.slipstream_timeout <= 0:
                self.slipstream_timeout = 15.0
        except (ValueError, Exception):
            self.slipstream_timeout = 15.0

        try:
            test_url_str = self.query_one("#input-test-url", Input).value.strip()
            self.proxy_test_url = test_url_str if test_url_str else "https://www.google.com/gen_204"
        except Exception:
            self.proxy_test_url = "https://www.google.com/gen_204"

        # If URL is the default gen_204, lock to 204; otherwise use the user's custom code
        DEFAULT_URL = "https://www.google.com/gen_204"
        if self.proxy_test_url == DEFAULT_URL:
            self.proxy_success_code = 204
        else:
            try:
                code_str = self.query_one("#input-proxy-success-code", Input).value.strip()
                self.proxy_success_code = int(code_str) if code_str else 200
                if self.proxy_success_code <= 0:
                    self.proxy_success_code = 200
            except (ValueError, Exception):
                self.proxy_success_code = 200

        try:
            threshold_str = self.query_one("#input-proxy-ping-threshold", Input).value.strip()
            self.proxy_ping_threshold = int(threshold_str) if threshold_str else 800
            # 0 means "test all proxies"; only negatives are invalid
            if self.proxy_ping_threshold < 0:
                self.proxy_ping_threshold = 0
        except (ValueError, Exception):
            self.proxy_ping_threshold = 800

        try:
            shuffle_str = self.query_one("#input-shuffle-threshold", Input).value.strip()
            custom_shuffle = int(shuffle_str) if shuffle_str else 0
            if custom_shuffle > 0:
                self.preset_shuffle_threshold = custom_shuffle
                self.preset_auto_shuffle = True
        except (ValueError, Exception):
            pass

        try:
            parallel_str = self.query_one("#input-proxy-parallel", Input).value.strip()
            self.slipstream_max_concurrent = max(1, min(10, int(parallel_str))) if parallel_str else 3
        except (ValueError, Exception):
            self.slipstream_max_concurrent = 3

        try:
            os_mtu_str = self.query_one("#input-os-mtu", Input).value.strip()
            self.os_mtu = max(0, min(1500, int(os_mtu_str))) if os_mtu_str else 0
        except (ValueError, Exception):
            self.os_mtu = 0

        try:
            qs_str = self.query_one("#input-slipnet-query-size", Input).value.strip()
            raw_qs = int(qs_str) if qs_str else 0
            # Enforce minimum of 50 if a non-zero value is set
            self.slipnet_query_size = max(50, raw_qs) if raw_qs > 0 else 0
        except (ValueError, Exception):
            self.slipnet_query_size = 0

        # Rebuild table columns based on enabled tests
        self._setup_table_columns()

        if not self.domain and self.active_protocol == "slipstream":
            self.notify("Please enter a domain!", severity="error")
            return

        # Save configuration for next session
        import base64
        config = {
            "domain": self.domain,
            "scan_preset": self.scan_preset,
            "concurrency": self.concurrency,
            "proxy_auth_enabled": self.proxy_auth_enabled,
            "proxy_username": self.proxy_username if self.proxy_auth_enabled else "",
            "proxy_password": base64.b64encode(self.proxy_password.encode("utf-8")).decode("utf-8") if self.proxy_auth_enabled and self.proxy_password else "",
            # slipstream-related flags
            "slipstream_enabled": self.test_slipstream,
            # Protocol & SlipNet
            "active_protocol": self.active_protocol,
            "slipnet_url": self.slipnet_url,
            "auth_mode": self.auth_mode,
            "ssh_host": self.ssh_host,
            "ssh_port": self.ssh_port,
            "ssh_user": self.ssh_user,
            "ssh_pass": base64.b64encode(self.ssh_pass.encode("utf-8")).decode("utf-8") if self.ssh_pass else "",
            # Advanced settings
            "dns_timeout": self.dns_timeout,
            "slipstream_timeout": self.slipstream_timeout,
            "proxy_test_url": self.proxy_test_url,
            "proxy_success_code": self.proxy_success_code,
            "proxy_ping_threshold": self.proxy_ping_threshold,
            "shuffle_threshold": self.preset_shuffle_threshold,
            "proxy_parallel": self.slipstream_max_concurrent,
            "os_mtu": self.os_mtu,
            "slipnet_query_size": self.slipnet_query_size,
        }
        self._save_config(config)

        # Check tunnel client version and download if needed
        if self.test_slipstream:
            protocol_name = "SlipNet" if self.active_protocol == "slipnet" else "Slipstream"
            self.notify(
                f"Checking {protocol_name} client...", severity="information", timeout=2
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
        log_widget.write("[yellow]DNS Types:[/yellow] NS, TXT, RND, DPI, EDNS0, NXD")
        log_widget.write(f"[yellow]Concurrency:[/yellow] {self.concurrency}")
        log_widget.write(f"[yellow]Scan Preset:[/yellow] {self.scan_preset}")
        log_widget.write(
            f"[yellow]Proxy Test:[/yellow] {'Enabled' if self.test_slipstream else 'Disabled'}"
        )
        log_widget.write(f"[yellow]DNS Timeout:[/yellow] {self.dns_timeout}s")
        if self.test_slipstream:
            log_widget.write(f"[yellow]Proxy Timeout:[/yellow] {self.slipstream_timeout}s")
            log_widget.write(f"[yellow]Proxy Test URL:[/yellow] {self.proxy_test_url}")
            if self.proxy_ping_threshold == 0:
                log_widget.write("[yellow]Minimum Ping to Test:[/yellow] all")
            else:
                log_widget.write(f"[yellow]Minimum Ping to Test:[/yellow] {self.proxy_ping_threshold}ms")
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
        log_widget.write(
            "[dim]DNS legend:[/dim] "
            "[white]F=Found[/white], [green]P=Pass[/green], [red]X=Fail[/red]"
        )
        log_widget.write(
            "[dim]SEC legend:[/dim] "
            "[bright_green]S=Secure[/bright_green], "
            "[bright_blue]N=Normal[/bright_blue], "
            "[orange1]F=Filtered[/orange1]"
        )
        log_widget.write("[green]Starting scan...[/green]\n")

        # Start scanning
        self.scan_started = True

        # Update keybinding visibility for scan mode
        self._update_keybinding_visibility(scanning=True, paused=False)

        self.run_worker(self._scan_async(), exclusive=True)

    async def _check_update_and_start_scan(self) -> None:
        """Check for tunnel client updates and then start the scan."""
        # Rebuild table columns (test toggles already read)
        self._setup_table_columns()

        # Switch to scan screen to show progress
        self.query_one("#start-screen").display = False
        self.query_one("#scan-screen").display = True

        # Get log widget AFTER switching to scan screen
        log_widget = self.query_one("#log-display", RichLog)
        log_widget.write("[bold cyan]PYDNS Scanner Log[/bold cyan]")

        # Determine which manager to use based on active protocol
        if self.active_protocol == "slipnet":
            manager = self.slipnet_manager
            protocol_name = "SlipNet"
        else:
            manager = self.slipstream_manager
            protocol_name = "Slipstream"

        log_widget.write(f"[cyan]Checking {protocol_name} client...[/cyan]")

        # Ensure tunnel client is installed (download only if not present)
        def log_callback(msg):
            log_widget.write(msg)

        success, message = await manager.ensure_installed(log_callback)

        # Verify we have a working client
        if not manager.is_installed():
            log_widget.write(f"[red]✗ Failed to get {protocol_name} client![/red]")
            log_widget.write(
                "[yellow]Please download manually or check your network connection.[/yellow]"
            )
            self.notify(f"{protocol_name} not available", severity="error")
            return

        # Ensure executable permissions
        manager.ensure_executable()
        if self.active_protocol == "slipnet":
            pass  # SlipNet doesn't need a path stored
        else:
            self.slipstream_path = str(manager.get_executable_path())

        # Continue with scan setup
        log_widget.write(f"[yellow]Subnet file:[/yellow] {self.subnet_file}")
        if self.active_protocol == "slipnet":
            log_widget.write(f"[yellow]SlipNet URL:[/yellow] {self.slipnet_url[:40]}...")
            log_widget.write(f"[yellow]Domain (from config):[/yellow] {self.domain}")
        else:
            log_widget.write(f"[yellow]Domain:[/yellow] {self.domain}")
        log_widget.write("[yellow]DNS Types:[/yellow] NS, TXT, RND, DPI, EDNS0, NXD")
        log_widget.write(f"[yellow]Concurrency:[/yellow] {self.concurrency}")
        log_widget.write(f"[yellow]Scan Preset:[/yellow] {self.scan_preset}")
        log_widget.write(f"[yellow]Proxy Test:[/yellow] Enabled ({protocol_name})")
        if self.active_protocol == "slipstream":
            log_widget.write(f"[yellow]Auth Mode:[/yellow] {self.auth_mode}")
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
        """Download tunnel client and then start the scan."""
        log_widget = self.query_one("#log-display", RichLog)
        # Shim: route download progress through the embedded stats bar
        _stats_ref = self._stats_widget

        class _DownloadProgressShim:
            def update_progress(self, progress: float, total: float) -> None:
                if _stats_ref:
                    _stats_ref.update_stats(bar_progress=float(progress), bar_total=float(total))

        progress_bar = _DownloadProgressShim()

        # Determine which manager to use
        if self.active_protocol == "slipnet":
            manager = self.slipnet_manager
            protocol_name = "SlipNet"
        else:
            manager = self.slipstream_manager
            protocol_name = "Slipstream"

        # Switch to scan screen to show progress
        self.query_one("#start-screen").display = False
        self.query_one("#scan-screen").display = True

        log_widget.write("[bold cyan]PYDNS Scanner Log[/bold cyan]")
        log_widget.write(
            f"[yellow]Platform:[/yellow] {manager.system} {manager.machine}"
        )
        log_widget.write(f"[cyan]Downloading {protocol_name} client...[/cyan]")
        log_widget.write(
            f"[dim]URL: {manager.get_download_url()}[/dim]"
        )

        success = await manager.download_with_ui(
            progress_bar=progress_bar,
            log_widget=log_widget,
        )

        if success:
            log_widget.write(f"[green]✓ {protocol_name} downloaded successfully![/green]")
            progress_bar.update_progress(100, 100)  # Show 100%
            if self.active_protocol != "slipnet":
                self.slipstream_path = str(manager.get_executable_path())

            # Continue with the scan
            log_widget.write(f"[yellow]Subnet file:[/yellow] {self.subnet_file}")
            if self.active_protocol == "slipnet":
                log_widget.write(f"[yellow]SlipNet URL:[/yellow] {self.slipnet_url[:40]}...")
            else:
                log_widget.write(f"[yellow]Domain:[/yellow] {self.domain}")
            log_widget.write("[yellow]DNS Types:[/yellow] NS, TXT, RND, DPI, EDNS0, NXD")
            log_widget.write(f"[yellow]Concurrency:[/yellow] {self.concurrency}")
            log_widget.write(f"[yellow]Proxy Test:[/yellow] Enabled ({protocol_name})")
            log_widget.write("[green]Starting scan...[/green]\n")

            self.scan_started = True

            # Update keybinding visibility for scan mode
            self._update_keybinding_visibility(scanning=True, paused=False)

            await self._scan_async()
        else:
            log_widget.write(
                f"[red]✗ Failed to download {protocol_name} after multiple retries![/red]"
            )
            log_widget.write(
                f"[yellow]Expected path: {manager.get_executable_path()}[/yellow]"
            )
            log_widget.write(
                "[yellow]Partial download saved. Run again to resume.[/yellow]"
            )
            log_widget.write(
                "[yellow]Or download manually and place in the path above.[/yellow]"
            )
            self.notify(
                f"Failed to download {protocol_name}. Run again to resume.", severity="error"
            )

    def _apply_os_mtu(self) -> None:
        """Set OS network adapter MTU. Elevates via UAC/pkexec/osascript if not admin."""
        if not self.os_mtu:
            return
        import platform as _platform
        _sys = _platform.system()
        try:
            if _sys == "Windows":
                self._mtu_op_windows(self.os_mtu, reverting=False)
            elif _sys == "Linux":
                self._mtu_op_linux(self.os_mtu, reverting=False)
            elif _sys == "Darwin":
                self._mtu_op_mac(self.os_mtu, reverting=False)
            else:
                self._log(f"[yellow]⚠ OS MTU change not supported on {_sys}[/yellow]")
        except Exception as e:
            self._log(f"[red]Failed to set OS MTU: {e}[/red]")
            self._original_mtu = 0
            self._mtu_interface = ""

    def _revert_os_mtu(self) -> None:
        """Restore OS network adapter MTU to its saved original value."""
        if not self._original_mtu or not self._mtu_interface:
            return
        import platform as _platform
        _sys = _platform.system()
        try:
            if _sys == "Windows":
                self._mtu_op_windows(self._original_mtu, reverting=True)
            elif _sys == "Linux":
                self._mtu_op_linux(self._original_mtu, reverting=True)
            elif _sys == "Darwin":
                self._mtu_op_mac(self._original_mtu, reverting=True)
        except Exception as e:
            logger.warning(f"Could not revert OS MTU: {e}")
        finally:
            self._original_mtu = 0
            self._mtu_interface = ""

    def _mtu_op_windows(self, mtu: int, reverting: bool) -> None:
        """Windows MTU apply/revert. Uses PowerShell; triggers UAC if not admin."""
        import base64
        import ctypes as _ctypes

        if not reverting:
            # Discover interface and save original MTU (no admin required)
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-NetIPInterface -AddressFamily IPv4 "
                 "| Where-Object ConnectionState -eq Connected "
                 "| Sort-Object InterfaceMetric "
                 "| Select-Object -First 1 -ExpandProperty InterfaceAlias"],
                capture_output=True, text=True, timeout=10)
            iface = r.stdout.strip().strip('"')
            if not iface:
                raise ValueError("No connected IPv4 interface found")
            r2 = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Get-NetIPInterface -InterfaceAlias '{iface}' -AddressFamily IPv4 "
                 f"| Select-Object -ExpandProperty NlMtu"],
                capture_output=True, text=True, timeout=10)
            self._original_mtu = int(r2.stdout.strip())
            self._mtu_interface = iface
        else:
            iface = self._mtu_interface

        set_cmd = (
            f"Set-NetIPInterface -InterfaceAlias '{iface}' "
            f"-AddressFamily IPv4 -NlMtuBytes {mtu}"
        )

        try:
            is_admin = bool(_ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            is_admin = False

        if is_admin:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", set_cmd],
                capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip() or r.stdout.strip())
        else:
            # Encode command as base64 UTF-16-LE to avoid quoting issues in RunAs
            b64 = base64.b64encode(set_cmd.encode("utf-16-le")).decode("ascii")
            uac = (
                f"Start-Process powershell.exe -Verb RunAs -Wait "
                f"-ArgumentList '-NoProfile','-EncodedCommand','{b64}'"
            )
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", uac],
                capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                raise RuntimeError("UAC elevation was cancelled or failed")

        if not reverting:
            self._log(f"[green]OS MTU set to {mtu} on '{iface}' (was {self._original_mtu})[/green]")
        else:
            logger.info(f"OS MTU reverted to {mtu} on '{iface}'")

    def _mtu_op_linux(self, mtu: int, reverting: bool) -> None:
        """Linux MTU apply/revert. Uses pkexec/sudo for elevation."""
        import os as _os
        import re as _re

        if not reverting:
            # Discover active interface via default route
            r = subprocess.run(["ip", "route", "get", "1.1.1.1"],
                               capture_output=True, text=True, timeout=5)
            iface = None
            toks = r.stdout.split()
            for i, t in enumerate(toks):
                if t == "dev" and i + 1 < len(toks):
                    iface = toks[i + 1]
                    break
            if not iface:
                raise ValueError("Could not determine active network interface")
            # Save original MTU
            r2 = subprocess.run(["ip", "link", "show", iface],
                                capture_output=True, text=True, timeout=5)
            m = _re.search(r'\bmtu\s+(\d+)', r2.stdout)
            self._original_mtu = int(m.group(1)) if m else 1500
            self._mtu_interface = iface
        else:
            iface = self._mtu_interface

        if _os.geteuid() == 0:
            subprocess.run(["ip", "link", "set", iface, "mtu", str(mtu)],
                           check=True, timeout=10)
        else:
            # Try pkexec (GUI PolicyKit dialog on desktop environments)
            r = subprocess.run(["pkexec", "ip", "link", "set", iface, "mtu", str(mtu)],
                               capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                # Fallback: passwordless sudo
                r2 = subprocess.run(["sudo", "ip", "link", "set", iface, "mtu", str(mtu)],
                                    capture_output=True, text=True, timeout=30)
                if r2.returncode != 0:
                    raise RuntimeError("pkexec/sudo failed — run as root or grant permission")

        if not reverting:
            self._log(f"[green]OS MTU set to {mtu} on '{iface}' (was {self._original_mtu})[/green]")
        else:
            logger.info(f"OS MTU reverted to {mtu} on '{iface}'")

    def _mtu_op_mac(self, mtu: int, reverting: bool) -> None:
        """macOS MTU apply/revert. Uses osascript admin dialog for elevation."""
        import os as _os
        import re as _re

        if not reverting:
            # Discover active interface
            r = subprocess.run(["route", "get", "default"],
                               capture_output=True, text=True, timeout=5)
            iface = None
            for line in r.stdout.splitlines():
                if "interface:" in line:
                    iface = line.split()[-1]
                    break
            if not iface:
                raise ValueError("Could not determine active network interface")
            # Save original MTU
            r2 = subprocess.run(["ifconfig", iface],
                                capture_output=True, text=True, timeout=5)
            m = _re.search(r'\bmtu\s+(\d+)', r2.stdout)
            self._original_mtu = int(m.group(1)) if m else 1500
            self._mtu_interface = iface
        else:
            iface = self._mtu_interface

        if _os.geteuid() == 0:
            subprocess.run(["ifconfig", iface, "mtu", str(mtu)], check=True, timeout=10)
        else:
            # osascript asks for admin password via macOS dialog
            r = subprocess.run(
                ["osascript", "-e",
                 f'do shell script "ifconfig {iface} mtu {mtu}" with administrator privileges'],
                capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                raise RuntimeError(f"Authentication failed or cancelled: {r.stderr.strip()}")

        if not reverting:
            self._log(f"[green]OS MTU set to {mtu} on '{iface}' (was {self._original_mtu})[/green]")
        else:
            logger.info(f"OS MTU reverted to {mtu} on '{iface}'")

    async def _scan_async(self) -> None:
        """Async scanning logic with instant shuffle support."""
        # Open debug log file if debug mode is enabled
        self._close_debug_log()
        if self.debug_mode:
            os.makedirs("logs", exist_ok=True)
            _dbg_ts = time.strftime("%Y-%m-%d_%H-%M-%S")
            _dbg_path = f"logs/debug_{_dbg_ts}.log"
            try:
                self._debug_log_file = open(_dbg_path, "w", encoding="utf-8", buffering=1)
                self._debug_log_file.write(f"# PYDNS Scanner Debug Log — {_dbg_ts}\n")
                self._debug_log_file.write(f"# Domain: {self.domain}\n")
                self._debug_log_file.write(f"# Protocol: {self.active_protocol}\n")
                self._debug_log_file.write(f"# Auth mode: {getattr(self, 'auth_mode', 'N/A')}\n")
                self._debug_log_file.write(f"# Test URL: {getattr(self, 'proxy_test_url', 'N/A')}\n\n")
                self._log(f"[cyan]Debug log: {_dbg_path}[/cyan]")
            except Exception as _e:
                logger.warning(f"Could not open debug log: {_e}")
                self.debug_mode = False

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
        self.dns_types_results.clear()
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

        # Reset pause state
        self.is_paused = False
        self.pause_event = asyncio.Event()
        self.pause_event.set()  # Not paused initially

        # Initialize shuffle signal
        self.shuffle_signal = asyncio.Event()

        # Ensure ISP cache is built (fetches from ip-api.com if needed)
        try:
            await self._ensure_isp_cache()
        except Exception as e:
            logger.warning(f"ISP cache build failed: {e}")
            self._log(f"[yellow]ISP cache unavailable: {e}[/yellow]")

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

        # Apply experimental OS MTU if configured
        if self.os_mtu:
            self._apply_os_mtu()

        # Placeholder — real start_time is set just before first IP submission
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.last_table_update_time = self.start_time

        # Start periodic sort refresh timer (every 3 seconds)
        self._sort_refresh_timer = self.set_interval(3.0, self._periodic_sort_refresh)

        # Start periodic stats refresh timer (every 0.5s — smooth speed/scanned display)
        self._stats_refresh_timer = self.set_interval(0.5, self._tick_stats)

        # Notify user about CIDR loading
        self.notify("Reading CIDR file...", severity="information", timeout=3)
        self._log("[cyan]Analyzing CIDR file...[/cyan]")
        await asyncio.sleep(0)

        # Fast count of total IPs (not lines) for accurate progress
        loop = asyncio.get_running_loop()
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
                stats.update_stats(
                    total=effective_total,
                    bar_progress=0.0,
                    bar_total=float(effective_total),
                )
        except Exception as e:
            logger.debug(f"Could not initialize stats widget: {e}")

        logger.info(f"Starting chunked scan with concurrency {self.concurrency}")
        self._log("[cyan]Scan mode: Streaming (no pre-loading)[/cyan]")
        self._log(f"[cyan]Concurrency: {self.concurrency} workers[/cyan]")
        await asyncio.sleep(0)

        self._log("[cyan]DNS method: Standard UDP (port 53)[/cyan]")
        await asyncio.sleep(0)

        self.notify("Scanning in real-time...", severity="information", timeout=3)

        # ── Create semaphore (same pattern as original) ──
        sem = asyncio.Semaphore(self.concurrency)

        self._log("[green]Starting memory-efficient streaming scan...[/green]")
        await asyncio.sleep(0)

        # ── Reset start_time NOW so speed metric excludes setup ────────
        self.start_time = time.time()
        self.last_update_time = self.start_time

        # Queue-based scheduler: O(1) per result instead of O(N) asyncio.wait.
        # Each worker task calls put_nowait when it finishes; the main loop
        # just reads from the queue — no callback-set juggling.
        max_outstanding = max(self.concurrency * 2, self.concurrency + 64)
        result_queue: asyncio.Queue = asyncio.Queue()
        active_tasks_set: set = set()  # kept only for cancel-on-shutdown
        in_flight: int = 0
        scan_complete = False

        async def _run_test(ip: str) -> None:
            """Run one DNS probe and push the result tuple to result_queue."""
            await self.pause_event.wait()
            try:
                result = await self._test_dns(ip, sem)
            except Exception as e:
                logger.debug(f"DNS test error for {ip}: {e}")
                result = (ip, False, 0.0)
            result_queue.put_nowait(result)

        async def _drain_results() -> None:
            """Process all results already in the queue without blocking."""
            nonlocal in_flight
            while not result_queue.empty():
                r = result_queue.get_nowait()
                in_flight -= 1
                await self._process_result(r)

        async def _wait_one() -> None:
            """Block until exactly one result arrives, then process it."""
            nonlocal in_flight
            r = await result_queue.get()
            in_flight -= 1
            await self._process_result(r)

        # Disable GC during the hot scan loop to avoid stop-the-world pauses.
        # We manually collect at natural idle points (shuffle/restart/completion).
        gc.disable()

        # Outer loop: restarts streaming when shuffle is signaled
        while not scan_complete:
            if self._shutdown_event and self._shutdown_event.is_set():
                break

            # Clear shuffle signal for this iteration
            self.shuffle_signal.clear()

            shuffled = False

            # Choose streaming strategy
            if self.scan_strategy == "redis":
                ip_stream = self._stream_ips_redis_style()
            else:
                ip_stream = self._stream_ips_from_file()

            # Stream IPs and feed them one-by-one into the task pool.
            # Backpressure is applied per-IP so progress is smooth & continuous.
            async for ip_chunk in ip_stream:
                # Check for shutdown
                if self._shutdown_event and self._shutdown_event.is_set():
                    break

                # Check for shuffle signal - break to restart stream with new order
                if self.shuffle_signal.is_set():
                    shuffled = True
                    self._log("[cyan]Reshuffling IP stream order...[/cyan]")
                    break

                for ip in ip_chunk:
                    # ── Shutdown / shuffle / pause gates ──
                    if self._shutdown_event and self._shutdown_event.is_set():
                        break
                    if self.shuffle_signal.is_set():
                        shuffled = True
                        self._log("[cyan]Reshuffling IP stream order...[/cyan]")
                        break
                    await self.pause_event.wait()

                    # Drain any completed results — O(1) per result, no asyncio.wait
                    await _drain_results()

                    # ── Backpressure: wait until there is room for a new task ──
                    while in_flight >= max_outstanding:
                        if self._shutdown_event and self._shutdown_event.is_set():
                            break
                        if self.shuffle_signal.is_set():
                            shuffled = True
                            self._log("[cyan]Reshuffling IP stream order...[/cyan]")
                            break
                        await self.pause_event.wait()
                        await _wait_one()

                    if shuffled or (self._shutdown_event and self._shutdown_event.is_set()):
                        break

                    # ── Admit one new task ──
                    self._current_scanning_ip = ip
                    task = asyncio.create_task(_run_test(ip))
                    active_tasks_set.add(task)
                    task.add_done_callback(active_tasks_set.discard)
                    self.active_scan_tasks = active_tasks_set
                    in_flight += 1

                # Break outer stream if shuffle/shutdown detected
                if shuffled or (self._shutdown_event and self._shutdown_event.is_set()):
                    break

                await _drain_results()

            # Check if shuffle was signaled but stream ended before we caught it
            if not shuffled and self.shuffle_signal.is_set():
                shuffled = True
                self._log("[cyan]Reshuffling IP stream order (post-stream)...[/cyan]")

            if not shuffled:
                # Stream completed normally (no shuffle interrupt)
                scan_complete = True
            else:
                # Shuffle was requested — drain via queue then cancel stragglers
                if in_flight > 0:
                    self._log(f"[dim]Draining {in_flight} active tasks before reshuffle...[/dim]")
                    drain_end = asyncio.get_event_loop().time() + 5.0
                    while in_flight > 0:
                        remaining = drain_end - asyncio.get_event_loop().time()
                        if remaining <= 0:
                            break
                        try:
                            r = await asyncio.wait_for(result_queue.get(), timeout=remaining)
                            in_flight -= 1
                            await self._process_result(r)
                        except asyncio.TimeoutError:
                            break
                # Cancel tasks still running after timeout
                for task in list(active_tasks_set):
                    task.cancel()
                active_tasks_set.clear()
                in_flight = 0
                self.active_scan_tasks = []
                # Flush any leftover items pushed by tasks before they saw the cancel
                while not result_queue.empty():
                    result_queue.get_nowait()

                self._log(
                    f"[cyan]Restarting stream (skipping {len(self.tested_subnets)} completed /24 blocks)[/cyan]"
                )
                gc.collect()
                await asyncio.sleep(0)

        # Check if we're shutting down
        if self._shutdown_event and self._shutdown_event.is_set():
            self._log("[yellow]Scan interrupted - cleaning up...[/yellow]")
            gc.enable()
            gc.collect()
            if hasattr(self, "_sort_refresh_timer") and self._sort_refresh_timer:
                self._sort_refresh_timer.stop()
                self._sort_refresh_timer = None
            if hasattr(self, "_stats_refresh_timer") and self._stats_refresh_timer:
                self._stats_refresh_timer.stop()
                self._stats_refresh_timer = None
            # Cancel remaining tasks
            for task in list(active_tasks_set):
                if not task.done():
                    task.cancel()
            # Close shared HTTP client on early exit
            try:
                await self._http_client.aclose()
            except Exception:
                pass
            self._close_debug_log()
            return

        # Drain all remaining in-flight results from the queue
        gc.enable()
        gc.collect()
        self._log("[cyan]Finishing remaining scans...[/cyan]")
        drain_timeout = max(self.dns_timeout * 2, 10.0)
        while in_flight > 0:
            try:
                r = await asyncio.wait_for(result_queue.get(), timeout=drain_timeout)
                in_flight -= 1
                await self._process_result(r)
            except asyncio.TimeoutError:
                # Guard against tasks that crashed before enqueuing a result
                if not active_tasks_set or all(t.done() for t in active_tasks_set):
                    break

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
        if hasattr(self, "_stats_refresh_timer") and self._stats_refresh_timer:
            self._stats_refresh_timer.stop()
            self._stats_refresh_timer = None

        # Rebuild table at end to show final sorted results
        self.table_needs_rebuild = True
        self._rebuild_table()

        # Full garbage collection after scan completes
        gc.collect()

        # Update final statistics
        try:
            stats = self._stats_widget
            if stats is not None:
                active_paused = self._paused_elapsed
                elapsed = max(0.0, time.time() - self.start_time - active_paused)
                stats.update_stats(
                    scanned=self.current_scanned,
                    found=len(self.found_servers),
                    passed=self._passed_count,
                    failed=self._failed_count,
                    elapsed=elapsed,
                    speed=self.current_scanned / elapsed if elapsed > 0 else 0,
                    total=self.current_scanned,  # Set total to actual scanned count
                    bar_progress=float(self.current_scanned),
                    bar_total=float(self.current_scanned),  # Force 100%
                )
        except Exception as e:
            logger.debug(f"Could not update final statistics: {e}")

        # Final table rebuild
        self.table_needs_rebuild = True
        self._rebuild_table()

        # Wait for extra test tasks FIRST — they determine which DNS to skip
        if self.extra_test_tasks:
            num_extra = len(self.extra_test_tasks)
            self._log(
                f"[cyan]Waiting for {num_extra} extra tests to complete (max 60s)...[/cyan]"
            )
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.extra_test_tasks, return_exceptions=True),
                    timeout=60.0,
                )
            except asyncio.TimeoutError:
                self._log("[yellow]Timeout waiting for extra tests[/yellow]")
            self.table_needs_rebuild = True
            self._rebuild_table()

        # Wait for all pending proxy tests to complete
        if self.test_slipstream and self.slipstream_tasks:
            proto_name = getattr(self, "active_protocol", "slipstream")
            num_tasks = len(self.slipstream_tasks)
            # Scale timeout: each test can take up to proxy_timeout + overhead,
            # limited by semaphore concurrency.  Give generous per-batch time.
            per_batch_time = getattr(self, "slipstream_timeout", 15) + 10
            max_concurrent = getattr(self, "slipstream_max_concurrent", 3)
            batches = (num_tasks + max_concurrent - 1) // max_concurrent
            dynamic_timeout = max(120.0, batches * per_batch_time)
            self._log(
                f"[cyan]Waiting for {num_tasks} {proto_name} tests to complete "
                f"(max {dynamic_timeout:.0f}s)...[/cyan]"
            )
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.slipstream_tasks, return_exceptions=True),
                    timeout=dynamic_timeout,
                )
            except asyncio.TimeoutError:
                self._log(
                    f"[yellow]Timeout waiting for {proto_name} tests[/yellow]"
                )
            # Mark any remaining Pending/Testing as Skip so counts add up
            for ip in list(self.proxy_results):
                if self.proxy_results[ip] in ("Pending", "Testing"):
                    self.proxy_results[ip] = "Skip"
                    self._failed_count += 1
            self.table_needs_rebuild = True
            self._rebuild_table()  # Rebuild after all tests complete
            # Collect garbage after proxy tests complete
            gc.collect()

        # Auto-save results
        self._auto_save_results()

        # Revert OS MTU if we changed it
        self._revert_os_mtu()

        # Close debug log
        self._close_debug_log()

        self.notify("Scan complete! Results auto-saved.", severity="information")

        # Close shared HTTP client
        try:
            await self._http_client.aclose()
        except Exception:
            pass

    async def _test_dns_with_callback(
        self, ip: str, sem: asyncio.Semaphore
    ) -> tuple[str, bool, float]:
        """Test DNS and return result tuple."""
        # Wait if paused
        await self.pause_event.wait()
        return await self._test_dns(ip, sem)

    async def _process_result(self, result: tuple[str, bool, float]) -> None:
        """Process a single DNS test result."""
        # Block result processing while paused so UI appears frozen
        await self.pause_event.wait()
        if isinstance(result, tuple):
            ip, is_valid, response_time = result

            # Update scanned count (no longer tracking tested_ips for memory efficiency)
            self.current_scanned += 1

            # Periodic garbage collection to prevent memory buildup
            # (GC is disabled during the hot scan loop for performance)
            if self.current_scanned % 500 == 0:
                gc.collect()

            if is_valid:
                # Reset auto-shuffle counter when DNS found
                self.ips_since_last_found = 0

                # Add to found servers and table immediately
                self._add_result(ip, response_time)
                self._log(
                    f"[green]✓ Found DNS: {ip} ({response_time*1000:.0f}ms)[/green]"
                )
                self._debug_log(f"DNS_FOUND ip={ip} ping_ms={response_time*1000:.2f}")
                ping = f'{response_time*1000:.0f}'

                # Queue slipstream test if enabled (non-blocking)
                should_test_proxy = (
                    self.proxy_ping_threshold == 0
                    or int(ping) <= self.proxy_ping_threshold
                )
                if self.test_slipstream and should_test_proxy:
                    # Dedup: skip if already pending/testing/done for this IP
                    if ip in self.proxy_results and self.proxy_results[ip] in ("Pending", "Testing", "Pass", "Fail"):
                        self._debug_log(f"PROXY_TEST_SKIP_DUPLICATE ip={ip} status={self.proxy_results[ip]}")
                    else:
                        self.proxy_results[ip] = "Pending"
                        self._debug_log(f"PROXY_TEST_QUEUED ip={ip} ping_ms={ping}")
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

            # Stats updates are handled by the _tick_stats timer (0.5s interval)
            # Also do inline updates every 10 IPs or 0.1s for immediate feedback
            current_time = time.time()
            should_update = (
                self.current_scanned % 10 == 0 or
                (current_time - self.last_update_time) >= 0.1
            )
            if should_update:
                active_paused = self._paused_elapsed
                elapsed = max(0.0, current_time - self.start_time - active_paused)
                self.last_update_time = current_time
                try:
                    secure_cnt, normal_cnt, filtered_cnt = self._get_security_summary_counts()
                    stats = self._stats_widget
                    if stats is not None:
                        stats.update_stats(
                            scanned=self.current_scanned,
                            elapsed=elapsed,
                            speed=self.current_scanned / elapsed if elapsed > 0 else 0,
                            found=len(self.found_servers),
                            passed=self._passed_count,
                            failed=self._failed_count,
                            secure=secure_cnt,
                            normal=normal_cnt,
                            filtered=filtered_cnt,
                            current_ip=self._current_scanning_ip,
                            current_range=self._current_scanning_range,
                            bar_progress=float(self.current_scanned),
                            bar_total=float(stats.total),
                        )
                except Exception as e:
                    logger.debug(f"Could not update stats during scan: {e}")

            # Yield to UI event loop after each result
            await asyncio.sleep(0)

    async def _test_dns(
        self, ip: str, sem: asyncio.Semaphore
    ) -> tuple[str, bool, float]:
        """Test if IP is a DNS server using dnspython (inline async)."""
        async with sem:
            try:
                domain = self.domain
                if self.random_subdomain:
                    prefix = random.randbytes(4).hex()
                    domain = f"{prefix}.{domain}"

                resolver = dns.asyncresolver.Resolver(configure=False)
                resolver.nameservers = [ip]
                resolver.timeout = self.dns_timeout
                resolver.lifetime = self.dns_timeout

                start = time.time()
                try:
                    await resolver.resolve(domain, self.dns_type)
                    # Any return (including empty answer) means the server responded.
                    # Do NOT re-check elapsed here: dnspython already enforced
                    # resolver.lifetime internally.  Re-checking wall-clock time
                    # causes false-negatives at high concurrency because event-loop
                    # scheduling delays inflate the measured elapsed beyond the
                    # configured timeout even though the network round-trip was fine.
                    elapsed = time.time() - start
                    return (ip, True, elapsed)
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                    # Server responded with a DNS error — it IS a DNS server.
                    elapsed = time.time() - start
                    return (ip, True, elapsed)
                except dns.resolver.NoNameservers as e:
                    # Server sent FORMERR / NOTIMP / SERVFAIL — still alive.
                    elapsed = time.time() - start
                    errors = getattr(e, "errors", None) or []
                    if any(len(x) > 4 and x[4] is not None for x in errors):
                        return (ip, True, elapsed)
                    return (ip, False, 0.0)
                except (dns.exception.Timeout, asyncio.TimeoutError):
                    return (ip, False, 0.0)

            except Exception as exc:
                logger.debug(f"Unexpected error testing DNS {ip}: {exc}")
                return (ip, False, 0.0)

    def _get_security_summary_counts(self) -> tuple[int, int, int]:
        """Return (secure, normal, filtered) counts from security test results."""
        secure = 0
        normal = 0
        filtered = 0

        try:
            for sec in self.security_results.values():
                if not isinstance(sec, dict):
                    continue
                if sec.get("filtered"):
                    filtered += 1
                elif sec.get("dnssec") and not sec.get("hijacked"):
                    secure += 1
                else:
                    normal += 1
        except Exception:
            pass

        return secure, normal, filtered

    def _tick_stats(self) -> None:
        """Periodic stats refresh for smooth speed/scanned display."""
        if not hasattr(self, "start_time") or self.start_time <= 0:
            return
        # Freeze speed and elapsed when paused
        if self.is_paused:
            return
        try:
            active_paused = self._paused_elapsed
            elapsed = max(0.0, time.time() - self.start_time - active_paused)
            secure_cnt, normal_cnt, filtered_cnt = self._get_security_summary_counts()
            stats = self._stats_widget
            if stats is not None:
                total = stats.total
                stats.update_stats(
                    scanned=self.current_scanned,
                    elapsed=elapsed,
                    speed=self.current_scanned / elapsed if elapsed > 0 else 0,
                    found=len(self.found_servers),
                    passed=self._passed_count,
                    failed=self._failed_count,
                    secure=secure_cnt,
                    normal=normal_cnt,
                    filtered=filtered_cnt,
                    current_ip=getattr(self, "_current_scanning_ip", ""),
                    current_range=getattr(self, "_current_scanning_range", ""),
                    bar_progress=float(self.current_scanned),
                    bar_total=float(total),
                )
        except Exception:
            pass

    def _periodic_sort_refresh(self) -> None:
        """Periodic full table rebuild for sorted display."""
        try:
            if hasattr(self, "found_servers") and self.found_servers:
                self.table_needs_rebuild = True
                self._rebuild_table()
        except Exception:
            pass

    def _log(self, message: str) -> None:
        """Add message to log display."""
        try:
            log_widget = self.query_one("#log-display", RichLog)
            log_widget.write(message)
        except Exception as e:
            # Widget might not be ready or mounted yet - this is expected during startup
            logger.debug(f"Log widget not available: {e}")

    def _debug_log(self, message: str) -> None:
        """Write a timestamped line to the debug log file when debug_mode is on."""
        if not self.debug_mode:
            return
        f = self._debug_log_file
        if f is None:
            return
        ts = time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"
        try:
            f.write(f"[{ts}] {message}\n")
            f.flush()
        except Exception:
            pass

    def _close_debug_log(self) -> None:
        """Close the debug log file if it is open."""
        f = self._debug_log_file
        if f is not None:
            try:
                f.write("# --- session ended ---\n")
                f.close()
            except Exception:
                pass
            self._debug_log_file = None

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
