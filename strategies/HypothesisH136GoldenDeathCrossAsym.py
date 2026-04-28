"""
HypothesisH136GoldenDeathCrossAsym.py
==================================
T-36 — GoldenDeathCrossAsym  [Trend-Following / Regime-Asymmetric]
Hypothesis Run #4, StrategyParrot Strategy Lab, 2026-04-01

Theory
------
Asymmetric SMA cross strategy respecting price-regime context. Golden
cross (fast > slow transition) → +1 always when market is bullish OR
not in a confirmed bear. Death cross (fast < slow transition) → -1 ONLY
when a bear regime is confirmed (rolling sign-of-returns mean < -bear_thresh).

Rationale: assets with upward drift (BTC, equities) spend most time in
bull/neutral regimes. Unfiltered death crosses produce many false shorts.
Restricting shorts to confirmed bear regimes cuts false negatives at the
cost of missing early shorts — acceptable for upward-drift assets.

Lo & MacKinlay (1999): regime-conditional strategies outperform in
trending assets by aligning bet direction with drift.

Entry: TRIGGER — SMA cross transitions, short gated by bear regime.
Class: HypothesisH136GoldenDeathCrossAsym
"""
import SopaDeOtoe._path_setup  # noqa: F401
import numpy as np
import pandas as pd
from src.strategy import BaseStrategy


class HypothesisH136GoldenDeathCrossAsym(BaseStrategy):
    """Golden cross → +1 (bull/neutral); death cross → -1 only in bear regime."""

    def __init__(self, fast_period=5, slow_period=20, regime_window=20,
                 bear_thresh=0.18, bull_thresh=0.18,
                 close_col="Close", **kwargs):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.regime_window = regime_window
        self.bear_thresh = bear_thresh
        self.bull_thresh = bull_thresh
        self.close_col = close_col

    def generate_signals(self, features):
        close = features[self.close_col]
        fast_sma = close.rolling(self.fast_period, min_periods=self.fast_period).mean()
        slow_sma = close.rolling(self.slow_period, min_periods=self.slow_period).mean()

        # Regime: rolling mean of sign of daily returns
        ret_sign = np.sign(close.pct_change().fillna(0.0))
        regime_val = ret_sign.rolling(self.regime_window, min_periods=max(5, self.regime_window // 4)).mean()

        bull_regime = regime_val > self.bull_thresh
        bear_regime = regime_val < -self.bear_thresh

        prev_fast = fast_sma.shift(1)
        prev_slow = slow_sma.shift(1)

        # Golden cross: fast crosses above slow
        golden_trans = (fast_sma > slow_sma) & (prev_fast <= prev_slow)
        # Golden cross fires when bull OR not bear
        golden = golden_trans & (bull_regime | ~bear_regime)

        # Death cross: fast crosses below slow, confirmed bear only
        death_trans = (fast_sma < slow_sma) & (prev_fast >= prev_slow)
        death = death_trans & bear_regime

        sig = pd.Series(0, index=features.index, dtype=int)
        sig[golden] = 1
        sig[death] = -1
        warmup = max(self.slow_period, self.regime_window) + 5
        sig.iloc[:warmup] = 0
        return sig
