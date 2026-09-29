"""
Unit Tests: Black-Scholes Greeks, Risk Gate, Monte Carlo & Backtesting
"""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from quant_suite.greeks_calculator import BlackScholesEngine
from quant_suite.risk_manager import RiskManager
from quant_suite.monte_carlo import MonteCarloSimulator
from quant_suite.backtest_harness import StrategyBacktestHarness


class TestQuantSuite(unittest.TestCase):

    def test_black_scholes_call(self):
        res = BlackScholesEngine.calculate_greeks(
            spot=24000.0,
            strike=24000.0,
            time_to_expiry_days=4.0,
            option_type="CE",
            volatility=0.15
        )
        self.assertGreater(res.price, 0.0)
        self.assertGreater(res.delta, 0.45)
        self.assertLess(res.delta, 0.58)
        self.assertGreater(res.gamma, 0.0)
        self.assertLess(res.theta, 0.0)  # Negative theta for long options
        self.assertGreater(res.vega, 0.0)
        self.assertEqual(res.moneyness, "ATM")
        self.assertGreaterEqual(res.confidence_score, 50.0)

    def test_black_scholes_put(self):
        res = BlackScholesEngine.calculate_greeks(
            spot=24000.0,
            strike=24000.0,
            time_to_expiry_days=4.0,
            option_type="PE",
            volatility=0.15
        )
        self.assertGreater(res.price, 0.0)
        self.assertLess(res.delta, 0.0)
        self.assertGreater(res.delta, -0.60)
        self.assertGreater(res.gamma, 0.0)
        self.assertLess(res.theta, 0.0)

    def test_risk_manager_approval_nifty(self):
        lot_sizes = {"NIFTY": 65, "BANKNIFTY": 30, "FINNIFTY": 60}
        rm = RiskManager(lot_sizes, max_capital_rupees=10000.0)

        # 65 * 120 = 7800 <= 10000 -> Approved
        result = rm.evaluate_entry("NIFTY", entry_price=120.0, stop_loss=95.0, targets=[155.0])
        self.assertTrue(result.approved)
        self.assertEqual(result.lot_size, 65)
        self.assertEqual(result.capital_required, 7800.0)
        self.assertIsNone(result.rejection_reason)

    def test_risk_manager_rejection_exceeds_10k(self):
        lot_sizes = {"NIFTY": 65, "BANKNIFTY": 30, "FINNIFTY": 60}
        rm = RiskManager(lot_sizes, max_capital_rupees=10000.0)

        # 65 * 180 = 11,700 > 10,000 -> Rejection required
        result = rm.evaluate_entry("NIFTY", entry_price=180.0, stop_loss=150.0, targets=[220.0])
        self.assertFalse(result.approved)
        self.assertEqual(result.lot_size, 65)
        self.assertEqual(result.capital_required, 11700.0)
        self.assertIn("exceeds max margin", result.rejection_reason)

    def test_risk_manager_banknifty(self):
        lot_sizes = {"NIFTY": 65, "BANKNIFTY": 30, "FINNIFTY": 60}
        rm = RiskManager(lot_sizes, max_capital_rupees=10000.0)

        # 30 * 300 = 9000 <= 10000 -> Approved
        res_approved = rm.evaluate_entry("BANKNIFTY", entry_price=300.0)
        self.assertTrue(res_approved.approved)

        # 30 * 350 = 10500 > 10000 -> Rejected
        res_rejected = rm.evaluate_entry("BANKNIFTY", entry_price=350.0)
        self.assertFalse(res_rejected.approved)

    def test_monte_carlo_simulation(self):
        sim = MonteCarloSimulator.simulate_trade_path(
            entry_price=200.0,
            stop_loss=170.0,
            target=250.0,
            time_to_expiry_days=2.0,
            num_paths=500
        )
        self.assertEqual(sim.num_paths, 500)
        self.assertGreaterEqual(sim.prob_target_hit, 0.0)
        self.assertLessEqual(sim.prob_target_hit, 1.0)
        self.assertGreater(sim.expected_payoff, 0.0)

    def test_backtest_harness(self):
        mock_trades = [
            {"pnl_rupees": 2400.0},
            {"pnl_rupees": -1500.0},
            {"pnl_rupees": 3200.0},
            {"pnl_rupees": 1800.0},
            {"pnl_rupees": -1200.0}
        ]
        metrics = StrategyBacktestHarness.evaluate_trades(mock_trades, initial_capital=50000.0)
        self.assertEqual(metrics.total_trades, 5)
        self.assertEqual(metrics.win_rate_pct, 60.0)
        self.assertEqual(metrics.total_pnl_rupees, 4700.0)
        self.assertGreater(metrics.profit_factor, 1.0)


if __name__ == "__main__":
    unittest.main()
