"""
HypothesisDMOM.py
=================
dMOM — Dynamic-Scaled Momentum

Time-series momentum strategy using BOTH predicted risk AND predicted return.
Can short momentum (negative weight) when in unfavorable predicted states.
This is the most sophisticated enhanced momentum strategy.

Scaling weight: wdMOM,t = (1 / 2λ) × (μ̂_t / σ̂²_t)
where μ̂_t is forecasted momentum return from expanding OLS regression.

Return forecast regression (Eq. 7, Hanauer & Windmuller 2022):
    R_MOM,t = γ₀ + γ_int × I[Bear,t-1] × σ²_RMRF,t-1 + ε_t

Paper: Hanauer & Windmuller (2022), "Enhanced Momentum Strategies", SSRN 3437919
Based on: Daniel & Moskowitz (2016)
"""
import SopaDeOtoe._path_setup  # noqa: F401

import numpy as np
import pandas as pd
from src.strategy import BaseStrategy

try:
    import statsmodels.api as sm
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False


class HypothesisDMOM(BaseStrategy):
    """
    Dynamic-Scaled Time-Series Momentum.

    Scales momentum by BOTH predicted risk AND predicted return.
    Can be negative when unfavorable market states are predicted.
    """

    def __init__(
        self,
        mom_formation: int = 252,
        mom_skip: int = 21,
        vol_lookback: int = 126,
        min_regression_window: int = 24,
        signal_thresh: float = 0.0,
        close_col: str = "Close",
        market_col: str = "Market",
        **kwargs,
    ):
        self.mom_formation = int(mom_formation)
        self.mom_skip = int(mom_skip)
        self.vol_lookback = int(vol_lookback)
        self.min_regression_window = int(min_regression_window)
        self.signal_thresh = float(signal_thresh)
        self.close_col = close_col
        self.market_col = market_col
        self._lambda: float = None
        self._mu_hat: pd.Series = None

    def _compute_bear_indicator(self, monthly_market: pd.Series) -> pd.Series:
        """Bear market: 1 if cumulative 24-month market return < 0."""
        cum = (1 + monthly_market).rolling(window=24, min_periods=24).apply(
            lambda x: (1 + x).prod() - 1, raw=False
        )
        return (cum < 0).astype(int)

    def _run_regression(self, monthly_mom: pd.Series, monthly_market: pd.Series) -> pd.Series:
        """Expanding OLS: R_MOM,t = γ₀ + γ_int × I_Bear,t-1 × σ²_RMRF,t-1 + ε_t"""
        bear = self._compute_bear_indicator(monthly_market)
        market_var = monthly_market.rolling(window=6, min_periods=6).var()
        interaction = bear.shift(1) * market_var.shift(1)

        X = pd.DataFrame({"const": 1.0, "interaction": interaction})
        y = monthly_mom

        mu_hat = pd.Series(np.nan, index=monthly_mom.index, dtype=float)
        min_window = self.min_regression_window

        for i in range(min_window, len(monthly_mom)):
            y_sub = y.iloc[:i].dropna()
            X_sub = X.iloc[:i].dropna()
            common = y_sub.index.intersection(X_sub.index)
            if len(common) < min_window:
                continue
            y_align = y_sub.loc[common]
            X_align = X_sub.loc[common]
            if HAS_STATSMODELS:
                model = sm.OLS(y_align, X_align).fit()
                mu_hat.iloc[i] = model.predict(X.iloc[i:i+1])[0]
            else:
                X_arr = X_align.values
                y_arr = y_align.values
                beta, _, _, _ = np.linalg.lstsq(X_arr, y_arr, rcond=None)
                x_new = X.iloc[i:i+1].values
                mu_hat.iloc[i] = float((x_new @ beta).item())

        return mu_hat

    def generate_signals(self, features: pd.DataFrame) -> pd.Series:
        close = features[self.close_col]
        log_ret = np.log(close / close.shift(1)).fillna(0)

        # Momentum formation
        mom = log_ret.shift(self.mom_skip).rolling(
            window=self.mom_formation, min_periods=self.mom_formation
        ).sum()
        mom = mom.shift(1)

        # Realized variance
        realized_var = log_ret.rolling(
            window=self.vol_lookback, min_periods=self.vol_lookback
        ).var(ddof=0) * 21.0

        # Monthly aggregation for regression
        monthly_mom = mom.resample("ME").apply(lambda x: (1 + x).prod() - 1)
        monthly_mkt = log_ret.resample("ME").apply(lambda x: (1 + x).prod() - 1)

        # Run regression to get μ̂
        if self._mu_hat is None:
            self._mu_hat = self._run_regression(monthly_mom, monthly_mkt)

        # Get μ̂ for current period
        last_month_end = mom.index[-1]
        candidates = self._mu_hat.index[self._mu_hat.index <= last_month_end]
        if len(candidates) == 0:
            sig = pd.Series(0, index=features.index, dtype=int)
            warmup = self.mom_formation + self.mom_skip + self.vol_lookback
            sig.iloc[:warmup] = 0
            return sig
        mu_t = self._mu_hat.loc[candidates[-1]]
        if pd.isna(mu_t):
            sig = pd.Series(0, index=features.index, dtype=int)
            warmup = self.mom_formation + self.mom_skip + self.vol_lookback
            sig.iloc[:warmup] = 0
            return sig

        # Lambda scaling
        if self._lambda is None:
            valid = self._mu_hat.dropna()
            if len(valid) > 12:
                var_mom = monthly_mom.loc[valid.index].var()
                mean_mu = valid.mean()
                if var_mom > 0:
                    self._lambda = (mean_mu / var_mom) / 2.0
                else:
                    self._lambda = 1.0
            else:
                self._lambda = 1.0

        # Dynamic weight: wdMOM,t = (1/2λ) × (μ̂_t / σ̂²_t)
        var_t = realized_var.iloc[-1] if len(realized_var) > 0 else 1e-8
        if var_t <= 0:
            var_t = 1e-8
        w_dynamic = (1 / (2 * self._lambda)) * (mu_t / var_t)

        # Apply dynamic weight to momentum signal
        mom_adjusted = mom * w_dynamic

        sig = pd.Series(0, index=features.index, dtype=int)
        sig[mom_adjusted > self.signal_thresh] = 1
        sig[mom_adjusted < -self.signal_thresh] = -1

        warmup = self.mom_formation + self.mom_skip + self.vol_lookback
        sig.iloc[:warmup] = 0
        return sig
