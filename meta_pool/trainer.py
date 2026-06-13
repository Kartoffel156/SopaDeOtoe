"""
trainer.py — Walk-forward OOS training for the pooled meta-model.

Imports WalkForwardCV and train_meta_model from v12 to train a single
meta-classifier on the pooled dataset of all graduated strategies.

Key invariants:
  - NEVER predict in-sample (the documented pipeline_meta.py bug)
  - First fold (seed) rows get P=0.5 (neutral, same convention as v12)
  - feature_prefilter disabled for large pooled N (~1500-2500)
"""

import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd


def _ensure_v12_imports():
    """Set up sys.path so v12 modules are importable."""
    sopa_dir = Path(__file__).resolve().parent.parent
    patacon_dir = sopa_dir.parent
    v12_dir = patacon_dir / "StrategyParrot" / "v12"
    for p in [str(patacon_dir), str(patacon_dir / "StrategyParrot"), str(v12_dir), str(sopa_dir)]:
        if p not in sys.path:
            sys.path.insert(0, p)
    # v12 modules expect cwd = v12_dir
    os.chdir(str(v12_dir))


def train_pooled_meta_model(
    X_pool: pd.DataFrame,
    y_pool: pd.Series,
    w_pool: pd.Series,
    cfg: dict,
    n_splits: int = 5,
    embargo_pct: float = 0.01,
    mode: str = 'expanding',
) -> tuple:
    """
    Train a meta-model on the pooled dataset using walk-forward OOS.

    Each fold trains on historical data and predicts the next unseen
    segment. The first fold (seed) has no training history, so those
    rows get P=0.5 (neutral).

    Args:
        X_pool      : Pooled features (from pool_datasets)
        y_pool      : Pooled meta-labels {0, 1}
        w_pool      : Pooled sample weights
        cfg         : v12 config dict (passed to train_meta_model)
        n_splits    : Number of walk-forward splits
        embargo_pct : Fraction of data to embargo between train/test
        mode        : 'expanding' or 'rolling'

    Returns:
        clf        : Final classifier trained on ALL data (for persistence)
        oos_proba  : pd.Series of OOS probabilities, same index as X_pool
        fold_clfs  : List of per-fold classifiers (for audit)
    """
    _ensure_v12_imports()
    from src.cross_validation import WalkForwardCV
    from src.models import train_meta_model

    wfcv = WalkForwardCV(
        n_splits=n_splits,
        embargo_pct=embargo_pct,
        mode=mode,
    )

    # Default neutral probability for seed fold
    oos_proba = pd.Series(0.5, index=X_pool.index)
    fold_clfs = []

    for fold_i, (train_idx, test_idx) in enumerate(wfcv.split(X_pool)):
        X_train = X_pool.iloc[train_idx]
        y_train = y_pool.iloc[train_idx]
        w_train = w_pool.iloc[train_idx]

        fold_clf = train_meta_model(X_train, y_train, w_train, cfg)
        fold_clfs.append(fold_clf)

        proba_test = fold_clf.predict_proba(X_pool.iloc[test_idx])[:, 1]
        oos_proba.iloc[test_idx] = proba_test

    # Final model trained on ALL data (for production/persistence)
    clf = train_meta_model(X_pool, y_pool, w_pool, cfg)

    return clf, oos_proba, fold_clfs


def train_null_model(
    X_pool: pd.DataFrame,
    y_pool: pd.Series,
    n_splits: int = 5,
    embargo_pct: float = 0.01,
    mode: str = 'expanding',
) -> pd.Series:
    """
    Train a DummyClassifier (prior strategy) with the same walk-forward
    splits. Returns OOS probabilities for comparison (gate G4).

    Args:
        X_pool      : Pooled features
        y_pool      : Pooled meta-labels
        n_splits    : Number of walk-forward splits
        embargo_pct : Embargo fraction
        mode        : 'expanding' or 'rolling'

    Returns:
        oos_proba_null : pd.Series of null-model OOS probabilities
    """
    _ensure_v12_imports()
    from sklearn.dummy import DummyClassifier
    from src.cross_validation import WalkForwardCV

    wfcv = WalkForwardCV(
        n_splits=n_splits,
        embargo_pct=embargo_pct,
        mode=mode,
    )

    oos_proba_null = pd.Series(0.5, index=X_pool.index)

    for fold_i, (train_idx, test_idx) in enumerate(wfcv.split(X_pool)):
        dummy = DummyClassifier(strategy='prior')
        dummy.fit(
            X_pool.iloc[train_idx],
            y_pool.iloc[train_idx],
        )
        proba_test = dummy.predict_proba(X_pool.iloc[test_idx])[:, 1]
        oos_proba_null.iloc[test_idx] = proba_test

    return oos_proba_null


def extract_strategy_probas(
    oos_proba: pd.Series,
    X_pool: pd.DataFrame,
    pool_metadata: dict,
) -> dict[str, pd.Series]:
    """
    Revert pooling: extract per-strategy OOS probabilities.

    Filters rows by strategy_id, then undoes the timestamp jitter
    so each strategy's probas have their original DatetimeIndex.

    Args:
        oos_proba     : OOS probabilities from train_pooled_meta_model
        X_pool        : Pooled features (contains strategy_id column)
        pool_metadata : Metadata dict from pool_datasets

    Returns:
        dict mapping strategy_name -> pd.Series of OOS probabilities
                                      with original timestamps
    """
    strategy_id_map = pool_metadata['strategy_id_map']
    strategy_ids = X_pool['strategy_id']

    result = {}
    for name, sid in strategy_id_map.items():
        mask = strategy_ids == sid
        probas = oos_proba[mask].copy()
        # Undo jitter: subtract the millisecond offset
        probas.index = probas.index - pd.Timedelta(milliseconds=sid)
        result[name] = probas

    return result
