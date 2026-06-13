"""
dataset.py — Load, validate, and pool meta-datasets from multiple strategies.

Each strategy export lives in results/exploration/meta_datasets/<strategy>/
and contains 7 parquets + 1 JSON (produced by worker.py --mode export).

This module:
  1. Loads individual exports
  2. Validates feature schema compatibility
  3. Pools them into a single (X, y, w) dataset with strategy indicators
"""

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd


def load_strategy_export(meta_export_dir: Path) -> dict:
    """
    Load the 7 parquets + 1 JSON from a single strategy's export directory.

    Args:
        meta_export_dir: Path to results/exploration/meta_datasets/<strategy>/

    Returns:
        dict with keys: meta_feat, meta_labels, weights, labels, side,
                        close, signal_times, config
    """
    meta_export_dir = Path(meta_export_dir)

    return {
        'meta_feat': pd.read_parquet(meta_export_dir / "meta_feat.parquet"),
        'meta_labels': pd.read_parquet(meta_export_dir / "meta_labels.parquet")['label'],
        'weights': pd.read_parquet(meta_export_dir / "weights.parquet")['weight'],
        'labels': pd.read_parquet(meta_export_dir / "labels.parquet"),
        'side': pd.read_parquet(meta_export_dir / "side.parquet")['side'],
        'close': pd.read_parquet(meta_export_dir / "close.parquet")['Close'],
        'signal_times': pd.read_parquet(meta_export_dir / "signal_times.parquet")['signal_time'],
        'config': json.loads((meta_export_dir / "config_snapshot.json").read_text()),
    }


def load_all_exports(meta_datasets_dir: Path) -> dict[str, dict]:
    """
    Discover and load all strategy exports from the meta_datasets directory.

    Args:
        meta_datasets_dir: Path to results/exploration/meta_datasets/

    Returns:
        dict mapping strategy_name -> export dict
    """
    meta_datasets_dir = Path(meta_datasets_dir)
    exports = {}
    for d in sorted(meta_datasets_dir.iterdir()):
        if d.is_dir() and (d / "meta_feat.parquet").exists():
            exports[d.name] = load_strategy_export(d)
    return exports


def validate_schemas(exports: dict[str, dict]) -> None:
    """
    Validate that feature columns across strategies are compatible.

    Raises ValueError if the intersection of features is < 50% of the
    union (too disparate to pool). Warns if they differ but overlap is
    reasonable.
    """
    if len(exports) < 2:
        return

    all_cols = {name: set(data['meta_feat'].columns) for name, data in exports.items()}
    union = set().union(*all_cols.values())
    intersection = set.intersection(*all_cols.values())

    if len(union) == 0:
        raise ValueError("All strategy exports have zero features")

    overlap_pct = len(intersection) / len(union)

    if overlap_pct < 0.5:
        diff_report = []
        for name, cols in all_cols.items():
            missing = union - cols
            if missing:
                diff_report.append(f"  {name}: missing {sorted(missing)}")
        raise ValueError(
            f"Feature schemas too disparate to pool. "
            f"Overlap: {len(intersection)}/{len(union)} ({overlap_pct:.0%}). "
            f"Diff:\n" + "\n".join(diff_report)
        )

    if intersection != union:
        only_in = {}
        for name, cols in all_cols.items():
            unique = cols - intersection
            if unique:
                only_in[name] = sorted(unique)
        if only_in:
            warnings.warn(
                f"[META_POOL] Feature schemas differ across strategies. "
                f"Overlap: {len(intersection)}/{len(union)} ({overlap_pct:.0%}). "
                f"Strategy-specific features (will be filled with 0): {only_in}"
            )


def pool_datasets(
    exports: dict[str, dict],
) -> tuple[pd.DataFrame, pd.Series, pd.Series, dict]:
    """
    Pool meta-datasets from multiple strategies into a single training set.

    Handles:
      - Feature union with fillna(0) for missing columns
      - Strategy identity columns (strategy_id + one-hot indicators)
      - Weight normalization (equal contribution per strategy)
      - Timestamp jitter to avoid index collisions
      - Temporal sort for walk-forward CV

    Args:
        exports: dict mapping strategy_name -> export dict
                 (from load_strategy_export or load_all_exports)

    Returns:
        X_pool   : pd.DataFrame — pooled features + strategy indicators
        y_pool   : pd.Series {0,1} — pooled meta-labels
        w_pool   : pd.Series — normalized weights
        metadata : dict with strategy_id_map, n_rows_per_strategy,
                   feature_columns, close_series, per_strategy_data
    """
    if not exports:
        raise ValueError("No exports to pool")

    strategy_names = sorted(exports.keys())
    strategy_id_map = {name: i for i, name in enumerate(strategy_names)}

    feat_parts = []
    label_parts = []
    weight_parts = []
    strategy_id_parts = []

    for name in strategy_names:
        data = exports[name]
        sid = strategy_id_map[name]
        mf = data['meta_feat'].copy()
        ml = data['meta_labels'].copy()
        w = data['weights'].copy()

        # Align to common index (meta_labels is the truth)
        common_idx = mf.index.intersection(ml.index).intersection(w.index)
        mf = mf.loc[common_idx]
        ml = ml.loc[common_idx]
        w = w.loc[common_idx]

        # Timestamp jitter: +1ms per strategy_id to avoid collisions
        jittered_idx = mf.index + pd.Timedelta(milliseconds=sid)
        mf.index = jittered_idx
        ml.index = jittered_idx
        w.index = jittered_idx

        # Normalize weights: equal contribution per strategy
        w *= 1.0 / len(w)

        feat_parts.append(mf)
        label_parts.append(ml)
        weight_parts.append(w)
        strategy_id_parts.append(
            pd.Series(sid, index=jittered_idx, name='strategy_id', dtype=np.int8)
        )

    # Concat features (outer join — fill missing with 0)
    X_pool = pd.concat(feat_parts, join='outer').fillna(0)
    y_pool = pd.concat(label_parts)
    w_pool = pd.concat(weight_parts)
    strategy_ids = pd.concat(strategy_id_parts)

    # Add strategy identity columns
    X_pool['strategy_id'] = strategy_ids

    # One-hot strategy indicators
    for name, sid in strategy_id_map.items():
        # Use a short prefix: strat_<name>
        col_name = f"strat_{name}"
        X_pool[col_name] = (strategy_ids == sid).astype(np.int8)

    # Normalize total weights to len(y_pool)
    w_pool *= len(y_pool) / w_pool.sum()

    # Sort temporally for walk-forward CV
    sort_order = X_pool.index.argsort()
    X_pool = X_pool.iloc[sort_order]
    y_pool = y_pool.iloc[sort_order]
    w_pool = w_pool.iloc[sort_order]

    # Use first strategy's close as reference (all use same base config)
    first_data = exports[strategy_names[0]]
    close_series = first_data['close']

    # Build per-strategy data for downstream gating/replay
    per_strategy_data = {}
    for name in strategy_names:
        data = exports[name]
        per_strategy_data[name] = {
            'side': data['side'],
            'labels': data['labels'],
            'signal_times': data['signal_times'],
            'close': data['close'],
            'config': data['config'],
        }

    n_rows_per_strategy = {
        name: len(exports[name]['meta_labels']) for name in strategy_names
    }

    # Feature columns (excluding strategy identity columns)
    identity_cols = ['strategy_id'] + [f"strat_{n}" for n in strategy_names]
    feature_columns = [c for c in X_pool.columns if c not in identity_cols]

    metadata = {
        'strategy_id_map': strategy_id_map,
        'n_rows_per_strategy': n_rows_per_strategy,
        'feature_columns': feature_columns,
        'close_series': close_series,
        'per_strategy_data': per_strategy_data,
    }

    return X_pool, y_pool, w_pool, metadata
