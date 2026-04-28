import pytest
import pandas as pd
import numpy as np
from portfolio.data_structures import StrategyResult, PortfolioSignal


def test_strategy_result_creation():
    idx = pd.date_range("2023-01-01", periods=10, freq="D")
    sr = StrategyResult(
        name="test_strat",
        returns=pd.Series(np.random.randn(10) * 0.01, index=idx),
        equity=pd.Series(np.linspace(100, 105, 10), index=idx),
        positions=pd.Series([0, 1, 1, 0, -1, -1, 0, 1, 1, 0], index=idx),
        signals=pd.Series([0, 1, 0, 0, -1, 0, 0, 1, 0, 0], index=idx),
        metrics={"sharpe": 1.2, "max_drawdown": -0.05},
        extended_metrics={},
        montecarlo={},
        trades=[],
        meta={
            "asset": "BTC-USD",
            "interval": "1d",
            "market_type": "crypto",
            "bar_type": "time",
            "bars_per_day": None,
            "n_trials": 1,
            "rf_rate": 0.045,
            "cost": 0.001,
        },
    )
    assert sr.name == "test_strat"
    assert len(sr.returns) == 10
    assert sr.meta["asset"] == "BTC-USD"


def test_portfolio_signal_creation():
    from datetime import datetime
    sig = PortfolioSignal(
        timestamp=datetime(2024, 1, 15, 12, 0),
        asset="BTC-USD",
        action="BUY",
        units=3.2,
        notional=198_400.0,
        position_pct=0.474,
        entry_price=62_000.0,
        order_type="MARKET",
        contributing_strategies=["A", "C"],
        execution_mode="net_position",
        reason="signal_entry",
        portfolio_dd_current=-0.03,
        portfolio_vol_realized=0.14,
        portfolio_vol_target=0.20,
        fdm=1.28,
        vol_scale=1.43,
        weights={"A": 0.35, "B": 0.40, "C": 0.25},
        signals={"A": 0.7, "B": 0.0, "C": 0.6},
    )
    assert sig.action == "BUY"
    assert sig.units == 3.2
    assert "A" in sig.contributing_strategies


def test_portfolio_signal_to_dict():
    from datetime import datetime
    sig = PortfolioSignal(
        timestamp=datetime(2024, 1, 15, 12, 0),
        asset="BTC-USD", action="CLOSE", units=0.0, notional=0.0,
        position_pct=0.0, entry_price=62_000.0, order_type="MARKET",
        contributing_strategies=[], execution_mode="net_position",
        reason="circuit_breaker", portfolio_dd_current=-0.16,
        portfolio_vol_realized=0.30, portfolio_vol_target=0.20,
        fdm=1.28, vol_scale=0.67,
        weights={"A": 0.35}, signals={"A": 0.0},
    )
    d = sig.to_dict()
    assert isinstance(d, dict)
    assert d["action"] == "CLOSE"
    assert d["reason"] == "circuit_breaker"
