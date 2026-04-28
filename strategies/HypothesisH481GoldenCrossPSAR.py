"""
HypothesisH481GoldenCrossPSAR.py
T-21 — GoldenCrossPSAR [Paper]
Hypothesis Run #16, 2026-04-12

Theory: H136 uses SMA cross + regime. psar_direction (Parabolic SAR, paper_features)
is +1 bullish, -1 bearish. PSAR as confirmation of SMA cross eliminates
counter-trend crosses. Mesicek (2025, SSRN 5598690).

Entry: TRIGGER — SMA cross confirmed by PSAR direction, asymmetric
Class: HypothesisH481GoldenCrossPSAR
"""
import SopaDeOtoe._path_setup  # noqa: F401
import numpy as np
import pandas as pd
from src.strategy import BaseStrategy


class HypothesisH481GoldenCrossPSAR(BaseStrategy):
    """SMA golden/death cross confirmed by Parabolic SAR direction."""

    def __init__(self, fast_period=7, slow_period=20,
                 psar_af=0.02, psar_max_af=0.20,
                 regime_window=25, bear_thresh=0.20,
                 close_col="Close", **kwargs):
        self.fast_period = int(fast_period)
        self.slow_period = int(slow_period)
        self.psar_af = float(psar_af)
        self.psar_max_af = float(psar_max_af)
        self.regime_window = int(regime_window)
        self.bear_thresh = float(bear_thresh)
        self.close_col = close_col

    def _psar(self, high, low, close):
        """Simple Parabolic SAR implementation returning direction series."""
        n = len(close)
        direction = pd.Series(1, index=close.index, dtype=int)
        psar_val = pd.Series(np.nan, index=close.index)

        af = self.psar_af
        ep = high.iloc[0]
        psar_val.iloc[0] = low.iloc[0]
        is_long = True

        for i in range(1, n):
            prev_psar = psar_val.iloc[i-1]
            if np.isnan(prev_psar):
                psar_val.iloc[i] = close.iloc[i]
                continue

            if is_long:
                psar_val.iloc[i] = prev_psar + af * (ep - prev_psar)
                psar_val.iloc[i] = min(psar_val.iloc[i], low.iloc[i-1])
                if i >= 2:
                    psar_val.iloc[i] = min(psar_val.iloc[i], low.iloc[i-2])

                if low.iloc[i] < psar_val.iloc[i]:
                    is_long = False
                    psar_val.iloc[i] = ep
                    af = self.psar_af
                    ep = low.iloc[i]
                else:
                    if high.iloc[i] > ep:
                        ep = high.iloc[i]
                        af = min(af + self.psar_af, self.psar_max_af)
            else:
                psar_val.iloc[i] = prev_psar - af * (prev_psar - ep)
                psar_val.iloc[i] = max(psar_val.iloc[i], high.iloc[i-1])
                if i >= 2:
                    psar_val.iloc[i] = max(psar_val.iloc[i], high.iloc[i-2])

                if high.iloc[i] > psar_val.iloc[i]:
                    is_long = True
                    psar_val.iloc[i] = ep
                    af = self.psar_af
                    ep = high.iloc[i]
                else:
                    if low.iloc[i] < ep:
                        ep = low.iloc[i]
                        af = min(af + self.psar_af, self.psar_max_af)

            direction.iloc[i] = 1 if is_long else -1

        return direction

    def generate_signals(self, features):
        close = features[self.close_col]
        high = features.get("High", close)
        low = features.get("Low", close)

        fast_sma = close.rolling(self.fast_period, min_periods=self.fast_period).mean()
        slow_sma = close.rolling(self.slow_period, min_periods=self.slow_period).mean()

        psar_dir = self._psar(high, low, close)

        ret_sign = np.sign(close.pct_change().fillna(0.0))
        regime_val = ret_sign.rolling(self.regime_window, min_periods=5).mean().fillna(0.0)
        bear_regime = regime_val < -self.bear_thresh

        cross_up = (fast_sma > slow_sma) & (fast_sma.shift(1) <= slow_sma.shift(1))
        cross_down = (fast_sma < slow_sma) & (fast_sma.shift(1) >= slow_sma.shift(1))

        long_sig = cross_up & (psar_dir == 1) & ~bear_regime
        short_sig = cross_down & (psar_dir == -1) & bear_regime

        signals = pd.Series(0, index=features.index, dtype=int)
        signals[long_sig] = 1
        signals[short_sig] = -1
        warmup = max(self.slow_period, self.regime_window) + 10
        signals.iloc[:warmup] = 0
        return signals
