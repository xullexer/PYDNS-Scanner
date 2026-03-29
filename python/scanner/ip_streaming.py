"""IP streaming, counting and loading methods."""

from __future__ import annotations

import asyncio
import ipaddress
import mmap
import random
import socket
import struct
from typing import AsyncGenerator

from .constants import logger


class IPStreamingMixin:
    """Mixin for streaming IPs from CIDR files.

    Expected attributes on *self*:
        subnet_file, _shutdown_event, shuffle_signal, tested_subnets,
        total_ips_yielded, preset_max_ips, concurrency, scan_strategy
    """

    def _count_total_ips_fast(self, filepath: str) -> int:
        """Fast counting of total IPs in CIDR file without loading into memory."""
        total_ips = 0
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        try:
                            network = ipaddress.IPv4Network(line, strict=False)
                            if network.prefixlen >= 31:
                                total_ips += network.num_addresses
                            else:
                                total_ips += network.num_addresses - 2
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

    def _load_subnets(self) -> list[ipaddress.IPv4Network]:
        subnets = []
        logger.info(f"Loading subnets from {self.subnet_file}")
        try:
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
                            logger.debug(f"Skipping invalid CIDR: {line_str[:50]} - {e}")
        except (ValueError, OSError, mmap.error) as e:
            logger.warning(
                f"mmap failed for '{self.subnet_file}': {e}, falling back to regular reading"
            )
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
                                logger.debug(f"Skipping invalid CIDR: {line[:50]} - {e}")
            except (OSError, IOError) as e:
                logger.error(f"Failed to read subnet file '{self.subnet_file}': {e}")

        logger.info(f"Loaded {len(subnets)} subnets")
        return subnets

    async def _stream_ips_from_file(self) -> AsyncGenerator[list[str], None]:
        """Stream IPs from CIDR file using mmap for zero-copy reads."""
        chunk: list[str] = []
        chunk_size = max(4, min(16, self.concurrency // 4 if self.concurrency > 0 else 8))
        max_ips = self.preset_max_ips
        rng = random.Random()
        loop = asyncio.get_running_loop()

        def read_and_process():
            subnets = []
            try:
                with open(self.subnet_file, "r+b") as f:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        for raw in iter(mm.readline, b""):
                            line_str = raw.decode("utf-8", errors="ignore").strip()
                            if line_str and not line_str.startswith("#"):
                                try:
                                    subnets.append(
                                        ipaddress.IPv4Network(line_str, strict=False)
                                    )
                                except (
                                    ipaddress.AddressValueError,
                                    ipaddress.NetmaskValueError,
                                    ValueError,
                                ):
                                    pass
            except (OSError, mmap.error) as e:
                logger.warning(f"mmap read failed for '{self.subnet_file}': {e}, falling back")
                try:
                    with open(self.subnet_file, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                try:
                                    subnets.append(
                                        ipaddress.IPv4Network(line, strict=False)
                                    )
                                except (ValueError,):
                                    pass
                except (OSError, IOError) as e2:
                    logger.error(f"Failed to read subnet file: {e2}")
            return subnets

        subnets = await loop.run_in_executor(None, read_and_process)
        rng.shuffle(subnets)

        _pack = struct.pack
        _ntoa = socket.inet_ntoa

        for net in subnets:
            if self._shutdown_event and self._shutdown_event.is_set():
                break

            if net.prefixlen >= 24:
                chunks_24 = [net]
            else:
                chunks_24 = list(net.subnets(new_prefix=24))
            rng.shuffle(chunks_24)

            for subnet_chunk in chunks_24:
                subnet_key = int(subnet_chunk.network_address)
                if subnet_key in self.tested_subnets:
                    continue

                if hasattr(self, "_current_scanning_range"):
                    self._current_scanning_range = str(subnet_chunk)

                net_int = subnet_key
                num_addr = subnet_chunk.num_addresses

                if num_addr == 1:
                    chunk.append(_ntoa(_pack(">I", net_int)))
                    self.total_ips_yielded += 1
                elif subnet_chunk.prefixlen >= 31:
                    indices = list(range(num_addr))
                    rng.shuffle(indices)
                    for idx in indices:
                        chunk.append(_ntoa(_pack(">I", net_int + idx)))
                        self.total_ips_yielded += 1
                        if max_ips > 0 and self.total_ips_yielded >= max_ips:
                            break
                else:
                    host_count = num_addr - 2
                    start_int = net_int + 1
                    for idx in rng.sample(range(host_count), host_count):
                        chunk.append(_ntoa(_pack(">I", start_int + idx)))
                        self.total_ips_yielded += 1
                        if max_ips > 0 and self.total_ips_yielded >= max_ips:
                            break

                if not hasattr(self, '_pending_subnet_keys'):
                    self._pending_subnet_keys: list[int] = []
                self._pending_subnet_keys.append(subnet_key)

                if len(chunk) >= chunk_size:
                    yield chunk
                    for sk in self._pending_subnet_keys:
                        self.tested_subnets.add(sk)
                    self._pending_subnet_keys.clear()
                    chunk = []
                    await asyncio.sleep(0)

                if max_ips > 0 and self.total_ips_yielded >= max_ips:
                    if chunk:
                        yield chunk
                        for sk in self._pending_subnet_keys:
                            self.tested_subnets.add(sk)
                        self._pending_subnet_keys.clear()
                    return

            if max_ips > 0 and self.total_ips_yielded >= max_ips:
                if chunk:
                    yield chunk
                    for sk in self._pending_subnet_keys:
                        self.tested_subnets.add(sk)
                    self._pending_subnet_keys.clear()
                return

        if chunk:
            yield chunk
            for sk in getattr(self, '_pending_subnet_keys', []):
                self.tested_subnets.add(sk)
            if hasattr(self, '_pending_subnet_keys'):
                self._pending_subnet_keys.clear()

    async def _stream_ips_redis_style(self) -> AsyncGenerator[list[str], None]:
        """Stream IPs using Redis-style pincer (dual-direction) strategy."""
        chunk_size = max(4, min(16, self.concurrency // 4 if self.concurrency > 0 else 8))
        max_ips = self.preset_max_ips
        rng = random.Random()
        loop = asyncio.get_running_loop()

        def read_subnets():
            subnets = []
            try:
                with open(self.subnet_file, "r+b") as f:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        for raw in iter(mm.readline, b""):
                            line_str = raw.decode("utf-8", errors="ignore").strip()
                            if line_str and not line_str.startswith("#"):
                                try:
                                    subnets.append(
                                        ipaddress.IPv4Network(line_str, strict=False)
                                    )
                                except (
                                    ipaddress.AddressValueError,
                                    ipaddress.NetmaskValueError,
                                    ValueError,
                                ):
                                    pass
            except (OSError, mmap.error) as e:
                logger.warning(f"mmap read failed: {e}, falling back")
                try:
                    with open(self.subnet_file, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                try:
                                    subnets.append(
                                        ipaddress.IPv4Network(line, strict=False)
                                    )
                                except (ValueError,):
                                    pass
                except (OSError, IOError) as e2:
                    logger.error(f"Failed to read subnet file: {e2}")
            return subnets

        subnets = await loop.run_in_executor(None, read_subnets)

        all_blocks: list[ipaddress.IPv4Network] = []
        for net in subnets:
            if net.prefixlen >= 24:
                blocks = [net]
            else:
                blocks = list(net.subnets(new_prefix=24))
            for blk in blocks:
                if int(blk.network_address) not in self.tested_subnets:
                    all_blocks.append(blk)

        if not all_blocks:
            return

        rng.shuffle(all_blocks)

        num_lanes = min(max(1, self.concurrency), len(all_blocks))

        self._log(
            f"[cyan]Redis stream mode: {num_lanes} interleaved lanes "
            f"across {len(all_blocks)} /24 blocks[/cyan]"
        )

        lanes: list[list[ipaddress.IPv4Network]] = [[] for _ in range(num_lanes)]
        for idx, blk in enumerate(all_blocks):
            lanes[idx % num_lanes].append(blk)

        for lane_idx in range(1, len(lanes), 2):
            lanes[lane_idx].reverse()

        positions = [0] * len(lanes)
        batch: list[str] = []
        _pack = struct.pack
        _ntoa = socket.inet_ntoa
        _sample = random.sample

        while True:
            if self._shutdown_event and self._shutdown_event.is_set():
                break
            if self.shuffle_signal and self.shuffle_signal.is_set():
                break

            any_remaining = False

            for lane_idx, lane_blocks in enumerate(lanes):
                pos = positions[lane_idx]
                if pos >= len(lane_blocks):
                    continue

                any_remaining = True
                subnet_chunk = lane_blocks[pos]
                positions[lane_idx] = pos + 1

                subnet_key = int(subnet_chunk.network_address)
                if subnet_key in self.tested_subnets:
                    continue

                # Track current range for stats widget (no object alloc needed)
                if hasattr(self, "_current_scanning_range"):
                    self._current_scanning_range = str(subnet_chunk)

                net_int = subnet_key
                num_addr = subnet_chunk.num_addresses

                if num_addr == 1:
                    batch.append(_ntoa(_pack(">I", net_int)))
                    self.total_ips_yielded += 1
                elif subnet_chunk.prefixlen >= 31:
                    indices = list(range(num_addr))
                    rng.shuffle(indices)
                    for idx in indices:
                        batch.append(_ntoa(_pack(">I", net_int + idx)))
                        self.total_ips_yielded += 1
                        if max_ips > 0 and self.total_ips_yielded >= max_ips:
                            break
                else:
                    host_count = num_addr - 2
                    start_int = net_int + 1
                    for idx in _sample(range(host_count), host_count):
                        batch.append(_ntoa(_pack(">I", start_int + idx)))
                        self.total_ips_yielded += 1
                        if max_ips > 0 and self.total_ips_yielded >= max_ips:
                            break

                if not hasattr(self, '_pending_redis_keys'):
                    self._pending_redis_keys: list[int] = []
                self._pending_redis_keys.append(subnet_key)

                if len(batch) >= chunk_size:
                    yield batch
                    for sk in self._pending_redis_keys:
                        self.tested_subnets.add(sk)
                    self._pending_redis_keys.clear()
                    batch = []
                    await asyncio.sleep(0)

                if max_ips > 0 and self.total_ips_yielded >= max_ips:
                    if batch:
                        yield batch
                        for sk in self._pending_redis_keys:
                            self.tested_subnets.add(sk)
                        self._pending_redis_keys.clear()
                    return

            if not any_remaining:
                break

        if batch:
            yield batch
            for sk in getattr(self, '_pending_redis_keys', []):
                self.tested_subnets.add(sk)
            if hasattr(self, '_pending_redis_keys'):
                self._pending_redis_keys.clear()

    def _collect_ips(self, subnets: list[ipaddress.IPv4Network]) -> list[str]:
        """Collect all IPs from subnets in random order."""
        logger.info(f"Collecting IPs from {len(subnets)} subnets")
        all_ips: list[str] = []
        rng = random.Random()

        subnets_copy = list(subnets)
        rng.shuffle(subnets_copy)

        for net in subnets_copy:
            if net.prefixlen >= 24:
                chunks = [net]
            else:
                chunks = list(net.subnets(new_prefix=24))
            rng.shuffle(chunks)

            for chunk in chunks:
                if chunk.num_addresses == 1:
                    all_ips.append(str(chunk.network_address))
                else:
                    ips = list(chunk.hosts())
                    rng.shuffle(ips)
                    all_ips.extend([str(ip) for ip in ips])

        logger.info(f"Collected {len(all_ips)} IPs to scan")
        return all_ips
