import pytest
import numpy as np
import pandas as pd
from portfolio.portfolio_metrics import (
    portfolio_sharpe, portfolio_dsr, risk_attribution,
    diversification_ratio, portfolio_calmar, portfolio_sortino,
    max_drawdown, portfolio_exposure, rolling_sharpe,
    compute_portfolio_metrics,
)


def _make_combined_returns(n=500, seed=42):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.Series(rng.normal(0.0003, 0.01, n), index=idx)


def test_portfolio_sharpe_positive():
    r = _make_combined_returns()
    sr = portfolio_sharpe(r, rf_rate=0.045)
    assert isinstance(sr, float)


def test_portfolio_sharpe_zero_vol():
    idx = pd.date_range("2023-01-01", periods=10, freq="D")
    r = pd.Series(np.zeros(10), index=idx)
    assert portfolio_sharpe(r) == 0.0


def test_portfolio_dsr_range():
    r = _make_combined_returns()
    dsr = portfolio_dsr(r, rf_rate=0.045, n_strategies=3,
                        n_trials_per_strategy=[1, 1, 1])
    assert 0.0 <= dsr <= 1.0


def test_portfolio_dsr_higher_trials_lower_dsr():
    r = _make_combined_returns()
    dsr_low = portfolio_dsr(r, 0.045, 3, [1, 1, 1])
    dsr_high = portfolio_dsr(r, 0.045, 3, [100, 100, 100])
    assert dsr_high <= dsr_low


def test_risk_attribution_sums_to_port_vol():
    cov = np.array([[0.04, 0.01], [0.01, 0.09]])
    w = np.array([0.6, 0.4])
    ra = risk_attribution(w, cov, ["A", "B"])
    port_vol = np.sqrt(w @ cov @ w)
    assert abs(ra["risk_contribution"].sum() - port_vol) < 1e-8
    assert len(ra) == 2


def test_diversification_ratio_no_correlation():
    """With zero correlation, DR > 1."""
    w = np.array([0.5, 0.5])
    vols = np.array([0.20, 0.20])
    cov = np.diag(vols ** 2)
    port_vol = np.sqrt(w @ cov @ w)
    dr = diversification_ratio(w, vols, port_vol)
    assert dr > 1.0


def test_diversification_ratio_perfect_correlation():
    """With perfect correlation, DR = 1."""
    w = np.array([0.5, 0.5])
    vols = np.array([0.20, 0.20])
    cov = np.outer(vols, vols)  # perfect correlation
    port_vol = np.sqrt(w @ cov @ w)
    dr = diversification_ratio(w, vols, port_vol)
    assert abs(dr - 1.0) < 0.01


def test_max_drawdown_negative():
    r = _make_combined_returns()
    mdd = max_drawdown(r)
    assert mdd <= 0.0


def test_calmar_positive_returns():
    r = _make_combined_returns()
    calmar = portfolio_calmar(r)
    assert isinstance(calmar, float)


def test_sortino():
    r = _make_combined_returns()
    s = portfolio_sortino(r, rf_rate=0.045)
    assert isinstance(s, float)


def test_portfolio_exposure():
    idx = pd.date_range("2023-01-01", periods=100, freq="D")
    positions = pd.DataFrame({
        "A": np.where(np.random.default_rng(42).random(100) < 0.3, 1, 0),
        "B": np.where(np.random.default_rng(43).random(100) < 0.2, 1, 0),
    }, index=idx)
    exp = portfolio_exposure(positions)
    assert 0.0 <= exp <= 1.0


def test_rolling_sharpe_length():
    r = _make_combined_returns()
    rs = rolling_sharpe(r, window=63)
    assert len(rs) == len(r)


def test_compute_portfolio_metrics_keys():
    r = _make_combined_returns()
    cov = np.array([[0.04, 0.01, 0.002],
                    [0.01, 0.09, 0.003],
                    [0.002, 0.003, 0.0225]])
    w = np.array([0.4, 0.35, 0.25])
    m = compute_portfolio_metrics(
        r, w, cov, ["A", "B", "C"],
        rf_rate=0.045, n_strategies=3,
        n_trials_per_strategy=[1, 1, 1],
    )
    assert "sharpe" in m
    assert "dsr" in m
    assert "max_drawdown" in m
    assert "diversification_ratio" in m
    assert "risk_attribution" in m
    assert isinstance(m["risk_attribution"], pd.DataFrame)


def test_portfolio_dsr_series_too_short_returns_zero():
    r = pd.Series([0.01], index=pd.date_range("2023-01-01", periods=1, freq="D"))
    assert portfolio_dsr(r, rf_rate=0.045, n_strategies=1,
                         n_trials_per_strategy=[1]) == 0.0


def test_portfolio_dsr_single_trial_skips_correction():
    """When n_trials <= 1 the Euler correction term is zero."""
    r = _make_combined_returns()
    dsr = portfolio_dsr(r, rf_rate=0.045, n_strategies=0,
                        n_trials_per_strategy=[])
    assert 0.0 <= dsr <= 1.0


def test_risk_attribution_zero_portfolio_vol_returns_zeros():
    cov = np.zeros((2, 2))
    w = np.array([0.5, 0.5])
    ra = risk_attribution(w, cov, ["A", "B"])
    assert (ra["risk_contribution"].values == 0).all()
    assert (ra["marginal_risk"].values == 0).all()


def test_diversification_ratio_zero_port_vol_returns_one():
    w = np.array([0.5, 0.5])
    vols = np.array([0.0, 0.0])
    assert diversification_ratio(w, vols, portfolio_vol=0.0) == 1.0


def test_portfolio_calmar_zero_drawdown_returns_zero():
    """Monotonic series → max_dd = 0 → calmar returns 0."""
    idx = pd.date_range("2023-01-01", periods=10, freq="D")
    r = pd.Series(np.ones(10) * 0.001, index=idx)  # all positive
    assert portfolio_calmar(r) == 0.0


def test_portfolio_sortino_no_downside_returns_zero():
    """All returns above rf → no downside → sortino = 0.0."""
    idx = pd.date_range("2023-01-01", periods=10, freq="D")
    r = pd.Series(np.ones(10) * 1.0, index=idx)
    assert portfolio_sortino(r, rf_rate=0.045) == 0.0


def test_portfolio_exposure_empty_df_returns_zero():
    assert portfolio_exposure(pd.DataFrame()) == 0.0
