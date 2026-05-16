"""
Realized Volatility Calculation for cMOM/sMOM/dMOM Strategies
============================================================
Computes 126-day rolling realized variance of daily MOM factor returns.

Formulas (Hanauer & Windmuller 2022, Eq. 3):
    σ̂²_MOM,t = 21 × (1/126) × Σ_{j=1}^{126} R²_MOM,d-j,t

For sMOM (semi-vol, Wang & Yan 2021):
    σ̂²_MOM,t,semi = 21 × (1/126) × Σ_{j=1}^{126} R²_MOM,d-j,t × I[R_MOM,d-j < 0]

For dMOM (market variance, Daniel & Moskowitz 2016):
    σ̂²_RMRF,t = 21 × (1/126) × Σ_{j=1}^{126} R²_RMRF,d-j,t
"""

import numpy as np
import pandas as pd


def realized_variance(daily_returns: pd.Series, lookback: int = 126) -> pd.Series:
    """
    Compute rolling realized variance from daily returns.

    Formula: σ² = 21 × mean(R²) over lookback window
    """
    if len(daily_returns) < lookback:
        raise ValueError(
            f"Need at least {lookback} days of data, got {len(daily_returns)}"
        )
    r2 = daily_returns.pow(2)
    rolling_mean = r2.rolling(window=lookback, min_periods=lookback).mean()
    var = 21.0 * rolling_mean
    return var


def realized_volatility(daily_returns: pd.Series, lookback: int = 126) -> pd.Series:
    """
    Compute rolling realized volatility (σ) from daily returns.
    """
    return realized_variance(daily_returns, lookback=lookback).pipe(np.sqrt)


def downside_realized_variance(daily_returns: pd.Series, lookback: int = 126) -> pd.Series:
    """
    Compute rolling DOWNSIDE realized variance (semi-volatility).

    Only squares returns on days when MOM return is NEGATIVE.
    """
    if len(daily_returns) < lookback:
        raise ValueError(
            f"Need at least {lookback} days of data, got {len(daily_returns)}"
        )
    downside_r2 = daily_returns.pow(2) * (daily_returns < 0).astype(float)
    rolling_mean = downside_r2.rolling(window=lookback, min_periods=lookback).mean()
    var = 21.0 * rolling_mean
    return var


def downside_realized_volatility(daily_returns: pd.Series, lookback: int = 126) -> pd.Series:
    """
    Compute rolling downside realized volatility (semi-volatility).
    """
    return downside_realized_variance(daily_returns, lookback=lookback).pipe(np.sqrt)


def scaling_weight(
    target_vol: float,
    realized_vol: pd.Series,
    cap: float = 5.0,
) -> pd.Series:
    """
    Compute cMOM/sMOM scaling weight: w_t = σ_target / σ_realized,t.
    """
    w = target_vol / realized_vol
    w = w.clip(upper=cap)
    return w


def full_sample_vol(monthly_returns: pd.Series) -> float:
    """
    Compute full-sample realized volatility of monthly returns.
    Used as σ_target for cMOM/sMOM scaling.
    """
    return monthly_returns.std(ddof=0)


def realized_variance_rmrf(market_returns: pd.Series, lookback: int = 126) -> pd.Series:
    """
    Compute rolling realized variance of market excess returns (RMRF).
    Used for dMOM regression (Eq. 7 in Hanauer & Windmuller 2022).
    """
    if len(market_returns) < lookback:
        raise ValueError(
            f"Need at least {lookback} days of data, got {len(market_returns)}"
        )
    r2 = market_returns.pow(2)
    rolling_mean = r2.rolling(window=lookback, min_periods=lookback).mean()
    var = 21.0 * rolling_mean
    return var
