"""
OpenQuant-FNO: Strategy Backtesting & Risk Analytics Harness
===========================================================
Event-driven and vectorized backtesting engine computing institutional performance
metrics: Sharpe Ratio, Sortino Ratio, Calmar Ratio, and Maximum Drawdown.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class BacktestMetrics:
    total_trades: int
    win_rate_pct: float
    total_pnl_rupees: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_rupees: float
    max_drawdown_pct: float
    avg_trade_pnl: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "win_rate_pct": round(self.win_rate_pct, 2),
            "total_pnl_rupees": round(self.total_pnl_rupees, 2),
            "profit_factor": round(self.profit_factor, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "calmar_ratio": round(self.calmar_ratio, 2),
            "max_drawdown_rupees": round(self.max_drawdown_rupees, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "avg_trade_pnl": round(self.avg_trade_pnl, 2)
        }


class StrategyBacktestHarness:
    """
    Analyzes historical trade executions or simulated signal sequences.
    """

    @staticmethod
    def evaluate_trades(trades: List[Dict[str, Any]], initial_capital: float = 100000.0) -> BacktestMetrics:
        """
        Calculates institutional risk-adjusted return metrics from trade records.
        """
        if not trades:
            return BacktestMetrics(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        df = pd.DataFrame(trades)
        if "pnl_rupees" not in df.columns:
            return BacktestMetrics(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        pnl_series = df["pnl_rupees"].values
        total_trades = len(pnl_series)
        wins = pnl_series[pnl_series > 0]
        losses = pnl_series[pnl_series < 0]

        win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0
        total_pnl = float(np.sum(pnl_series))
        gross_profit = float(np.sum(wins)) if len(wins) > 0 else 0.0
        gross_loss = abs(float(np.sum(losses))) if len(losses) > 0 else 0.0

        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

        # Equity Curve and Drawdown
        equity_curve = initial_capital + np.cumsum(pnl_series)
        peak_curve = np.maximum.accumulate(equity_curve)
        drawdowns_rupees = peak_curve - equity_curve
        max_dd_rupees = float(np.max(drawdowns_rupees)) if len(drawdowns_rupees) > 0 else 0.0
        drawdowns_pct = (drawdowns_rupees / peak_curve) * 100.0
        max_dd_pct = float(np.max(drawdowns_pct)) if len(drawdowns_pct) > 0 else 0.0

        # Return Series
        trade_returns = pnl_series / initial_capital
        mean_ret = np.mean(trade_returns) if len(trade_returns) > 0 else 0.0
        std_ret = np.std(trade_returns) if len(trade_returns) > 0 else 0.0

        # Sharpe Ratio (annualized assuming ~250 trading days, ~2 trades/day)
        sharpe = (mean_ret / std_ret * np.sqrt(250 * 2)) if std_ret > 1e-6 else 0.0

        # Downside Deviation for Sortino
        negative_returns = trade_returns[trade_returns < 0]
        downside_std = np.std(negative_returns) if len(negative_returns) > 0 else 0.0
        sortino = (mean_ret / downside_std * np.sqrt(250 * 2)) if downside_std > 1e-6 else (sharpe if sharpe > 0 else 0.0)

        # Calmar Ratio: Annual Return / Max Drawdown
        annual_return = (total_pnl / initial_capital) * (250.0 / max(1, total_trades))
        calmar = (annual_return / (max_dd_pct / 100.0)) if max_dd_pct > 0 else 0.0

        return BacktestMetrics(
            total_trades=total_trades,
            win_rate_pct=win_rate,
            total_pnl_rupees=total_pnl,
            profit_factor=profit_factor,
            sharpe_ratio=float(sharpe),
            sortino_ratio=float(sortino),
            calmar_ratio=float(calmar),
            max_drawdown_rupees=max_dd_rupees,
            max_drawdown_pct=max_dd_pct,
            avg_trade_pnl=float(np.mean(pnl_series)) if total_trades > 0 else 0.0
        )
