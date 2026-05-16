"""
Cross-Sectional Momentum (MOM) Factor Construction
===================================================
Implements the base MOM portfolio construction from Hanauer & Windmuller (2022).

Formation period: t-12 to t-2 (skip t-1 to avoid reversal)
Portfolio sorting: 30/40/30 terciles on NYSE breakpoints
Weighting: Value-weighted portfolios
Rebalancing: Monthly

Supports cMOM, sMOM, and dMOM by providing compute_daily_mom_factor().
"""

import numpy as np
import pandas as pd


def nyse_tercile_breakpoints(
    formation_returns: pd.Series,
    nyse_stocks: list[str] = None,
) -> tuple[float, float]:
    """
    Compute NYSE-only tercile breakpoints from formation returns.
    """
    if nyse_stocks is not None:
        fr_nyse = formation_returns[nyse_stocks]
    else:
        fr_nyse = formation_returns.dropna()
    pct30 = fr_nyse.quantile(0.30)
    pct70 = fr_nyse.quantile(0.70)
    return pct30, pct70


def sort_to_terciles(
    formation_returns: pd.Series,
    breakpoint_30: float,
    breakpoint_70: float,
) -> pd.Series:
    """
    Assign stocks to winner/neutral/loser terciles.
    """
    tercile = pd.Series("neutral", index=formation_returns.index)
    tercile[formation_returns <= breakpoint_30] = "loser"
    tercile[formation_returns >= breakpoint_70] = "winner"
    return tercile


def value_weighted_portfolio_return(
    returns: pd.Series,
    weights: pd.Series = None,
    cap_weights: float = 0.05,
) -> float:
    """
    Compute value-weighted portfolio return.
    """
    if weights is None:
        return returns.mean()
    w = weights / weights.sum()
    w = w.clip(upper=cap_weights)
    w = w / w.sum()
    return (w * returns).sum()


def mom_factor_return(
    winner_returns: pd.Series,
    loser_returns: pd.Series,
    weights: pd.Series = None,
) -> float:
    """
    Compute MOM factor return: long winners, short losers.
    """
    r_w = value_weighted_portfolio_return(winner_returns, weights)
    r_l = value_weighted_portfolio_return(loser_returns, weights)
    return r_w - r_l


def compute_formation_returns(
    prices: pd.DataFrame,
    rebalance_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    """
    Compute formation-period cumulative returns for each rebalance date.
    """
    results = []
    for rd in rebalance_dates:
        try:
            rd_idx = prices.index.get_loc(rd)
        except KeyError:
            rd_idx = prices.index.searchsorted(rd) - 1
        start_idx = rd_idx - (12 * 21)
        end_idx = rd_idx - (2 * 21)
        if start_idx < 0 or end_idx >= len(prices):
            results.append(pd.Series(np.nan, index=prices.columns))
            continue
        p_start = prices.iloc[start_idx]
        p_end = prices.iloc[end_idx]
        ret = (p_end / p_start) - 1.0
        results.append(ret)
    return pd.DataFrame(results, index=rebalance_dates)


def build_mom_signal(
    prices: pd.DataFrame,
    rebalance_dates: pd.DatetimeIndex,
    nyse_stocks: list[str] = None,
) -> pd.DataFrame:
    """
    Build full MOM signal (formation returns per rebalance date).
    """
    formation = compute_formation_returns(prices, rebalance_dates)
    return formation


def compute_daily_mom_factor(
    prices: pd.DataFrame,
    rebalance_dates: pd.DatetimeIndex,
    nyse_stocks: list[str] = None,
) -> pd.Series:
    """
    Compute daily MOM factor returns (long winners, short losers).

    Returns a Series of daily MOM factor returns indexed by date,
    covering only the holding periods (between rebalance dates).
    """
    daily_mom = []
    for i, rd in enumerate(rebalance_dates[:-1]):
        next_rd = rebalance_dates[i + 1]
        try:
            rd_idx = prices.index.get_loc(rd)
        except KeyError:
            rd_idx = prices.index.searchsorted(rd) - 1
        start_idx = rd_idx - (12 * 21)
        end_idx = rd_idx - (2 * 21)
        if start_idx < 0 or end_idx >= len(prices):
            continue
        p_start = prices.iloc[start_idx]
        p_end = prices.iloc[end_idx]
        fr = (p_end / p_start) - 1.0
        if nyse_stocks is not None:
            fr_nyse = fr[nyse_stocks]
        else:
            fr_nyse = fr
        pct30 = fr_nyse.quantile(0.30)
        pct70 = fr_nyse.quantile(0.70)
        winners = fr.index[fr >= pct70]
        losers = fr.index[fr <= pct30]
        mask = (prices.index > rd) & (prices.index <= next_rd)
        daily_prices = prices.loc[mask]
        if len(daily_prices) == 0:
            continue
        p_end_w = p_end[winners]
        p_end_l = p_end[losers]
        w_w = p_end_w / p_end_w.sum()
        w_l = p_end_l / p_end_l.sum()
        p_start_w = prices.iloc[rd_idx][winners]
        p_start_l = prices.iloc[rd_idx][losers]
        daily_rets_w = (daily_prices[winners].values / p_start_w.values) - 1.0
        daily_rets_l = (daily_prices[losers].values / p_start_l.values) - 1.0
        daily_vw_w = (w_w.values * daily_rets_w).sum(axis=1)
        daily_vw_l = (w_l.values * daily_rets_l).sum(axis=1)
        mom_daily = daily_vw_w - daily_vw_l
        mom_series = pd.Series(mom_daily, index=daily_prices.index)
        daily_mom.append(mom_series)
    return pd.concat(daily_mom).sort_index()
