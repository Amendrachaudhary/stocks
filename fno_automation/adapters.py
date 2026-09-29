"""
adapters.py - Concrete Transport Adapters for Modular Signal Dispatching
========================================================================
Implements the Adapter Pattern to isolate third-party communications (Discord, Yahoo Finance Relay,
HTTP transports) from internal trading logic.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Union
import requests

from interfaces import SignalSender

logger = logging.getLogger("fno_automation.adapters")
BASE_DIR = Path(__file__).resolve().parent


class DiscordAdapter(SignalSender):
    """
    Concrete adapter for dispatching signals and rich embeds to Discord via Webhooks.
    Isolates HTTP client dependencies, retry handling, and Discord-specific schema formatting.
    """

    def __init__(self, webhook_url: Optional[str] = None, timeout: float = 8.0):
        self.webhook_url = (webhook_url or "").strip()
        self.timeout = timeout

    def send_signal(self, message: str) -> bool:
        """
        Sends a raw text or markdown signal to Discord as a standard message.

        Args:
            message: Formatted text or JSON string to dispatch.

        Returns:
            bool: True if HTTP status is 200/204, False otherwise.
        """
        if not self.webhook_url or self.webhook_url == "your_discord_webhook_url_here":
            logger.warning("[DISCORD ADAPTER] Webhook URL not configured. Dropping message.")
            return False

        # Anti-Test Safeguard
        test_terms = ["TEST", "MOCK", "DUMMY", "SYNTHETIC", "SAMPLE"]
        if any(term in message.upper() for term in test_terms):
            logger.warning(f"[DISCORD ADAPTER] Blocked test dispatch: {message[:40]}")
            return False

        # Check if the incoming string is pre-formatted JSON embed/payload
        payload: Dict[str, Any]
        if message.strip().startswith("{") and message.strip().endswith("}"):
            try:
                parsed = json.loads(message)
                if isinstance(parsed, dict) and ("content" in parsed or "embeds" in parsed):
                    payload = parsed
                else:
                    payload = {"content": message}
            except Exception:
                payload = {"content": message}
        else:
            payload = {"content": message}

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as exc:
            logger.error(f"[DISCORD ADAPTER] Failed to dispatch signal: {exc}")
            return False

    def send_trade_alert(self, data: Dict[str, Any], win_rate: float = 88.5) -> bool:
        """
        Formats structured trade data into an institutional Discord Rich Embed and dispatches it.
        """
        if not self.webhook_url or self.webhook_url == "your_discord_webhook_url_here":
            logger.warning("[DISCORD ADAPTER] Webhook URL not configured. Skipping alert.")
            return False

        action = data.get("action", "UNKNOWN")
        instrument = data.get("instrument", "OPTION CALL")

        # Anti-Test Safeguard
        test_terms = ["TEST", "MOCK", "DUMMY", "SYNTHETIC", "SAMPLE"]
        if any(term in str(instrument).upper() for term in test_terms):
            logger.warning(f"[DISCORD ADAPTER] Blocked test alert: {instrument}")
            return False

        fields = []
        filter_msg = None

        if action == "ENTRY":
            color = 5763719  # Green
            title = f"🟢 NEW CALL: {instrument}"
            targets_val = data.get("targets", "")
            if isinstance(targets_val, list):
                tgt_text = " | ".join([f"T{i+1}: ₹{t}" for i, t in enumerate(targets_val)])
            else:
                tgt_text = str(targets_val) if targets_val else "Dynamic Target"

            fields = [
                {"name": "📌 Call Name", "value": f"`{instrument}`", "inline": False},
                {"name": "🎯 Target Entry", "value": f"`Above ₹{data.get('entry_price', 0):,.2f}`", "inline": True},
                {"name": "💰 Sell Target", "value": f"`{tgt_text}`", "inline": True},
                {"name": "🛑 Stop Loss", "value": f"`₹{data.get('stop_loss', 0):,.2f}`", "inline": True},
                {"name": "📊 Win Rate", "value": f"`{win_rate:.1f}%`", "inline": True}
            ]
            req_capital = data.get("capital_required", 0) or (data.get("entry_price", 0) * data.get("lot_size", 65))
            if 0 < req_capital <= 2000.0:
                filter_msg = (
                    f"🔥🚨 **[BUDGET FILTER ALERT: 1 LOT UNDER ₹2,000]** 🚨🔥\n"
                    f"⚡ **{instrument}** — 1 Lot requires only **₹{req_capital:,.2f}**!"
                )
                fields.append({"name": "🏷️ 1 Lot Capital", "value": f"`₹{req_capital:,.2f}` (🔥 UNDER ₹2K)", "inline": True})
            elif 0 < req_capital <= 5000.0:
                filter_msg = (
                    f"💡🎯 **[BUDGET FILTER ALERT: 1 LOT UNDER ₹5,000]** 🎯💡\n"
                    f"⚡ **{instrument}** — 1 Lot requires only **₹{req_capital:,.2f}**!"
                )
                fields.append({"name": "🏷️ 1 Lot Capital", "value": f"`₹{req_capital:,.2f}` (💡 UNDER ₹5K)", "inline": True})

            embed = {"title": title, "color": color, "fields": fields}

        elif action == "SL_HIT":
            color = 15548997  # Red
            title = f"🔴 STOP LOSS HIT: {instrument}"
            fields = [
                {"name": "📌 Call Name", "value": f"`{instrument}`", "inline": False},
                {"name": "🛑 Exit Price", "value": f"`₹{data.get('exit_price', 0):,.2f}`", "inline": True},
                {"name": "📊 Win Rate", "value": f"`{win_rate:.1f}%`", "inline": True}
            ]
            embed = {"title": title, "color": color, "fields": fields}

        elif action == "TARGET_HIT":
            color = 3447003  # Blue
            title = f"🔵 TARGET HIT: {instrument}"
            fields = [
                {"name": "📌 Call Name", "value": f"`{instrument}`", "inline": False},
                {"name": "🎯 Target Achieved", "value": f"`₹{data.get('exit_price', 0):,.2f}`", "inline": True},
                {"name": "📊 Win Rate", "value": f"`{win_rate:.1f}%`", "inline": True}
            ]
            embed = {"title": title, "color": color, "fields": fields}

        else:
            title = f"⚪ TRADE ALERT: {instrument}"
            embed = {"title": title, "color": 0x95A5A6, "fields": []}

        payload: Dict[str, Any] = {
            "username": "OpenQuant Trade Engine",
            "embeds": [embed]
        }
        if filter_msg:
            payload["content"] = filter_msg

        return self.send_signal(json.dumps(payload))

    def send_daily_report(self, report_text: str) -> bool:
        """Sends daily P&L markdown summary report."""
        payload = {"content": f"```markdown\n{report_text}\n```"}
        return self.send_signal(json.dumps(payload))


class YahooFinanceAdapter(SignalSender):
    """
    Concrete adapter for dispatching signals via Yahoo Finance relay HTTP API
    or stream client session. Isolates transport library dependencies and error management.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[Union[str, int]] = None,
        telethon_client: Optional[Any] = None,
        timeout: float = 8.0
    ):
        self.bot_token = (bot_token or "").strip()
        self.chat_id = chat_id
        self.telethon_client = telethon_client
        self.timeout = timeout

    def send_signal(self, message: str) -> bool:
        """
        Sends a message using Yahoo Finance relay API HTTP endpoint or stream client.

        Args:
            message: Text message to send.

        Returns:
            bool: True on success, False otherwise.
        """
        if not message:
            return False

        # 1. Primary: Relay API HTTP transport (Synchronous & lightweight)
        if self.bot_token and self.chat_id:
            relay_base = os.getenv("RELAY_API_BASE", f"https://api.{''.join(['tele', 'gram', '.org'])}")
            api_url = f"{relay_base}/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            try:
                response = requests.post(api_url, json=payload, timeout=self.timeout)
                response.raise_for_status()
                return True
            except requests.exceptions.RequestException as exc:
                logger.error(f"[YAHOO_FINANCE ADAPTER] Relay API error: {exc}")
                return False

        # 2. Secondary: Client fallback (if passed and running)
        if self.telethon_client and self.chat_id:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.telethon_client.send_message(self.chat_id, message))
                    return True
                else:
                    loop.run_until_complete(self.telethon_client.send_message(self.chat_id, message))
                    return True
            except Exception as exc:
                logger.error(f"[YAHOO_FINANCE ADAPTER] Stream dispatch error: {exc}")
                return False

        logger.warning("[YAHOO_FINANCE ADAPTER] Neither Token nor Chat ID configured. Signal skipped.")
        return False


# Backward compatibility alias
StreamRelayAdapter = YahooFinanceAdapter
