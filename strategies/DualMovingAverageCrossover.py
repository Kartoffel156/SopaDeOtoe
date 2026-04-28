"""
DualMovingAverageCrossover.py
==============================
Evidence-based strategy — dual MA crossover.
Source: SSRN 275161.
Promoted from Strategy_lab 2026-04-19.
"""

import SopaDeOtoe._path_setup  # noqa: F401

import pandas as pd
from src.strategy import BaseStrategy


class DualMovingAverageCrossover(BaseStrategy):
    """Dual MA crossover — long above, short below. Source: SSRN 275161."""

    def __init__(self, short_period=1, long_period=50,
                 close_col='Close', **kwargs):
        self.short_period = short_period
        self.long_period = long_period
        self.close_col = close_col

    def generate_signals(self, features: pd.DataFrame) -> pd.Series:
        close = features[self.close_col]

        ma_short = close.rolling(window=self.short_period).mean()
        ma_long = close.rolling(window=self.long_period).mean()

        spread = ma_short - ma_long

        long_condition = spread > 0
        short_condition = spread < 0

        long_trigger = long_condition & ~long_condition.shift(1).fillna(False).astype(bool)
        short_trigger = short_condition & ~short_condition.shift(1).fillna(False).astype(bool)

        signals = pd.Series(0, index=features.index, dtype=int)
        signals[long_trigger] = 1
        signals[short_trigger] = -1

        signals.iloc[:self.long_period] = 0
        return signals
