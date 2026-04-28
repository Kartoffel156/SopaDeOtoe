"""
HypothesisH236MomentumReversalAsym.py
========================================
H236 — MomentumReversalAsym
StrategyParrot Strategy Lab, 2026-04-02

Theory
------
Short-term corrections within uptrends offer asymmetric return opportunities.
When the 5-day cumulative return dips below -dn_thresh, it signals a
short-term correction that tends to reverse in trending assets. Enter long
on the first bar satisfying this condition.

Long only: triggered when cum5 < -dn_thresh (rising edge).

References: Jegadeesh (1990) short-run return reversals; Lehmann (1990).
"""
import SopaDeOtoe._path_setup  # noqa: F401

import numpy as np
import pandas as pd
from src.strategy import BaseStrategy


class HypothesisH236MomentumReversalAsym(BaseStrategy):
    """Long only on 5-day cumulative return dip below -dn_thresh."""

    def __init__(self, up_thresh: float = 0.020, dn_thresh: float = 0.020,
                 close_col: str = "Close", **kwargs):
        self.up_thresh = up_thresh
        self.dn_thresh = dn_thresh
        self.close_col = close_col

    def generate_signals(self, features: pd.DataFrame) -> pd.Series:
        warmup = 10
        close = features[self.close_col]

        log_ret = np.log(close / close.shift(1)).fillna(0)
        cum5 = log_ret.rolling(5, min_periods=1).sum().shift(1)

        # Long: dip below -dn_thresh
        long_cond = cum5 < -self.dn_thresh

        long_prev = long_cond.shift(1).fillna(False).astype(bool)
        long_trig = long_cond & ~long_prev

        sig = pd.Series(0, index=features.index, dtype=int)
        sig[long_trig] = 1
        sig.iloc[:warmup] = 0
        return sig
