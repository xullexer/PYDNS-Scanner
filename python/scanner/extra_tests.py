"""Extra test methods — security, IPv6, EDNS0, TCP/UDP, ISP, resolve."""

from __future__ import annotations

import asyncio
import random
import secrets
import socket
import struct

import dns.asyncquery
import dns.asyncresolver
import dns.exception
import dns.message
import dns.rdatatype
import dns.resolver

from .constants import logger


def _make_resolver(nameserver: str, timeout: float = 3.0) -> dns.asyncresolver.Resolver:
    """Create a dnspython async resolver pointed at a single nameserver."""
    r = dns.asyncresolver.Resolver(configure=False)
    r.nameservers = [nameserver]
    r.timeout = timeout
    r.lifetime = timeout
    return r


def _has_response(exc: dns.resolver.NoNameservers) -> bool:
    """True if the server returned any DNS response (even FORMERR/NOTIMP)."""
    for entry in (getattr(exc, 'errors', None) or []):
        if len(entry) > 4 and entry[4] is not None:
            return True
    return False


class ExtraTestsMixin:
    """Mixin providing supplementary DNS/network tests.

    Expected attributes on *self*:
        extra_test_semaphore, security_test_enabled, ipv6_test_enabled,
        edns0_test_enabled, isp_info_enabled, security_results,
        protocol_results, isp_results, resolve_results, tcp_udp_results,
        extra_test_tasks, domain, dns_type, _isp_cache_path
    """

    @staticmethod
    def _is_bogon_ip(addr: str) -> bool:
        """Return True if *addr* is a private / bogon / filtered address."""
        try:
            parts = addr.split(".")
            if len(parts) != 4:
                return False
            a, b = int(parts[0]), int(parts[1])
            return (
                a == 0
                or a == 10
                or a == 127
                or (a == 100 and 64 <= b <= 127)
                or (a == 169 and b == 254)
                or (a == 172 and 16 <= b <= 31)
                or (a == 192 and b == 168)
                or a >= 224
            )
        except (ValueError, IndexError):
            return False

    def _queue_extra_tests(self, ip: str) -> None:
        """Queue enabled extra tests for a found DNS server."""
        async def _run_extras(dns_ip: str) -> None:
            async with self.extra_test_semaphore:
                tasks: list[asyncio.Task] = []
                tasks.append(asyncio.create_task(self._test_tcp_udp_support(dns_ip)))
                tasks.append(asyncio.create_task(self._test_dns_types(dns_ip)))

                if self.security_test_enabled:
                    tasks.append(asyncio.create_task(self._test_security(dns_ip)))
                if self.ipv6_test_enabled:
                    tasks.append(asyncio.create_task(self._test_ipv6(dns_ip)))
                tasks.append(asyncio.create_task(self._test_resolve(dns_ip)))
                if self.edns0_test_enabled:
                    tasks.append(asyncio.create_task(self._test_edns0(dns_ip)))
                if self.isp_info_enabled:
                    tasks.append(asyncio.create_task(self._test_isp_info(dns_ip)))
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

                # Post-check: if the resolved IP is a bogon/private address
                # the DNS server is returning filtered/censored responses — update
                # security_results for display only; do NOT skip proxy based on this.
                resolved = self.resolve_results.get(dns_ip, "-")
                if resolved != "-" and self._is_bogon_ip(resolved.split(",")[0].strip()):
                    self.security_results[dns_ip] = {
                        "dnssec": False, "hijacked": False, "filtered": True,
                    }
                    self._log(
                        f"[yellow]⚠ {dns_ip}: Resolved to bogon {resolved} "
                        f"→ Filtered[/yellow]"
                    )

                # Safety-net: skip proxy if DNS type score < 4.
                # Primary enforcement is in _queue_slipstream_test (before semaphore),
                # but this catches any edge case where the task hasn't run yet.
                dns_types = self.dns_types_results.get(dns_ip, {})
                dns_score = sum(1 for v in dns_types.values() if v)
                if dns_types and dns_score < 4:
                    if self.test_slipstream and self.proxy_results.get(dns_ip) in (
                        "Pending", "Testing", "N/A",
                    ):
                        self.proxy_results[dns_ip] = "Skip"
                        self._log(
                            f"[yellow]⚠ {dns_ip}: DNS type score {dns_score}/6 < 4 "
                            f"→ skipping proxy test[/yellow]"
                        )

                self._update_table_row(dns_ip)

        task = asyncio.create_task(_run_extras(ip))
        self.extra_test_tasks.add(task)
        task.add_done_callback(self.extra_test_tasks.discard)

    # ── Security tests ──────────────────────────────────────────────────

    async def _test_security(self, ip: str) -> None:
        result: dict = {"dnssec": False, "hijacked": False, "filtered": False}
        try:
            # Detect private/filtered IP ranges
            parts = ip.split(".")
            if len(parts) == 4:
                first, second = int(parts[0]), int(parts[1])
                if (
                    first == 10
                    or (first == 172 and 16 <= second <= 31)
                    or (first == 192 and second == 168)
                ):
                    result["filtered"] = True
                    self.security_results[ip] = result
                    return

            nxdomain_test = f"nxdomain-{random.randbytes(6).hex()}.example.invalid"

            async def _check_dnssec() -> bool:
                try:
                    return await asyncio.wait_for(
                        self._check_dnssec_raw(ip), timeout=4.0
                    )
                except Exception:
                    return False

            async def _check_hijack() -> bool:
                try:
                    r = _make_resolver(ip)
                    answer = await r.resolve(nxdomain_test, "A")
                    return bool(answer)  # Got real answer for nonexistent domain = hijacked
                except dns.resolver.NXDOMAIN:
                    return False  # Correct response
                except Exception:
                    return False

            dnssec_ok, hijacked = await asyncio.gather(
                _check_dnssec(), _check_hijack()
            )
            result["dnssec"] = dnssec_ok
            result["hijacked"] = hijacked
        except Exception as e:
            logger.debug(f"Security test error for {ip}: {e}")

        self.security_results[ip] = result
        if result["dnssec"]:
            self._log(f"[cyan]\U0001f512 {ip}: DNSSEC supported[/cyan]")
        if result["hijacked"]:
            self._log(f"[red]\u26a0 {ip}: DNS hijacking detected[/red]")

    async def _check_dnssec_raw(self, ip: str) -> bool:
        txn_id = secrets.token_bytes(2)
        flags = b"\x01\x00"
        counts = b"\x00\x01\x00\x00\x00\x00\x00\x01"
        qname = b"\x07example\x03com\x00"
        qtype = b"\x00\x01"
        qclass = b"\x00\x01"
        opt_rr = b"\x00\x00\x29\x10\x00\x00\x00\x80\x00\x00\x00"

        query = txn_id + flags + counts + qname + qtype + qclass + opt_rr

        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        sock.settimeout(0)

        try:
            await loop.sock_sendto(sock, query, (ip, 53))
            data = await asyncio.wait_for(loop.sock_recv(sock, 4096), timeout=3.0)

            if len(data) < 12:
                return False

            resp_flags = data[2:4]
            ad_flag = (resp_flags[1] >> 5) & 1
            if ad_flag:
                return True

            arcount = struct.unpack("!H", data[10:12])[0]
            if arcount > 0:
                if b"\x00\x29" in data[12:]:
                    return True

            return False
        except Exception:
            return False
        finally:
            sock.close()

    # ── IPv6 test ───────────────────────────────────────────────────────

    async def _test_ipv6(self, ip: str) -> None:
        result = False
        try:
            r = _make_resolver(ip)
            try:
                answer = await r.resolve("google.com", "AAAA")
                result = bool(answer)
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                result = True  # Server processed the AAAA query
            except dns.resolver.NoNameservers as e:
                result = _has_response(e)  # Server responded with FORMERR/NOTIMP
        except Exception as e:
            logger.debug(f"IPv6 test error for {ip}: {e}")

        self.protocol_results.setdefault(ip, {})["ipv6"] = result
        if result:
            self._log(f"[cyan]{ip}: IPv6 (AAAA) supported[/cyan]")

    # ── Resolve test ────────────────────────────────────────────────────

    async def _test_resolve(self, ip: str) -> None:
        if self.dns_type == "A":
            resolve_domain = self.domain.strip() or "google.com"
        else:
            resolve_domain = "google.com"
        try:
            r = _make_resolver(ip, timeout=3.0)
            answer = await r.resolve(resolve_domain, "A")
            if answer:
                addrs = [rdata.address for rdata in answer]
                resolved = addrs[0] if len(addrs) == 1 else ", ".join(addrs[:2])
                self.resolve_results[ip] = resolved
                self._log(f"[cyan]{ip}: {resolve_domain} \u2192 {resolved}[/cyan]")
            else:
                self.resolve_results[ip] = "-"
        except Exception as e:
            logger.debug(f"Resolve test error for {ip}: {e}")
            self.resolve_results[ip] = "-"

    # ── EDNS0 test ──────────────────────────────────────────────────────

    async def _test_edns0(self, ip: str) -> None:
        result = False
        payload_size = 0
        try:
            txn_id = secrets.token_bytes(2)
            flags = b"\x01\x00"
            counts = b"\x00\x01\x00\x00\x00\x00\x00\x01"
            qname = b"\x07example\x03com\x00"
            qtype = b"\x00\x01"
            qclass = b"\x00\x01"
            opt_rr = b"\x00\x00\x29\x10\x00\x00\x00\x00\x00\x00\x00"

            query = txn_id + flags + counts + qname + qtype + qclass + opt_rr

            loop = asyncio.get_running_loop()
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)

            try:
                await loop.sock_sendto(sock, query, (ip, 53))
                data = await asyncio.wait_for(
                    loop.sock_recv(sock, 4096), timeout=3.0
                )
                if len(data) >= 12:
                    arcount = struct.unpack("!H", data[10:12])[0]
                    if arcount > 0:
                        # Find OPT record (type 41 = 0x0029) in additional section
                        idx = data.find(b"\x00\x29", 12)
                        if idx >= 0:
                            result = True
                            # OPT RR: NAME(0x00) TYPE(0x0029) CLASS(2 bytes = UDP payload size)
                            # The 2 bytes after the type field are the UDP payload size
                            if idx + 4 <= len(data):
                                payload_size = struct.unpack("!H", data[idx + 2:idx + 4])[0]
            finally:
                sock.close()
        except Exception as e:
            logger.debug(f"EDNS0 test error for {ip}: {e}")

        proto = self.protocol_results.setdefault(ip, {})
        proto["edns0"] = result
        proto["edns0_payload"] = payload_size
        if result:
            size_str = f" ({payload_size})" if payload_size else ""
            self._log(f"[cyan]{ip}: EDNS0 supported{size_str}[/cyan]")

    # ── DNS Types test ──────────────────────────────────────────────────

    # The 6 DNS test categories (score 0-6, tunnel compatibility):
    #   NS    – NS delegation + glue records
    #   TXT   – TXT record support
    #   RND   – random subdomain resolution
    #   DPI   – encoded payload queries (tunnel realism)
    #   EDNS0 – EDNS0 buffer size support
    #   NXD   – NXDOMAIN correctness

    _DNS_TYPE_LABELS = ("NS", "TXT", "RND", "DPI", "EDNS0", "NXD")

    async def _test_dns_types(self, ip: str) -> None:
        """Test tunnel compatibility across 6 DNS categories (score 0-6)."""
        passed: dict[str, bool] = {}
        domain = self.domain.strip() or "google.com"

        async def _test_ns() -> None:
            # NS delegation + glue records: verify NS records exist AND
            # nameserver A/AAAA glue is present in the additional section.
            try:
                request = dns.message.make_query(domain, dns.rdatatype.NS)
                response = await asyncio.wait_for(
                    dns.asyncquery.udp(request, ip, timeout=3.0),
                    timeout=4.0,
                )
                has_ns = any(
                    rrset.rdtype == dns.rdatatype.NS
                    for section in (response.answer, response.authority)
                    for rrset in section
                )
                has_glue = any(
                    rrset.rdtype in (dns.rdatatype.A, dns.rdatatype.AAAA)
                    for rrset in response.additional
                )
                passed["NS"] = has_ns and has_glue
            except Exception:
                passed["NS"] = False

        async def _test_txt() -> None:
            try:
                await _make_resolver(ip).resolve(domain, "TXT")
                passed["TXT"] = True
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                passed["TXT"] = True
            except dns.resolver.NoNameservers as e:
                passed["TXT"] = _has_response(e)
            except Exception:
                passed["TXT"] = False

        async def _test_rnd() -> None:
            try:
                prefix = random.randbytes(4).hex()
                await _make_resolver(ip).resolve(f"{prefix}.{domain}", "A")
                passed["RND"] = True
            except dns.resolver.NXDOMAIN:
                passed["RND"] = True  # Expected: server correctly returned NXDOMAIN
            except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
                passed["RND"] = True  # Server processed the query
            except Exception:
                passed["RND"] = False

        async def _test_dpi() -> None:
            # Encoded payload: hex-encoded subdomain simulating DNS tunnel traffic.
            # Resolvers with DPI filtering drop or time out on such queries.
            try:
                encoded = secrets.token_bytes(10).hex()  # 20-char hex label
                await _make_resolver(ip).resolve(f"{encoded}.{domain}", "TXT")
                passed["DPI"] = True
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                passed["DPI"] = True  # Resolver processed the encoded query (not DPI-blocked)
            except dns.resolver.NoNameservers as e:
                passed["DPI"] = _has_response(e)
            except Exception:
                passed["DPI"] = False

        async def _test_edns0_type() -> None:
            # EDNS0 buffer size support via raw OPT record query.
            try:
                txn_id = secrets.token_bytes(2)
                flags = b"\x01\x00"
                counts = b"\x00\x01\x00\x00\x00\x00\x00\x01"
                qname = b"\x07example\x03com\x00"
                qtype = b"\x00\x01"
                qclass = b"\x00\x01"
                opt_rr = b"\x00\x00\x29\x10\x00\x00\x00\x00\x00\x00\x00"
                query = txn_id + flags + counts + qname + qtype + qclass + opt_rr
                loop = asyncio.get_running_loop()
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setblocking(False)
                try:
                    await loop.sock_sendto(sock, query, (ip, 53))
                    data = await asyncio.wait_for(loop.sock_recv(sock, 4096), timeout=3.0)
                    passed["EDNS0"] = (
                        len(data) >= 12
                        and struct.unpack("!H", data[10:12])[0] > 0
                        and data.find(b"\x00\x29", 12) >= 0
                    )
                finally:
                    sock.close()
            except Exception:
                passed["EDNS0"] = False

        async def _test_nxd() -> None:
            try:
                nxd_name = f"{random.randbytes(6).hex()}.nxdomain-test.invalid"
                await _make_resolver(ip).resolve(nxd_name, "A")
                passed["NXD"] = False  # Got real answer for nonexistent domain = hijacked
            except dns.resolver.NXDOMAIN:
                passed["NXD"] = True  # Correct: server returned NXDOMAIN
            except Exception:
                passed["NXD"] = False

        await asyncio.gather(
            _test_ns(), _test_txt(), _test_rnd(),
            _test_dpi(), _test_edns0_type(), _test_nxd(),
            return_exceptions=True,
        )

        self.dns_types_results[ip] = passed
        ok = [t for t in self._DNS_TYPE_LABELS if passed.get(t)]
        self._log(f"[cyan]{ip}: DNS types {','.join(ok)} {len(ok)}/6[/cyan]")

    # ── ISP info ────────────────────────────────────────────────────────

    async def _test_isp_info(self, ip: str) -> None:
        import ipaddress

        info: dict = {"org": "-", "isp": "-", "asn": "", "country": "IR"}
        try:
            ip_int = int(ipaddress.IPv4Address(ip))
            table = self._get_isp_table()

            lo, hi = 0, len(table) - 1
            while lo <= hi:
                mid = (lo + hi) // 2
                start, end, org, asn = table[mid]
                if ip_int < start:
                    hi = mid - 1
                elif ip_int > end:
                    lo = mid + 1
                else:
                    info = {"org": org, "isp": org, "asn": asn, "country": "IR"}
                    break
        except Exception as e:
            logger.debug(f"ISP info error for {ip}: {e}")

        self.isp_results[ip] = info
        if info.get("org") and info["org"] != "-":
            self._log(f"[dim]{ip}: {info['org']} ({info.get('country', '')})[/dim]")

    # ── TCP/UDP support ─────────────────────────────────────────────────

    async def _test_tcp_udp_support(self, ip: str) -> None:
        tcp_works = False
        udp_works = True  # Confirmed during main scan

        try:
            txn_id = secrets.token_bytes(2)
            flags = b"\x01\x00"
            counts = b"\x00\x01\x00\x00\x00\x00\x00\x00"
            qname = b"\x06google\x03com\x00"
            qtype = b"\x00\x01"
            qclass = b"\x00\x01"
            dns_msg = txn_id + flags + counts + qname + qtype + qclass

            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, 53), timeout=2.0
            )
            try:
                length_prefix = struct.pack("!H", len(dns_msg))
                writer.write(length_prefix + dns_msg)
                await writer.drain()

                resp_len_bytes = await asyncio.wait_for(
                    reader.readexactly(2), timeout=2.0
                )
                resp_len = struct.unpack("!H", resp_len_bytes)[0]

                if resp_len > 0:
                    resp_data = await asyncio.wait_for(
                        reader.readexactly(resp_len), timeout=2.0
                    )
                    if len(resp_data) >= 12 and resp_data[:2] == txn_id:
                        tcp_works = True
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"TCP test error for {ip}: {e}")

        if tcp_works and udp_works:
            result = "TCP/UDP"
        elif tcp_works:
            result = "TCP only"
        elif udp_works:
            result = "UDP only"
        else:
            result = "None"

        self.tcp_udp_results[ip] = result
        logger.debug(f"{ip}: Protocol support = {result}")
