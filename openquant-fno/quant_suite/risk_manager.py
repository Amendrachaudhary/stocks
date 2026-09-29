"""
OpenQuant-FNO: Quantitative Risk Management & Capital Allocation Gate
===================================================================
Enforces strict institutional capital bounds (skips trades > ₹10,000 capital),
calculates position margin, verifies lot sizing, and evaluates risk-to-reward ratios.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger("openquant.risk")


@dataclass
class MarginCheckResult:
    approved: bool
    capital_required: float
    max_capital: float
    lot_size: int
    num_lots: int
    risk_per_share: float
    reward_per_share: float
    risk_reward_ratio: float
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "capital_required": round(self.capital_required, 2),
            "max_capital": round(self.max_capital, 2),
            "lot_size": self.lot_size,
            "num_lots": self.num_lots,
            "risk_per_share": round(self.risk_per_share, 2),
            "reward_per_share": round(self.reward_per_share, 2),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "rejection_reason": self.rejection_reason
        }


class RiskManager:
    """
    Evaluates institutional risk gates, capital thresholds, and contract limits.
    """

    def __init__(self, lot_sizes: Dict[str, int], max_capital_rupees: float = 10000.0):
        self.lot_sizes = lot_sizes
        self.max_capital_rupees = max_capital_rupees

    def get_lot_size(self, underlying: str) -> int:
        """Retrieves official 2026 contract lot size for the given index."""
        cleaned = underlying.upper().replace(" ", "")
        return self.lot_sizes.get(cleaned, 65)  # Defaults to NIFTY standard 65

    def evaluate_entry(
        self,
        underlying: str,
        entry_price: float,
        stop_loss: float = 0.0,
        targets: Optional[List[float]] = None
    ) -> MarginCheckResult:
        """
        Validates whether an entry signal passes the hard ₹10,000 capital constraint
        and returns position sizing metrics.
        """
        lot_size = self.get_lot_size(underlying)
        capital_required = entry_price * lot_size

        # Evaluate Risk-to-Reward
        risk_per_share = max(1.0, (entry_price - stop_loss)) if (stop_loss > 0 and stop_loss < entry_price) else (entry_price * 0.20)
        
        target_1 = targets[0] if (targets and len(targets) > 0 and targets[0] > entry_price) else (entry_price + (risk_per_share * 1.5))
        reward_per_share = max(1.0, target_1 - entry_price)
        rr_ratio = reward_per_share / risk_per_share

        # Hard Gate: Max ₹10,000 Capital Limit Rule
        if capital_required > self.max_capital_rupees:
            reason = (
                f"Capital required (₹{capital_required:,.2f}) exceeds max margin "
                f"threshold (₹{self.max_capital_rupees:,.2f}) for 1 lot ({lot_size} units @ ₹{entry_price:.2f})."
            )
            logger.warning(f"[RISK GATE] REJECTED: {underlying} - {reason}")
            return MarginCheckResult(
                approved=False,
                capital_required=capital_required,
                max_capital=self.max_capital_rupees,
                lot_size=lot_size,
                num_lots=0,
                risk_per_share=risk_per_share,
                reward_per_share=reward_per_share,
                risk_reward_ratio=rr_ratio,
                rejection_reason=reason
            )

        # Approved
        logger.info(
            f"[RISK GATE] APPROVED: {underlying} - Capital ₹{capital_required:,.2f} "
            f"within limit (1 Lot: {lot_size} units). R:R = {rr_ratio:.2f}"
        )
        return MarginCheckResult(
            approved=True,
            capital_required=capital_required,
            max_capital=self.max_capital_rupees,
            lot_size=lot_size,
            num_lots=1,
            risk_per_share=risk_per_share,
            reward_per_share=reward_per_share,
            risk_reward_ratio=rr_ratio,
            rejection_reason=None
        )

    def calculate_pnl(
        self,
        underlying: str,
        entry_price: float,
        exit_price: float
    ) -> tuple[float, float]:
        """
        Calculates realized points and rupees based on lot size.
        """
        if entry_price <= 0.0 or exit_price <= 0.0:
            return 0.0, 0.0

        pnl_points = exit_price - entry_price
        lot_size = self.get_lot_size(underlying)
        pnl_rupees = pnl_points * lot_size
        return round(pnl_points, 2), round(pnl_rupees, 2)
