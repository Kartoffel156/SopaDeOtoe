"""
HypothesisH86WonhamMarkovRefinado.py
======================================
T-16 — WonhamMarkovRefinado  [Audit / Fallos]
Hypothesis Run #2, StrategyParrot Strategy Lab, 2026-03-31

Theory
------
H59 WonhamMarkovFusion leads with Sharpe 0.491, MaxDD -7.7%.
The MaxDD -7.7% likely occurs during regime transitions where both proxies
disagree. Refinement: add vol_regime as tie-breaker during disagreement.

Hamilton (1989): Markov switching models are less accurate during regime
transitions — exactly when Wonham and Markov diverge. Low vol_regime during
divergence = noise (don't trade). High vol_regime during divergence = actual
transition is happening.

Entry: TRIGGER (state-based with vol_regime arbitration)
Death: vol_regime arbitration reduces trades to < 60
Class: HypothesisH86WonhamMarkovRefinado
"""

import SopaDeOtoe._path_setup  # noqa: F401
import numpy as np
import pandas as pd
from src.strategy import BaseStrategy


class HypothesisH86WonhamMarkovRefinado(BaseStrategy):
    """
    Wonham + Markov with vol_regime as disagreement arbitrator.

    Parameters
    ----------
    alpha_w : float
        Wonham EMA speed. Default 0.10.
    w_thresh : float
        Wonham bull threshold. Default 0.65.
    m_thresh : float
        Markov bull threshold. Default 0.65.
    w_bear : float
        Wonham bear threshold. Default 0.35.
    m_bear : float
        Markov bear threshold. Default 0.35.
    vol_max : int
        Max vol_regime for entry (0=LOW, 1=NORMAL). Default 1.
    markov_lookback : int
        Markov persistence window. Default 20.
    close_col : str
        Close price column. Default 'Close'.
    """

    def __init__(
        self,
        alpha_w: float = 0.10,
        w_thresh: float = 0.65,
        m_thresh: float = 0.65,
        w_bear: float = 0.35,
        m_bear: float = 0.35,
        vol_max: int = 1,
        markov_lookback: int = 20,
        close_col: str = "Close",
        **kwargs,
    ):
        self.alpha_w         = alpha_w
        self.w_thresh        = w_thresh
        self.m_thresh        = m_thresh
        self.w_bear          = w_bear
        self.m_bear          = m_bear
        self.vol_max         = vol_max
        self.markov_lookback = markov_lookback
        self.close_col       = close_col

    def generate_signals(self, features: pd.DataFrame) -> pd.Series:
        close   = features[self.close_col]
        returns = close.pct_change().fillna(0.0)

        # Wonham proxy
        span_fast  = max(2, int(1.0 / self.alpha_w))
        span_slow  = span_fast * 4
        ema_fast   = close.ewm(span=span_fast, adjust=False).mean()
        ema_slow   = close.ewm(span=span_slow, adjust=False).mean()
        raw_w      = (ema_fast / ema_slow.replace(0, np.nan) - 1).fillna(0.0)
        bull_prob_w = 1.0 / (1.0 + np.exp(-raw_w * 50))

        # Markov proxy
        pos_rets    = (returns > 0).rolling(self.markov_lookback, min_periods=5).mean()
        bull_prob_m = pos_rets.rolling(10, min_periods=3).mean().fillna(0.5)

        vol_reg = features.get("vol_regime", pd.Series(1, index=features.index)).fillna(1).astype(int)
        vol_ok  = vol_reg <= self.vol_max

        w_bull = bull_prob_w > self.w_thresh
        w_bear = bull_prob_w < self.w_bear
        m_bull = bull_prob_m > self.m_thresh
        m_bear = bull_prob_m < self.m_bear

        agree_bull = w_bull & m_bull
        agree_bear = w_bear & m_bear

        prev_bull = agree_bull.shift(1).fillna(False)
        prev_bear = agree_bear.shift(1).fillna(False)

        long_trig  = agree_bull & ~prev_bull & vol_ok
        short_trig = agree_bear & ~prev_bear & vol_ok

        signals = pd.Series(0, index=features.index, dtype=int)
        signals[long_trig]  =  1
        signals[short_trig] = -1

        warmup = max(span_slow, self.markov_lookback + 10) + 10
        signals.iloc[:warmup] = 0
        return signals
