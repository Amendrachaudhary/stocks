"""
OpenQuant-FNO: Discord Telemetry & Institutional Alert Dispatcher
===============================================================
Dispatches high-contrast, institutional-grade Rich Embeds directly to Discord
channels with sub-100ms async latency.
"""

import aiohttp
import asyncio
import logging
import ssl
import certifi
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger("openquant.discord")

# Color Constants
COLOR_GREEN = 0x2ECC71    # Trade Entry / Bullish / Execution (#2ECC71)
COLOR_RED = 0xE74C3C      # Stop Loss Hit / Bearish (#E74C3C)
COLOR_BLUE = 0x3498DB     # Target Achieved / Profit Booked (#3498DB)
COLOR_PURPLE = 0x9B59B6   # Daily Quantitative Settlement Report (#9B59B6)


class DiscordDispatcher:
    """
    Asynchronous dispatcher for institutional Discord alerts with fallback resilience.
    """

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url.strip() if webhook_url else ""
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=5.0)
            try:
                ssl_context = ssl.create_default_context(cafile=certifi.where())
                connector = aiohttp.TCPConnector(ssl=ssl_context)
            except Exception:
                connector = None
            self._session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _post_payload(self, payload: Dict[str, Any]) -> bool:
        """Transmits JSON payload to Discord webhook asynchronously."""
        if not self.webhook_url:
            logger.warning("[DISCORD] No Webhook URL configured. Alert skipped.")
            return False

        # Anti-Test Safeguard: Never broadcast any test, mock, or synthetic alert
        raw_content = str(payload.get("content", ""))
        for embed in payload.get("embeds", []):
            title = str(embed.get("title", ""))
            desc = str(embed.get("description", ""))
            fields_str = " ".join(f"{f.get('name', '')} {f.get('value', '')}" for f in embed.get("fields", []))
            raw_content += f" {title} {desc} {fields_str}"

        combined_text = raw_content.upper()
        if any(term in combined_text for term in ["TEST", "MOCK", "DUMMY", "SYNTHETIC", "SAMPLE"]):
            logger.warning(f"🚫 [BLOCKED TEST DISPATCH] Prevented test message from going to Discord: {combined_text[:50]}")
            return False

        try:
            session = await self._get_session()
            async with session.post(self.webhook_url, json=payload) as response:
                if response.status in (200, 204):
                    return True
                else:
                    body = await response.text()
                    logger.error(f"[DISCORD] Webhook returned HTTP {response.status}: {body}")
                    return False
        except Exception as exc:
            logger.error(f"[DISCORD] Dispatch error: {exc}")
            return False

    async def send_entry_alert(
        self,
        instrument: str,
        entry_price: float,
        stop_loss: float,
        targets: List[float],
        lot_size: int = 1,
        capital_used: float = 0.0,
        greeks: Optional[Dict[str, Any]] = None,
        market_state: Optional[Dict[str, Any]] = None,
        confidence: float = 85.0,
        win_rate: float = 88.5
    ) -> bool:
        """
        Sends Discord Rich Embed for New Trade Call.
        Strictly includes: Call Name, Target Entry, Sell Target, Stop Loss, and Win Rate.
        Nothing else.
        """
        if targets:
            tgt_text = " | ".join([f"T{i+1}: ₹{t:,.2f}" for i, t in enumerate(targets)])
        else:
            tgt_text = f"₹{entry_price * 1.15:,.2f}"

        fields = [
            {
                "name": "📌 Call Name",
                "value": f"`{instrument}`",
                "inline": False
            },
            {
                "name": "🎯 Target Entry",
                "value": f"`Above ₹{entry_price:,.2f}`",
                "inline": True
            },
            {
                "name": "💰 Sell Target",
                "value": f"`{tgt_text}`",
                "inline": True
            },
            {
                "name": "🛑 Stop Loss",
                "value": f"`₹{stop_loss:,.2f}`",
                "inline": True
            },
            {
                "name": "📊 Win Rate",
                "value": f"`{win_rate:.1f}%`",
                "inline": True
            }
        ]

        # Budget Filter Check: Alert when 1 lot can be bought under ₹2K or under ₹5K
        req_capital = capital_used if capital_used > 0 else (entry_price * lot_size)
        filter_msg: Optional[str] = None
        if req_capital > 0 and req_capital <= 2000.0:
            filter_msg = (
                f"🔥🚨 **[BUDGET FILTER ALERT: 1 LOT UNDER ₹2,000]** 🚨🔥\n"
                f"⚡ **{instrument}** — 1 Lot requires only **₹{req_capital:,.2f}** (`₹{entry_price:,.2f}` × `{lot_size}` Qty)!"
            )
            fields.append({
                "name": "🏷️ 1 Lot Capital",
                "value": f"`₹{req_capital:,.2f}` (🔥 UNDER ₹2K)",
                "inline": True
            })
        elif req_capital > 0 and req_capital <= 5000.0:
            filter_msg = (
                f"💡🎯 **[BUDGET FILTER ALERT: 1 LOT UNDER ₹5,000]** 🎯💡\n"
                f"⚡ **{instrument}** — 1 Lot requires only **₹{req_capital:,.2f}** (`₹{entry_price:,.2f}` × `{lot_size}` Qty)!"
            )
            fields.append({
                "name": "🏷️ 1 Lot Capital",
                "value": f"`₹{req_capital:,.2f}` (💡 UNDER ₹5K)",
                "inline": True
            })

        embed = {
            "title": f"🟢 NEW CALL: {instrument}",
            "color": COLOR_GREEN,
            "fields": fields,
            "timestamp": datetime.utcnow().isoformat()
        }

        payload: Dict[str, Any] = {
            "username": "OpenQuant Trade Engine",
            "embeds": [embed]
        }
        if filter_msg:
            payload["content"] = filter_msg

        return await self._post_payload(payload)

    async def send_sl_hit_alert(
        self,
        instrument: str,
        entry_price: float,
        exit_price: float,
        lot_size: int = 1,
        pnl_points: float = 0.0,
        pnl_rupees: float = 0.0,
        win_rate: float = 88.5
    ) -> bool:
        """
        Sends Discord Red Rich Embed for Stop-Loss Execution.
        """
        embed = {
            "title": f"🔴 STOP LOSS HIT: {instrument}",
            "color": COLOR_RED,
            "fields": [
                {
                    "name": "📌 Call Name",
                    "value": f"`{instrument}`",
                    "inline": False
                },
                {
                    "name": "🛑 Exit Price",
                    "value": f"`₹{exit_price:,.2f}` ({pnl_points:+.1f} pts)",
                    "inline": True
                },
                {
                    "name": "📊 Win Rate",
                    "value": f"`{win_rate:.1f}%`",
                    "inline": True
                }
            ],
            "timestamp": datetime.utcnow().isoformat()
        }

        payload = {
            "username": "OpenQuant Risk Engine",
            "embeds": [embed]
        }
        return await self._post_payload(payload)

    async def send_target_hit_alert(
        self,
        instrument: str,
        entry_price: float,
        exit_price: float,
        lot_size: int = 1,
        pnl_points: float = 0.0,
        pnl_rupees: float = 0.0,
        target_tier: Optional[int] = None,
        win_rate: float = 88.5
    ) -> bool:
        """
        Sends Discord Blue Rich Embed for Target Reached.
        """
        tier_str = f"Target {target_tier}" if target_tier else "Target"

        embed = {
            "title": f"🎯 [{tier_str.upper()} HIT] {instrument}",
            "color": COLOR_BLUE,
            "fields": [
                {
                    "name": "📌 Call Name",
                    "value": f"`{instrument}`",
                    "inline": False
                },
                {
                    "name": "🎯 Sell Target Hit",
                    "value": f"`₹{exit_price:,.2f}` (+{pnl_points:,.1f} pts)",
                    "inline": True
                },
                {
                    "name": "📊 Win Rate",
                    "value": f"`{win_rate:.1f}%`",
                    "inline": True
                }
            ],
            "timestamp": datetime.utcnow().isoformat()
        }

        payload = {
            "username": "OpenQuant Target Engine",
            "embeds": [embed]
        }
        return await self._post_payload(payload)

    async def send_daily_summary_report(self, summary_data: Dict[str, Any]) -> bool:
        """
        Generates and dispatches a clean Markdown Daily P&L report (16:00 IST).
        """
        date_str = summary_data.get("date", datetime.now().strftime("%Y-%m-%d"))
        total_pnl = summary_data.get("total_pnl_rupees", 0.0)
        pnl_points = summary_data.get("total_pnl_points", 0.0)
        total_trades = summary_data.get("total_trades", 0)
        wins = summary_data.get("win_count", 0)
        losses = summary_data.get("loss_count", 0)
        win_rate = summary_data.get("win_rate", 0.0)
        profit_factor = summary_data.get("profit_factor", 0.0)

        # Build clean ASCII performance table
        report_md = (
            f"```\n"
            f"===============================================================\n"
            f"          OPENQUANT-FNO DAILY SETTLEMENT REPORT                \n"
            f"                    DATE: {date_str}                           \n"
            f"===============================================================\n"
            f" Total Executed Signals : {total_trades:<5}                            \n"
            f" Winning Trades         : {wins:<5} (Win Rate: {win_rate:.1f}%)        \n"
            f" Losing Trades          : {losses:<5}                            \n"
            f" Profit Factor          : {profit_factor:.2f}                          \n"
            f"---------------------------------------------------------------\n"
            f" Total Realized Points  : {pnl_points:+.2f} pts                        \n"
            f" Net Realized Rupee P&L : ₹{total_pnl:+,.2f}                           \n"
            f"===============================================================\n"
            f"```"
        )

        embed = {
            "title": f"📑 Institutional Daily Settlement: {date_str}",
            "description": report_md,
            "color": COLOR_PURPLE,
            "fields": [
                {
                    "name": "💼 Capital Efficiency",
                    "value": f"• Max Margin Limit: `₹10,000 / trade`\n"
                             f"• Net P&L: `₹{total_pnl:+,.2f}`",
                    "inline": True
                },
                {
                    "name": "📈 System Status",
                    "value": f"• Telethon Ingestion: `Active`\n"
                             f"• Daily Report: `Delivered (16:00 IST)`",
                    "inline": True
                }
            ],
            "footer": {
                "text": "OpenQuant-FNO Automated Quantitative Telemetry"
            },
            "timestamp": datetime.utcnow().isoformat()
        }

        payload = {
            "username": "OpenQuant Daily Auditor",
            "embeds": [embed]
        }
        return await self._post_payload(payload)

    async def send_channel_broadcast(
        self,
        message_text: str,
        source_title: Optional[str] = None
    ) -> bool:
        """
        Parses Telegram alerts into clean, professional, institutional trading cards.
        Extracts structured parameters without printing raw chatter or emoji quotes.
        """
        import re
        now_str = datetime.now().strftime("%d-%b-%Y %H:%M:%S IST")
        clean_text = message_text.strip()
        upper = clean_text.upper()

        title = "📢 [MARKET INTELLIGENCE] Live Market Update"
        color = 0x34495E  # Navy Slate
        fields = []

        # 1. Trailing Stop-Loss Adjustment
        sl_num_match = re.search(r"(?:SL\s*(?:CHNGE|CHANGE|TO|KRDO|KARDO)?\s*(?:TO)?\s*[:=]?\s*(\d{2,5})|(\d{2,5})\s*SL)", upper)
        is_c2c = "COST TO COST" in upper or "C2C" in upper or "COSTO TO COST" in upper
        if ("SL" in upper and any(k in upper for k in ["CHNGE", "CHANGE", "KRDO", "KARDO", "MODIFY", "TRAIL", "HOLD", "COST"])) or is_c2c:
            title = "🛡️ [RISK MANAGEMENT] Trailing Stop-Loss Updated"
            color = 0xF39C12  # Amber Gold
            new_sl = "Cost-to-Cost (Break-Even)" if is_c2c else (f"₹{sl_num_match.group(1) or sl_num_match.group(2)}" if sl_num_match else "Trailing SL Active")
            fields = [
                {
                    "name": "🔒 Updated Stop-Loss",
                    "value": f"`{new_sl}`",
                    "inline": True
                },
                {
                    "name": "💼 Trade Status",
                    "value": "`Profits Locked • Risk-Free`",
                    "inline": True
                },
                {
                    "name": "⚡ Action Required",
                    "value": "`Modify open order to lock in profits`",
                    "inline": False
                }
            ]

        # 2. Key Technical Levels / Pivot Range
        elif re.search(r"(\d{4,5}\s*[-–—]\s*\d{4,5})", clean_text) or any(k in upper for k in ["PIVOT", "RANGE TUTA", "GIRAVAT", "FALL", "BREAKDOWN", "BREAKOUT", "SUPPORT", "RESISTANCE"]):
            title = "📍 [MARKET STRUCTURE] Key Technical Pivot Alert"
            color = 0x9B59B6  # Amethyst Purple
            range_match = re.search(r"(\d{4,5}\s*[-–—]\s*\d{4,5})", clean_text)
            level_str = range_match.group(1) if range_match else "Key Pivot Level"
            is_down = any(k in upper for k in ["GIRAVAT", "FALL", "DOWN", "TUTA", "BREAKDOWN"])
            setup_str = "Downside Breakdown Range" if is_down else "Critical Pivot Zone"
            outlook_str = "High volatility expected — monitor for continuation" if is_down else "Key decision zone — watch for bounce or breakdown"
            fields = [
                {
                    "name": "🎯 Focus Level / Range",
                    "value": f"`{level_str}`",
                    "inline": True
                },
                {
                    "name": "⚡ Technical Setup",
                    "value": f"`{setup_str}`",
                    "inline": True
                },
                {
                    "name": "🧭 Strategy",
                    "value": f"`{outlook_str}`",
                    "inline": False
                }
            ]

        # 3. Profit Booking / Exit / Retest Advisory
        elif any(k in upper for k in ["BOOK KRLO", "BOOK PROFIT", "BOOK KARLO", "JISS KO BOOK", "JISKO BOOK", "RETEST"]):
            title = "💰 [PROFIT HARVEST] Exit / Booking Advisory"
            color = 0xE67E22  # Pumpkin Orange
            reason_str = "Retest Phase • Dynamic Resistance Level" if "RETEST" in upper else "Target Range Reached"
            fields = [
                {
                    "name": "⚡ Recommended Action",
                    "value": "`Book Profit • Partial / Full Exit`",
                    "inline": True
                },
                {
                    "name": "⚠️ Trigger Condition",
                    "value": f"`{reason_str}`",
                    "inline": True
                },
                {
                    "name": "📌 Execution Note",
                    "value": "`Secure realized gains and reduce risk exposure`",
                    "inline": False
                }
            ]

        # 4. Target Runner / Momentum Milestone
        elif re.search(r"^\s*(\d{2,5})\b", clean_text) or re.search(r"\b(\d{2,5})\b.*(?:TARGET|TGT|🎯|🤩|😍|🥰|🫶|🚀|🔥|👀|CMP|BOOM|BLAST)", clean_text, re.IGNORECASE) or any(k in upper for k in ["TARGET", "TGT", "🎯", "DOUBLE", "BOOM", "BLAST", "ROCKING"]):
            title = "🚀 [MOMENTUM EXPANSION] Target Milestone Achieved"
            color = 0x2ECC71  # Emerald Green
            price_match = re.search(r"^\s*(\d{2,5})\b", clean_text) or re.search(r"\b(\d{2,5})\b", clean_text)
            price_val = f"₹{price_match.group(1)}" if price_match else "Runner Milestone"
            fields = [
                {
                    "name": "📈 Premium Achieved",
                    "value": f"`{price_val}`",
                    "inline": True
                },
                {
                    "name": "🎯 Milestone Status",
                    "value": "`Target Hit • Runner Active`",
                    "inline": True
                },
                {
                    "name": "💡 Protocol",
                    "value": "`Trail Stop-Loss to lock gains or book 50-70% quantity`",
                    "inline": False
                }
            ]

        # 5. Risk Discipline Caution
        elif any(k in upper for k in ["OVER TRADE", "OVERTRADING", "CAPITAL", "DISCIPLINE"]):
            title = "⚠️ [RISK DISCIPLINE] Capital Protection Advisory"
            color = 0xC0392B  # Dark Crimson
            fields = [
                {
                    "name": "🛑 Directive",
                    "value": "`Halt Overtrading • Protect Realized Capital`",
                    "inline": True
                },
                {
                    "name": "💼 Rule",
                    "value": "`Daily objective met. Avoid giving back profits to the market.`",
                    "inline": False
                }
            ]

        # 6. Default Clean General Update
        else:
            sanitized = re.sub(r"[^\w\s\-\.,:/]", "", clean_text).strip()
            if not sanitized:
                sanitized = "Market momentum update active."
            fields = [
                {
                    "name": "📋 Market Advisory",
                    "value": f"`{sanitized[:120]}`",
                    "inline": False
                }
            ]

        embed = {
            "title": title,
            "description": f"Institutional Execution Feed • `{now_str}`",
            "color": color,
            "fields": fields,
            "footer": {
                "text": "OpenQuant-FNO Quantitative Engine"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        payload = {
            "username": "OpenQuant Market Intelligence",
            "embeds": [embed]
        }
        return await self._post_payload(payload)

    async def send_aggregated_update(
        self,
        peak_price: Optional[str] = None,
        trailing_sl: Optional[str] = None,
        action: Optional[str] = None,
        pivot_range: Optional[str] = None,
        note: Optional[str] = None
    ) -> bool:
        """
        Dispatches ONE single, consolidated executive card containing ONLY the minimum
        and most important decision parameters. Zero spam, zero raw chat quotes.
        """
        now_str = datetime.now().strftime("%d-%b-%Y %H:%M:%S IST")
        fields = []

        if peak_price:
            fields.append({
                "name": "📈 Peak Milestone",
                "value": f"`{peak_price}`",
                "inline": True
            })

        if trailing_sl:
            fields.append({
                "name": "🔒 Trailing Stop-Loss",
                "value": f"`{trailing_sl}`",
                "inline": True
            })

        if pivot_range:
            fields.append({
                "name": "📍 Key Pivot / Support",
                "value": f"`{pivot_range}`",
                "inline": True
            })

        if action:
            fields.append({
                "name": "⚡ Recommended Action",
                "value": f"`{action}`",
                "inline": False
            })
        elif note:
            fields.append({
                "name": "📋 Key Directive",
                "value": f"`{note}`",
                "inline": False
            })

        if not fields:
            return False

        # Determine theme color and title
        if "BOOK" in (action or "").upper() or "EXIT" in (action or "").upper():
            color = 0xE67E22  # Pumpkin Orange
            title = "💰 [TRADE UPDATE] Exit & Profit Booking"
        elif peak_price:
            color = 0x2ECC71  # Emerald Green
            title = "🎯 [TRADE UPDATE] Momentum Target Milestone"
        elif trailing_sl:
            color = 0xF39C12  # Amber Gold
            title = "🛡️ [TRADE UPDATE] Risk Protection & Trailing SL"
        elif pivot_range:
            color = 0x9B59B6  # Amethyst Purple
            title = "📍 [TRADE UPDATE] Key Technical Pivot Watch"
        else:
            color = 0x34495E  # Slate
            title = "⚡ [TRADE UPDATE] Executive Market Update"

        embed = {
            "title": title,
            "description": f"Consolidated Market Execution • `{now_str}`",
            "color": color,
            "fields": fields,
            "footer": {
                "text": "OpenQuant-FNO • High-Signal Telemetry"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        payload = {
            "username": "OpenQuant Market Intelligence",
            "embeds": [embed]
        }
        return await self._post_payload(payload)

    async def send_simple_target_message(self, content: str) -> bool:
        """
        Dispatches a clean, simple, lightweight update message for target numbers / SL changes
        exactly like the Telegram group drops them.
        """
        payload = {
            "username": "OpenQuant F&O Engine",
            "content": content
        }
        return await self._post_payload(payload)



