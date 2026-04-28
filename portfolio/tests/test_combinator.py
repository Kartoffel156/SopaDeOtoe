import pytest
import numpy as np
import pandas as pd
from portfolio.combinator import (
    forecast_diversification_multiplier,
    combine_weighted_returns,
)


def test_fdm_perfect_correlation_is_1():
    w = np.array([0.5, 0.5])
    corr = np.array([[1.0, 1.0], [1.0, 1.0]])
    fdm = forecast_diversification_multiplier(w, corr)
    assert abs(fdm - 1.0) < 0.01


def test_fdm_zero_correlation_equals_sqrt_n():
    """With equal weights and zero correlation, FDM = √N."""
    n = 4
    w = np.ones(n) / n
    corr = np.eye(n)
    fdm = forecast_diversification_multiplier(w, corr)
    assert abs(fdm - np.sqrt(n)) < 0.01


def test_fdm_capped_at_max():
    """FDM should not exceed max_fdm (default 2.5)."""
    n = 25
    w = np.ones(n) / n
    corr = np.eye(n)
    fdm = forecast_diversification_multiplier(w, corr, max_fdm=2.5)
    assert fdm <= 2.5 + 1e-6


def test_fdm_floors_negative_correlations():
    """Carver Cap. 8: floor correlations at zero before computing FDM."""
    w = np.array([0.5, 0.5])
    corr = np.array([[1.0, -0.8], [-0.8, 1.0]])
    fdm = forecast_diversification_multiplier(w, corr)
    # Should behave as if corr = 0, not -0.8
    fdm_zero = forecast_diversification_multiplier(w, np.eye(2))
    assert abs(fdm - fdm_zero) < 0.01


def test_combine_weighted_returns():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    returns = pd.DataFrame({
        "A": [0.01, -0.005, 0.02, 0.0, -0.01],
        "B": [0.0, 0.015, -0.01, 0.005, 0.0],
    }, index=idx)
    weights = np.array([0.6, 0.4])
    fdm = 1.2
    combined = combine_weighted_returns(returns, weights, fdm)
    # Bar 0: (0.6*0.01 + 0.4*0.0) * 1.2 = 0.0072
    assert abs(combined.iloc[0] - 0.0072) < 1e-8


def test_fdm_degenerate_denominator_returns_one():
    """When w' x corr_floored x w <= 0 (all zero), FDM falls back to 1.0."""
    w = np.array([0.0, 0.0])
    corr = np.eye(2)
    fdm = forecast_diversification_multiplier(w, corr)
    assert fdm == 1.0
