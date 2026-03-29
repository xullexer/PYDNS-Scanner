"""ISP detection — built-in Iranian ISP lookup table.

Uses a hardcoded CIDR→ISP mapping covering all major Iranian providers, so
ISP names appear instantly on the very first run with zero network requests.
A JSON cache file is still loaded as a supplementary source if it exists.
"""

from __future__ import annotations

import ipaddress
import json
from pathlib import Path

from .constants import logger

# ---------------------------------------------------------------------------
# Built-in Iranian ISP CIDR → name mapping
# ---------------------------------------------------------------------------
# Each entry is ("CIDR", "Short ISP name").
# Ranges are compiled from public BGP/RIPE data and cover the iran-ipv4.cidrs
# file shipped with the project.  The table is converted to integer intervals
# once at import time for O(log n) binary-search lookup.
# ---------------------------------------------------------------------------

_BUILTIN_ISP_ENTRIES: list[tuple[str, str]] = [
    # ── MCI (Mobile Communication Company of Iran) — AS197207 ───────
    ("2.176.0.0/12", "MCI"),
    ("5.112.0.0/12", "MCI"),
    ("5.72.0.0/15", "MCI"),
    ("5.74.0.0/16", "MCI"),
    ("5.75.0.0/17", "MCI"),
    ("5.190.0.0/16", "MCI"),
    ("5.106.0.0/16", "MCI"),
    ("37.98.0.0/17", "MCI"),
    ("37.137.0.0/16", "MCI"),
    ("37.221.0.0/18", "MCI"),
    ("80.242.0.0/20", "MCI"),
    ("80.210.0.0/16", "MCI"),
    ("91.227.246.0/24", "MCI"),
    ("91.251.0.0/16", "MCI"),
    ("92.42.48.0/21", "MCI"),
    ("93.88.64.0/21", "MCI"),
    ("151.232.0.0/14", "MCI"),
    ("151.238.0.0/15", "MCI"),
    ("164.215.128.0/17", "MCI"),
    ("172.80.128.0/17", "MCI"),

    # ── Irancell (MTN Irancell) — AS44244 ───────────────────────────
    ("5.52.0.0/16", "Irancell"),
    ("5.53.32.0/19", "Irancell"),
    ("5.125.0.0/16", "Irancell"),
    ("5.126.0.0/16", "Irancell"),
    ("5.127.0.0/16", "Irancell"),
    ("37.32.0.0/14", "Irancell"),
    ("37.130.200.0/21", "Irancell"),
    ("37.148.0.0/16", "Irancell"),
    ("37.156.106.0/23", "Irancell"),
    ("37.156.110.0/23", "Irancell"),
    ("93.119.32.0/19", "Irancell"),
    ("100.64.0.0/13", "Irancell"),
    ("113.203.0.0/17", "Irancell"),
    ("119.235.0.0/17", "Irancell"),
    ("158.58.0.0/17", "Irancell"),

    # ── ITC (Information Technology Company / IRITCO) — AS12880 ─────
    ("2.144.0.0/14", "ITC"),
    ("5.200.64.0/18", "ITC"),
    ("5.200.128.0/17", "ITC"),
    ("5.201.128.0/17", "ITC"),
    ("5.208.0.0/13", "ITC"),
    ("5.232.0.0/13", "ITC"),
    ("78.38.0.0/15", "ITC"),
    ("80.191.0.0/16", "ITC"),
    ("85.185.0.0/16", "ITC"),
    ("85.133.0.0/16", "ITC"),
    ("85.15.0.0/16", "ITC"),
    ("109.162.128.0/17", "ITC"),
    ("130.255.192.0/18", "ITC"),
    ("188.0.240.0/20", "ITC"),
    ("217.218.0.0/15", "ITC"),

    # ── TCI (Iran Telecommunication Company) — AS58224 ──────────────
    ("2.178.0.0/16", "TCI"),
    ("2.186.0.0/15", "TCI"),
    ("5.22.0.0/17", "TCI"),
    ("37.130.0.0/16", "TCI"),
    ("37.254.0.0/15", "TCI"),
    ("77.81.32.0/20", "TCI"),
    ("77.81.144.0/20", "TCI"),

    # ── Rightel — AS57218 ───────────────────────────────────────────
    ("5.159.48.0/21", "Rightel"),
    ("5.198.160.0/19", "Rightel"),
    ("77.81.192.0/19", "Rightel"),
    ("93.88.72.0/21", "Rightel"),

    # ── Shatel — AS31549 ───────────────────────────────────────────
    ("2.57.3.0/24", "Shatel"),  # also ITC — Shatel is the retail brand
    ("5.22.192.0/21", "Shatel"),
    ("5.22.200.0/22", "Shatel"),
    ("5.56.128.0/21", "Shatel"),
    ("31.56.0.0/14", "Shatel"),
    ("46.224.0.0/15", "Shatel"),
    ("78.157.32.0/19", "Shatel"),
    ("84.241.0.0/18", "Shatel"),
    ("94.182.0.0/15", "Shatel"),

    # ── Asiatech — AS43754 ─────────────────────────────────────────
    ("5.134.128.0/18", "Asiatech"),
    ("5.250.0.0/17", "Asiatech"),
    ("37.49.144.0/20", "Asiatech"),
    ("79.127.0.0/17", "Asiatech"),
    ("89.36.96.0/19", "Asiatech"),
    ("94.183.0.0/17", "Asiatech"),
    ("176.65.192.0/18", "Asiatech"),

    # ── Pars Online (POL) — AS16322 ────────────────────────────────
    ("5.202.0.0/16", "ParsOnline"),
    ("31.2.128.0/17", "ParsOnline"),
    ("46.209.0.0/16", "ParsOnline"),
    ("91.108.128.0/17", "ParsOnline"),
    ("91.185.128.0/17", "ParsOnline"),
    ("188.253.0.0/18", "ParsOnline"),
    ("213.233.160.0/19", "ParsOnline"),

    # ── Respina — AS42337 ──────────────────────────────────────────
    ("5.63.8.0/21", "Respina"),
    ("5.63.23.0/24", "Respina"),
    ("77.104.64.0/18", "Respina"),
    ("77.237.64.0/19", "Respina"),

    # ── Mobinnet — AS50810 ─────────────────────────────────────────
    ("5.23.112.0/21", "Mobinnet"),
    ("37.156.0.0/22", "Mobinnet"),
    ("46.100.0.0/16", "Mobinnet"),
    ("78.158.160.0/19", "Mobinnet"),
    ("176.123.64.0/18", "Mobinnet"),

    # ── Afranet — AS25152 ──────────────────────────────────────────
    ("5.34.192.0/20", "Afranet"),
    ("37.156.16.0/20", "Afranet"),
    ("46.41.192.0/18", "Afranet"),
    ("78.109.192.0/20", "Afranet"),
    ("79.175.128.0/18", "Afranet"),
    ("80.75.0.0/20", "Afranet"),
    ("185.4.0.0/22", "Afranet"),

    # ── PishgamanToseworeh (PTEC) — AS44208 ────────────────────────
    ("77.237.160.0/19", "Pishgaman"),
    ("79.132.208.0/20", "Pishgaman"),

    # ── Fanava — AS48159 ───────────────────────────────────────────
    ("46.34.96.0/21", "Fanava"),
    ("46.62.128.0/17", "Fanava"),
    ("185.8.172.0/22", "Fanava"),

    # ── Dade Samane (DadeParadaz) — AS62442 ─────────────────────────
    ("78.157.60.0/22", "DadeSamane"),

    # ── Zi-Tel — AS48434 ───────────────────────────────────────────
    ("5.62.160.0/19", "ZiTel"),
    ("5.62.192.0/18", "ZiTel"),

    # ── Rayaneh Kamangar (RayKam) — AS48551 ────────────────────────
    ("31.7.64.0/20", "RayKam"),
    ("212.80.0.0/19", "RayKam"),

    # ── AbrArvan (ArvanCloud) — AS202468 ────────────────────────────
    ("185.143.232.0/22", "ArvanCloud"),

    # ── Tose'h Fanavari Pasargad / TIC — AS24631 ───────────────────
    ("78.154.32.0/19", "Pasargad"),
    ("80.71.112.0/20", "Pasargad"),

    # ── Sabanet — AS56402 ──────────────────────────────────────────
    ("93.110.0.0/16", "Sabanet"),
    ("93.115.224.0/19", "Sabanet"),

    # ── Tebyan — AS56503 ──────────────────────────────────────────
    ("94.184.0.0/16", "Tebyan"),

    # ── Neda Gostar Saba (Saba) — AS49100 ──────────────────────────
    ("5.104.208.0/21", "SabaNet"),
    ("5.144.128.0/21", "SabaNet"),

    # ── Rayaneh Gostar Tehran — AS39501 ────────────────────────────
    ("31.14.80.0/20", "RayGostar"),
    ("91.92.208.0/21", "RayGostar"),

    # ── Datak — AS49666 ────────────────────────────────────────────
    ("37.19.80.0/20", "Datak"),
    ("37.156.144.0/22", "Datak"),

    # ── HiWEB — AS25184 ────────────────────────────────────────────
    ("5.216.0.0/14", "HiWEB"),
    ("5.220.0.0/15", "HiWEB"),
    ("37.44.0.0/18", "HiWEB"),
    ("37.129.0.0/16", "HiWEB"),
    ("93.118.96.0/19", "HiWEB"),

    # ── ApTel (Aptec) — AS199654 ───────────────────────────────────
    ("5.145.112.0/21", "ApTel"),

    # ── Pernet — AS47262 ──────────────────────────────────────────
    ("91.186.192.0/18", "Pernet"),
    ("176.102.224.0/19", "Pernet"),

    # ── ParsData (Haraz / Didehban Net) — AS56611 ──────────────────
    ("31.47.32.0/19", "ParsData"),
    ("185.3.200.0/22", "ParsData"),

    # ── AsiaTek / DPI — AS56568 ────────────────────────────────────
    ("37.156.48.0/20", "AsiaTek"),

    # ── ChaparNet — AS48551 ────────────────────────────────────────
    ("91.147.64.0/20", "ChaparNet"),

    # ── Andishe Sabz Khazar — AS48309 ──────────────────────────────
    ("5.57.32.0/21", "ASK"),
    ("185.2.12.0/22", "ASK"),

    # ── Fanap (Telecom) — AS48431 ──────────────────────────────────
    ("185.3.124.0/22", "Fanap"),

    # ── Catch-all for common ranges ────────────────────────────────
    ("5.1.43.0/24", "Iran"),
    ("95.38.0.0/16", "Iran"),
    ("95.162.0.0/16", "Iran"),
]

def _build_builtin_table() -> list[tuple[int, int, str]]:
    """Convert CIDR strings to sorted integer intervals for binary search."""
    table: list[tuple[int, int, str]] = []
    for cidr, isp in _BUILTIN_ISP_ENTRIES:
        try:
            net = ipaddress.IPv4Network(cidr, strict=False)
            table.append((int(net.network_address), int(net.broadcast_address), isp))
        except ValueError:
            pass
    # Sort by start address; for overlapping ranges, narrower first (smaller range)
    table.sort(key=lambda t: (t[0], t[1] - t[0]))
    return table

_BUILTIN_TABLE: list[tuple[int, int, str]] = _build_builtin_table()


class ISPCacheMixin:
    """Mixin for ISP detection — instant built-in table + optional JSON cache.

    The built-in table covers all major Iranian ISPs and requires zero network
    calls or file I/O.  If a JSON cache file exists it is merged in to fill
    gaps, but it is no longer *required*.
    """

    # Class-level cache shared by all instances: (start, end, org, asn)
    _ISP_TABLE: list[tuple[int, int, str, str]] | None = None

    def _get_isp_table(self) -> list[tuple[int, int, str, str]]:
        """Return (and cache) a sorted list of (start_int, end_int, org, asn).

        Merges the built-in table with any JSON cache entries.
        """
        if ISPCacheMixin._ISP_TABLE is not None:
            return ISPCacheMixin._ISP_TABLE

        # Start with the built-in table (always available)
        table: list[tuple[int, int, str, str]] = [
            (s, e, name, "") for s, e, name in _BUILTIN_TABLE
        ]

        # Merge JSON cache entries if the file exists
        try:
            cache_path = getattr(self, "_isp_cache_path", None)
            if cache_path and Path(str(cache_path)).exists():
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                for entry in cache_data.get("entries", []):
                    cidr = entry.get("cidr", "")
                    org = entry.get("org", "")
                    asn = entry.get("asn", "")
                    if not org or org in ("-", "Unknown"):
                        continue
                    try:
                        net = ipaddress.IPv4Network(cidr, strict=False)
                        table.append(
                            (int(net.network_address), int(net.broadcast_address), org, asn)
                        )
                    except (ValueError, TypeError):
                        pass
                logger.info(f"Merged JSON ISP cache from {cache_path}")
        except Exception as e:
            logger.debug(f"No JSON ISP cache loaded: {e}")

        table.sort(key=lambda t: (t[0], t[1] - t[0]))
        ISPCacheMixin._ISP_TABLE = table
        logger.info(f"ISP lookup table ready: {len(table)} entries (built-in + cache)")
        return table

    @staticmethod
    def _lookup_isp_builtin(ip_str: str) -> str:
        """Fast O(log n) lookup against the built-in table only."""
        try:
            ip_int = int(ipaddress.IPv4Address(ip_str))
        except (ValueError, TypeError):
            return ""
        table = _BUILTIN_TABLE
        lo, hi = 0, len(table) - 1
        best = ""
        while lo <= hi:
            mid = (lo + hi) // 2
            start, end, name = table[mid]
            if ip_int < start:
                hi = mid - 1
            elif ip_int > end:
                lo = mid + 1
            else:
                # Found a match — but prefer the narrowest (most specific) range
                best = name
                # Search for a more specific match (narrower range to the right)
                lo = mid + 1
        return best

    async def _ensure_isp_cache(self) -> None:
        """Pre-warm the ISP table. No network calls needed anymore."""
        # Just prime the table — it uses the built-in data instantly
        self._get_isp_table()
        logger.info("ISP lookup table initialized (built-in data)")
