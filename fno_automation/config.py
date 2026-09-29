"""
config.py - Centralized Configuration & Environment Isolation
=============================================================
Strictly routes all credentials and parameters through environment variables
using python-dotenv. No secrets or tokens are hardcoded.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Ensure local .env is loaded reliably regardless of working directory
load_dotenv(BASE_DIR / ".env")

# --- Yahoo Finance API Ingestion Credentials ---
_raw_api_id = os.getenv("API_ID", "")
API_ID = int(_raw_api_id.strip()) if _raw_api_id.strip().isdigit() else None
API_HASH = os.getenv("API_HASH", "").strip()
SESSION_NAME = os.getenv("SESSION_NAME", "fno_session").strip()

# Target Yahoo Finance Channels / Feeds
_channels_str = os.getenv("TARGET_CHANNELS", "")
TARGET_CHANNELS = []
for ch in _channels_str.split(","):
    ch = ch.strip()
    if ch:
        if ch.lstrip("-").isdigit():
            TARGET_CHANNELS.append(int(ch))
        else:
            TARGET_CHANNELS.append(ch)

# --- Fallback Yahoo Finance Relay Transport (Optional) ---
YAHOO_FINANCE_RELAY_TOKEN = os.getenv("YAHOO_FINANCE_RELAY_TOKEN", os.getenv("STREAM_RELAY_BOT_TOKEN", "")).strip()
YAHOO_FINANCE_RELAY_CHAT_ID = os.getenv("YAHOO_FINANCE_RELAY_CHAT_ID", os.getenv("STREAM_RELAY_CHAT_ID", "")).strip()
STREAM_RELAY_BOT_TOKEN = YAHOO_FINANCE_RELAY_TOKEN
STREAM_RELAY_CHAT_ID = YAHOO_FINANCE_RELAY_CHAT_ID

# --- Discord Transport ---
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# --- Data Protection & Cryptography ---
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "").strip()

# --- Quantitative Risk & Execution Constraints ---
MAX_MARGIN_RUPEES = float(os.getenv("MAX_MARGIN_RUPEES", 10000.0))

# Lot Sizes for Indian Derivative Indices (2026 Revision)
LOT_SIZES = {
    "NIFTY": 65,
    "BANKNIFTY": 30,
    "FINNIFTY": 60
}
