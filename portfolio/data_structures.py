"""
Data structures shared across the portfolio combinator layer.

StrategyResult: output of a single strategy pipeline run.
PortfolioSignal: atomic execution instruction — the final output of the combinator.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
import pandas as pd


@dataclass
class StrategyResult:
    """Complete output of one strategy pipeline run."""
    name: str
    returns: pd.Series
    equity: pd.Series
    positions: pd.Series
    signals: pd.Series
    metrics: dict
    extended_metrics: dict
    montecarlo: dict
    trades: list
    meta: dict


@dataclass
class PortfolioSignal:
    """
    Atomic execution instruction. The final output of the entire combinator chain.
    Identical structure for backtest and live — only the destination changes.
    """
    # Execution instruction
    timestamp: datetime
    asset: str
    action: str                             # BUY | SELL | CLOSE
    units: float
    notional: float
    position_pct: float
    entry_price: float
    order_type: str                         # MARKET | LIMIT

    # Decision context (audit trail)
    contributing_strategies: list
    execution_mode: str                     # net_position | per_strategy
    reason: str

    # Portfolio state snapshot
    portfolio_dd_current: float
    portfolio_vol_realized: float
    portfolio_vol_target: float
    fdm: float
    vol_scale: float
    weights: dict
    signals: dict

    def to_dict(self) -> dict:
        """Serialize to dict for JSON logging. Converts datetime to ISO string."""
        d = asdict(self)
        if isinstance(d.get("timestamp"), datetime):
            d["timestamp"] = d["timestamp"].isoformat()
        return d
