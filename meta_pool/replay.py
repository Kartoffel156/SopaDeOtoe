"""
replay.py — Backtest gated positions and package as StrategyResult for Layer 2.

Two functions:
  1. replay_to_returns: run vectorized backtest with v12's cost model
  2. build_strategy_result: wrap equity/returns into StrategyResult so Layer 2
     doesn't know Layer 1.5 existed
"""

import os
import sys
from pathlib import Path

import pandas as pd


def _ensure_v12_imports():
    """Set up sys.path so v12 modules are importable."""
    sopa_dir = Path(__file__).resolve().parent.parent
    patacon_dir = sopa_dir.parent
    v12_dir = patacon_dir / "StrategyParrot" / "v12"
    for p in [str(patacon_dir), str(patacon_dir / "StrategyParrot"), str(v12_dir), str(sopa_dir)]:
        if p not in sys.path:
            sys.path.insert(0, p)
    os.chdir(str(v12_dir))


def replay_to_returns(
    positions: pd.Series,
    close: pd.Series,
    cfg: dict,
) -> dict:
    """
    Run vectorized backtest with the same cost model as v12.

    Args:
        positions      : Output of gate_positions(), indexed on close.index
        close          : Close prices (dollar bars)
        cfg            : Config dict with cost, slippage_bps, spread_bps,
                         initial_capital

    Returns:
        dict with keys: equity (pd.Series), positions, n_trades
    """
    _ensure_v12_imports()
    from src.backtest import run_backtest

    results = run_backtest(
        prices=close,
        signals=positions,
        cost=cfg['cost'],
        initial_capital=cfg['initial_capital'],
        slippage_bps=cfg.get('slippage_bps', 2.0),
        spread_bps=cfg.get('spread_bps', 1.0),
        min_rebalance=cfg.get('min_rebalance', 0.0),
    )

    return {
        'equity': results['equity'],
        'positions': positions,
        'n_trades': int((positions.diff().abs() > 0.01).sum()),
    }


def build_strategy_result(
    name: str,
    replay_result: dict,
    source_meta: dict,
):
    """
    Package replay output as a StrategyResult for Layer 2.

    Aggregates intraday equity to daily, computes basic metrics,
    and wraps everything so the portfolio layer can consume it
    without knowing about Layer 1.5.

    Args:
        name           : Strategy name (e.g. 'HypothesisH136WonhamMarkov')
        replay_result  : Output of replay_to_returns()
        source_meta    : Extra metadata (pivot, v12_run_dir, etc.)

    Returns:
        StrategyResult ready for Layer 2 portfolio construction
    """
    from portfolio.data_structures import StrategyResult

    eq = replay_result['equity']

    # Aggregate to daily: last value per calendar day
    daily_eq = eq.groupby(eq.index.normalize()).last().sort_index()
    daily_eq.index.name = None

    returns = daily_eq.pct_change().fillna(0.0).astype(float)
    returns.name = name
    equity = daily_eq.astype(float)
    equity.name = name

    # Positions proxy: activity indicator
    positions = (returns.abs() > 1e-12).astype(int)
    positions.name = name
    signals = positions.copy()
    signals.name = name

    # Basic metrics
    ann_factor = 252
    mean_r = returns.mean()
    std_r = returns.std()
    sharpe = (mean_r / std_r * (ann_factor ** 0.5)) if std_r > 0 else 0.0
    cum_ret = (1 + returns).prod() - 1
    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max
    max_dd = float(drawdown.min())
    calmar = float(cum_ret / abs(max_dd)) if abs(max_dd) > 1e-10 else 0.0

    metrics = {
        'sharpe': float(sharpe),
        'total_return': float(cum_ret),
        'max_drawdown': max_dd,
        'calmar': calmar,
        'n_trades': replay_result['n_trades'],
    }

    return StrategyResult(
        name=name,
        returns=returns,
        equity=equity,
        positions=positions,
        signals=signals,
        metrics=metrics,
        extended_metrics={},
        montecarlo={},
        trades=[],
        meta={
            'source': 'pooled_meta',
            'daily_bars': len(daily_eq),
            **source_meta,
        },
    )
