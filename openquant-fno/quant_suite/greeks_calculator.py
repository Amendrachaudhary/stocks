"""
OpenQuant-FNO: Analytical Black-Scholes Greeks Engine
===================================================
Calculates analytical Delta, Gamma, Theta, Vega, Rho, and Implied Volatility for
European Options on Indian Equity Indices (NSE NIFTY, BANKNIFTY, FINNIFTY).
Computes synthetic Quantitative Risk Confidence metric (0% - 100%).
"""

import math
from dataclasses import dataclass
from typing import Optional, Dict, Any
from scipy.stats import norm


@dataclass
class GreeksResult:
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    iv: float
    moneyness: str  # "ITM", "ATM", "OTM"
    confidence_score: float  # 0.0 to 100.0%

    def to_dict(self) -> Dict[str, Any]:
        return {
            "theoretical_price": round(self.price, 2),
            "delta": round(self.delta, 4),
            "gamma": round(self.gamma, 6),
            "theta": round(self.theta, 2),
            "vega": round(self.vega, 2),
            "rho": round(self.rho, 4),
            "iv": round(self.iv, 4),
            "moneyness": self.moneyness,
            "confidence_score": round(self.confidence_score, 1)
        }


class BlackScholesEngine:
    """
    High-performance analytical options pricing and risk sensitivity engine.
    """

    DEFAULT_RISK_FREE_RATE = 0.065  # 6.5% Indian 10Y / RBI Repo rate baseline
    DEFAULT_ANNUAL_VOLATILITY = 0.16  # 16% India VIX representative baseline

    @staticmethod
    def calculate_greeks(
        spot: float,
        strike: float,
        time_to_expiry_days: float = 4.0,
        option_type: str = "CE",
        market_premium: Optional[float] = None,
        volatility: Optional[float] = None,
        risk_free_rate: float = DEFAULT_RISK_FREE_RATE
    ) -> GreeksResult:
        """
        Computes analytical Greeks using closed-form Black-Scholes formulas.
        """
        # Sanitization
        spot = max(1.0, float(spot))
        strike = max(1.0, float(strike))
        T = max(1e-4, time_to_expiry_days / 365.0)  # Time in years
        r = float(risk_free_rate)
        opt_type = option_type.upper().strip()

        # Moneyness classification
        ratio = spot / strike
        if opt_type == "CE":
            if ratio >= 1.015:
                moneyness = "ITM"
            elif ratio <= 0.985:
                moneyness = "OTM"
            else:
                moneyness = "ATM"
        else:
            if ratio <= 0.985:
                moneyness = "ITM"
            elif ratio >= 1.015:
                moneyness = "OTM"
            else:
                moneyness = "ATM"

        # Determine Implied Volatility
        sigma = volatility or BlackScholesEngine.DEFAULT_ANNUAL_VOLATILITY
        if market_premium and market_premium > 0 and volatility is None:
            # Estimate IV from market premium using Newton-Raphson or Brent's method
            estimated_iv = BlackScholesEngine.implied_volatility(
                market_premium, spot, strike, T, r, opt_type
            )
            if estimated_iv is not None and 0.05 < estimated_iv < 2.0:
                sigma = estimated_iv

        # Black-Scholes d1, d2
        sqrt_T = math.sqrt(T)
        d1 = (math.log(spot / strike) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T

        pdf_d1 = norm.pdf(d1)
        cdf_d1 = norm.cdf(d1)
        cdf_d2 = norm.cdf(d2)
        cdf_neg_d1 = norm.cdf(-d1)
        cdf_neg_d2 = norm.cdf(-d2)

        exp_neg_rT = math.exp(-r * T)

        # Theoretical Price & Greeks
        if opt_type == "CE":
            theoretical_price = (spot * cdf_d1) - (strike * exp_neg_rT * cdf_d2)
            delta = cdf_d1
            # Theta per calendar day
            theta = (-(spot * pdf_d1 * sigma) / (2.0 * sqrt_T) - (r * strike * exp_neg_rT * cdf_d2)) / 365.0
            rho = (strike * T * exp_neg_rT * cdf_d2) / 100.0
        else:
            theoretical_price = (strike * exp_neg_rT * cdf_neg_d2) - (spot * cdf_neg_d1)
            delta = cdf_d1 - 1.0  # or -cdf_neg_d1
            theta = (-(spot * pdf_d1 * sigma) / (2.0 * sqrt_T) + (r * strike * exp_neg_rT * cdf_neg_d2)) / 365.0
            rho = (-strike * T * exp_neg_rT * cdf_neg_d2) / 100.0

        # Gamma (identical for Call & Put)
        gamma = pdf_d1 / (spot * sigma * sqrt_T)

        # Vega (1% change in volatility)
        vega = (spot * sqrt_T * pdf_d1) / 100.0

        # Quantitative Confidence Metric Calculation (0% - 100%)
        # Synthesizes Delta sweet-spot (0.35 - 0.65 for high momentum),
        # Moneyness preference (ATM/near-ITM), and Vega exposure.
        abs_delta = abs(delta)
        delta_score = 100.0 - (abs(abs_delta - 0.50) * 120.0)
        delta_score = max(20.0, min(100.0, delta_score))

        moneyness_weights = {"ATM": 1.0, "ITM": 0.92, "OTM": 0.78}
        conf = delta_score * moneyness_weights.get(moneyness, 0.85)

        # Premium proximity adjustment if market premium provided
        if market_premium and theoretical_price > 0:
            price_discrepancy = abs(market_premium - theoretical_price) / max(market_premium, 1.0)
            if price_discrepancy > 0.40:
                conf *= 0.85

        confidence_score = max(10.0, min(99.0, conf))

        return GreeksResult(
            price=max(0.05, theoretical_price),
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho,
            iv=sigma,
            moneyness=moneyness,
            confidence_score=confidence_score
        )

    @staticmethod
    def implied_volatility(
        price: float,
        spot: float,
        strike: float,
        T: float,
        r: float,
        option_type: str = "CE",
        max_iter: int = 50,
        tol: float = 1e-4
    ) -> Optional[float]:
        """
        Inverts Black-Scholes using Newton-Raphson iteration to derive IV.
        """
        # Initial guess from Brenner-Subrahmanyam approximation
        sigma = math.sqrt(2.0 * math.pi / T) * (price / spot)
        sigma = max(0.05, min(sigma, 1.5))

        for _ in range(max_iter):
            sqrt_T = math.sqrt(T)
            d1 = (math.log(spot / strike) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
            d2 = d1 - sigma * sqrt_T

            if option_type == "CE":
                est_price = (spot * norm.cdf(d1)) - (strike * math.exp(-r * T) * norm.cdf(d2))
            else:
                est_price = (strike * math.exp(-r * T) * norm.cdf(-d2)) - (spot * norm.cdf(-d1))

            vega = (spot * sqrt_T * norm.pdf(d1))
            diff = est_price - price

            if abs(diff) < tol:
                return sigma

            if vega < 1e-6:
                break

            sigma -= diff / vega
            if sigma <= 0.01 or sigma >= 3.0:
                break

        return None
