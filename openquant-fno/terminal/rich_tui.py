"""
OpenQuant-FNO: Bloomberg / Institutional Hedge-Fund Terminal TUI
===============================================================
Renders a high-density, multi-panel terminal layout with live ingestion status,
blotter table, risk bounds, and quantitative telemetry using the Rich library.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich import box


class OpenQuantTUI:
    """
    Renders institutional terminal layouts and tables for OpenQuant-FNO.
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def generate_layout(
        self,
        channels: List[Any],
        openbb_status: str,
        openbb_url: str,
        daily_summary: Dict[str, Any],
        recent_trades: List[Dict[str, Any]],
        max_margin: float = 10000.0,
        lot_sizes: Optional[Dict[str, int]] = None
    ) -> Layout:
        """
        Builds the complete multi-panel Bloomberg-style terminal layout.
        """
        lot_sizes = lot_sizes or {"NIFTY": 65, "BANKNIFTY": 30, "FINNIFTY": 60}
        layout = Layout()

        # Split into Header, Body (Blotter + Side Panels), and Footer
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )

        # Split main into left (Blotter) and right (Telemetry / Risk)
        layout["main"].split_row(
            Layout(name="blotter", ratio=3),
            Layout(name="side", ratio=2)
        )

        # Split side into System State and Risk Parameters
        layout["side"].split(
            Layout(name="system_status", ratio=1),
            Layout(name="quant_telemetry", ratio=1)
        )

        # ----------------------------------------------------------------------
        # Header Panel
        # ----------------------------------------------------------------------
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        header_text = Text()
        header_text.append("⚡ OPENQUANT-FNO ", style="bold bright_green")
        header_text.append("│ AUTOMATED OPTIONS INGESTION & QUANTITATIVE RESEARCH STATION │ ", style="bold bright_white")
        header_text.append(f"CLOCK: {now_str}", style="bold bright_cyan")
        layout["header"].update(Panel(header_text, style="white on black", box=box.HEAVY))

        # ----------------------------------------------------------------------
        # Trade Blotter Table (Live Database state)
        # ----------------------------------------------------------------------
        blotter_table = Table(
            title="[bold bright_white]LIVE EXECUTION BLOTTER (ACTIVE SESSION)[/bold bright_white]",
            box=box.ROUNDED,
            expand=True,
            header_style="bold bright_cyan",
            title_style="bold bright_white"
        )
        blotter_table.add_column("ID", justify="right", style="dim", width=4)
        blotter_table.add_column("Time", justify="center", width=8)
        blotter_table.add_column("Instrument", justify="left", style="bold", width=22)
        blotter_table.add_column("Entry", justify="right", width=9)
        blotter_table.add_column("SL", justify="right", width=8)
        blotter_table.add_column("Exit", justify="right", width=9)
        blotter_table.add_column("Points", justify="right", width=10)
        blotter_table.add_column("Net P&L", justify="right", width=12)
        blotter_table.add_column("State", justify="center", width=8)

        if not recent_trades:
            blotter_table.add_row("-", "--:--:--", "Awaiting Ingestion Signals...", "-", "-", "-", "-", "-", "[dim]IDLE[/dim]")
        else:
            for t in recent_trades:
                tid = str(t.get("id", ""))
                # Extract HH:MM:SS from ISO timestamp
                ts_raw = t.get("timestamp", "")
                ts = ts_raw.split("T")[-1][:8] if "T" in ts_raw else ts_raw[:8]
                inst = t.get("instrument", "")
                ep = f"₹{t.get('entry_price', 0.0):.2f}"
                sl = f"₹{t.get('stop_loss', 0.0):.2f}" if t.get("stop_loss") else "-"
                xp = f"₹{t.get('exit_price', 0.0):.2f}" if t.get("exit_price") else "-"
                
                pts = t.get("pnl_points", 0.0)
                rupees = t.get("pnl_rupees", 0.0)
                status = t.get("status", "OPEN")

                if status == "CLOSED":
                    if rupees > 0:
                        pts_str = f"[bright_green]+{pts:.1f}[/bright_green]"
                        rupees_str = f"[bold bright_green]+₹{rupees:,.2f}[/bold bright_green]"
                        state_str = "[green]CLOSED[/green]"
                    elif rupees < 0:
                        pts_str = f"[bright_red]{pts:.1f}[/bright_red]"
                        rupees_str = f"[bold bright_red]-₹{abs(rupees):,.2f}[/bold bright_red]"
                        state_str = "[red]SL_HIT[/red]"
                    else:
                        pts_str = "0.0"
                        rupees_str = "₹0.00"
                        state_str = "[yellow]EVEN[/yellow]"
                else:
                    pts_str = "[dim]--[/dim]"
                    rupees_str = "[dim]--[/dim]"
                    state_str = "[bold bright_yellow]OPEN[/bold bright_yellow]"

                blotter_table.add_row(tid, ts, inst, ep, sl, xp, pts_str, rupees_str, state_str)

        layout["blotter"].update(Panel(blotter_table, box=box.ROUNDED, border_style="bright_blue"))

        # ----------------------------------------------------------------------
        # System & OpenBB Status Panel
        # ----------------------------------------------------------------------
        channels_display = ", ".join([str(c) for c in channels]) if channels else "None"
        obb_color = "bright_green" if "RUNNING" in openbb_status.upper() or "ACTIVE" in openbb_status.upper() else "yellow"

        status_table = Table(box=box.SIMPLE, show_header=False, expand=True)
        status_table.add_column("Key", style="bold bright_white")
        status_table.add_column("Val", style="bright_cyan")

        status_table.add_row("Telethon Listener", "[bright_green]ONLINE (Listening)[/bright_green]")
        status_table.add_row("Target Channels", f"[white]{channels_display}[/white]")
        status_table.add_row("OpenBB Platform API", f"[{obb_color}]{openbb_status} ({openbb_url})[/{obb_color}]")
        status_table.add_row("SQLite DB Engine", "[bright_green]THREAD-SAFE (WAL MODE)[/bright_green]")
        status_table.add_row("Max Margin Gate", f"[bold bright_yellow]₹{max_margin:,.2f} / trade[/bold bright_yellow]")
        status_table.add_row(
            "Contract Lots (2026)",
            f"NIFTY:{lot_sizes.get('NIFTY',65)} | BN:{lot_sizes.get('BANKNIFTY',30)} | FIN:{lot_sizes.get('FINNIFTY',60)}"
        )

        layout["system_status"].update(
            Panel(status_table, title="[bold bright_white]SYSTEM & INFRASTRUCTURE TELEMETRY[/bold bright_white]",
                  box=box.ROUNDED, border_style="bright_cyan")
        )

        # ----------------------------------------------------------------------
        # Daily Quantitative Settlement & Risk Gauge
        # ----------------------------------------------------------------------
        tot_pnl = daily_summary.get("total_pnl_rupees", 0.0)
        pnl_color = "bright_green" if tot_pnl > 0 else ("bright_red" if tot_pnl < 0 else "white")
        tot_pts = daily_summary.get("total_pnl_points", 0.0)
        win_rate = daily_summary.get("win_rate", 0.0)
        pf = daily_summary.get("profit_factor", 0.0)
        total_executed = daily_summary.get("total_trades", 0)
        closed = daily_summary.get("closed_count", 0)

        quant_table = Table(box=box.SIMPLE, show_header=False, expand=True)
        quant_table.add_column("Metric", style="bold bright_white")
        quant_table.add_column("Value", style="bright_white")

        quant_table.add_row("Session Net P&L", f"[bold {pnl_color}]₹{tot_pnl:+,.2f} ({tot_pts:+.1f} pts)[/bold {pnl_color}]")
        quant_table.add_row("Executed / Closed", f"{total_executed} / {closed} trades")
        quant_table.add_row("Model Win Rate", f"[bold bright_cyan]{win_rate:.1f}%[/bold bright_cyan]")
        quant_table.add_row("Profit Factor", f"{pf:.2f}")
        quant_table.add_row("Daily Report Schedule", "[bright_magenta]16:00 IST Automated Dispatch[/bright_magenta]")

        layout["quant_telemetry"].update(
            Panel(quant_table, title="[bold bright_white]SESSION QUANTITATIVE METRICS[/bold bright_white]",
                  box=box.ROUNDED, border_style="bright_magenta")
        )

        # ----------------------------------------------------------------------
        # Footer
        # ----------------------------------------------------------------------
        footer_text = Text()
        footer_text.append("Press ", style="dim")
        footer_text.append("Ctrl+C", style="bold yellow")
        footer_text.append(" to safely shutdown • OpenQuant Dual-Layer Architecture: Real-Time Execution + Quant Suite", style="dim")
        layout["footer"].update(Panel(footer_text, style="white on black", box=box.HEAVY))

        return layout

    def render(
        self,
        channels: List[Any],
        openbb_status: str,
        openbb_url: str,
        daily_summary: Dict[str, Any],
        recent_trades: List[Dict[str, Any]],
        max_margin: float = 10000.0,
        lot_sizes: Optional[Dict[str, int]] = None
    ):
        """Prints the updated terminal layout."""
        layout = self.generate_layout(
            channels, openbb_status, openbb_url, daily_summary, recent_trades, max_margin, lot_sizes
        )
        self.console.print(layout)
