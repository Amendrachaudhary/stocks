"""
OpenQuant-FNO: Core Execution Layer
High-throughput Market Ingestion Stream, regex normalization, SQLite persistence, and Discord telemetry.
"""

from .regex_parser import parse_signal, NormalizedSignal
from .sqlite_db import TradeDatabase
from .discord_dispatcher import DiscordDispatcher

__all__ = [
    "parse_signal",
    "NormalizedSignal",
    "TradeDatabase",
    "DiscordDispatcher"
]
