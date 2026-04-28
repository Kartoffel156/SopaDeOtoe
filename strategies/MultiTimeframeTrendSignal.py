"""
MultiTimeframeTrendSignal.py
=============================
Evidence-based strategy — multi-timeframe vol-normalized trend signal.
Source: SSRN 4745633, Vyas (2023).
Promoted from Strategy_lab 2026-04-19.
"""

import SopaDeOtoe._path_setup  # noqa: F401

import numpy as np
import pandas as pd
from src.strategy import BaseStrategy


class MultiTimeframeTrendSignal(BaseStrategy):
    """Multi-timeframe vol-normalized trend signal, truncated and averaged.
    Source: SSRN 4745633. Vyas (2023) — Systematic Trend-Following study.
    """

    _scalable_params = {"short_window", "mid_window", "long_window", "vol_window"}

    def __init__(self, short_window=20, mid_window=60, long_window=240,
                 vol_window=60, close_col="Close", **kwargs):
        self.short_window = short_window
        self.mid_window = mid_window
        self.long_window = long_window
        self.vol_window = vol_window
        self.close_col = close_col

    def generate_signals(self, features: pd.DataFrame) -> pd.Series:
        close = features[self.close_col]
        log_ret = np.log(close / close.shift(1)).fillna(0)

        rolling_vol = log_ret.rolling(self.vol_window, min_periods=self.vol_window).std()
        rolling_vol = rolling_vol.replace(0, np.nan)

        def risk_adj_signal(window):
            cum_ret = log_ret.rolling(window, min_periods=window).sum()
            signal = cum_ret / (rolling_vol * np.sqrt(window))
            return signal.clip(-2, 2)

        s1 = risk_adj_signal(self.short_window)
        s2 = risk_adj_signal(self.mid_window)
        s3 = risk_adj_signal(self.long_window)

        combined = (s1 + s2 + s3) / 3.0

        long_trigger  = (combined > 0) & (combined.shift(1) <= 0)
        short_trigger = (combined < 0) & (combined.shift(1) >= 0)

        signals = pd.Series(0, index=features.index, dtype=int)
        signals[long_trigger]  = 1
        signals[short_trigger] = -1

        warmup = self.long_window + self.vol_window
        signals.iloc[:warmup] = 0
        return signals
