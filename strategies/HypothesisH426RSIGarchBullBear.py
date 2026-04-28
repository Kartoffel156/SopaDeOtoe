"""H426 — RSIGarchBullBear: RSI gated by rolling log-ret regime, garch collar."""
import SopaDeOtoe._path_setup  # noqa: F401
import numpy as np, pandas as pd
from src.strategy import BaseStrategy

class HypothesisH426RSIGarchBullBear(BaseStrategy):
    def __init__(self, regime_w=30, rsi_p=9, ov_bull=38, ov_bear=30,
                 ob_bull=70, lev_long=-1.5, lev_short=-1.0, close_col="Close", **kwargs):
        self.regime_w=regime_w; self.rsi_p=rsi_p; self.ov_bull=ov_bull; self.ov_bear=ov_bear
        self.ob_bull=ob_bull; self.lev_long=lev_long; self.lev_short=lev_short; self.close_col=close_col

    def _rsi(self, close):
        d = close.diff()
        g = d.where(d>0, 0.); l = -d.where(d<0, 0.)
        ag = g.rolling(self.rsi_p, min_periods=self.rsi_p).mean()
        al = l.rolling(self.rsi_p, min_periods=self.rsi_p).mean()
        return (100. - 100./(1. + ag/al.replace(0., np.nan))).fillna(50.)

    def generate_signals(self, features):
        close = features[self.close_col].astype(float)
        rsi = self._rsi(close)
        lev = features.get("garch_leverage", pd.Series(0., index=features.index)).fillna(0.)
        log_ret = np.log(close / close.shift(1)).fillna(0.)
        regime  = log_ret.rolling(self.regime_w, min_periods=5).mean().fillna(0.)
        bull = regime > 0
        bear = regime <= 0
        in_ov_bull = (rsi < self.ov_bull) & bull & (lev > self.lev_long)
        in_ov_bear = (rsi < self.ov_bear) & bear & (lev > -0.8)
        in_ob_bull = (rsi > self.ob_bull) & bull & (lev < self.lev_short)
        long_cond  = in_ov_bull | in_ov_bear
        short_cond = in_ob_bull
        sig = pd.Series(0, index=features.index, dtype=int)
        sig[long_cond  & ~long_cond.shift(1).fillna(False)]  =  1
        sig[short_cond & ~short_cond.shift(1).fillna(False)] = -1
        sig.iloc[:max(self.regime_w, self.rsi_p) + 5] = 0
        return sig
