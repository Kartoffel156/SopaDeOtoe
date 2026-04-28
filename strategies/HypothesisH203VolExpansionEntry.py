"""
HypothesisH203VolExpansionEntry.py
====================================
H203 — VolExpansionEntry
Hypothesis Run, StrategyParrot Strategy Lab, 2026-04-01

Theory
------
The first bar of a volatility-regime expansion (vol_reg > prior vol_reg)
marks a potential regime break. Order flow imbalance (OFI) direction at
that moment reveals whether buyers or sellers are in control, giving a
directional edge on the new regime.

De Prado: regime-break entries aligned with order flow.
Signal target: 20–5000 in ~17072 bars.
"""
import Strategy_lab._path_setup  # noqa: F401
import numpy as np
import pandas as pd
from src.strategy import BaseStrategy


class HypothesisH203VolExpansionEntry(BaseStrategy):
    """First bar of vol-regime expansion + OFI direction -> entry."""

    def __init__(self, ofi_window: int = 3, close_col: str = "Close", **kwargs):
        self.ofi_window = ofi_window
        self.close_col = close_col

    def _vol_regime(self, features: pd.DataFrame) -> pd.Series:
        rets = np.log(
            features[self.close_col] / features[self.close_col].shift(1)
        ).fillna(0)
        vol_pct = (
            rets.rolling(20).std()
            .rolling(60, min_periods=20).rank(pct=True)
            .fillna(0.5)
        )
        vol_reg = pd.cut(
            vol_pct, bins=[0, .50, .75, .90, 1.01], labels=[0, 1, 2, 3]
        ).fillna(1).astype(int)
        return vol_reg

    def _ofi(self, features: pd.DataFrame) -> pd.Series:
        if 'order_flow_imbalance' in features.columns:
            return features['order_flow_imbalance']
        bv = features.get('buy_volume', pd.Series(np.nan, index=features.index))
        sv = features.get('sell_volume', pd.Series(np.nan, index=features.index))
        if bv.isna().all():
            return np.sign(features[self.close_col].diff()).fillna(0) * 0.5
        return ((bv - sv) / (bv + sv).replace(0, np.nan)).fillna(0.)

    def generate_signals(self, features: pd.DataFrame) -> pd.Series:
        vol_reg = self._vol_regime(features)
        vol_prev = vol_reg.shift(1).fillna(1).astype(int)
        expanding = vol_reg > vol_prev

        ofi = self._ofi(features)
        ofi_ma = ofi.rolling(self.ofi_window, min_periods=2).mean()

        long_cond = expanding & (ofi_ma > 0)
        short_cond = expanding & (ofi_ma < 0)

        long_trig = long_cond & ~long_cond.shift(1).fillna(False).astype(bool)
        short_trig = short_cond & ~short_cond.shift(1).fillna(False).astype(bool)

        sig = pd.Series(0, index=features.index, dtype=int)
        sig[long_trig] = 1
        sig[short_trig] = -1

        warmup = 65
        sig.iloc[:warmup] = 0
        return sig
