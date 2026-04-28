import pytest
import numpy as np
from portfolio.risk_budget import (
    equal_weight, inverse_volatility,
    equal_risk_contribution, risk_contribution,
    hierarchical_risk_parity, risk_budget_solve,
)


# --- Equal weight & inverse vol ---

def test_equal_weight():
    w = equal_weight(4)
    assert len(w) == 4
    assert abs(w.sum() - 1.0) < 1e-10
    assert np.allclose(w, 0.25)


def test_inverse_volatility():
    vols = np.array([0.10, 0.20, 0.40])
    w = inverse_volatility(vols)
    assert abs(w.sum() - 1.0) < 1e-10
    # Lowest vol gets highest weight
    assert w[0] > w[1] > w[2]


def test_inverse_volatility_equal_vols():
    vols = np.array([0.15, 0.15, 0.15])
    w = inverse_volatility(vols)
    assert np.allclose(w, 1/3)


# --- ERC ---

def test_erc_weights_sum_to_one():
    cov = np.array([[0.04, 0.006], [0.006, 0.09]])
    w = equal_risk_contribution(cov)
    assert abs(w.sum() - 1.0) < 1e-6


def test_erc_risk_contributions_are_equal():
    cov = np.array([[0.04, 0.006, 0.002],
                    [0.006, 0.09, 0.004],
                    [0.002, 0.004, 0.0225]])
    w = equal_risk_contribution(cov)
    rc = risk_contribution(w, cov)
    # All risk contributions should be approximately equal
    assert np.std(rc) < 0.01 * np.mean(rc)


def test_erc_diagonal_equals_inverse_vol():
    """With zero correlation, ERC = inverse vol."""
    vols = np.array([0.10, 0.20, 0.30])
    cov = np.diag(vols ** 2)
    w_erc = equal_risk_contribution(cov)
    w_iv = inverse_volatility(vols)
    assert np.allclose(w_erc, w_iv, atol=0.01)


def test_risk_contribution_sums_to_portfolio_vol():
    """Euler theorem: Σ RC_i = σ(portfolio)."""
    cov = np.array([[0.04, 0.01], [0.01, 0.09]])
    w = np.array([0.6, 0.4])
    rc = risk_contribution(w, cov)
    port_vol = np.sqrt(w @ cov @ w)
    assert abs(rc.sum() - port_vol) < 1e-8


# --- HRP ---

def test_hrp_weights_sum_to_one():
    cov = np.array([[0.04, 0.01, 0.002],
                    [0.01, 0.09, 0.003],
                    [0.002, 0.003, 0.0225]])
    corr = np.corrcoef(np.random.default_rng(42).multivariate_normal(
        [0, 0, 0], cov, 1000).T)
    w = hierarchical_risk_parity(cov, corr)
    assert abs(w.sum() - 1.0) < 1e-6
    assert (w > 0).all()


def test_hrp_low_vol_gets_more_weight():
    """With low correlations, HRP should behave roughly like inverse-vol."""
    cov = np.diag([0.01, 0.04, 0.09])
    corr = np.eye(3)
    w = hierarchical_risk_parity(cov, corr)
    assert w[0] > w[1] > w[2]


def test_risk_contribution_zero_port_vol_returns_zeros():
    """Null covariance → zero risk contributions (no division by zero)."""
    cov = np.zeros((3, 3))
    w = np.array([0.3, 0.3, 0.4])
    rc = risk_contribution(w, cov)
    assert (rc == 0).all()
    assert len(rc) == 3


def test_risk_budget_solve_normalizes_budgets():
    """Public API should accept unnormalized budgets and renormalize internally."""
    cov = np.array([[0.04, 0.006], [0.006, 0.09]])
    w1 = risk_budget_solve(cov, budgets=np.array([1.0, 1.0]))  # normalized to 0.5/0.5
    w2 = risk_budget_solve(cov, budgets=np.array([5.0, 5.0]))  # also 0.5/0.5 after norm
    assert np.allclose(w1, w2, atol=1e-6)
    # Equal budgets → ERC
    w_erc = equal_risk_contribution(cov)
    assert np.allclose(w1, w_erc, atol=1e-4)


def test_hrp_single_strategy_returns_unit_weight():
    cov = np.array([[0.04]])
    corr = np.array([[1.0]])
    w = hierarchical_risk_parity(cov, corr)
    assert w.tolist() == [1.0]


def test_risk_budget_solve_zero_covariance_objective_short_circuits():
    """Zero covariance → objective() sees port_vol ~ 0 → returns 0, solver still completes."""
    cov = np.zeros((3, 3))
    budgets = np.array([1.0, 1.0, 1.0])
    w = risk_budget_solve(cov, budgets)
    assert abs(w.sum() - 1.0) < 1e-6
    assert (w >= 0).all()
