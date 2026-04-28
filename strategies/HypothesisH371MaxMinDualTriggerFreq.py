"""
HypothesisH371MaxMinDualTriggerFreq.py
=======================================
H371 — MaxMinDualTriggerFreq [Mean Reversion — Alta Frecuencia]
Hypothesis Run #13, StrategyParrot Strategy Lab, 2026-04-03

Theory
------
H113/H114 proven that max/min touch + oscillator generates 200-222 high-quality
trades. Using DUAL lookbacks (short 7 + long 20) captures extremes at two
different time horizons, producing ~2x independent triggers vs. single lookback.

Kaufman (Trading Systems): short-range extremes within long-range extremes
identify double-confirmed support zones — price respects them repeatedly.
Black (1976): garch_leverage collar blocks entries when vol amplification risk
is high (leverage very negative).

Entry: TRIGGER (long-only)
Signal: +1 on min-touch at EITHER lookback when garch_leverage >= floor
Death: If short_lb and long_lb triggers are correlated > 0.7, dual adds no value
Class: HypothesisH371MaxMinDualTriggerFreq
"""
import SopaDeOtoe._path_setup  # noqa: F401
import numpy as np
import pandas as pd
from src.strategy import BaseStrategy


class HypothesisH371MaxMinDualTriggerFreq(BaseStrategy):
    """Dual-lookback max/min trigger with garch_leverage collar."""

    def __init__(self, short_lb=7, long_lb=20, lev_floor=-0.8,
                 close_col="Close", **kwargs):
        self.short_lb = short_lb
        self.long_lb = long_lb
        self.lev_floor = lev_floor
        self.close_col = close_col

    def generate_signals(self, features):
        close = features[self.close_col].astype(float)

        rmin_s = close.rolling(self.short_lb, min_periods=self.short_lb).min()
        rmin_l = close.rolling(self.long_lb, min_periods=self.long_lb).min()

        at_min_s = close <= rmin_s
        at_min_l = close <= rmin_l

        prev_min_s = at_min_s.shift(1).fillna(False)
        prev_min_l = at_min_l.shift(1).fillna(False)

        trig_s = at_min_s & ~prev_min_s
        trig_l = at_min_l & ~prev_min_l

        lev = features.get("garch_leverage",
                            pd.Series(0.0, index=features.index)).fillna(0.0)
        lev_ok = lev >= self.lev_floor

        entry = (trig_s | trig_l) & lev_ok

        sig = pd.Series(0, index=features.index, dtype=int)
        sig[entry] = 1
        warmup = max(self.short_lb, self.long_lb) + 10
        sig.iloc[:warmup] = 0
        return sig
