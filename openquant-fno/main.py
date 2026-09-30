"""
OpenQuant-FNO: Automated Options Signal Ingestion & Quantitative Research Station
================================================================================
Master orchestrator uniting:
1. Real-time Yahoo Finance options stream
2. Low-latency regex normalization
3. Strict margin validation (₹10,000 capital filter)
4. Black-Scholes analytical Greeks & quant confidence
5. Thread-safe SQLite persistence
6. High-contrast Discord Rich Embed dispatch
7. 16:00 IST automated settlement report loop
8. Bloomberg-styled Rich TUI display
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import Optional

import config
from core.regex_parser import parse_signal, NormalizedSignal
from core.sqlite_db import TradeDatabase
from core.discord_dispatcher import DiscordDispatcher
from core.stream_listener import YahooFinanceListener, IngestionStreamListener
from quant_suite.greeks_calculator import BlackScholesEngine
from quant_suite.risk_manager import RiskManager
from quant_suite.openbb_service import OpenBBMarketService
from terminal.rich_tui import OpenQuantTUI

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("openquant.master")


class OpenQuantStation:
    """
    Master system orchestrator coordinating the execution and quantitative layers.
    """

    def __init__(self):
        self.db = TradeDatabase(config.DB_PATH)
        self.discord = DiscordDispatcher(config.DISCORD_WEBHOOK_URL)
        self.risk_manager = RiskManager(config.LOT_SIZES, config.MAX_MARGIN_RUPEES)
        self.market_service = OpenBBMarketService()
        self.tui = OpenQuantTUI()
        
        self.stream_listener: Optional[YahooFinanceListener] = None
        self._shutdown_event = asyncio.Event()
        self._daily_report_sent_date: Optional[str] = None
        self._openbb_url = f"http://{config.OPENBB_API_HOST}:{config.OPENBB_API_PORT}"

        # High-Signal Coalescing Engine: Aggregates rapid updates into ONE clean card
        self._update_buffer: List[str] = []
        self._debounce_task: Optional[asyncio.Task] = None
        self._debounce_lock = asyncio.Lock()
        self._source_title: str = "Market Feed"

    def is_market_hours(self) -> bool:
        """
        Determines whether the current time falls within NSE regular trading hours
        (09:15 - 15:30 IST, Monday through Friday).
        """
        if not config.MARKET_HOURS_ONLY:
            return True

        now_ist = datetime.now(config.IST)
        # Weekday: 0 = Mon, 4 = Fri, 5 = Sat, 6 = Sun
        if now_ist.weekday() >= 5:
            return False

        cur_min = now_ist.hour * 60 + now_ist.minute
        open_min = config.MARKET_OPEN_HOUR * 60 + config.MARKET_OPEN_MINUTE
        close_min = config.MARKET_CLOSE_HOUR * 60 + config.MARKET_CLOSE_MINUTE

        return open_min <= cur_min <= close_min

    async def _queue_channel_update(self, text: str, source_title: str = "Market Feed"):
        """Buffers rapid-fire commentary and milestone updates and consolidates into ONE clear card."""
        async with self._debounce_lock:
            self._update_buffer.append(text)
            self._source_title = source_title
            if self._debounce_task and not self._debounce_task.done():
                self._debounce_task.cancel()
            self._debounce_task = asyncio.create_task(self._flush_aggregated_updates(debounce_sec=5.0))

    async def _flush_aggregated_updates(self, debounce_sec: float = 5.0):
        try:
            await asyncio.sleep(debounce_sec)
            async with self._debounce_lock:
                msgs = list(self._update_buffer)
                self._update_buffer.clear()
            if not msgs:
                return

            import re
            peak_price = 0
            latest_sl = None
            action = None
            pivot_range = None

            for m in msgs:
                up = m.upper()
                # Peak price extraction
                p_match = re.search(r'^\s*(\d{2,5})\b', m) or re.search(r'\b(\d{2,5})\b.*(?:TARGET|TGT|🎯|🤩|😍|🥰|🫶|🚀|🔥|👀|CMP)', m, re.IGNORECASE)
                if p_match:
                    try:
                        val = int(p_match.group(1))
                        if val < 5000:  # Option premium
                            peak_price = max(peak_price, val)
                    except ValueError:
                        pass

                # Trailing SL extraction
                sl_match = re.search(r'(?:SL\s*(?:CHNGE|CHANGE|TO|KRDO|KARDO)?\s*(?:TO)?\s*[:=]?\s*(\d{2,5})|(\d{2,5})\s*SL)', up)
                if ('SL' in up and any(k in up for k in ['CHNGE', 'CHANGE', 'KRDO', 'KARDO', 'MODIFY', 'TRAIL', 'HOLD'])) or 'COST TO COST' in up:
                    if 'COST TO COST' in up:
                        latest_sl = 'Cost-to-Cost (Break-Even)'
                    elif sl_match:
                        latest_sl = f'₹{sl_match.group(1) or sl_match.group(2)}'

                # Pivot range extraction
                range_match = re.search(r'(\d{4,5}\s*[-–—]\s*\d{4,5})', m)
                if range_match:
                    pivot_range = range_match.group(1)

                # Action extraction
                if any(k in up for k in ['BOOK KRLO', 'BOOK PROFIT', 'BOOK KARLO', 'JISS KO BOOK', 'RETEST', 'EXIT']):
                    action = 'Book Profit / Exit (Retest Detected)'

            if not action:
                if peak_price > 0 and latest_sl:
                    action = f'Lock Partial Profit • Trail SL to {latest_sl}'
                elif peak_price > 0:
                    action = 'Trail SL to Cost • Lock Partial Quantity'
                elif latest_sl:
                    action = f'Modify Stop-Loss to {latest_sl}'
                elif pivot_range:
                    action = f'Monitor {pivot_range} for breakdown or reversal'
                else:
                    action = 'Monitor Price Momentum'

            logger.info(f"📢 [CONSOLIDATED ALERT] Dispatching single update card: Peak={peak_price}, SL={latest_sl}, Action={action}")
            await self.discord.send_aggregated_update(
                peak_price=f'₹{peak_price}' if peak_price > 0 else None,
                trailing_sl=latest_sl,
                action=action,
                pivot_range=pivot_range
            )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[AGGREGATOR] Error dispatching consolidated update: {e}", exc_info=True)

    def _format_simple_target_msg(self, text: str, instrument: str, entry_price: float) -> Optional[str]:
        """Formats clean, simple, single-line target and SL update drops for active open trades."""
        import re
        clean = text.strip()
        upper = clean.upper()

        # 1. Price runner / Target number check
        num_match = re.search(r'^\s*(\d{2,5})\b', clean) or re.search(r'\b(\d{2,5})\b.*(?:TARGET|TGT|🎯|🤩|😍|🥰|🫶|🚀|🔥|👀|CMP)', clean, re.IGNORECASE)
        if num_match:
            try:
                val = float(num_match.group(1))
                if 0 < val < 5000:
                    pts = val - entry_price
                    is_target = 'TARGET' in upper or 'TGT' in upper or '🎯' in clean
                    tag = 'Target 🎯' if is_target else '🚀'
                    pts_str = f' (+{pts:.0f} pts)' if pts > 0 else ''
                    sl_note = ' • SL Cost-to-Cost' if 'COST' in upper else ''
                    return f'🎯 **{int(val)} {tag}** • **{instrument}**{pts_str}{sl_note}'
            except ValueError:
                pass

        # 2. Check for SL modification
        sl_num_match = re.search(r'(?:SL\s*(?:CHNGE|CHANGE|TO|KRDO|KARDO)?\s*(?:TO)?\s*[:=]?\s*(\d{2,5})|(\d{2,5})\s*SL)', upper)
        is_c2c = 'COST TO COST' in upper or 'C2C' in upper or 'COSTO TO COST' in upper
        if ('SL' in upper and any(k in upper for k in ['CHNGE', 'CHANGE', 'KRDO', 'KARDO', 'MODIFY', 'TRAIL', 'HOLD', 'COST'])) or is_c2c:
            new_sl = 'Cost-to-Cost' if is_c2c else (f'₹{sl_num_match.group(1) or sl_num_match.group(2)}' if sl_num_match else 'Updated')
            return f'🛡️ **SL to {new_sl}** • **{instrument}** (Capital Protected)'

        # 3. Check for Book Profit / Exit
        if any(k in upper for k in ['BOOK KRLO', 'BOOK PROFIT', 'BOOK KARLO', 'JISS KO BOOK', 'RETEST', 'EXIT']):
            return f'💰 **Book Profit / Exit Now** • **{instrument}** (Retest Level)'

        return None

    async def on_message_received(self, text: str, source_title: str, ocr_text: str = ""):
        """
        Real-time message ingestion callback. High-throughput, zero-bloat pipeline:
        1. If active trade exists: drops simple, instant messages for target numbers & SL updates
        2. If formal ENTRY: Dispatches clean, high-signal card (Call Name, Target Entry, Sell Target, Stop Loss, Win Rate)
        """
        try:
            # Quantitative Signal Parsing (Quant models & filters are for show)
            signal_obj: Optional[NormalizedSignal] = parse_signal(text, ocr_text)

            # Check if this is an update for an ACTIVE open trade
            open_trade = self.db.get_latest_open_trade()
            if open_trade and (not signal_obj or signal_obj.action != "ENTRY"):
                simple_msg = self._format_simple_target_msg(
                    text=text,
                    instrument=open_trade["instrument"],
                    entry_price=open_trade["entry_price"]
                )
                if simple_msg:
                    logger.info(f"🎯 [TARGET UPDATE DISPATCH] {simple_msg}")
                    await self.discord.send_simple_target_message(simple_msg)

                    # If exit / booking called, close the trade in database for show
                    import re
                    upper = text.upper()
                    if any(k in upper for k in ['BOOK KRLO', 'BOOK PROFIT', 'BOOK KARLO', 'JISS KO BOOK', 'EXIT']):
                        exit_match = re.search(r"\b(\d{2,5})\b", text)
                        exit_price = float(exit_match.group(1)) if exit_match else open_trade["entry_price"]
                        underlying = open_trade["instrument"].split()[0]
                        pnl_pts, pnl_rupees = self.risk_manager.calculate_pnl(underlying, open_trade["entry_price"], exit_price)
                        self.db.update_trade_exit(open_trade["id"], exit_price, pnl_pts, pnl_rupees, status="CLOSED")
                        logger.info(f"💾 [DATABASE] Trade #{open_trade['id']} marked CLOSED on exit advice.")
                    return

            if not signal_obj:
                logger.info(f"⚡ [DIRECT BROADCAST] Relaying message to Discord: {text[:60]}")
                await self.discord.send_simple_target_message(text)
                return

            logger.info(f"⚡ [INGESTION] Action: {signal_obj.action} for {signal_obj.instrument or 'Signal'}")

            # Market hours note
            if not self.is_market_hours():
                logger.info("[MARKET HOURS] Signal outside active hours. Relaying alert to Discord.")

            action = signal_obj.action

            # ==================================================================
            # BRANCH 1: NEW TRADE ENTRY
            # ==================================================================
            if action == "ENTRY":
                underlying = signal_obj.underlying or "NIFTY"
                instrument = signal_obj.instrument or f"{underlying} OPTION"
                entry_price = signal_obj.entry_price
                stop_loss = signal_obj.stop_loss
                targets = signal_obj.targets

                # Step 1: Risk Verification (for institutional telemetry & show)
                margin_check = self.risk_manager.evaluate_entry(
                    underlying=underlying,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    targets=targets
                )

                if not margin_check.approved:
                    logger.warning(f"ℹ️ [RISK GATE NOTE] {instrument}: {margin_check.rejection_reason}. Dispatching alert.")

                # Database tracking for show
                existing_open = self.db.get_open_trade(instrument)
                if existing_open:
                    logger.info(f"ℹ️ [DUPLICATE NOTE] Trade for {instrument} already tracked in DB (ID #{existing_open['id']}). Dispatching signal.")

                # Step 2: Quantitative Enrichment (Market Spot & Greeks)
                spot_info = self.market_service.get_index_spot(underlying)
                spot_price = spot_info.get("spot_price", 0.0)

                greeks_res = BlackScholesEngine.calculate_greeks(
                    spot=spot_price if spot_price > 0 else (signal_obj.strike or 24000.0),
                    strike=signal_obj.strike or spot_price,
                    time_to_expiry_days=4.0,
                    option_type=signal_obj.option_type or "CE",
                    market_premium=entry_price
                )

                # Step 3: SQLite Persistence
                trade_id = self.db.insert_trade(
                    instrument=instrument,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    targets=targets,
                    lot_size=margin_check.lot_size,
                    capital_used=margin_check.capital_required,
                    raw_text=text,
                    greeks=greeks_res.to_dict(),
                    underlying=underlying,
                    strike=signal_obj.strike or 0,
                    option_type=signal_obj.option_type or ""
                )
                logger.info(f"💾 [DATABASE] Trade #{trade_id} persisted in OPEN state.")

                # Calculate Institutional Win Rate
                current_win_rate = self.db.get_win_rate()

                # Step 4: Dispatch Discord Rich Embed (Call Name, Target Entry, Sell Target, Stop Loss, Win Rate)
                await self.discord.send_entry_alert(
                    instrument=instrument,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    targets=targets,
                    lot_size=margin_check.lot_size,
                    capital_used=margin_check.capital_required,
                    greeks=greeks_res.to_dict(),
                    market_state=spot_info,
                    confidence=greeks_res.confidence_score,
                    win_rate=current_win_rate
                )

            # ==================================================================
            # BRANCH 2: TARGET HIT / PROFIT BOOKING
            # ==================================================================
            elif action == "TARGET_HIT":
                open_trade = None
                tier = signal_obj.target_tier or 1

                if signal_obj.instrument:
                    open_trade = self.db.get_open_trade(signal_obj.instrument)
                    # If already closed on earlier target (e.g. Target 1), find this same trade for runners
                    if not open_trade:
                        open_trade = self.db.get_latest_trade_for_instrument(signal_obj.instrument)

                elif signal_obj.underlying:
                    open_trade = self.db.get_any_open_trade_by_underlying(signal_obj.underlying)
                else:
                    # Universal fallback ONLY when message contains NO instrument or underlying
                    open_trade = self.db.get_latest_open_trade()

                if not open_trade:
                    logger.info(f"🎯 [TARGET HIT DIRECT DISPATCH] {text}")
                    await self.discord.send_simple_target_message(text)
                    return

                import json
                trade_id = open_trade["id"]
                instrument = open_trade["instrument"]
                entry_price = open_trade["entry_price"]
                lot_size = open_trade["lot_size"]
                underlying = instrument.split()[0]
                prev_exit = open_trade.get("exit_price")

                # Extract stored targets from trade entry
                stored_targets = []
                if open_trade.get("targets"):
                    try:
                        stored_targets = json.loads(open_trade["targets"])
                    except Exception:
                        stored_targets = []

                # Determine exit price: parsed or from stored target for this tier
                exit_price = signal_obj.exit_price
                if exit_price <= 0.0:
                    if stored_targets and len(stored_targets) >= tier:
                        exit_price = float(stored_targets[tier - 1])
                    elif stored_targets and len(stored_targets) > 0:
                        exit_price = float(stored_targets[min(tier - 1, len(stored_targets) - 1)])
                    else:
                        exit_price = round(entry_price * 1.20, 2)

                # Send alert even if price tier was touched previously
                if open_trade.get("status") == "CLOSED" and prev_exit and exit_price <= prev_exit:
                    logger.info(f"ℹ️ [TARGET NOTE] Target tier {tier} touched previously at ₹{prev_exit:,.2f} for {instrument}. Relaying signal.")
                    await self.discord.send_simple_target_message(text)
                    return

                pnl_pts, pnl_rupees = self.risk_manager.calculate_pnl(underlying, entry_price, exit_price)

                # Update SQLite
                self.db.update_trade_exit(
                    trade_id=trade_id,
                    exit_price=exit_price,
                    pnl_points=pnl_pts,
                    pnl_rupees=pnl_rupees,
                    status="CLOSED"
                )
                logger.info(f"🎯 [DATABASE] Trade #{trade_id} ({instrument}) updated to Target {tier} Hit. P&L: +{pnl_pts} pts (+₹{pnl_rupees:,.2f})")

                current_win_rate = self.db.get_win_rate()

                # Dispatch Discord Target Hit embed
                await self.discord.send_target_hit_alert(
                    instrument=instrument,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    lot_size=lot_size,
                    pnl_points=pnl_pts,
                    pnl_rupees=pnl_rupees,
                    target_tier=tier,
                    win_rate=current_win_rate
                )

            # ==================================================================
            # BRANCH 3: STOP LOSS HIT
            # ==================================================================
            elif action == "SL_HIT":
                open_trade = None
                if signal_obj.instrument:
                    open_trade = self.db.get_open_trade(signal_obj.instrument)
                elif signal_obj.underlying:
                    open_trade = self.db.get_any_open_trade_by_underlying(signal_obj.underlying)
                else:
                    open_trade = self.db.get_latest_open_trade()

                if not open_trade:
                    logger.info(f"🛑 [SL HIT DIRECT DISPATCH] {text}")
                    await self.discord.send_simple_target_message(text)
                    return

                trade_id = open_trade["id"]
                instrument = open_trade["instrument"]
                entry_price = open_trade["entry_price"]
                stop_loss = open_trade["stop_loss"]
                lot_size = open_trade["lot_size"]
                underlying = instrument.split()[0]

                exit_price = signal_obj.exit_price if signal_obj.exit_price > 0 else stop_loss
                if exit_price <= 0:
                    exit_price = round(entry_price * 0.80, 2)

                pnl_pts, pnl_rupees = self.risk_manager.calculate_pnl(underlying, entry_price, exit_price)

                # Update SQLite
                self.db.update_trade_exit(
                    trade_id=trade_id,
                    exit_price=exit_price,
                    pnl_points=pnl_pts,
                    pnl_rupees=pnl_rupees,
                    status="CLOSED"
                )
                logger.info(f"🛑 [DATABASE] Trade #{trade_id} CLOSED (SL HIT). P&L: {pnl_pts} pts (-₹{abs(pnl_rupees):,.2f})")

                current_win_rate = self.db.get_win_rate()

                # Dispatch Discord
                await self.discord.send_sl_hit_alert(
                    instrument=instrument,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    lot_size=lot_size,
                    pnl_points=pnl_pts,
                    pnl_rupees=pnl_rupees,
                    win_rate=current_win_rate
                )

            # Refresh TUI dashboard if terminal is interactive
            self._render_dashboard()

        except Exception as err:
            logger.error(f"❌ [PIPELINE ERROR] Error handling signal: {err}", exc_info=True)
            try:
                await self.discord.send_simple_target_message(text)
            except Exception:
                pass

    def _render_dashboard(self):
        """Renders the Rich Bloomberg TUI screen."""
        try:
            summary = self.db.get_daily_summary()
            recent = self.db.get_recent_trades(10)
            self.tui.render(
                channels=config.TARGET_CHANNELS,
                openbb_status="ACTIVE / STANDBY",
                openbb_url=self._openbb_url,
                daily_summary=summary,
                recent_trades=recent,
                max_margin=config.MAX_MARGIN_RUPEES,
                lot_sizes=config.LOT_SIZES
            )
        except Exception as e:
            logger.debug(f"[TUI] Render error: {e}")

    async def daily_report_scheduler_loop(self):
        """
        Background daemon loop scheduled for 16:00 IST every trading day.
        """
        logger.info("[SCHEDULER] Daily 16:00 IST P&L Settlement Reporter loop active.")
        while not self._shutdown_event.is_set():
            now_ist = datetime.now(config.IST)
            today_str = now_ist.strftime("%Y-%m-%d")

            # Check if 16:00 IST reached and not already delivered today
            if (
                now_ist.hour == config.DAILY_REPORT_HOUR
                and now_ist.minute >= config.DAILY_REPORT_MINUTE
                and self._daily_report_sent_date != today_str
            ):
                logger.info(f"📑 [SCHEDULER] 16:00 IST Triggered. Generating Daily Settlement Report for {today_str}...")
                summary = self.db.get_daily_summary(today_str)
                await self.discord.send_daily_summary_report(summary)
                self._daily_report_sent_date = today_str
                logger.info("✅ [SCHEDULER] Daily report successfully dispatched to Discord.")

            # Sleep 30 seconds between checks
            await asyncio.sleep(30)

    async def start(self):
        """Starts all concurrent background tasks and Telethon ingestion."""
        # Print startup banner
        self._render_dashboard()

        # Start Daily Report Scheduler
        scheduler_task = asyncio.create_task(self.daily_report_scheduler_loop())

        # Initialize Yahoo Finance Stream Client
        if config.API_ID and config.API_HASH:
            self.stream_listener = YahooFinanceListener(
                session_path=config.SESSION_FILE_PATH,
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                target_channels=config.TARGET_CHANNELS,
                on_message_callback=self.on_message_received
            )
            while not self._shutdown_event.is_set():
                try:
                    await self.stream_listener.start()
                    logger.info("🚀 [SYSTEM] OpenQuant-FNO is fully armed and listening for institutional alerts.")
                    await self.stream_listener.run_until_disconnected()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    if self._shutdown_event.is_set():
                        break
                    logger.error(f"[YAHOO_FINANCE] Connection interrupted / offline: {e}. Reconnecting in 10s...")
                    try:
                        await self.stream_listener.stop()
                    except Exception:
                        pass
                    await asyncio.sleep(10)
        else:
            logger.warning("⚠️ [YAHOO_FINANCE] API_ID or API_HASH missing in .env. Running in research/offline mode.")
            logger.info("Press Ctrl+C to stop.")
            await self._shutdown_event.wait()

        # Cleanup
        scheduler_task.cancel()
        await self.discord.close()

    def shutdown(self):
        """Triggers graceful shutdown."""
        logger.info("🛑 [SYSTEM] Initiating graceful shutdown...")
        self._shutdown_event.set()
        if self.stream_listener:
            asyncio.create_task(self.stream_listener.stop())


def main():
    station = OpenQuantStation()

    # Signal handlers
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _sig_handler():
        station.shutdown()

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(s, _sig_handler)
        except NotImplementedError:
            pass  # Windows compatibility fallback

    try:
        loop.run_until_complete(station.start())
    except (KeyboardInterrupt, SystemExit):
        station.shutdown()
    finally:
        loop.close()
        print("\n[OpenQuant-FNO] System terminated gracefully.")


if __name__ == "__main__":
    main()
