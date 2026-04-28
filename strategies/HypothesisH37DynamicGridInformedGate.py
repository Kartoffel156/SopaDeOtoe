"""
Dynamic ATR Grid with Uninformed Flow Gate — activates grid only in rangebound markets.

Source: Internal Hypothesis H37, StrategyParrot Corpus Analysis Vol.2, 2026.
Inspiration: DynamicGridStrategy: Sh=-0.643 BUT meta+=+1.984. Grid strategy has
             the right structure but fires in trending markets where it bleeds.
Edge: Grid strategies profit in mean-reverting (ranging) markets. The key filter:
      only activate when flow is UNINFORMED (low VPIN, neutral OFI, no MK trend).
      Uninformed flow → price oscillates around grid midpoint → reversions reliable.

ORIGINAL CONTEXT:
  Asset: BTC-USD dollar bars
  Timeframe: ~4h, 6 bars/day, 2020-2026
  Reference: DynamicGridStrategy (arXiv 2506.11921)

How it works:
  1. Compute ATR-based dynamic grid bands around rolling midpoint.
  2. Gate: vpin_pct < 0.40 AND |ofi| < 0.15 AND |mk_z| < 1.0 (uninformed flow).
  3. Long when price crosses below lower grid band (AND uninformed flow active).
  4. Short when price crosses above upper grid band (AND uninformed flow active).

Parameters:
  grid_period (int): MA period for grid midpoint. Default: 20 bars.
  grid_mult (float): ATR multiplier for grid band width. Default: 1.5.
  atr_period (int): ATR estimation period. Default: 14 bars.
  vpin_pct_thresh (float): VPIN percentile threshold for low-toxicity. Default: 0.40.
  ofi_neutral_thresh (float): Max |OFI| for neutral flow condition. Default: 0.15.
  mk_no_trend (float): Max |MK z-score| for no-trend condition. Default: 1.0.
"""

import Strategy_lab._path_setup  # noqa: F401

import numpy as np
import pandas as pd
from src.strategy import BaseStrategy


class HypothesisH37DynamicGridInformedGate(BaseStrategy):
    """Dynamic ATR grid gated by uninformed flow conditions. Source: Internal Hypothesis H37."""

    def __init__(self, grid_period=20, grid_mult=1.5, atr_period=14,
                 vpin_pct_thresh=0.40, ofi_neutral_thresh=0.15, mk_no_trend=1.0,
                 close_col="Close", **kwargs):
        self.grid_period = grid_period
        self.grid_mult = grid_mult
        self.atr_period = atr_period
        self.vpin_pct_thresh = vpin_pct_thresh
        self.ofi_neutral_thresh = ofi_neutral_thresh
        self.mk_no_trend = mk_no_trend
        self.close_col = close_col

    def generate_signals(self, features: pd.DataFrame) -> pd.Series:
        close = features[self.close_col]
        high  = features.get('High', close)
        low_  = features.get('Low',  close)

        vpin = features.get('vpin', pd.Series(0.5, index=features.index))
        ofi  = features.get('order_flow_imbalance', pd.Series(0.0, index=features.index))
        mk_z = features.get('mann_kendall_z', pd.Series(0.0, index=features.index))

        # Uninformed flow gate: ALL three conditions must hold
        vpin_pct   = vpin.rolling(63, min_periods=20).rank(pct=True)
        low_vpin   = vpin_pct < self.vpin_pct_thresh    # flow is not toxic
        neut_ofi   = ofi.abs() < self.ofi_neutral_thresh  # no directional pressure
        no_trend   = mk_z.abs() < self.mk_no_trend        # no statistical trend
        uninformed = low_vpin & neut_ofi & no_trend

        # ATR (True Range) for grid spacing
        tr = pd.concat([
            high - low_,
            (high - close.shift(1)).abs(),
            (low_  - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(self.atr_period, min_periods=self.atr_period).mean()

        # Grid midpoint and bands (shift to make causal — use previous bar's grid)
        mid        = close.rolling(self.grid_period, min_periods=self.grid_period).mean()
        grid_lower = (mid - self.grid_mult * atr).shift(1)
        grid_upper = (mid + self.grid_mult * atr).shift(1)

        # Price crosses grid bands (with causal grid levels)
        grid_long  = (close < grid_lower) & (close.shift(1) >= grid_lower.shift(1))
        grid_short = (close > grid_upper) & (close.shift(1) <= grid_upper.shift(1))

        long_trigger  = grid_long  & uninformed
        short_trigger = grid_short & uninformed

        signals = pd.Series(0, index=features.index, dtype=int)
        signals[long_trigger]  = 1
        signals[short_trigger] = -1

        warmup = max(self.grid_period, self.atr_period, 63) + 5
        signals.iloc[:warmup] = 0
        return signals


# ── Registry hint ─────────────────────────────────────────────────
# StrategyMeta(HypothesisH37DynamicGridInformedGate, param_ranges={
#     'grid_mult':          (1.0, 2.5),
#     'vpin_pct_thresh':    (0.25, 0.55),
#     'ofi_neutral_thresh': (0.08, 0.25),
# }, description="H37: ATR grid + uninformed-flow gate — DynamicGrid rescue meta+=1.98")
