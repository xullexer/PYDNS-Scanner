"""Proxy (slipstream) testing mixin."""

from __future__ import annotations

import asyncio
import time

import httpx
from rich.markup import escape as markup_escape

from .constants import logger
from .utils import _run_tunnel_sync


class ProxyTestingMixin:
    """Mixin providing slipstream / slipnet proxy testing methods.

    Expected attributes on *self*:
        slipstream_semaphore, available_ports, slipstream_manager,
        slipstream_domain, proxy_results, proxy_auth_enabled,
        proxy_username, proxy_password, slipstream_timeout,
        proxy_test_url, slipstream_processes, slipstream_tasks,
        bell_sound_enabled, _stats_widget, _passed_count, _failed_count,
        table_needs_rebuild,
        active_protocol, slipnet_manager, slipnet_url,
        min_dns_type_score, proxy_test_retries
    """

    async def _queue_slipstream_test(self, dns_ip: str) -> None:
        """Queue and run slipstream/slipnet test with semaphore for max concurrent tests."""
        # Block while scan is paused
        await self.pause_event.wait()
        protocol = getattr(self, "active_protocol", "slipstream")

        # Wait for DNS type test to complete BEFORE acquiring a proxy slot.
        # Timeout after 90 s in case extra tests never populate the entry.
        for _ in range(900):
            if dns_ip in self.dns_types_results:
                break
            await asyncio.sleep(0.1)

        # Early exit: already flagged for skip
        if self.proxy_results.get(dns_ip) == "Skip":
            return

        # Skip low DNS-type scores using configurable threshold.
        # 0 means use default threshold (4).
        min_score_cfg = int(getattr(self, "min_dns_type_score", 0) or 0)
        min_score = 4 if min_score_cfg == 0 else max(1, min(6, min_score_cfg))
        dns_types = self.dns_types_results.get(dns_ip, {})
        dns_score = sum(1 for v in dns_types.values() if v)
        if dns_types and dns_score < min_score:
            self.proxy_results[dns_ip] = "Skip"
            self._log(
                f"[yellow]⚠ {dns_ip}: DNS type score {dns_score}/6 < {min_score} "
                f"→ skipping proxy test[/yellow]"
            )
            self._update_table_row(dns_ip)
            return

        async with self.slipstream_semaphore:
            # Re-check after waiting for semaphore slot
            if self.proxy_results.get(dns_ip) == "Skip":
                return

            while not self.available_ports:
                await asyncio.sleep(0.1)

            port = self.available_ports.popleft()

            try:
                attempts = max(1, min(5, int(getattr(self, "proxy_test_retries", 1) or 1)))
                self.proxy_results[dns_ip] = "Testing"
                self._update_table_row(dns_ip)
                self._log(f"[cyan]Testing {dns_ip} with {protocol} on port {port}...[/cyan]")

                result: str = "Failed"
                proxy_latency: float | None = None

                for attempt in range(1, attempts + 1):
                    if attempt > 1:
                        self._log(
                            f"[yellow]{dns_ip}: proxy test retry {attempt}/{attempts} "
                            f"— restarting tunnel…[/yellow]"
                        )
                        await asyncio.sleep(2.0)
                        self.proxy_results[dns_ip] = "Testing"
                        self._update_table_row(dns_ip)

                    result, proxy_latency = await self._test_slipstream_proxy(dns_ip, port)

                    if result == "Success":
                        break

                if result == "Success" and proxy_latency is not None:
                    self.proxy_results[dns_ip] = f"Success|{proxy_latency:.0f}ms"
                else:
                    self.proxy_results[dns_ip] = result

                if result == "Success":
                    self._passed_count += 1
                elif result == "Failed":
                    self._failed_count += 1

                try:
                    stats = self._stats_widget
                    if stats is not None:
                        stats.update_stats(
                            passed=self._passed_count, failed=self._failed_count
                        )
                except Exception as e:
                    logger.debug(f"Could not update stats after proxy test: {e}")

                if result == "Success":
                    ping_str = f" ({proxy_latency:.0f}ms)" if proxy_latency else ""
                    self._log(f"[green]✓ Proxy test PASSED: {dns_ip}{ping_str}[/green]")
                    if self.bell_sound_enabled:
                        from .utils import _play_bell_sound
                        _play_bell_sound()
                else:
                    self._log(f"[red]✗ Proxy test FAILED: {dns_ip} (all {attempts} attempt(s) exhausted)[/red]")

                # Always trigger a sort rebuild so Success rows move to top
                # and Failed/Skip rows rank correctly below in-progress rows
                self.table_needs_rebuild = True
                self._update_table_row(dns_ip)

            except asyncio.CancelledError:
                # Scan was cancelled — never leave proxy stuck at "Testing"
                if self.proxy_results.get(dns_ip) in ("Testing", "Pending"):
                    self.proxy_results[dns_ip] = "Failed"
                raise
            except Exception as exc:
                logger.error(f"[{dns_ip}] Unexpected error in proxy queue: {exc}", exc_info=True)
                if self.proxy_results.get(dns_ip) in ("Testing", "Pending"):
                    self.proxy_results[dns_ip] = "Failed"
                self.table_needs_rebuild = True
                self._update_table_row(dns_ip)
            finally:
                self.available_ports.append(port)

    async def _test_slipstream_proxy(
        self, dns_ip: str, port: int
    ) -> tuple[str, float | None]:
        """Test DNS server using slipstream proxy on a specific port.

        Returns:
            ("Success", latency_ms) if proxy works, ("Failed", None) otherwise
        """
        process = None
        protocol = getattr(self, "active_protocol", "slipstream")
        self._log(f"[dim]Starting {protocol} proxy test for {dns_ip} on port {port}\u2026[/dim]")
        self._debug_log(f"PROXY_TEST_START ip={dns_ip} protocol={protocol} port={port}")
        try:
            if protocol == "slipnet":
                cmd = self.slipnet_manager.get_run_command(
                    dns_ip, port, self.slipnet_url,
                    query_size=getattr(self, "slipnet_query_size", 0),
                )
                ready_string = "Connected!"
            else:
                cmd = self.slipstream_manager.get_run_command(
                    dns_ip, port, self.slipstream_domain
                )
                ready_string = "Connection ready"

            logger.info(f"[{dns_ip}] Starting {protocol} on port {port}")
            logger.debug(f"[{dns_ip}] Command: {' '.join(cmd)}")
            self._debug_log(f"TUNNEL_CMD ip={dns_ip} cmd={' '.join(cmd)}")
            self._debug_log(f"TUNNEL_READY_STRING ip={dns_ip} ready_string={ready_string!r} timeout={getattr(self, 'slipstream_timeout', '?')}s")

            process, connection_ready, output_lines = await asyncio.to_thread(
                _run_tunnel_sync, cmd, self.slipstream_timeout, ready_string
            )

            logger.debug(
                f"[{dns_ip}] {protocol} thread returned, PID={process.pid}, "
                f"connection_ready={connection_ready}, lines={len(output_lines)}"
            )
            self._debug_log(
                f"TUNNEL_DONE ip={dns_ip} pid={process.pid} "
                f"connection_ready={connection_ready} output_lines={len(output_lines)}"
            )

            for i, line in enumerate(output_lines):
                logger.debug(f"[{dns_ip}] {protocol}: {line}")
                self._debug_log(f"TUNNEL_OUTPUT[{i}] ip={dns_ip} line={line!r}")
                if "Listening on TCP port" in line or "SOCKS5 proxy listening" in line:
                    self._log(f"[dim]{dns_ip}: {markup_escape(line)}[/dim]")
                elif "WARN" in line or "ERR" in line:
                    self._log(f"[yellow]{dns_ip}: {markup_escape(line)}[/yellow]")

            self.slipstream_processes.append(process)

            if not connection_ready:
                if not output_lines:
                    reason = "no_output (binary crashed or not found)"
                    logger.warning(f"[{dns_ip}] {protocol} produced no output")
                    self._log(
                        f"[red]{dns_ip}: {protocol} produced no output (crashed?)[/red]"
                    )
                else:
                    reason = f"timeout_after_{getattr(self, 'slipstream_timeout', '?')}s (ready_string not seen)"
                    logger.warning(
                        f"[{dns_ip}] {protocol} connection timeout after {self.slipstream_timeout}s"
                    )
                    self._log(
                        f"[yellow]{dns_ip}: No tunnel established via this DNS "
                        f"({self.slipstream_timeout}s timeout)[/yellow]"
                    )
                self._debug_log(f"TUNNEL_FAIL ip={dns_ip} reason={reason}")
                return ("Failed", None)

            logger.info(f"[{dns_ip}] {protocol} connected on port {port}")
            self._log(f"[cyan]{dns_ip}: {protocol} connected on port {port}[/cyan]")
            self._debug_log(f"TUNNEL_CONNECTED ip={dns_ip} protocol={protocol} port={port}")

            logger.debug(f"[{dns_ip}] Waiting 2.5s for proxy to fully initialize")
            await asyncio.sleep(2.5)

            test_success = False
            proxy_latency_ms: float | None = None

            # Build SOCKS5 proxy URL.
            # - Slipstream SOCKS5 mode: user-provided credentials for the local proxy.
            # - Slipstream SSH mode: SSH auth is for the remote tunnel only;
            #   the local proxy is no-auth (proxy_auth_enabled=False for SSH mode).
            # - SlipNet v2.4.1: auth handled internally via slipnet:// URI, always no-auth.
            if getattr(self, "proxy_auth_enabled", False) and getattr(self, "proxy_username", ""):
                from urllib.parse import quote
                encoded_user = quote(self.proxy_username, safe="")
                encoded_pass = quote(getattr(self, "proxy_password", ""), safe="")
                socks5_url = f"socks5://{encoded_user}:{encoded_pass}@127.0.0.1:{port}"
                socks5_url_log = f"socks5://{self.proxy_username}:****@127.0.0.1:{port}"
            else:
                socks5_url = f"socks5://127.0.0.1:{port}"
                socks5_url_log = socks5_url

            TEST_URL = self.proxy_test_url
            # Always accept 200 (google.com) and 204 (generate_204) alongside redirects
            _success_code = getattr(self, "proxy_success_code", 200)
            SUCCESS_CODES = (200, 204, _success_code, 301, 302, 307, 308)

            self._debug_log(f"SOCKS5_URL ip={dns_ip} url={socks5_url_log}")
            self._debug_log(f"TEST_URL ip={dns_ip} url={TEST_URL}")
            self._debug_log(f"SUCCESS_CODES ip={dns_ip} codes={SUCCESS_CODES}")

            # Single SOCKS5 attempt per call — the retry loop that restarts
            # the full tunnel lives in _queue_slipstream_test, so each retry
            # gets a brand-new tunnel process and a clean port state.
            logger.info(f"[{dns_ip}] Testing SOCKS5 proxy at {socks5_url_log}")
            hard_timeout = self.slipstream_timeout + 5
            self._debug_log(
                f"SOCKS5_HARD_TIMEOUT ip={dns_ip} "
                f"hard_timeout={hard_timeout}s inner_timeout={self.slipstream_timeout}s"
            )

            socks_client = None
            start_time = time.time()
            try:
                async def _do_socks5_test():
                    nonlocal socks_client
                    socks_client = httpx.AsyncClient(
                        proxy=socks5_url,
                        timeout=self.slipstream_timeout,
                        follow_redirects=True,
                        verify=False,
                    )
                    try:
                        return await socks_client.get(TEST_URL)
                    finally:
                        await socks_client.aclose()
                        socks_client = None

                response = await asyncio.wait_for(_do_socks5_test(), timeout=hard_timeout)
                elapsed = time.time() - start_time
                logger.debug(
                    f"[{dns_ip}] SOCKS5 proxy status={response.status_code} "
                    f"in {elapsed:.2f}s"
                )
                self._debug_log(
                    f"SOCKS5_RESPONSE ip={dns_ip} status={response.status_code} "
                    f"elapsed={elapsed:.3f}s elapsed_ms={elapsed*1000:.0f}ms expected_codes={SUCCESS_CODES} "
                    f"result={'PASS' if response.status_code in SUCCESS_CODES else 'FAIL_WRONG_STATUS'}"
                )
                if response.status_code in SUCCESS_CODES:
                    test_success = True
                    proxy_latency_ms = elapsed * 1000
                    logger.info(
                        f"[{dns_ip}] SOCKS5 proxy test PASSED "
                        f"(status {response.status_code}, {elapsed:.2f}s)"
                    )
                    self._log(
                        f"[green]{dns_ip}: SOCKS5 proxy test passed "
                        f"(status {response.status_code})[/green]"
                    )
                else:
                    logger.warning(
                        f"[{dns_ip}] SOCKS5 proxy unexpected status: "
                        f"{response.status_code}"
                    )
            except asyncio.TimeoutError:
                elapsed = time.time() - start_time
                logger.error(
                    f"[{dns_ip}] SOCKS5 proxy test timed out after {elapsed:.1f}s"
                )
                self._debug_log(
                    f"SOCKS5_TIMEOUT ip={dns_ip} elapsed={elapsed:.3f}s "
                    f"hard_timeout={hard_timeout}s reason=asyncio.TimeoutError"
                )
                self._log(f"[red]{dns_ip}: SOCKS5 proxy test timed out after {elapsed:.1f}s[/red]")
            except Exception as socks_err:
                elapsed = time.time() - start_time
                logger.error(
                    f"[{dns_ip}] SOCKS5 proxy test failed: "
                    f"{type(socks_err).__name__}: {socks_err}"
                )
                self._debug_log(
                    f"SOCKS5_EXCEPTION ip={dns_ip} elapsed={elapsed:.3f}s "
                    f"type={type(socks_err).__name__} msg={socks_err!r}"
                )
                self._log(f"[red]{dns_ip}: SOCKS5 proxy test failed[/red]")
            finally:
                if socks_client is not None:
                    try:
                        await socks_client.aclose()
                    except Exception:
                        pass

            final_result = "Success" if test_success else "Failed"
            logger.info(f"[{dns_ip}] Final result: {final_result}")
            self._debug_log(
                f"PROXY_TEST_FINAL ip={dns_ip} result={final_result} "
                f"latency_ms={proxy_latency_ms:.0f}" if proxy_latency_ms else
                f"PROXY_TEST_FINAL ip={dns_ip} result={final_result} latency_ms=None"
            )
            return (final_result, proxy_latency_ms)

        except Exception as e:
            logger.error(
                f"[{dns_ip}] Tunnel error: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            self._debug_log(f"TUNNEL_EXCEPTION ip={dns_ip} type={type(e).__name__} msg={str(e)!r}")
            self._log(
                f"[red]Tunnel error for {dns_ip}: "
                f"{type(e).__name__}: {markup_escape(str(e))}[/red]"
            )
            return ("Failed", None)
        finally:
            if process:
                try:
                    process.kill()
                    await asyncio.to_thread(process.wait)
                    if process in self.slipstream_processes:
                        self.slipstream_processes.remove(process)
                except (ProcessLookupError, OSError) as e:
                    logger.debug(f"Process cleanup for {dns_ip}: {e}")
                finally:
                    # IMPORTANT: explicitly close inherited pipe handles.
                    # On long scans, relying on GC can leak enough descriptors
                    # to hit Windows select() limits (too many file descriptors).
                    try:
                        if process.stdout:
                            process.stdout.close()
                    except Exception:
                        pass
                    try:
                        if process.stderr:
                            process.stderr.close()
                    except Exception:
                        pass
