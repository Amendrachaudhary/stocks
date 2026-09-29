"""
Unit Tests: Thread-Safe SQLite Trade Persistence & Settlement Engine
"""

import unittest
import tempfile
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.sqlite_db import TradeDatabase


class TestSQLiteBlotter(unittest.TestCase):

    def setUp(self):
        self.tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db = TradeDatabase(self.tmp_file.name)

    def tearDown(self):
        try:
            Path(self.tmp_file.name).unlink(missing_ok=True)
        except Exception:
            pass

    def test_insert_and_get_open_trade(self):
        trade_id = self.db.insert_trade(
            instrument="BANKNIFTY 48000 CE",
            entry_price=220.0,
            stop_loss=190.0,
            targets=[260.0, 300.0],
            lot_size=30,
            capital_used=6600.0,
            underlying="BANKNIFTY",
            strike=48000,
            option_type="CE"
        )
        self.assertGreater(trade_id, 0)

        open_trade = self.db.get_open_trade("BANKNIFTY 48000 CE")
        self.assertIsNotNone(open_trade)
        self.assertEqual(open_trade["id"], trade_id)
        self.assertEqual(open_trade["entry_price"], 220.0)

    def test_update_trade_exit_target_hit(self):
        trade_id = self.db.insert_trade(
            instrument="NIFTY 24200 CE",
            entry_price=120.0,
            stop_loss=95.0,
            targets=[150.0],
            lot_size=65,
            capital_used=7800.0,
            underlying="NIFTY"
        )
        
        # Exit at 155 -> +35 pts -> +2,275 Rs
        pnl_pts = 35.0
        pnl_rs = 35.0 * 65
        success = self.db.update_trade_exit(
            trade_id=trade_id,
            exit_price=155.0,
            pnl_points=pnl_pts,
            pnl_rupees=pnl_rs,
            status="CLOSED"
        )
        self.assertTrue(success)

        # Confirm trade is no longer OPEN
        self.assertIsNone(self.db.get_open_trade("NIFTY 24200 CE"))

        # Check daily summary
        summary = self.db.get_daily_summary()
        self.assertEqual(summary["total_trades"], 1)
        self.assertEqual(summary["closed_count"], 1)
        self.assertEqual(summary["win_count"], 1)
        self.assertEqual(summary["total_pnl_rupees"], pnl_rs)

    def test_daily_summary_aggregate_pnl(self):
        # Trade 1: Win (+₹1,500)
        t1 = self.db.insert_trade("NIFTY 24000 CE", 100.0, 80.0, [130.0], lot_size=65, capital_used=6500.0)
        self.db.update_trade_exit(t1, 125.0, 25.0, 1625.0, "CLOSED")

        # Trade 2: Loss (-₹1,300)
        t2 = self.db.insert_trade("BANKNIFTY 50000 PE", 200.0, 170.0, [250.0], lot_size=30, capital_used=6000.0)
        self.db.update_trade_exit(t2, 170.0, -30.0, -900.0, "CLOSED")

        summary = self.db.get_daily_summary()
        self.assertEqual(summary["closed_count"], 2)
        self.assertEqual(summary["win_count"], 1)
        self.assertEqual(summary["loss_count"], 1)
        self.assertEqual(summary["win_rate"], 50.0)
        self.assertEqual(summary["total_pnl_rupees"], 725.0)  # 1625 - 900


if __name__ == "__main__":
    unittest.main()
