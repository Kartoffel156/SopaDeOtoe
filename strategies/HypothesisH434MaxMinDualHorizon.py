"""
HypothesisH434MaxMinDualHorizon.py
====================================
T-04 — MaxMinDualHorizon  [Distribución]
Hypothesis Run #15, StrategyParrot Strategy Lab, 2026-04-04

Theory
------
MaxMinTrendReversion tiene alta variabilidad paramétrica (std retornos 25% vs
mediana 20.7%). Un lookback único es frágil. Combinar DOS lookbacks en OR
estabiliza y aumenta trades naturalmente.

Carver (Systematic Trading): diversificación de horizontes = varianza reducida
sin perder edge. Fast y slow rara vez coinciden, así que suman.

Entry: MaxMin trigger fast OR slow (long-only)
Death: Si std(retornos) no baja vs baseline lookback único, no funciona.
Class: HypothesisH434MaxMinDualHorizon
"""
import SopaDeOtoe._path_setup  # noqa: F401
import numpy as np
import pandas as pd
from src.strategy import BaseStrategy


class HypothesisH434MaxMinDualHorizon(BaseStrategy):
    """MaxMin con 2 lookbacks ortogonales (fast + slow) en OR."""

    _scalable_params = {'lookback_fast', 'lookback_slow'}

    def __init__(self, lookback_fast: int = 28, lookback_slow: int = 80,
                 zs_thresh: float = 1.7, close_col: str = "Close", **kwargs):
        self.lookback_fast = int(lookback_fast)
        self.lookback_slow = int(lookback_slow)
        self.zs_thresh = float(zs_thresh)
        self.close_col = close_col

    def _mm_trigger(self, close: pd.Series, lookback: int) -> pd.Series:
        rmax = close.rolling(lookback, min_periods=lookback).max()
        rmin = close.rolling(lookback, min_periods=lookback).min()
        at_max = close >= rmax
        at_min = close <= rmin
        zone = at_max | at_min
        return zone & ~zone.shift(1).fillna(False)

    def generate_signals(self, features: pd.DataFrame) -> pd.Series:
        close = features[self.close_col]

        fast_trig = self._mm_trigger(close, self.lookback_fast)
        slow_trig = self._mm_trigger(close, self.lookback_slow)

        # Selectivity gate: zscore lejos del centro (ruido filtrado)
        zs = features.get("zscore", pd.Series(0.0, index=features.index)).fillna(0.0)
        zs_ok = zs.abs() > self.zs_thresh

        combined = (fast_trig | slow_trig) & zs_ok

        signals = pd.Series(0, index=features.index, dtype=int)
        signals[combined] = 1

        warmup = max(self.lookback_fast, self.lookback_slow) + 5
        signals.iloc[:warmup] = 0
        return signals
