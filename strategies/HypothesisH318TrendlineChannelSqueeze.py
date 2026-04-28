"""
HypothesisH318TrendlineChannelSqueeze.py
====================================
H318 — TrendlineChannelSqueeze  [Trendline Channel Squeeze Release]
StrategyParrot Strategy Lab, 2026-04-02

Theory
------
When price is squeezed between trendline upper and lower bounds (both
distances small), it is building energy.  A release — price escaping one
side — tends to produce follow-through.  Squeeze momentum confirms
direction.

  squeeze = abs(upper_dist) < width AND abs(lower_dist) < width
  release_up   = was_squeezed AND upper_dist > width AND sq_mom > 0
  release_down = was_squeezed AND lower_dist < -width AND sq_mom < 0

  LONG  on release_up  rising edge
  SHORT on release_down rising edge

Class : HypothesisH318TrendlineChannelSqueeze
"""
import Strategy_lab._path_setup  # noqa: F401

import numpy as np
import pandas as pd
from src.strategy import BaseStrategy


class HypothesisH318TrendlineChannelSqueeze(BaseStrategy):
    """Trendline channel squeeze-release breakout strategy."""

    def __init__(
        self,
        tl_channel_width: float = 0.8,
        close_col: str = "Close",
        **kwargs,
    ):
        self.tl_channel_width = float(tl_channel_width)
        self.close_col        = close_col

    def generate_signals(self, features: pd.DataFrame) -> pd.Series:
        warmup = 30
        signals = pd.Series(0, index=features.index, dtype=int)

        tl_upper_dist = features.get(
            "trendline_upper_dist", pd.Series(1.0, index=features.index)
        ).fillna(1.0)
        tl_lower_dist = features.get(
            "trendline_lower_dist", pd.Series(-1.0, index=features.index)
        ).fillna(-1.0)
        sq_mom = features.get(
            "squeeze_momentum", pd.Series(0.0, index=features.index)
        ).fillna(0.0)

        w = self.tl_channel_width

        # Price near upper trendline (overbought within channel) AND momentum turning down
        near_upper = tl_upper_dist < w  # small positive = near upper resistance
        near_lower = tl_lower_dist < w  # small positive = near lower support

        sq_mom_down = sq_mom < 0
        sq_mom_up   = sq_mom > 0

        # Momentum acceleration (sign change = turning point)
        sq_mom_prev = sq_mom.shift(1).fillna(0)
        mom_cross_down = (sq_mom < 0) & (sq_mom_prev >= 0)
        mom_cross_up   = (sq_mom > 0) & (sq_mom_prev <= 0)

        # Short: near upper trendline AND momentum turning negative (channel resistance)
        short_raw = near_upper & mom_cross_down
        # Long: near lower trendline AND momentum turning positive (channel support)
        long_raw  = near_lower & mom_cross_up

        trig_long  = long_raw  & ~long_raw.shift(1).fillna(False).astype(bool)
        trig_short = short_raw & ~short_raw.shift(1).fillna(False).astype(bool)

        signals[trig_long]  = 1
        signals[trig_short] = -1
        signals.iloc[:warmup] = 0
        return signals
