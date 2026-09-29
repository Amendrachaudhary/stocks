"""
discord_webhook.py - Backward Compatibility Facade
==================================================
Routes legacy procedural calls directly into the decoupled DiscordAdapter.
Preserves existing integrations while delegating to the new architectural abstractions.
"""

import config
from adapters import DiscordAdapter

# Shared singleton adapter instance configured from environment
_default_adapter = DiscordAdapter(config.DISCORD_WEBHOOK_URL)


def send_trade_alert(data: dict, win_rate: float = 88.5) -> bool:
    """Delegates to DiscordAdapter.send_trade_alert."""
    return _default_adapter.send_trade_alert(data, win_rate=win_rate)


def send_daily_report(report_text: str) -> bool:
    """Delegates to DiscordAdapter.send_daily_report."""
    return _default_adapter.send_daily_report(report_text)
