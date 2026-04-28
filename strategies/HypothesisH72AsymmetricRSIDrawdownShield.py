"""
HypothesisH72AsymmetricRSIDrawdownShield.py
=============================================
T-02 — AsymmetricRSIDrawdownShield  [Distribución]
Hypothesis Run #2, StrategyParrot Strategy Lab, 2026-03-31

Theory
------
H2 AsymmetricRSIRegime leads in frequency (201 trades) with Sharpe 0.409
but MaxDD -9.6%. 3 configs of H2 appear in top 19 with almost identical
metrics, indicating the signal is robust but drawdown control is the
bottleneck.

Kaufman (Trading Systems): mean-reversion systems fail systematically when
vol-of-vol increases — signal that the market is in regime transition, not
normal oscillation. High vov blocks RSI entries because "oversold" may be
the start of a trend.

Entry: TRIGGER
Death: vov filter reduces trades < 80 or Sharpe < 0.3
Class: HypothesisH72AsymmetricRSIDrawdownShield
"""

import SopaDeOtoe._path_setup  # noqa: F401
import numpy as np
import pandas as pd
from src.strategy import BaseStrategy


class HypothesisH72AsymmetricRSIDrawdownShield(BaseStrategy):
    """
    Asymmetric RSI with vol_of_vol drawdown shield.

    Parameters
    ----------
    rsi_period : int
        RSI period. Default 14.
    rsi_bull : float
        RSI overbought threshold -> short. Default 70.
    rsi_bear : float
        RSI oversold threshold -> long. Default 30.
    vov_shield : float
        Max vol_of_vol percentile to enter. Default 0.65.
    lookback : int
        Ranking window for vol_of_vol (days, scaled). Default 42.
    close_col : str
        Close price column. Default 'Close'.
    """

    def __init__(
        self,
        rsi_period: int = 14,
        rsi_bull: float = 70.0,
        rsi_bear: float = 30.0,
        vov_shield: float = 0.65,
        lookback: int = 42,
        close_col: str = "Close",
        **kwargs,
    ):
        self.rsi_period = rsi_period
        self.rsi_bull   = rsi_bull
        self.rsi_bear   = rsi_bear
        self.vov_shield = vov_shield
        self.lookback   = lookback
        self.close_col  = close_col

    def _rsi(self, close: pd.Series, period: int) -> pd.Series:
        delta = close.diff()
        gain  = delta.clip(lower=0).ewm(alpha=1.0 / period, adjust=False).mean()
        loss  = (-delta.clip(upper=0)).ewm(alpha=1.0 / period, adjust=False).mean()
        rs    = gain / loss.replace(0, np.nan)
        return 100.0 - 100.0 / (1.0 + rs)

    def generate_signals(self, features: pd.DataFrame) -> pd.Series:
        close = features[self.close_col]
        rsi_v = self._rsi(close, self.rsi_period)

        # vol_of_vol: std of rolling vol
        vov = features.get("vol_of_vol", pd.Series(np.nan, index=features.index))
        if vov.isna().all():
            vol_20 = close.pct_change().rolling(20).std()
            vov    = vol_20.rolling(21).std()
        vov_pct = vov.rolling(self.lookback, min_periods=max(5, self.lookback // 4)).rank(pct=True).fillna(0.5)

        vov_ok = vov_pct < self.vov_shield

        long_cond  = (rsi_v < self.rsi_bear)  & vov_ok
        short_cond = (rsi_v > self.rsi_bull)  & vov_ok

        long_trig  = long_cond  & ~long_cond.shift(1).fillna(False)
        short_trig = short_cond & ~short_cond.shift(1).fillna(False)

        signals = pd.Series(0, index=features.index, dtype=int)
        signals[long_trig]  =  1
        signals[short_trig] = -1

        warmup = max(self.rsi_period * 3, self.lookback) + 10
        signals.iloc[:warmup] = 0
        return signals
