"""
Final signal output of the portfolio combinator chain.

Translates position targets into PortfolioSignal objects.
Same object for backtest and live — only destination changes.
"""

from datetime import datetime, timezone
import pandas as pd
from portfolio.data_structures import PortfolioSignal


class SignalEmitter:
    def __init__(self, mode: str, trading_capital: float):
        self.mode = mode
        self.trading_capital = trading_capital
        self.signals_emitted: list[PortfolioSignal] = []

    def emit(self, asset: str, position_target: float,
             current_price: float, executor_orders: list[dict],
             portfolio_state: dict) -> PortfolioSignal | None:
        if not executor_orders:
            return None

        first_order = executor_orders[-1]  # most recent order is the action
        action_raw = first_order.get("action", "")

        if action_raw == "CLOSE":
            action = "CLOSE"
            units = 0.0
            notional = 0.0
        elif action_raw == "OPEN":
            direction = first_order.get("direction", "long")
            action = "BUY" if direction == "long" else "SELL"
            notional = abs(position_target) * self.trading_capital
            units = notional / current_price if current_price > 0 else 0.0
        else:
            return None

        reason = first_order.get("reason", "unknown")

        signal = PortfolioSignal(
            timestamp=datetime.now(timezone.utc),
            asset=asset,
            action=action,
            units=round(units, 6),
            notional=round(notional, 2),
            position_pct=round(position_target, 6),
            entry_price=current_price,
            order_type="MARKET",
            contributing_strategies=portfolio_state.get("contributing_strategies", []),
            execution_mode=portfolio_state.get("execution_mode", "net_position"),
            reason=reason,
            portfolio_dd_current=portfolio_state.get("dd_current", 0),
            portfolio_vol_realized=portfolio_state.get("vol_realized", 0),
            portfolio_vol_target=portfolio_state.get("vol_target", 0),
            fdm=portfolio_state.get("fdm", 1.0),
            vol_scale=portfolio_state.get("vol_scale", 1.0),
            weights=portfolio_state.get("weights", {}),
            signals=portfolio_state.get("signals", {}),
        )

        self.signals_emitted.append(signal)
        return signal

    def replay(self) -> list[PortfolioSignal]:
        return list(self.signals_emitted)

    def to_dataframe(self) -> pd.DataFrame:
        if not self.signals_emitted:
            return pd.DataFrame()
        rows = [s.to_dict() for s in self.signals_emitted]
        return pd.DataFrame(rows)
