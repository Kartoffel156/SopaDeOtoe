"""
HypothesisH167BollingerRangingOFIGate.py
===========================================
H167 — BollingerRangingOFIGate  [Mean-Reversion/Microstructure]
Hypothesis Run #5, StrategyParrot Strategy Lab, 2026-04-01

Theory
------
Bollinger Band mean-reversion entries (H166) are improved by an order
flow imbalance (OFI) confirmation filter.  OFI measures the net balance
of buyer-vs-seller-initiated volume; negative OFI at a lower-band touch
means sellers are still active and the reversal is not yet confirmed.

By requiring OFI > -ofi_thresh before entering long mean-reversion
(i.e. excluding confirmed seller dominance), false reversal entries
are reduced.  Conversely, OFI < -ofi_thresh at an upper-band touch
in ranging confirms seller conviction → short entry.

In trending regimes, OFI acts as a breakout quality gate:
  - Trending break_up entry requires no special OFI gate (direction
    already confirmed by breakout above upper band).
  - Trending break_down requires seller OFI confirmation for short.

Easley & O'Hara (2012): OFI correlates with informed trading flow.
Order flow skew at extremes improves entry timing.

Entry: TRIGGER (transition-based)
  Long  → touch_lower & is_ranging & ofi_avg > -ofi_thresh
           OR break_up & ~is_ranging
  Short → touch_upper & is_ranging & ofi_avg < -ofi_thresh
           OR break_down & ~is_ranging
Class: HypothesisH167BollingerRangingOFIGate
"""
import Strategy_lab._path_setup  # noqa: F401
import numpy as np
import pandas as pd
from src.strategy import BaseStrategy


class HypothesisH167BollingerRangingOFIGate(BaseStrategy):
    """Bollinger regime + OFI gate for both long and short entries."""

    def __init__(self, bb_period=20, bb_std=2.0, bw_pct=50,
                 ofi_thresh=0.20, ofi_window=5,
                 close_col="Close", **kwargs):
        self.bb_period  = bb_period
        self.bb_std     = bb_std
        self.bw_pct     = bw_pct
        self.ofi_thresh = ofi_thresh
        self.ofi_window = ofi_window
        self.close_col  = close_col

    # ------------------------------------------------------------------
    def _kama(self, close, n=10):
        er = (close.diff(n).abs()
              / close.diff().abs().rolling(n).sum().replace(0, np.nan))
        fast, slow = 2 / (2 + 1), 2 / (30 + 1)
        sc = (er * (fast - slow) + slow) ** 2
        kama = close.copy()
        for i in range(1, len(close)):
            if np.isnan(kama.iloc[i - 1]) or np.isnan(sc.iloc[i]):
                kama.iloc[i] = close.iloc[i]
            else:
                kama.iloc[i] = kama.iloc[i - 1] + sc.iloc[i] * (close.iloc[i] - kama.iloc[i - 1])
        return kama

    def _ofi(self, features):
        buy_vol  = features.get("buy_volume",  pd.Series(np.nan, index=features.index))
        sell_vol = features.get("sell_volume", pd.Series(np.nan, index=features.index))
        if buy_vol.isna().all() or sell_vol.isna().all():
            close = features[self.close_col]
            ret = close.diff()
            vol = features.get("Volume", pd.Series(1.0, index=features.index))
            buy_vol  = pd.Series(np.where(ret > 0, vol, 0.0), index=close.index)
            sell_vol = pd.Series(np.where(ret < 0, vol, 0.0), index=close.index)
        total = (buy_vol + sell_vol).replace(0, np.nan)
        return ((buy_vol - sell_vol) / total).fillna(0.0)

    # ------------------------------------------------------------------
    def generate_signals(self, features: pd.DataFrame) -> pd.Series:
        close = features[self.close_col]

        # Bollinger Bands
        ma  = close.rolling(self.bb_period, min_periods=self.bb_period).mean()
        std = close.rolling(self.bb_period, min_periods=self.bb_period).std()
        upper = ma + self.bb_std * std
        lower = ma - self.bb_std * std

        # Bandwidth percentile
        bw = (2 * self.bb_std * std / ma.replace(0, np.nan))
        bw_rank = bw.rolling(self.bb_period, min_periods=max(2, self.bb_period // 4)).rank(pct=True).fillna(0.5)
        is_ranging = bw_rank < (self.bw_pct / 100.0)

        # OFI
        ofi = self._ofi(features)
        ofi_avg = ofi.rolling(self.ofi_window, min_periods=max(2, self.ofi_window // 2)).mean()
        no_sell = ofi_avg > -self.ofi_thresh
        sell_confirmed = ofi_avg < -self.ofi_thresh

        # Band transition triggers
        touch_lower = (close < lower) & ~(
            close.shift(1) < lower.shift(1).fillna(np.inf)
        ).astype(bool)

        touch_upper = (close > upper) & ~(
            close.shift(1) > upper.shift(1).fillna(-np.inf)
        ).astype(bool)

        break_up = (close > upper) & ~(
            close.shift(1) > upper.shift(1).fillna(-np.inf)
        ).astype(bool)

        break_down = (close < lower) & ~(
            close.shift(1) < lower.shift(1).fillna(np.inf)
        ).astype(bool)

        long_trig  = (touch_lower & is_ranging & no_sell)   | (break_up   & ~is_ranging)
        short_trig = (touch_upper & is_ranging & sell_confirmed) | (break_down & ~is_ranging)

        sig = pd.Series(0, index=features.index, dtype=int)
        sig[long_trig]  = 1
        sig[short_trig] = -1

        warmup = max(self.bb_period, self.ofi_window) + 10
        sig.iloc[:warmup] = 0
        return sig
