"""Results table management, column formatters, CSV export."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .constants import logger
from .utils import _format_time


class ResultsMixin:
    """Mixin for results table operations and CSV export.

    Expected attributes on *self*:
        found_servers, server_times, proxy_results, security_results,
        protocol_results, isp_results, resolve_results, tcp_udp_results,
        test_slipstream, security_test_enabled, ipv6_test_enabled,
        edns0_test_enabled, isp_info_enabled, table_needs_rebuild
    """

    def _add_result(self, ip: str, response_time: float) -> None:
        self.found_servers.add(ip)
        self.server_times[ip] = response_time

        try:
            time_str = _format_time(response_time)

            row = []
            if self.test_slipstream:
                row.append(self._get_proxy_str(ip))
            row.extend([ip, time_str])
            row.extend([
                self._get_ipver_column(ip),
                self._get_security_column(ip),
                self._get_tcp_udp_column(ip),
                self._get_dns_types_column(ip),
                self._get_edns0_column(ip),
                self._get_resolve_column(ip),
                self._get_isp_column(ip),
            ])

            from textual.widgets import DataTable
            table = self.query_one("#results-table", DataTable)
            table.add_row(*row, key=ip)
        except Exception as e:
            logger.debug(f"Could not add result row to table: {e}")

    # ── Column formatters ───────────────────────────────────────────────

    def _get_proxy_str(self, ip: str) -> str:
        proxy_status = self.proxy_results.get(ip, "N/A")
        if proxy_status.startswith("Success"):
            if "|" in proxy_status:
                latency = proxy_status.split("|", 1)[1]
                return f"[green]\\[\u2713] {latency}[/green]"
            return "[green]\\[\u2713][/green]"
        elif proxy_status == "Failed":
            return "[red]\\[x][/red]"
        elif proxy_status in ("Testing", "Pending", "N/A"):
            return "[blue]\\[\u25cf][/blue]"
        elif proxy_status == "Skip":
            return "[dim grey]\\[s][/dim grey]"
        return "[blue]\\[\u25cf][/blue]"

    def _get_ipver_column(self, ip: str) -> str:
        proto = self.protocol_results.get(ip, {})
        if ip not in self.protocol_results:
            return "[dim]\u2026[/dim]"
        if proto.get("ipv6"):
            return "[green]v4/v6[/green]"
        return "[cyan]v4[/cyan]"

    def _get_security_column(self, ip: str) -> str:
        sec = self.security_results.get(ip)
        if not sec:
            return "[dim]\u2026[/dim]"
        if sec.get("filtered"):
            return "[yellow]Filtered[/yellow]"
        if sec.get("hijacked"):
            return "[red]Hijacked[/red]"
        if sec.get("dnssec"):
            return "[green]Secure[/green]"
        return "[cyan]Normal[/cyan]"

    def _get_resolve_column(self, ip: str) -> str:
        if ip not in self.resolve_results:
            return "[dim]\u2026[/dim]"
        result = self.resolve_results[ip]
        if result == "-":
            return "[dim]-[/dim]"
        return f"[cyan]{result}[/cyan]"

    def _get_edns0_column(self, ip: str) -> str:
        proto = self.protocol_results.get(ip, {})
        if ip not in self.protocol_results:
            return "[dim]\u2026[/dim]"
        if proto.get("edns0"):
            payload = proto.get("edns0_payload", 0)
            if payload:
                return f"[green]\u2713 {payload}[/green]"
            return "[green]\u2713[/green]"
        return "[red]\u2717[/red]"

    def _get_dns_types_column(self, ip: str) -> str:
        types = self.dns_types_results.get(ip)
        if types is None:
            return "[dim]\u2026[/dim]"
        labels = ("NS", "TXT", "RND", "DPI", "EDNS0", "NXD")
        ok = [t for t in labels if types.get(t)]
        count = len(ok)
        total = len(labels)
        names = ",".join(ok) if ok else "-"
        if count == total:
            return f"[green]{names} {count}/{total}[/green]"
        elif count >= 4:
            return f"[cyan]{names} {count}/{total}[/cyan]"
        elif count >= 1:
            return f"[yellow]{names} {count}/{total}[/yellow]"
        return f"[red]{names} {count}/{total}[/red]"

    def _get_isp_column(self, ip: str) -> str:
        if ip not in self.isp_results:
            return "[dim]\u2026[/dim]"
        isp = self.isp_results[ip]
        org = isp.get("org", "-") or "-"
        if org == "-":
            return "[dim]-[/dim]"
        return f"[cyan]{org}[/cyan]"

    def _get_tcp_udp_column(self, ip: str) -> str:
        result = self.tcp_udp_results.get(ip)
        if not result:
            return "[dim]Testing\u2026[/dim]"
        if result == "TCP/UDP":
            return "[green]T/U[/green]"
        elif result == "TCP only":
            return "[yellow]T[/yellow]"
        elif result == "UDP only":
            return "[cyan]U[/cyan]"
        return "[dim]Unknown[/dim]"

    # ── Table operations ────────────────────────────────────────────────

    def _update_table_row(self, ip: str) -> None:
        try:
            from textual.widgets import DataTable
            table = self.query_one("#results-table", DataTable)
            if ip in table._row_locations:
                if self.test_slipstream:
                    table.update_cell(ip, "proxy", self._get_proxy_str(ip))
                table.update_cell(ip, "ipver", self._get_ipver_column(ip))
                table.update_cell(ip, "isp", self._get_isp_column(ip))
                table.update_cell(ip, "security", self._get_security_column(ip))
                table.update_cell(ip, "tcpudp", self._get_tcp_udp_column(ip))
                table.update_cell(ip, "resolved", self._get_resolve_column(ip))
                table.update_cell(ip, "dns_types", self._get_dns_types_column(ip))
                table.update_cell(ip, "edns0", self._get_edns0_column(ip))
        except Exception as e:
            logger.debug(f"Could not update table row for {ip}: {e}")

    def _rebuild_table(self) -> None:
        if not self.table_needs_rebuild:
            return
        try:
            ips = list(self.server_times.keys())
            finalized = [ip for ip in ips if self._is_ip_finalized(ip)]
            testing = [ip for ip in ips if not self._is_ip_finalized(ip)]

            def _sort_key(ip):
                proxy = self.proxy_results.get(ip, "N/A") if self.test_slipstream else ""
                if self.test_slipstream:
                    if proxy.startswith("Success"):
                        proxy_rank = 0
                    elif proxy == "Failed":
                        proxy_rank = 1
                    elif proxy == "Skip":
                        proxy_rank = 2
                    else:  # Testing, Pending, N/A
                        proxy_rank = 3
                else:
                    proxy_rank = 0
                dns_score_rank = 6 - sum(
                    1 for v in self.dns_types_results.get(ip, {}).values() if v
                )
                dnssec_rank = (
                    0 if self.security_results.get(ip, {}).get("dnssec") else 1
                )
                return (proxy_rank, dns_score_rank, dnssec_rank, self.server_times.get(ip, 9999.0))

            sorted_final = sorted(finalized, key=_sort_key)
            sorted_testing = sorted(testing, key=_sort_key)

            from textual.widgets import DataTable
            table = self.query_one("#results-table", DataTable)
            scroll_x = table.scroll_x
            scroll_y = table.scroll_y

            table.clear(columns=True)
            for label, key, width in self._get_table_columns():
                table.add_column(label, key=key, width=width)
            table.cursor_type = "row"

            for ip in sorted_final + sorted_testing:
                row = []
                if self.test_slipstream:
                    row.append(self._get_proxy_str(ip))
                row.extend([ip, _format_time(self.server_times[ip])])
                row.extend([
                    self._get_ipver_column(ip),
                    self._get_security_column(ip),
                    self._get_tcp_udp_column(ip),
                    self._get_dns_types_column(ip),
                    self._get_edns0_column(ip),
                    self._get_resolve_column(ip),
                    self._get_isp_column(ip),
                ])
                table.add_row(*row, key=ip)

            table.scroll_x = scroll_x
            table.scroll_y = scroll_y

            self.table_needs_rebuild = False
        except Exception as e:
            logger.debug(f"Could not rebuild results table: {e}")

    def _is_ip_finalized(self, ip: str) -> bool:
        if ip not in self.tcp_udp_results:
            return False
        if ip not in self.dns_types_results:
            return False
        if self.security_test_enabled and ip not in self.security_results:
            return False
        if self.isp_info_enabled and ip not in self.isp_results:
            return False
        proto = self.protocol_results.get(ip, {})
        if self.ipv6_test_enabled and "ipv6" not in proto:
            return False
        if ip not in self.resolve_results:
            return False
        if self.edns0_test_enabled and "edns0" not in proto:
            return False
        if self.test_slipstream and self.proxy_results.get(ip) in (
            "Pending", "Testing"
        ):
            return False
        return True

    def _periodic_sort_refresh(self) -> None:
        if self.found_servers and not self.is_paused:
            self.table_needs_rebuild = True
            self._rebuild_table()

    # ── CSV export ──────────────────────────────────────────────────────

    def _build_csv_headers_and_rows(
        self, servers_to_save: dict
    ) -> tuple[list[str], list[list[str]]]:
        headers = []
        if self.test_slipstream:
            headers.append("Proxy")
        headers.extend(["DNS", "Ping (ms)"])
        headers.append("IPv4/IPv6")
        headers.append("TCP/UDP")
        if self.security_test_enabled:
            headers.append("Security")
        headers.append("DNS Types")
        if self.edns0_test_enabled:
            headers.append("EDNS0")
        headers.append("IP")
        headers.append("ISP")

        def _csv_sort_key(item):
            ip, t = item
            proxy = self.proxy_results.get(ip, "N/A") if self.test_slipstream else ""
            if self.test_slipstream:
                if proxy.startswith("Success"):
                    proxy_rank = 0
                elif proxy == "Failed":
                    proxy_rank = 1
                elif proxy == "Skip":
                    proxy_rank = 2
                else:
                    proxy_rank = 3
            else:
                proxy_rank = 0
            dns_score_rank = 6 - sum(
                1 for v in self.dns_types_results.get(ip, {}).values() if v
            )
            dnssec_rank = (
                0 if self.security_results.get(ip, {}).get("dnssec") else 1
            )
            return (proxy_rank, dns_score_rank, dnssec_rank, t)

        sorted_servers = sorted(servers_to_save.items(), key=_csv_sort_key)

        rows: list[list[str]] = []
        for ip, resp_time in sorted_servers:
            row = []
            if self.test_slipstream:
                raw = self.proxy_results.get(ip, "N/A")
                if raw.startswith("Success"):
                    latency = raw.split("|", 1)[1] if "|" in raw else ""
                    row.append(f"[\u2713] {latency}" if latency else "[\u2713]")
                elif raw == "Failed":
                    row.append("[x]")
                elif raw == "Skip":
                    row.append("[s]")
                else:
                    row.append("[\u25cf]")
            row.extend([ip, f"{resp_time * 1000:.0f}"])
            # IPv4/IPv6
            proto = self.protocol_results.get(ip, {})
            if proto.get("ipv6"):
                row.append("v4/v6")
            elif ip in self.protocol_results:
                row.append("v4")
            else:
                row.append("")
            # TCP/UDP
            row.append(self.tcp_udp_results.get(ip, ""))
            # Security
            if self.security_test_enabled:
                sec = self.security_results.get(ip, {})
                if ip in self.security_results:
                    if sec.get("filtered"):
                        row.append("Filtered")
                    elif sec.get("hijacked"):
                        row.append("Hijacked")
                    elif sec.get("dnssec"):
                        row.append("Secure")
                    else:
                        row.append("Normal")
                else:
                    row.append("")
            # DNS Types
            dt = self.dns_types_results.get(ip)
            if dt:
                labels = ("NS", "TXT", "RND", "DPI", "EDNS0", "NXD")
                ok = [t for t in labels if dt.get(t)]
                row.append(f"{','.join(ok)} {len(ok)}/6" if ok else "0/6")
            else:
                row.append("")
            # EDNS0
            if self.edns0_test_enabled:
                if ip in self.protocol_results and "edns0" in self.protocol_results[ip]:
                    if proto.get("edns0"):
                        payload = proto.get("edns0_payload", 0)
                        row.append(f"Yes ({payload})" if payload else "Yes")
                    else:
                        row.append("No")
                else:
                    row.append("")
            # IP (resolved)
            row.append(self.resolve_results.get(ip, ""))
            # ISP
            isp = self.isp_results.get(ip, {})
            org = isp.get("org", "") or ""
            row.append(org if org != "-" else "")
            rows.append(row)
        return headers, rows

    def _auto_save_results(self) -> None:
        if self.test_slipstream:
            passed_servers = {
                ip: time
                for ip, time in self.server_times.items()
                if self.proxy_results.get(ip, "").startswith("Success")
            }
            if not passed_servers:
                self._log(
                    "[yellow]No DNS servers passed proxy test - nothing to save.[/yellow]"
                )
                self._log(
                    f"[yellow]Total DNS found: {len(self.found_servers)}, Passed proxy: 0[/yellow]"
                )
                logger.warning(
                    f"No servers passed proxy test. Total found: {len(self.found_servers)}"
                )
                return
            servers_to_save = passed_servers
            self._log(
                f"[cyan]Saving {len(passed_servers)}/{len(self.found_servers)} "
                f"DNS servers that passed proxy test...[/cyan]"
            )
            logger.info(f"Saving {len(passed_servers)} servers that passed proxy test")
        else:
            if not self.found_servers:
                self._log("[yellow]No DNS servers found to save.[/yellow]")
                return
            servers_to_save = self.server_times

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = Path("results")

        try:
            output_dir.mkdir(exist_ok=True)
        except (OSError, PermissionError) as e:
            self._log(f"[red]Failed to create results directory: {e}[/red]")
            logger.error(f"Failed to create results directory: {e}")
            return

        csv_file = output_dir / f"{timestamp}.csv"
        headers, rows = self._build_csv_headers_and_rows(servers_to_save)

        try:
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
            self._log(f"[green]\u2713 Results auto-saved to: {csv_file}[/green]")
            logger.info(f"Results auto-saved to {csv_file}")
        except (OSError, IOError, PermissionError) as e:
            self._log(f"[red]Failed to save results: {e}[/red]")
            logger.error(f"Failed to auto-save results to {csv_file}: {e}")

    def action_save_results(self) -> None:
        if self.test_slipstream:
            passed_servers = {
                ip: time
                for ip, time in self.server_times.items()
                if self.proxy_results.get(ip, "").startswith("Success")
            }
            if not passed_servers:
                self.notify("No servers passed proxy test!", severity="warning")
                return
            servers_to_save = passed_servers
        else:
            if not self.found_servers:
                self.notify("No results to save!", severity="warning")
                return
            servers_to_save = self.server_times

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = Path("results")

        try:
            output_dir.mkdir(exist_ok=True)
        except (OSError, PermissionError) as e:
            self.notify(f"Failed to create results directory: {e}", severity="error")
            logger.error(f"Failed to create results directory: {e}")
            return

        csv_file = output_dir / f"scan_{timestamp}.csv"
        headers, rows = self._build_csv_headers_and_rows(servers_to_save)

        try:
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
            self.notify(
                f"Saved {len(rows)} servers: {csv_file.name}",
                severity="information",
            )
            logger.info(f"Results saved to {csv_file}")
        except (OSError, IOError, PermissionError) as e:
            self.notify(f"Failed to save results: {e}", severity="error")
            logger.error(f"Failed to save results to {csv_file}: {e}")
