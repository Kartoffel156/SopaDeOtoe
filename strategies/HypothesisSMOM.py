"""
HypothesisSMOM.py
=================
sMOM — Constant Semi-Volatility-Scaled Momentum

Time-series momentum strategy using DOWNSDIE (semi-)volatility scaling.
Same construction as cMOM but uses semi-volatility instead of total volatility.
Semi-volatility only counts squared returns on NEGATIVE momentum days,
capturing asymmetric crash risk better than cMOM.

Paper: Hanauer & Windmuller (2022), "Enhanced Momentum Strategies", SSRN 3437919
Based on: Wang & Yan (2021)
"""
import SopaDeOtoe._path_setup  # noqa: F401

import numpy as np
import pandas as pd
from src.strategy import BaseStrategy


class HypothesisSMOM(BaseStrategy):
    """
    Constant Semi-Volatility-Scaled Time-Series Momentum.

    Like cMOM but scales by downside (semi-)volatility instead of total
    volatility. When momentum is trending upward (few negative days),
    semi-vol shrinks → larger weights.
    """

    def __init__(
        self,
        mom_formation: int = 252,
        mom_skip: int = 21,
        vol_lookback: int = 126,
        weight_cap: float = 5.0,
        signal_thresh: float = 0.0,
        close_col: str = "Close",
        **kwargs,
    ):
        self.mom_formation = int(mom_formation)
        self.mom_skip = int(mom_skip)
        self.vol_lookback = int(vol_lookback)
        self.weight_cap = float(weight_cap)
        self.signal_thresh = float(signal_thresh)
        self.close_col = close_col
        self._target_vol: float = None

    def _downside_vol(self, returns: pd.Series, lookback: int) -> pd.Series:
        """Semi-volatility: only negative return days contribute to variance."""
        downside_r2 = returns.pow(2) * (returns < 0).astype(float)
        rolling = downside_r2.rolling(window=lookback, min_periods=lookback).mean()
        return np.sqrt(21.0 * rolling)

    def generate_signals(self, features: pd.DataFrame) -> pd.Series:
        close = features[self.close_col]
        log_ret = np.log(close / close.shift(1)).fillna(0)

        # Momentum formation
        mom = log_ret.shift(self.mom_skip).rolling(
            window=self.mom_formation, min_periods=self.mom_formation
        ).sum()
        mom = mom.shift(1)

        # Semi-volatility (downside vol)
        semi_vol = self._downside_vol(log_ret, self.vol_lookback)

        # Target vol
        if self._target_vol is None:
            warmup = self.mom_formation + self.mom_skip + self.vol_lookback
            if len(log_ret) > warmup:
                self._target_vol = semi_vol.iloc[warmup:].mean()
            else:
                self._target_vol = 0.05

        vol_adj = (self._target_vol / semi_vol.clip(lower=1e-8)).fillna(1.0)
        vol_adj = vol_adj.clip(upper=self.weight_cap)

        mom_scaled = mom * vol_adj

        sig = pd.Series(0, index=features.index, dtype=int)
        sig[mom_scaled > self.signal_thresh] = 1
        sig[mom_scaled < -self.signal_thresh] = -1

        warmup = self.mom_formation + self.mom_skip + self.vol_lookback
        sig.iloc[:warmup] = 0
        return sig
