"""
TSIMeanReversion.py
====================
Evidence-based strategy — TSI mean reversion.
Source: SSRN 4708400.
Promoted from Strategy_lab 2026-04-19.
"""

import SopaDeOtoe._path_setup  # noqa: F401

import numpy as np
import pandas as pd
from src.strategy import BaseStrategy


class TSIMeanReversion(BaseStrategy):
    """TSI mean reversion: long on oversold, short on overbought. Source: SSRN 4708400."""

    _scalable_params = {'tsi_r', 'tsi_s', 'rsi_period'}

    def __init__(self, tsi_r=5, tsi_s=3,
                 tsi_oversold=-20, tsi_overbought=20,
                 rsi_period=5, rsi_oversold=35, rsi_overbought=65,
                 close_col="Close", **kwargs):
        self.tsi_r = tsi_r
        self.tsi_s = tsi_s
        self.tsi_oversold = tsi_oversold
        self.tsi_overbought = tsi_overbought
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.close_col = close_col

    def generate_signals(self, features: pd.DataFrame) -> pd.Series:
        close = features[self.close_col]

        delta = close.diff()
        smoothed_delta = delta.ewm(span=self.tsi_r, adjust=False).mean()
        double_smoothed_delta = smoothed_delta.ewm(span=self.tsi_s, adjust=False).mean()
        smoothed_abs = delta.abs().ewm(span=self.tsi_r, adjust=False).mean()
        double_smoothed_abs = smoothed_abs.ewm(span=self.tsi_s, adjust=False).mean()
        tsi = 100 * double_smoothed_delta / double_smoothed_abs.replace(0, np.nan)

        gain = delta.where(delta > 0, 0).rolling(self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.rsi_period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        tsi_enter_oversold = (tsi < self.tsi_oversold) & (tsi.shift(1) >= self.tsi_oversold)
        rsi_confirms_long = rsi < self.rsi_oversold

        tsi_enter_overbought = (tsi > self.tsi_overbought) & (tsi.shift(1) <= self.tsi_overbought)
        rsi_confirms_short = rsi > self.rsi_overbought

        signals = pd.Series(0, index=features.index, dtype=int)
        signals[tsi_enter_oversold & rsi_confirms_long] = 1
        signals[tsi_enter_overbought & rsi_confirms_short] = -1

        warmup = self.tsi_r + self.tsi_s + 5
        signals.iloc[:warmup] = 0
        return signals
