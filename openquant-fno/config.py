"""
OpenQuant-FNO: Central Configuration & System Constants
======================================================
Defines lot sizing, environment bindings, risk constraints, and Indian standard
market timekeeping for options execution.
"""

import os
from pathlib import Path
from datetime import timezone, timedelta
from dotenv import load_dotenv

# Base Directory paths
BASE_DIR = Path(__file__).resolve().parent
# Store databases in ~/.openquant/data outside iCloud Drive (Desktop/Documents)
# to avoid macOS fileproviderd locking SQLite files with disk I/O errors.
DATA_DIR = Path.home() / ".openquant" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Auto-migrate legacy files from project data/ if they exist
_legacy_data = BASE_DIR / "data"
if _legacy_data.exists():
    import shutil
    for _fname in ["fno_session.session", "openquant_trades.db"]:
        _src = _legacy_data / _fname
        _dst = DATA_DIR / _fname
        if _src.exists() and not _dst.exists():
            shutil.copy2(_src, _dst)

# Load environment variables from .env in the project directory or parent
env_path = BASE_DIR / ".env"
if not env_path.exists():
    # Try parent directory if available
    parent_env = BASE_DIR.parent / ".env"
    if parent_env.exists():
        load_dotenv(parent_env)
    else:
        load_dotenv(env_path)
else:
    load_dotenv(env_path)

# ------------------------------------------------------------------------------
# Telegram API Ingestion Settings
# ------------------------------------------------------------------------------
API_ID_RAW = os.getenv("API_ID", "")
API_ID = int(API_ID_RAW) if API_ID_RAW.strip().isdigit() else None
API_HASH = os.getenv("API_HASH", "")
SESSION_NAME = os.getenv("SESSION_NAME", "openquant_session")
SESSION_FILE_PATH = str(DATA_DIR / SESSION_NAME)

# Channel Routing
_raw_channels = os.getenv("TARGET_CHANNELS", "")
TARGET_CHANNELS = []
for ch in _raw_channels.split(","):
    cleaned = ch.strip()
    if not cleaned:
        continue
    # Support numeric channel IDs (e.g., -100123456789)
    if cleaned.lstrip('-').isdigit():
        TARGET_CHANNELS.append(int(cleaned))
    else:
        TARGET_CHANNELS.append(cleaned)

# ------------------------------------------------------------------------------
_raw_webhook = os.getenv("DISCORD_WEBHOOK_URL", "")
DISCORD_WEBHOOK_URL = _raw_webhook.replace("discordapp.com", "discord.com").strip()
# Strict Execution Mode: ONLY send formal signal execution cards (no chatter/broadcast noise)
FORWARD_CHANNEL_UPDATES = os.getenv("FORWARD_CHANNEL_UPDATES", "false").lower() in ("true", "1", "yes")

# ------------------------------------------------------------------------------
# Official 2026 Indian Contract Lot Sizing (NSE / NIFTY Indices)
# ------------------------------------------------------------------------------
LOT_SIZES = {
    "NIFTY": 65,
    "BANKNIFTY": 30,
    "FINNIFTY": 60,
    "MIDCPNIFTY": 120,
    "SENSEX": 20
}

# ------------------------------------------------------------------------------
# Quantitative Risk & Margin Limits
# ------------------------------------------------------------------------------
# Strict ₹10,000 max capital threshold per single lot entry
MAX_MARGIN_RUPEES = float(os.getenv("MAX_MARGIN_RUPEES", 10000.0))

# ------------------------------------------------------------------------------
# Database Configuration
# ------------------------------------------------------------------------------
DB_PATH = str(DATA_DIR / "openquant_trades.db")

# ------------------------------------------------------------------------------
# Timezone & Market Hours (IST: UTC+05:30)
# ------------------------------------------------------------------------------
IST = timezone(timedelta(hours=5, minutes=30))

MARKET_OPEN_HOUR = 8
MARKET_OPEN_MINUTE = 0
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0
DAILY_REPORT_HOUR = 16
DAILY_REPORT_MINUTE = 0

# Market Hours Enforcement flag (set to False for off-market backtesting/testing)
MARKET_HOURS_ONLY = os.getenv("MARKET_HOURS_ONLY", "false").lower() in ("true", "1", "yes")

# ------------------------------------------------------------------------------
# OpenBB Platform Configuration
# ------------------------------------------------------------------------------
OPENBB_API_HOST = os.getenv("OPENBB_API_HOST", "127.0.0.1")
OPENBB_API_PORT = int(os.getenv("OPENBB_API_PORT", 6900))
