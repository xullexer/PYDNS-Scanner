"""DNS worker pool — single background thread with ProactorEventLoop.

A single daemon thread runs one ``asyncio`` event loop:
- **Windows** → ``ProactorEventLoop`` (IOCP — no 64-socket ``select()`` cap).
- **Linux/macOS** → default event loop (``epoll`` / ``kqueue``).

Inside that loop the scan uses the exact same pattern as the original
single-loop code: ``asyncio.Semaphore`` for concurrency control,
``asyncio.create_task`` per IP, and ``asyncio.wait(FIRST_COMPLETED)``
for immediate result harvesting.

The main Textual thread communicates via two ``queue.Queue`` objects
(``ip_queue`` for input, ``result_queue`` for output).  This keeps
cross-thread overhead to the absolute minimum while removing the
Windows socket-count bottleneck.
"""

from __future__ import annotations

import asyncio
import queue
import random
import sys
import threading
import time
from typing import Optional

import dns.asyncresolver
import dns.exception
import dns.resolver

from .constants import logger


class DNSWorkerPool:
    """Single-thread async DNS pool — no socket limit on Windows.

    Architecture
    ~~~~~~~~~~~~
    * **One** daemon thread running its own ``asyncio`` event loop.
    * ``asyncio.Semaphore(concurrency)`` gates parallel DNS tasks
      (same pattern as the original single-loop scanner).
    * ``ip_queue`` feeds IPs from the main thread.
    * ``result_queue`` returns ``(ip, ok, elapsed)`` tuples.
    """

    def __init__(
        self,
        concurrency: int,
        domain: str,
        dns_type: str,
        dns_timeout: float,
        random_subdomain: bool,
    ) -> None:
        self.concurrency = concurrency
        self.domain = domain
        self.dns_type = dns_type
        self.dns_timeout = dns_timeout
        self.random_subdomain = random_subdomain

        # Thread-safe communication
        self.ip_queue: queue.Queue[Optional[str]] = queue.Queue()
        self.result_queue: queue.Queue[tuple[str, bool, float]] = queue.Queue()

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # not paused

        # Active-task counter (thread-safe)
        self._active_lock = threading.Lock()
        self._active_count: int = 0

    # ── Lifecycle ────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the single background worker thread."""
        self._stop_event.clear()
        self._pause_event.set()
        self._active_count = 0

        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="dns-worker",
        )
        self._thread.start()

        logger.info(
            f"DNS worker pool started: 1 thread, "
            f"semaphore concurrency={self.concurrency}"
        )

    def stop(self, timeout: float = 8.0) -> None:
        """Signal the worker to stop and wait for it to finish."""
        self._stop_event.set()
        self._pause_event.set()  # unblock if paused

        # Drain ip_queue so the worker unblocks from get()
        while not self.ip_queue.empty():
            try:
                self.ip_queue.get_nowait()
            except queue.Empty:
                break

        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def pause(self) -> None:
        self._pause_event.clear()

    def resume(self) -> None:
        self._pause_event.set()

    # ── Submitting work ─────────────────────────────────────────────────

    def submit_batch(self, ips: list[str] | tuple[str, ...]) -> None:
        for ip in ips:
            self.ip_queue.put(ip)

    # ── Collecting results ──────────────────────────────────────────────

    def get_results(self, max_results: int = 500) -> list[tuple[str, bool, float]]:
        """Non-blocking batch fetch of available results."""
        out: list[tuple[str, bool, float]] = []
        for _ in range(max_results):
            try:
                out.append(self.result_queue.get_nowait())
            except queue.Empty:
                break
        return out

    def drain_ip_queue(self) -> int:
        n = 0
        while True:
            try:
                self.ip_queue.get_nowait()
                n += 1
            except queue.Empty:
                break
        return n

    # ── Observability ───────────────────────────────────────────────────

    @property
    def total_concurrency(self) -> int:
        return self.concurrency

    @property
    def pending_ips(self) -> int:
        return self.ip_queue.qsize()

    @property
    def pending_results(self) -> int:
        return self.result_queue.qsize()

    @property
    def active_count(self) -> int:
        return self._active_count

    @property
    def is_idle(self) -> bool:
        return (
            self._active_count == 0
            and self.ip_queue.empty()
            and self.result_queue.empty()
        )

    # ── Internal ────────────────────────────────────────────────────────

    def _inc_active(self) -> None:
        with self._active_lock:
            self._active_count += 1

    def _dec_active(self) -> None:
        with self._active_lock:
            self._active_count -= 1

    def _run_loop(self) -> None:
        """Entry point for the single background thread."""
        # ProactorEventLoop on Windows → IOCP, no 64-socket select() limit.
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
        else:
            loop = asyncio.new_event_loop()

        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self._scan_loop())
        except Exception as exc:
            logger.error(f"dns-worker crashed: {exc}", exc_info=True)
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()

    async def _scan_loop(self) -> None:
        """Core async loop — mirrors the original single-loop scanner.

        Uses ``asyncio.Semaphore`` for concurrency and
        ``asyncio.wait(FIRST_COMPLETED)`` for immediate result
        harvesting — the exact pattern that achieved 160+ ip/sec.
        """
        sem = asyncio.Semaphore(self.concurrency)
        active: set[asyncio.Task] = set()
        max_outstanding = self.concurrency * 2

        while not self._stop_event.is_set():
            # ── Pause gate ──
            while not self._pause_event.is_set() and not self._stop_event.is_set():
                await asyncio.sleep(0.05)
            if self._stop_event.is_set():
                break

            # ── Pull IPs from queue ──
            batch: list[str] = []
            headroom = max_outstanding - len(active)
            if headroom > 0:
                for _ in range(headroom):
                    try:
                        batch.append(self.ip_queue.get_nowait())
                    except queue.Empty:
                        break

            # If nothing queued and nothing in-flight, block briefly
            if not batch and not active:
                try:
                    batch.append(self.ip_queue.get(timeout=0.05))
                except queue.Empty:
                    continue

            # ── Create tasks (semaphore-guarded, like original) ──
            for ip in batch:
                task = asyncio.create_task(self._test_dns_sem(ip, sem))
                active.add(task)

            # ── Harvest completed — FIRST_COMPLETED for minimum latency ──
            if active:
                done, active = await asyncio.wait(
                    active,
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=0.1,
                )
                for t in done:
                    try:
                        self.result_queue.put_nowait(t.result())
                    except Exception:
                        pass

        # ── Drain remaining tasks on shutdown ──
        if active:
            done, pending = await asyncio.wait(
                active, timeout=self.dns_timeout + 2
            )
            for t in done:
                try:
                    self.result_queue.put_nowait(t.result())
                except Exception:
                    pass
            for t in pending:
                t.cancel()

    async def _test_dns_sem(
        self, ip: str, sem: asyncio.Semaphore
    ) -> tuple[str, bool, float]:
        """Semaphore-guarded wrapper (mirrors original ``_test_dns``)."""
        async with sem:
            return await self._test_dns(ip)

    async def _test_dns(self, ip: str) -> tuple[str, bool, float]:
        """Test whether *ip* is a working DNS server."""
        self._inc_active()
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
                elapsed = time.time() - start
                return (ip, True, elapsed) if elapsed < self.dns_timeout else (ip, False, 0.0)
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                # Server responded — it is alive.
                elapsed = time.time() - start
                return (ip, True, elapsed) if elapsed < self.dns_timeout else (ip, False, 0.0)
            except dns.resolver.NoNameservers as e:
                # Server sent FORMERR / NOTIMP / etc. — still alive.
                elapsed = time.time() - start
                errors = getattr(e, "errors", None) or []
                if any(len(x) > 4 and x[4] is not None for x in errors) and elapsed < self.dns_timeout:
                    return (ip, True, elapsed)
                return (ip, False, 0.0)
            except (dns.exception.Timeout, asyncio.TimeoutError):
                return (ip, False, 0.0)

        except Exception as exc:
            logger.debug(f"DNS test error {ip}: {exc}")
            return (ip, False, 0.0)
        finally:
            self._dec_active()
