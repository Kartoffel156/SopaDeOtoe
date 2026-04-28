"""
Weight allocation methods for the portfolio combinator.

Roncalli Cap. 2 (ERC, risk budgeting), Prado AFML Cap. 16 (HRP),
Carver Cap. 4+8 (handcrafting, inverse vol).
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.cluster import hierarchy as sch
from scipy.spatial.distance import squareform


def equal_weight(n: int) -> np.ndarray:
    """1/N allocation. Baseline benchmark."""
    return np.ones(n) / n


def inverse_volatility(volatilities: np.ndarray) -> np.ndarray:
    """
    Carver default / Roncalli ρ=0 analytical ERC.
    w_i = (1/σ_i) / Σ(1/σ_j)
    """
    inv = 1.0 / np.maximum(volatilities, 1e-10)
    return inv / inv.sum()


# --- Equal Risk Contribution (Roncalli Cap. 2) ---

def risk_contribution(weights: np.ndarray, covariance: np.ndarray) -> np.ndarray:
    """
    Roncalli Cap. 2: RC_i = w_i × (Σw)_i / σ(w)

    Returns array of risk contributions. Σ RC_i = σ(portfolio) by Euler theorem.
    """
    port_vol = np.sqrt(weights @ covariance @ weights)
    if port_vol < 1e-12:
        return np.zeros(len(weights))
    marginal = covariance @ weights / port_vol
    return weights * marginal


def equal_risk_contribution(covariance: np.ndarray,
                            max_iter: int = 1000,
                            tol: float = 1e-10) -> np.ndarray:
    """
    Roncalli Cap. 2 (Eq. 2.22): ERC via SQP optimization.

    min Σ_i Σ_j (RC_i - RC_j)²
    s.t. Σ w_i = 1, w_i ≥ 0
    """
    n = covariance.shape[0]
    budgets = np.ones(n) / n
    return _risk_budget_solve(covariance, budgets, max_iter, tol)


def risk_budget_solve(covariance: np.ndarray,
                      budgets: np.ndarray,
                      max_iter: int = 1000,
                      tol: float = 1e-10) -> np.ndarray:
    """
    Roncalli Cap. 2 (Eq. 2.21): Generalized risk budgeting.
    Public API — delegates to internal solver.
    """
    budgets = np.asarray(budgets, dtype=float)
    budgets = budgets / budgets.sum()  # normalize
    return _risk_budget_solve(covariance, budgets, max_iter, tol)


def _risk_budget_solve(covariance: np.ndarray,
                       budgets: np.ndarray,
                       max_iter: int,
                       tol: float) -> np.ndarray:
    """
    Internal SQP solver for risk budgeting.

    Roncalli Cap. 2 (Remark 28): solve without Σw_i=1 constraint,
    then rescale. More numerically stable.

    Objective: min Σ_i Σ_j (w_i(Σw)_i/b_i - w_j(Σw)_j/b_j)²
    """
    n = covariance.shape[0]
    x0 = np.ones(n) / n

    def objective(w):
        port_vol = np.sqrt(w @ covariance @ w)
        if port_vol < 1e-12:
            return 0.0
        rc = w * (covariance @ w) / port_vol
        rc_scaled = rc / budgets
        total = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                total += (rc_scaled[i] - rc_scaled[j]) ** 2
        return total

    bounds = [(1e-6, None)] * n
    constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]

    result = minimize(objective, x0, method="SLSQP",
                      bounds=bounds, constraints=constraints,
                      options={"maxiter": max_iter, "ftol": tol})
    w = result.x
    w = np.maximum(w, 0)
    return w / w.sum()


# --- Hierarchical Risk Parity (Prado AFML Cap. 16) ---

def hierarchical_risk_parity(covariance: np.ndarray,
                             correlation: np.ndarray) -> np.ndarray:
    """
    Prado AFML Cap. 16, Sec. 16.4: Three-stage HRP algorithm.
    Stage 1: Tree clustering. Stage 2: Quasi-diagonalization. Stage 3: Recursive bisection.
    """
    n = covariance.shape[0]
    if n == 1:
        return np.array([1.0])

    # Stage 1: Clustering
    dist = np.sqrt(0.5 * (1 - correlation))
    np.fill_diagonal(dist, 0)
    condensed = squareform(dist, checks=False)
    link = sch.linkage(condensed, method="single")

    # Stage 2: Quasi-diagonalization (seriation)
    sort_ix = _get_quasi_diag(link)

    # Stage 3: Recursive bisection
    weights = np.zeros(n)
    _recursive_bisect(covariance, sort_ix, weights)
    return weights / weights.sum()


def _get_quasi_diag(link: np.ndarray) -> list:
    """Recover leaf order from linkage matrix (seriation)."""
    n = int(link[-1, 3])
    sort_ix = pd.Series([link[-1, 0], link[-1, 1]])

    while sort_ix.max() >= n:
        sort_ix.index = range(0, sort_ix.shape[0] * 2, 2)
        df0 = sort_ix[sort_ix >= n]
        i = df0.index
        j = df0.values - n
        sort_ix[i] = link[j.astype(int), 0]
        df1 = pd.Series(link[j.astype(int), 1], index=i + 1)
        sort_ix = pd.concat([sort_ix, df1])
        sort_ix = sort_ix.sort_index()
        sort_ix.index = range(sort_ix.shape[0])

    return sort_ix.astype(int).tolist()


def _recursive_bisect(cov: np.ndarray, sort_ix: list, weights: np.ndarray):
    """Recursive bisection: split variance between left and right branches."""
    if len(sort_ix) <= 1:
        weights[sort_ix[0]] = 1.0
        return

    mid = len(sort_ix) // 2
    left = sort_ix[:mid]
    right = sort_ix[mid:]

    # Cluster variance = inverse variance weighting within each cluster
    var_left = _cluster_var(cov, left)
    var_right = _cluster_var(cov, right)
    alpha = 1.0 - var_left / (var_left + var_right)

    _recursive_bisect(cov, left, weights)
    _recursive_bisect(cov, right, weights)

    weights[left] *= alpha
    weights[right] *= (1.0 - alpha)


def _cluster_var(cov: np.ndarray, indices: list) -> float:
    """Variance of an inverse-variance-weighted cluster."""
    sub_cov = cov[np.ix_(indices, indices)]
    ivp = 1.0 / np.diag(sub_cov)
    ivp = ivp / ivp.sum()
    return ivp @ sub_cov @ ivp
