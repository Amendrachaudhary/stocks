"""
router.py - Core Trading Pipeline Logic & Dependency Injection Router
====================================================================
Encapsulates message parsing, risk filtering, database synchronization,
and signal dispatching. Decoupled from transport specifics via SignalSender.
"""

import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

from interfaces import SignalSender
from parser import parse_message, calculate_pnl, enrich_entry_data
import database

logger = logging.getLogger("fno_automation.router")
BASE_DIR = Path(__file__).resolve().parent
IST = timezone(timedelta(hours=5, minutes=30))


class SignalRouter:
    """
    Core pipeline orchestrator for processing FNO option signals.
    Employs Dependency Injection to route verified trade alerts to any SignalSender.
    """

    def __init__(
        self,
        sender: SignalSender,
        lot_sizes: Optional[Dict[str, int]] = None,
        max_capital: float = 10000.0,
        enforce_trading_hours: bool = True
    ):
        if not isinstance(sender, SignalSender):
            raise TypeError("sender must implement interfaces.SignalSender")

        self.sender = sender
        self.lot_sizes = lot_sizes or {
            "NIFTY": 65,
            "BANKNIFTY": 30,
            "FINNIFTY": 60
        }
        self.max_capital = max_capital
        self.enforce_trading_hours = enforce_trading_hours

    def is_within_trading_hours(self) -> bool:
        """Evaluates whether current IST time is between 08:00 AM and 16:00 PM."""
        if not self.enforce_trading_hours:
            return True

        now_ist = datetime.now(IST)
        start_time = now_ist.replace(hour=8, minute=0, second=0, microsecond=0)
        end_time = now_ist.replace(hour=16, minute=0, second=0, microsecond=0)
        return start_time <= now_ist <= end_time

    def process_message(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """
        Processes raw channel messages through normalization, validation,
        persistence, and dispatching.

        Args:
            raw_text: Raw incoming text string from channel or socket.

        Returns:
            Optional[Dict[str, Any]]: Normalized payload if parsed and executed, None otherwise.
        """
        if not raw_text or not raw_text.strip():
            return None

        if not self.is_within_trading_hours():
            logger.info("[ROUTER] Message received outside trading hours. Ignoring.")
            return None

        try:
            parsed_data = parse_message(raw_text)
            if not parsed_data:
                return None

            action = parsed_data.get("action")
            instrument = parsed_data.get("instrument")

            if action == "ENTRY":
                # Apply 10k budget filter and enrich trade data
                enriched = enrich_entry_data(parsed_data, self.lot_sizes)
                if not enriched:
                    logger.info(f"[ROUTER] Trade {instrument} exceeded max capital. Filtered out.")
                    return None

                parsed_data = enriched
                # Persist entry to database
                database.insert_trade(
                    instrument,
                    parsed_data["entry_price"],
                    parsed_data["stop_loss"]
                )
                win_rate = database.get_win_rate()

                # Dispatch signal via injected adapter
                self._dispatch(parsed_data, win_rate)
                return parsed_data

            elif action in ("SL_HIT", "TARGET_HIT"):
                open_trade = database.get_open_trade(instrument)
                if open_trade:
                    entry_price = open_trade["entry_price"]
                    exit_price = parsed_data.get("exit_price", 0.0)

                    pnl_points, pnl_rupees = calculate_pnl(
                        instrument, entry_price, exit_price, action, self.lot_sizes
                    )

                    database.update_trade_exit(
                        instrument, exit_price, pnl_points, pnl_rupees, status="CLOSED"
                    )

                    parsed_data["pnl_points"] = round(pnl_points, 2)
                    parsed_data["pnl_rupees"] = round(pnl_rupees, 2)
                
                win_rate = database.get_win_rate()
                self._dispatch(parsed_data, win_rate)
                return parsed_data

        except Exception as exc:
            logger.error(f"[ROUTER] Error processing message: {exc}", exc_info=True)
            return None

        return None

    def _dispatch(self, data: Dict[str, Any], win_rate: float) -> bool:
        """Internal helper to dispatch structured alert or formatted text."""
        if hasattr(self.sender, "send_trade_alert") and callable(getattr(self.sender, "send_trade_alert")):
            return self.sender.send_trade_alert(data, win_rate=win_rate)

        # Fallback to standard string signal
        summary = (
            f"[{data.get('action')}] {data.get('instrument')} | "
            f"Price: {data.get('entry_price') or data.get('exit_price')} | Win Rate: {win_rate}%"
        )
        return self.sender.send_signal(summary)

    def generate_and_send_daily_report(self) -> bool:
        """Fetches today's closed trades, formats P&L settlement summary, and dispatches it."""
        rows = database.get_daily_pnl()
        if not rows:
            msg = "Daily P&L Report: No trades closed today."
            if hasattr(self.sender, "send_daily_report") and callable(getattr(self.sender, "send_daily_report")):
                return self.sender.send_daily_report(msg)
            return self.sender.send_signal(msg)

        report = "Daily P&L Report\n"
        report += "=" * 20 + "\n\n"
        total_rupees = 0.0

        for row in rows:
            instrument, pts, rps = row
            report += f"- {instrument}: {pts:.2f} pts | Rs. {rps:.2f}\n"
            total_rupees += rps

        report += f"\nTotal P&L: Rs. {total_rupees:.2f}"

        if hasattr(self.sender, "send_daily_report") and callable(getattr(self.sender, "send_daily_report")):
            return self.sender.send_daily_report(report)
        return self.sender.send_signal(report)
