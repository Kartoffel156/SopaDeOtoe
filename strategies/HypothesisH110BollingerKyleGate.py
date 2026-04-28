"""
HypothesisH110BollingerKyleGate.py
=====================================
T-10 — BollingerKyleGate  [Microestructura]
Hypothesis Run #3, StrategyParrot Strategy Lab, 2026-04-01

Theory
------
BollingerRegime breakouts can be false if no informed flow backs them.
Kyle (1985): high lambda = smart money present. Breakout + high lambda =
informed buyers confirm the breakout. MR entries in range don't need this.

Entry: TRIGGER (bidirectional)
Death: kyle_lambda high on breakouts in BTC always (no discriminant power)
Class: HypothesisH110BollingerKyleGate
"""
import Strategy_lab._path_setup  # noqa: F401
import numpy as np
import pandas as pd
from src.strategy import BaseStrategy


class HypothesisH110BollingerKyleGate(BaseStrategy):
    """BollingerRegime with Kyle lambda gate on breakouts only."""

    def __init__(self, bb_period=20, bb_std=2.0, bw_lookback=20,
                 bw_percentile=50.0, lam_thresh=0.60, lookback=30,
                 close_col="Close", **kwargs):
        self.bb_period=bb_period; self.bb_std=bb_std
        self.bw_lookback=bw_lookback; self.bw_percentile=bw_percentile
        self.lam_thresh=lam_thresh; self.lookback=lookback; self.close_col=close_col

    def generate_signals(self, features):
        close=features[self.close_col]
        ma=close.rolling(self.bb_period,min_periods=self.bb_period).mean()
        std=close.rolling(self.bb_period,min_periods=self.bb_period).std()
        upper=ma+self.bb_std*std; lower=ma-self.bb_std*std
        bw=((2*self.bb_std*std)/ma.replace(0,np.nan))
        bwp=bw.rolling(self.bw_lookback,min_periods=max(5,self.bw_lookback//4)).rank(pct=True).fillna(0.5)
        trending=bwp>(self.bw_percentile/100.)
        break_up=(close>upper.shift(1).fillna(np.inf))&(close.shift(1)<=upper.shift(2).fillna(np.inf))
        break_dn=(close<lower.shift(1).fillna(-np.inf))&(close.shift(1)>=lower.shift(2).fillna(-np.inf))
        touch_lo=(close<lower)&(close.shift(1)>=lower.shift(1).fillna(-np.inf))
        touch_hi=(close>upper)&(close.shift(1)<=upper.shift(1).fillna(np.inf))
        lam=features.get("kyle_lambda",pd.Series(np.nan,index=features.index))
        if lam.isna().all(): lam=pd.Series(1.,index=features.index)
        lp=lam.rolling(self.lookback,min_periods=max(5,self.lookback//4)).rank(pct=True).fillna(0.5)
        informed=lp>self.lam_thresh
        sig=pd.Series(0,index=features.index,dtype=int)
        sig[break_up&trending&informed]=1; sig[break_dn&trending&informed]=-1
        sig[touch_lo&~trending]=1; sig[touch_hi&~trending]=-1
        sig.iloc[:max(self.bb_period,self.bw_lookback,self.lookback)+10]=0
        return sig
