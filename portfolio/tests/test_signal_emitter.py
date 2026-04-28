import pytest
import pandas as pd
from portfolio.signal_emitter import SignalEmitter
from portfolio.data_structures import PortfolioSignal


def test_emit_buy_signal():
    emitter = SignalEmitter(mode="backtest", trading_capital=100_000)
    sig = emitter.emit(
        asset="BTC-USD", position_target=0.30, current_price=50_000.0,
        executor_orders=[{"action": "OPEN", "size": 0.30, "direction": "long"}],
        portfolio_state={
            "dd_current": -0.02, "vol_realized": 0.14,
            "vol_target": 0.20, "fdm": 1.28, "vol_scale": 1.43,
            "weights": {"A": 0.35}, "signals": {"A": 0.7},
            "contributing_strategies": ["A"],
            "execution_mode": "net_position",
        },
    )
    assert isinstance(sig, PortfolioSignal)
    assert sig.action == "BUY"
    assert sig.units == pytest.approx(0.60, abs=0.01)  # 0.30 * 100k / 50k
    assert sig.notional == pytest.approx(30_000, abs=100)


def test_emit_close_signal():
    emitter = SignalEmitter(mode="backtest", trading_capital=100_000)
    sig = emitter.emit(
        asset="BTC-USD", position_target=0.0, current_price=50_000.0,
        executor_orders=[{"action": "CLOSE", "size": 0.30, "reason": "circuit_breaker"}],
        portfolio_state={
            "dd_current": -0.16, "vol_realized": 0.30,
            "vol_target": 0.20, "fdm": 1.28, "vol_scale": 0.67,
            "weights": {}, "signals": {},
            "contributing_strategies": [],
            "execution_mode": "net_position",
        },
    )
    assert sig.action == "CLOSE"
    assert sig.units == 0.0


def test_emit_returns_none_when_no_orders():
    emitter = SignalEmitter(mode="backtest", trading_capital=100_000)
    sig = emitter.emit(
        asset="BTC-USD", position_target=0.30, current_price=50_000.0,
        executor_orders=[],
        portfolio_state={
            "dd_current": 0, "vol_realized": 0.15,
            "vol_target": 0.15, "fdm": 1.0, "vol_scale": 1.0,
            "weights": {}, "signals": {},
            "contributing_strategies": [],
            "execution_mode": "net_position",
        },
    )
    assert sig is None


def test_signals_emitted_accumulate():
    emitter = SignalEmitter(mode="backtest", trading_capital=100_000)
    state = {
        "dd_current": 0, "vol_realized": 0.15, "vol_target": 0.15,
        "fdm": 1.0, "vol_scale": 1.0, "weights": {}, "signals": {},
        "contributing_strategies": ["A"], "execution_mode": "net_position",
    }
    emitter.emit("BTC", 0.3, 50000, [{"action": "OPEN", "size": 0.3, "direction": "long"}], state)
    emitter.emit("ETH", 0.2, 3000, [{"action": "OPEN", "size": 0.2, "direction": "long"}], state)
    df = emitter.to_dataframe()
    assert len(df) == 2
    assert "asset" in df.columns
    assert "action" in df.columns


def test_emit_returns_none_for_unknown_action():
    emitter = SignalEmitter(mode="backtest", trading_capital=100_000)
    sig = emitter.emit(
        asset="BTC-USD", position_target=0.30, current_price=50_000.0,
        executor_orders=[{"action": "MUTATE"}],  # neither OPEN nor CLOSE
        portfolio_state={
            "dd_current": 0, "vol_realized": 0.15, "vol_target": 0.15,
            "fdm": 1.0, "vol_scale": 1.0, "weights": {}, "signals": {},
            "contributing_strategies": [], "execution_mode": "net_position",
        },
    )
    assert sig is None


def test_to_dataframe_empty_returns_empty_frame():
    emitter = SignalEmitter(mode="backtest", trading_capital=100_000)
    df = emitter.to_dataframe()
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_replay_returns_all_signals():
    emitter = SignalEmitter(mode="backtest", trading_capital=100_000)
    state = {
        "dd_current": 0, "vol_realized": 0.15, "vol_target": 0.15,
        "fdm": 1.0, "vol_scale": 1.0, "weights": {}, "signals": {},
        "contributing_strategies": ["A"], "execution_mode": "net_position",
    }
    emitter.emit("BTC", 0.3, 50000, [{"action": "OPEN", "size": 0.3, "direction": "long"}], state)
    signals = emitter.replay()
    assert len(signals) == 1
    assert isinstance(signals[0], PortfolioSignal)
