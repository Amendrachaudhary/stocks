"""
main.py - Master Application Entry Point & Service Orchestrator
===============================================================
Remains as uncompiled Python. Orchestrates:
1. Environment loading and CLI argument parsing.
2. Dependency Injection wiring: DiscordAdapter -> SignalRouter.
3. Yahoo Finance options listener event loop.
4. Daily 16:00 IST P&L settlement reporting task.
5. At-rest cryptographic security utilities (DataProtector).
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Ensure absolute project directory is in python path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from adapters import DiscordAdapter, YahooFinanceAdapter, StreamRelayAdapter
from router import SignalRouter
from encryption import DataProtector, generate_encryption_key
from stream_client import get_client
from telethon import events

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("fno_automation.master")
IST = timezone(timedelta(hours=5, minutes=30))


def build_arg_parser() -> argparse.ArgumentParser:
    """Builds the command-line interface arguments."""
    parser = argparse.ArgumentParser(
        description="OpenQuant / FNO Automation Master Execution Engine & Cryptographic Station"
    )
    parser.add_argument(
        "--generate-key",
        action="store_true",
        help="Generate a new cryptographically secure Fernet 32-byte encryption key."
    )
    parser.add_argument(
        "--encrypt-file",
        metavar="PATH",
        type=str,
        help="Encrypt a target file (e.g. database, session, logs) at rest using ENCRYPTION_KEY."
    )
    parser.add_argument(
        "--decrypt-file",
        metavar="PATH",
        type=str,
        help="Decrypt a target file at rest using ENCRYPTION_KEY."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without subscribing to network sockets (validation mode)."
    )
    return parser


async def daily_report_task(router: SignalRouter):
    """Runs continuously and triggers daily report at exactly 16:00 IST."""
    while True:
        now_ist = datetime.now(IST)
        target_time = now_ist.replace(hour=16, minute=0, second=0, microsecond=0)

        # If it's already past 16:00 today, schedule for tomorrow
        if now_ist >= target_time:
            target_time += timedelta(days=1)

        wait_seconds = (target_time - now_ist).total_seconds()
        logger.info(f"[SCHEDULER] Next daily P&L report in {wait_seconds:.0f}s (16:00 IST)")
        await asyncio.sleep(wait_seconds)

        logger.info("[SCHEDULER] Executing daily P&L settlement report...")
        router.generate_and_send_daily_report()


async def run_listener(router: SignalRouter):
    """Runs the primary Telethon listener loop with dependency-injected SignalRouter."""
    client = get_client()
    if not client:
        logger.warning(
            "⚠️ Yahoo Finance client not configured. Please supply API_ID & API_HASH in .env."
        )
        return

    target_channels = config.TARGET_CHANNELS
    if not target_channels:
        logger.warning("⚠️ No TARGET_CHANNELS defined in .env. Listener running idle.")

    # Register event handler with time-gating and router dispatching
    @client.on(events.NewMessage(chats=target_channels if target_channels else None))
    async def on_new_message(event):
        text = event.raw_text
        if not text:
            return

        # Route through decoupled router
        result = router.process_message(text)
        if result:
            logger.info(f"⚡ [PROCESSED] Action={result.get('action')} | Instrument={result.get('instrument')}")

    logger.info("🚀 Starting Yahoo Finance client session...")
    await client.start()
    logger.info(f"✅ Yahoo Finance client connected. Subscribed channels: {target_channels}")

    # Launch background daily report scheduler
    asyncio.create_task(daily_report_task(router))

    # Keep client listening until disconnected
    await client.run_until_disconnected()


def main():
    """Application entry point."""
    parser = build_arg_parser()
    args = parser.parse_args()

    # 1. Cryptographic Key Generation Command
    if args.generate_key:
        new_key = generate_encryption_key()
        print("=" * 60)
        print("🔑 Generated Fernet Symmetric Encryption Key:")
        print(f"ENCRYPTION_KEY={new_key}")
        print("=" * 60)
        print("Add the line above to your .env file to persist this master key.")
        return

    # 2. File Encryption Command
    if args.encrypt_file:
        protector = DataProtector()
        enc_path = protector.encrypt_file(args.encrypt_file)
        print(f"🔒 [ENCRYPTED] File securely encrypted at: {enc_path}")
        return

    # 3. File Decryption Command
    if args.decrypt_file:
        protector = DataProtector()
        dec_bytes = protector.decrypt_file(args.decrypt_file, output_path=args.decrypt_file + ".dec")
        print(f"🔓 [DECRYPTED] File decrypted ({len(dec_bytes)} bytes) to: {args.decrypt_file}.dec")
        return

    # 4. Dependency Injection Setup
    logger.info("Initializing OpenQuant Trading Engine (Decoupled Architecture)...")

    # Instantiate transport adapter (Primary: Discord Webhook)
    discord_adapter = DiscordAdapter(webhook_url=config.DISCORD_WEBHOOK_URL)

    # Injected into core pipeline router
    router = SignalRouter(
        sender=discord_adapter,
        lot_sizes=config.LOT_SIZES,
        max_capital=config.MAX_MARGIN_RUPEES,
        enforce_trading_hours=True
    )

    if args.dry_run:
        logger.info("✅ Dry-run validation complete. Adapters and Router initialized cleanly.")
        return

    # Launch asynchronous ingestion loop
    try:
        asyncio.run(run_listener(router))
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped gracefully by user interrupt.")
    except Exception as exc:
        logger.critical(f"❌ Fatal runtime error: {exc}", exc_info=True)


if __name__ == "__main__":
    main()
