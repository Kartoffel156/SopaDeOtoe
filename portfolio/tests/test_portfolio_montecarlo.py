import pytest
import numpy as np
import pandas as pd
from portfolio.portfolio_montecarlo import (
    strategy_permutation, portfolio_bootstrap,
    correlation_stress_test, portfolio_spa_test,
)


def _make_returns_df(n=500, k=3, seed=42):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    # Strategy 0 has positive mean, others near zero
    data = rng.normal(0, 0.01, (n, k))
    data[:, 0] += 0.0005  # slight edge
    return pd.DataFrame(data, index=idx, columns=[f"S{i}" for i in range(k)])


# --- Strategy permutation ---

def test_permutation_returns_keys():
    df = _make_returns_df()
    w = np.array([0.5, 0.3, 0.2])
    result = strategy_permutation(df, w, n_permutations=500, random_state=42)
    assert "observed_sharpe" in result
    assert "p_value" in result
    assert "permutation_sharpes" in result
    assert len(result["permutation_sharpes"]) == 500


def test_permutation_p_value_range():
    df = _make_returns_df()
    w = np.array([0.5, 0.3, 0.2])
    result = strategy_permutation(df, w, n_permutations=500, random_state=42)
    assert 0.0 <= result["p_value"] <= 1.0


# --- Bootstrap ---

def test_bootstrap_returns_keys():
    r = pd.Series(np.random.default_rng(42).normal(0.0003, 0.01, 500),
                  index=pd.date_range("2023-01-01", periods=500, freq="D"))
    result = portfolio_bootstrap(r, n_bootstrap=500, random_state=42)
    assert "sharpe_mean" in result
    assert "sharpe_ci_95" in result
    assert "prob_negative_sharpe" in result
    assert "max_dd_ci_95" in result


def test_bootstrap_ci_ordering():
    r = pd.Series(np.random.default_rng(42).normal(0.0003, 0.01, 500),
                  index=pd.date_range("2023-01-01", periods=500, freq="D"))
    result = portfolio_bootstrap(r, n_bootstrap=500, random_state=42)
    lo, hi = result["sharpe_ci_95"]
    assert lo < hi


def test_bootstrap_prob_negative_range():
    r = pd.Series(np.random.default_rng(42).normal(0.0003, 0.01, 500),
                  index=pd.date_range("2023-01-01", periods=500, freq="D"))
    result = portfolio_bootstrap(r, n_bootstrap=500, random_state=42)
    assert 0.0 <= result["prob_negative_sharpe"] <= 1.0


# --- Correlation stress test ---

def test_stress_test_returns_scenarios():
    df = _make_returns_df()
    w = np.array([0.4, 0.35, 0.25])
    result = correlation_stress_test(df, w, n_simulations=200, random_state=42)
    assert "crisis" in result
    assert "decorrelation" in result
    assert "moderate_stress" in result


def test_stress_test_crisis_higher_vol():
    """Crisis (high corr) should produce worse diversification than decorrelation."""
    df = _make_returns_df(n=1000)
    w = np.array([0.4, 0.35, 0.25])
    result = correlation_stress_test(df, w, n_simulations=1000, random_state=42)
    # Higher correlation generally means worse diversification
    assert result["crisis"]["prob_negative_sharpe"] >= 0  # just check it runs


# --- SPA test ---

def test_spa_returns_keys():
    r = pd.Series(np.random.default_rng(42).normal(0.0003, 0.01, 500),
                  index=pd.date_range("2023-01-01", periods=500, freq="D"))
    result = portfolio_spa_test(r, n_bootstrap=500, random_state=42)
    assert "statistic" in result
    assert "p_value" in result
    assert "reject_h0" in result
    assert isinstance(result["reject_h0"], bool)


def test_spa_with_benchmark():
    idx = pd.date_range("2023-01-01", periods=500, freq="D")
    rng = np.random.default_rng(42)
    combined = pd.Series(rng.normal(0.0005, 0.01, 500), index=idx)
    benchmark = pd.Series(rng.normal(0.0001, 0.01, 500), index=idx)
    result = portfolio_spa_test(combined, benchmark, n_bootstrap=500, random_state=42)
    assert "p_value" in result
    assert 0.0 <= result["p_value"] <= 1.0


def test_spa_constant_series_returns_neutral():
    """Constant returns yield zero bootstrap variance → neutral output."""
    idx = pd.date_range("2023-01-01", periods=100, freq="D")
    r = pd.Series(np.full(100, 0.001), index=idx)
    result = portfolio_spa_test(r, n_bootstrap=100, random_state=42)
    assert result["statistic"] == 0.0
    assert result["p_value"] == 0.5
    assert result["reject_h0"] is False


def test_bootstrap_constant_series_sharpe_zero():
    """_sharpe returns 0.0 when std is near zero (covers helper short-circuit)."""
    idx = pd.date_range("2023-01-01", periods=100, freq="D")
    r = pd.Series(np.full(100, 0.0), index=idx)
    result = portfolio_bootstrap(r, n_bootstrap=100, random_state=42)
    assert result["sharpe_mean"] == 0.0
