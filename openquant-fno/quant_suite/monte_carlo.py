"""
OpenQuant-FNO: Monte Carlo Strike Path & Option Viability Simulator
==================================================================
Runs 1,000 to 5,000 stochastic Geometric Brownian Motion (GBM) trajectories to
compute empirical probability of reaching target before stop-loss trigger.
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class SimulationResult:
    num_paths: int
    prob_target_hit: float      # % of paths that touch target before SL or expiry
    prob_sl_hit: float          # % of paths that breach SL first
    expected_payoff: float      # Mean option terminal payoff
    var_95: float               # 95% Value at Risk
    cvar_95: float              # 95% Conditional Value at Risk (Expected Shortfall)
    median_time_to_target_hrs: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "num_paths": self.num_paths,
            "prob_target_hit_pct": round(self.prob_target_hit * 100.0, 1),
            "prob_sl_hit_pct": round(self.prob_sl_hit * 100.0, 1),
            "expected_payoff": round(self.expected_payoff, 2),
            "var_95": round(self.var_95, 2),
            "cvar_95": round(self.cvar_95, 2),
            "median_time_to_target_hrs": round(self.median_time_to_target_hrs, 1) if self.median_time_to_target_hrs else None
        }


class MonteCarloSimulator:
    """
    Stochastic strike path simulator evaluating probability of target vs stop-loss hit.
    """

    @staticmethod
    def simulate_trade_path(
        entry_price: float,
        stop_loss: float,
        target: float,
        time_to_expiry_days: float = 3.0,
        annual_volatility: float = 0.35,  # Option implied volatility
        num_paths: int = 1000,
        time_steps_per_day: int = 24       # Hourly discretization
    ) -> SimulationResult:
        """
        Simulates option price trajectories using Geometric Brownian Motion (GBM)
        with absorbing boundaries at target and stop_loss.
        """
        if entry_price <= 0 or target <= 0 or stop_loss <= 0:
            return SimulationResult(num_paths, 0.5, 0.5, entry_price, 0.0, 0.0, None)

        total_steps = max(10, int(time_to_expiry_days * time_steps_per_day))
        dt = (time_to_expiry_days / 365.0) / total_steps
        mu = 0.05  # Drift assumption

        # Pre-allocate random normal shock matrix
        np.random.seed(42)  # Deterministic seed for reproducible testing
        shocks = np.random.normal(0, 1, size=(num_paths, total_steps))

        # Vectorized GBM simulation
        drift = (mu - 0.5 * (annual_volatility ** 2)) * dt
        diffusion = annual_volatility * np.sqrt(dt)
        log_returns = drift + diffusion * shocks

        price_paths = np.zeros((num_paths, total_steps + 1))
        price_paths[:, 0] = entry_price

        # Cumulative path calculation
        price_paths[:, 1:] = entry_price * np.exp(np.cumsum(log_returns, axis=1))

        # Check barrier hits
        target_hits = 0
        sl_hits = 0
        target_hit_steps = []

        for i in range(num_paths):
            path = price_paths[i, :]
            # Find first time target or stop-loss is hit
            t_hit_indices = np.where(path >= target)[0]
            sl_hit_indices = np.where(path <= stop_loss)[0]

            first_t = t_hit_indices[0] if len(t_hit_indices) > 0 else 999999
            first_sl = sl_hit_indices[0] if len(sl_hit_indices) > 0 else 999999

            if first_t < first_sl and first_t < total_steps:
                target_hits += 1
                target_hit_steps.append(first_t)
            elif first_sl < first_t and first_sl < total_steps:
                sl_hits += 1

        prob_target = target_hits / num_paths
        prob_sl = sl_hits / num_paths

        # Terminal P&L distribution
        terminal_prices = price_paths[:, -1]
        terminal_returns = terminal_prices - entry_price

        # Value at Risk (5th percentile loss)
        var_95 = float(-np.percentile(terminal_returns, 5))
        cvar_95 = float(-np.mean(terminal_returns[terminal_returns <= -var_95])) if np.any(terminal_returns <= -var_95) else var_95

        median_hrs = (float(np.median(target_hit_steps)) / time_steps_per_day * 24.0) if target_hit_steps else None

        return SimulationResult(
            num_paths=num_paths,
            prob_target_hit=prob_target,
            prob_sl_hit=prob_sl,
            expected_payoff=float(np.mean(terminal_prices)),
            var_95=max(0.0, var_95),
            cvar_95=max(0.0, cvar_95),
            median_time_to_target_hrs=median_hrs
        )
