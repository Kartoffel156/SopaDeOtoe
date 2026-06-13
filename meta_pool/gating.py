"""
gating.py — Convert meta-model probabilities into sized positions.

Replicates the v12 bet-sizing pipeline (main.py L971-1030):
  probability → bet_size → direction × size → average active signals → discretize

Each strategy gets its own pivot threshold from pooled_meta_settings.yaml.
Strategies in hedge_bypass pass through without meta-model filtering.
"""

import os
import sys
from pathlib import Path

import pandas as pd
import yaml


def _ensure_v12_imports():
    """Set up sys.path so v12 modules are importable."""
    sopa_dir = Path(__file__).resolve().parent.parent
    patacon_dir = sopa_dir.parent
    v12_dir = patacon_dir / "StrategyParrot" / "v12"
    for p in [str(patacon_dir), str(patacon_dir / "StrategyParrot"), str(v12_dir), str(sopa_dir)]:
        if p not in sys.path:
            sys.path.insert(0, p)
    os.chdir(str(v12_dir))


def load_gating_config(config_path: Path = None) -> dict:
    """
    Load gating configuration from pooled_meta_settings.yaml.

    Args:
        config_path: Path to YAML. Defaults to config/pooled_meta_settings.yaml.

    Returns:
        dict with keys: pivots, hedge_bypass, bet_sizing_step
    """
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config" / "pooled_meta_settings.yaml"
    config_path = Path(config_path)
    with open(config_path) as f:
        return yaml.safe_load(f)


def gate_positions(
    proba: pd.Series,
    side: pd.Series,
    labels: pd.DataFrame,
    signal_times: pd.DatetimeIndex,
    close: pd.Series,
    cfg: dict,
    pivot: float = 0.50,
) -> pd.Series:
    """
    Convert OOS probabilities into sized, direction-aware positions.

    Replicates v12/main.py bet-sizing pipeline:
      1. Probability → bet size (AFML Eq. 10.1)
      2. Multiply by side direction
      3. Average concurrently active signals
      4. Discretize to grid
      5. Reindex to close.index

    Args:
        proba        : OOS probability per event (index = t0)
        side         : {-1, +1} primary direction
        labels       : DataFrame with cols t1, ret
        signal_times : Timestamps of primary signals
        close        : Close prices (dollar bars)
        cfg          : Config dict with bet_sizing_step
        pivot        : Decision threshold (default 0.50)

    Returns:
        pd.Series: positions indexed on close.index, values in [-1, +1]
    """
    _ensure_v12_imports()
    from src.bet_sizing import (
        average_active_signals,
        bet_size_from_probability,
        discretize_signal,
    )

    # 1. Probability → bet size (only positive bets = meta approves)
    raw_sizes = proba.apply(
        lambda p: bet_size_from_probability(p, pivot=pivot)
    ).clip(lower=0.0)

    # 2. Multiply by side direction
    sized_signals = raw_sizes * side.reindex(raw_sizes.index, method='ffill')

    # 3. Build DataFrame with t0/t1 for average_active_signals
    signals_df = pd.DataFrame({
        'signal': sized_signals,
        't0': sized_signals.index,
        't1': labels['t1'].reindex(sized_signals.index),
    })
    signals_df = signals_df.dropna(subset=['t1'])

    # 4. Average concurrently active signals (temporal concurrence)
    avg_signal = average_active_signals(signals_df)

    # 5. Discretize to grid
    step = cfg.get('bet_sizing_step', 0.01)
    positions = discretize_signal(avg_signal, step=step)

    # 6. Reindex to close.index
    positions = positions.reindex(close.index, method='ffill').fillna(0.0)

    return positions
