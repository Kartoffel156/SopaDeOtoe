"""
Portfolio-level metrics suite.

Prado AFML Cap. 14 (Sharpe, DSR), Roncalli Cap. 1-2 (risk attribution,
diversification ratio), Carver (exposure, turnover).
"""

import numpy as np
import pandas as pd
from scipy.stats import norm


def portfolio_sharpe(combined_returns: pd.Series,
                     rf_rate: float = 0.045,
                     ann_factor: float = 252.0,
                     active_mask: pd.Series | None = None) -> float:
    """
    v12-consistent Sharpe: computed on active bars only, with ann_factor
    adjusted to active_bars_per_year (mirrors BUG-15/BUG-16 fixes in
    StrategyParrot/v12/src/metrics.py).

    Filters to bars where at least one strategy holds a position so that
    flat periods do not accumulate a daily -rf/252 penalty.
    ann_factor_active = ann_factor * (n_active / T)
    """
    if active_mask is not None:
        active = combined_returns[active_mask]
    else:
        active = combined_returns[combined_returns != 0]

    if len(active) < 2:
        return 0.0

    n_active = len(active)
    T = len(combined_returns)
    ann_factor_active = ann_factor * (n_active / T)

    rf_per_bar = rf_rate / ann_factor
    excess = active - rf_per_bar
    if excess.std() < 1e-12:
        return 0.0
    return (excess.mean() / excess.std()) * np.sqrt(ann_factor_active)


def portfolio_dsr(combined_returns: pd.Series,
                  rf_rate: float,
                  n_strategies: int,
                  n_trials_per_strategy: list[int],
                  ann_factor: float = 252.0,
                  active_mask: pd.Series | None = None) -> float:
    """
    AFML Cap. 14, Eq. 14.2: Portfolio-level Deflated Sharpe Ratio.

    n_trials = 1 + sum(n_trials_per_strategy)
    DSR = Phi(SR_bar * sqrt(T-1) - E[max(z)])
    E[max(z)] ~ (1-gamma) * Phi_inv(1-1/n) + gamma * Phi_inv(1-1/(n+1))

    Uses active bars only (consistent with portfolio_sharpe).
    """
    n_trials = 1 + sum(n_trials_per_strategy)

    if active_mask is not None:
        active = combined_returns[active_mask]
    else:
        active = combined_returns[combined_returns != 0]

    T = len(active)
    if T < 2:
        return 0.0

    rf_per_bar = rf_rate / ann_factor
    excess = active - rf_per_bar
    sr_bar = excess.mean() / excess.std() if excess.std() > 1e-12 else 0.0

    gamma = 0.5772156649  # Euler-Mascheroni
    if n_trials <= 1:
        e_max_z = 0.0
    else:
        e_max_z = ((1 - gamma) * norm.ppf(1 - 1.0 / n_trials) +
                   gamma * norm.ppf(1 - 1.0 / (n_trials + 1)))

    dsr = norm.cdf(sr_bar * np.sqrt(T - 1) - e_max_z)
    return float(dsr)


def risk_attribution(weights: np.ndarray,
                     covariance: np.ndarray,
                     strategy_names: list[str]) -> pd.DataFrame:
    """
    Roncalli Cap. 2 (Sec. 2.1.2): Euler decomposition of portfolio risk.

    RC_i = w_i x (Sigma @ w)_i / sigma(w)
    Invariant: sum(RC_i) = sigma(portfolio) (Euler theorem).
    """
    port_vol = np.sqrt(weights @ covariance @ weights)
    if port_vol < 1e-12:
        return pd.DataFrame({
            "strategy": strategy_names,
            "weight": weights,
            "marginal_risk": np.zeros(len(weights)),
            "risk_contribution": np.zeros(len(weights)),
            "risk_contribution_pct": np.zeros(len(weights)),
        })

    marginal = covariance @ weights / port_vol
    rc = weights * marginal
    rc_pct = rc / port_vol

    return pd.DataFrame({
        "strategy": strategy_names,
        "weight": weights,
        "marginal_risk": marginal,
        "risk_contribution": rc,
        "risk_contribution_pct": rc_pct,
    })


def diversification_ratio(weights: np.ndarray,
                          volatilities: np.ndarray,
                          portfolio_vol: float) -> float:
    """
    Roncalli Cap. 1: DR = sum(w_i x sigma_i) / sigma(portfolio)

    DR >= 1 always. DR = 1 means no diversification benefit.
    Target: DR > 1.5 for a multi-strategy portfolio.
    """
    if portfolio_vol < 1e-12:
        return 1.0
    return float(np.sum(weights * volatilities) / portfolio_vol)


def portfolio_calmar(combined_returns: pd.Series,
                     ann_factor: float = 252.0) -> float:
    """Annualized return / max drawdown."""
    equity = (1 + combined_returns).cumprod()
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max
    max_dd = abs(dd.min())
    ann_return = combined_returns.mean() * ann_factor
    if max_dd < 1e-12:
        return 0.0
    return ann_return / max_dd


def portfolio_sortino(combined_returns: pd.Series,
                      rf_rate: float = 0.045,
                      ann_factor: float = 252.0,
                      active_mask: pd.Series | None = None) -> float:
    """Sortino ratio: excess return / downside deviation (active bars only)."""
    if active_mask is not None:
        active = combined_returns[active_mask]
    else:
        active = combined_returns[combined_returns != 0]

    if len(active) < 2:
        return 0.0

    n_active = len(active)
    T = len(combined_returns)
    ann_factor_active = ann_factor * (n_active / T)

    rf_per_bar = rf_rate / ann_factor
    excess = active - rf_per_bar
    downside = excess[excess < 0]
    if len(downside) == 0 or downside.std() < 1e-12:
        return 0.0
    return (excess.mean() / downside.std()) * np.sqrt(ann_factor_active)


def max_drawdown(combined_returns: pd.Series) -> float:
    """Maximum drawdown from combined return series."""
    equity = (1 + combined_returns).cumprod()
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max
    return float(dd.min())


def portfolio_exposure(positions_df: pd.DataFrame) -> float:
    """Fraction of bars where at least one strategy is active."""
    if positions_df.empty:
        return 0.0
    any_active = (positions_df.fillna(0) != 0).any(axis=1)
    return float(any_active.mean())


def rolling_sharpe(combined_returns: pd.Series,
                   window: int = 63,
                   rf_rate: float = 0.045,
                   ann_factor: float = 252.0) -> pd.Series:
    """Rolling Sharpe ratio for regime detection."""
    rf_per_bar = rf_rate / ann_factor
    excess = combined_returns - rf_per_bar
    rolling_mean = excess.rolling(window).mean()
    rolling_std = excess.rolling(window).std()
    return (rolling_mean / rolling_std.replace(0, np.nan)) * np.sqrt(ann_factor)


def compute_portfolio_metrics(combined_returns: pd.Series,
                              weights: np.ndarray,
                              covariance: np.ndarray,
                              strategy_names: list[str],
                              positions_df: pd.DataFrame | None = None,
                              rf_rate: float = 0.045,
                              ann_factor: float = 252.0,
                              n_strategies: int = 0,
                              n_trials_per_strategy: list[int] | None = None) -> dict:
    """
    Compute full portfolio metrics suite. Single entry point.
    """
    n_trials_per_strategy = n_trials_per_strategy or [1] * n_strategies

    equity = (1 + combined_returns).cumprod()
    vols = np.sqrt(np.diag(covariance))
    port_vol = np.sqrt(weights @ covariance @ weights)

    # Active-bars mask: bars where at least one strategy holds a position.
    # Used by Sharpe/Sortino/DSR to match v12's BUG-15/BUG-16 convention.
    active_mask = None
    if positions_df is not None:
        active_mask = (positions_df.fillna(0) != 0).any(axis=1)
        active_mask = active_mask.reindex(combined_returns.index, fill_value=False)

    metrics = {
        "sharpe": portfolio_sharpe(combined_returns, rf_rate, ann_factor, active_mask),
        "dsr": portfolio_dsr(combined_returns, rf_rate, n_strategies,
                             n_trials_per_strategy, ann_factor, active_mask),
        "annualized_return": float(combined_returns.mean() * ann_factor),
        "annualized_volatility": float(combined_returns.std() * np.sqrt(ann_factor)),
        "max_drawdown": max_drawdown(combined_returns),
        "calmar": portfolio_calmar(combined_returns, ann_factor),
        "sortino": portfolio_sortino(combined_returns, rf_rate, ann_factor, active_mask),
        "diversification_ratio": diversification_ratio(weights, vols, port_vol),
        "portfolio_volatility": float(port_vol * np.sqrt(ann_factor)),
        "risk_attribution": risk_attribution(weights, covariance, strategy_names),
    }

    if positions_df is not None:
        metrics["exposure"] = portfolio_exposure(positions_df)

    return metrics
