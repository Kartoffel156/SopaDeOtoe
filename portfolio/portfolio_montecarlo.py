"""
Ensemble-level Monte Carlo validation for the portfolio combinator.

Strategy permutation, block bootstrap, correlation stress testing,
Hansen's SPA test at portfolio level, portfolio-level CPCV.
"""

import numpy as np
import pandas as pd
from itertools import combinations
from scipy.stats import norm


def strategy_permutation(
    strategy_returns_df: pd.DataFrame,
    weights: np.ndarray,
    n_permutations: int = 10_000,
    random_state: int | None = None,
) -> dict:
    """
    Permute which strategy's return is assigned to which weight slot.

    H0: The specific mapping of strategies to weights does not matter.
    If p_value < 0.05, the allocation method is capturing real
    diversification structure, not random noise.
    """
    rng = np.random.default_rng(random_state)
    n_strategies = len(weights)

    # Observed combined Sharpe
    observed_returns = strategy_returns_df.values @ weights
    observed_sharpe = _sharpe(observed_returns)

    # Permutation distribution
    perm_sharpes = np.zeros(n_permutations)
    for i in range(n_permutations):
        perm_idx = rng.permutation(n_strategies)
        perm_returns = strategy_returns_df.values @ weights[perm_idx]
        perm_sharpes[i] = _sharpe(perm_returns)

    p_value = float(np.mean(perm_sharpes >= observed_sharpe))

    return {
        "observed_sharpe": float(observed_sharpe),
        "permutation_sharpes": perm_sharpes,
        "p_value": p_value,
        "mean_perm_sharpe": float(perm_sharpes.mean()),
        "std_perm_sharpe": float(perm_sharpes.std()),
        "n_permutations": n_permutations,
    }


def portfolio_bootstrap(
    combined_returns: pd.Series,
    n_bootstrap: int = 10_000,
    block_size: int = 21,
    random_state: int | None = None,
) -> dict:
    """
    Circular block bootstrap (Politis & Romano 1994) on combined returns.

    Block size = 21 (~1 month) preserves autocorrelation structure.
    Returns Sharpe distribution, CI, probability of negative Sharpe.
    """
    rng = np.random.default_rng(random_state)
    T = len(combined_returns)
    values = combined_returns.values

    boot_sharpes = np.zeros(n_bootstrap)
    boot_max_dds = np.zeros(n_bootstrap)

    for i in range(n_bootstrap):
        indices = _block_bootstrap_indices(T, block_size, rng)
        sample = values[indices]
        boot_sharpes[i] = _sharpe(sample)
        boot_max_dds[i] = _max_dd(sample)

    return {
        "sharpe_distribution": boot_sharpes,
        "sharpe_mean": float(boot_sharpes.mean()),
        "sharpe_std": float(boot_sharpes.std()),
        "sharpe_ci_95": (float(np.percentile(boot_sharpes, 2.5)),
                         float(np.percentile(boot_sharpes, 97.5))),
        "prob_negative_sharpe": float(np.mean(boot_sharpes < 0)),
        "max_dd_ci_95": (float(np.percentile(boot_max_dds, 2.5)),
                         float(np.percentile(boot_max_dds, 97.5))),
        "n_bootstrap": n_bootstrap,
        "block_size": block_size,
    }


def correlation_stress_test(
    strategy_returns_df: pd.DataFrame,
    weights: np.ndarray,
    stress_scenarios: list[dict] | None = None,
    n_simulations: int = 5_000,
    random_state: int | None = None,
) -> dict:
    """
    Simulate portfolio performance under stressed correlation regimes.

    Default scenarios:
    - crisis: all pairwise correlations -> 0.8
    - decorrelation: all pairwise correlations -> 0.0
    - inversion: correlation signs flip
    """
    rng = np.random.default_rng(random_state)
    n = strategy_returns_df.shape[1]
    T = strategy_returns_df.shape[0]
    means = strategy_returns_df.mean().values
    vols = strategy_returns_df.std().values

    if stress_scenarios is None:
        stress_scenarios = [
            {"name": "crisis", "correlation": 0.8},
            {"name": "decorrelation", "correlation": 0.0},
            {"name": "moderate_stress", "correlation": 0.5},
        ]

    results = {}
    for scenario in stress_scenarios:
        name = scenario["name"]
        target_corr = scenario["correlation"]

        # Build stressed covariance
        corr_stressed = np.full((n, n), target_corr)
        np.fill_diagonal(corr_stressed, 1.0)
        cov_stressed = np.outer(vols, vols) * corr_stressed

        # Ensure positive semi-definite
        eigvals, eigvecs = np.linalg.eigh(cov_stressed)
        eigvals = np.maximum(eigvals, 1e-10)
        cov_stressed = eigvecs @ np.diag(eigvals) @ eigvecs.T

        # Simulate returns
        sim_sharpes = np.zeros(n_simulations)
        for i in range(n_simulations):
            sim_returns = rng.multivariate_normal(means, cov_stressed, T)
            combined = sim_returns @ weights
            sim_sharpes[i] = _sharpe(combined)

        results[name] = {
            "sharpe_mean": float(sim_sharpes.mean()),
            "sharpe_std": float(sim_sharpes.std()),
            "sharpe_ci_95": (float(np.percentile(sim_sharpes, 2.5)),
                             float(np.percentile(sim_sharpes, 97.5))),
            "prob_negative_sharpe": float(np.mean(sim_sharpes < 0)),
            "target_correlation": target_corr,
        }

    return results


def portfolio_spa_test(
    combined_returns: pd.Series,
    benchmark_returns: pd.Series | None = None,
    n_bootstrap: int = 10_000,
    block_size: int = 21,
    random_state: int | None = None,
) -> dict:
    """
    Hansen's Superior Predictive Ability test (Hansen 2005) at portfolio level.

    H0: The combined portfolio does not outperform the benchmark
    (default: risk-free = 0) after accounting for data snooping.
    """
    rng = np.random.default_rng(random_state)

    if benchmark_returns is not None:
        common_idx = combined_returns.index.intersection(benchmark_returns.index)
        d = combined_returns.loc[common_idx].values - benchmark_returns.loc[common_idx].values
    else:
        d = combined_returns.values

    T = len(d)
    d_bar = d.mean()

    # Stationary bootstrap for variance estimation
    boot_stats = np.zeros(n_bootstrap)
    for i in range(n_bootstrap):
        indices = _block_bootstrap_indices(T, block_size, rng)
        boot_d = d[indices]
        boot_stats[i] = boot_d.mean()

    # HAC variance estimate from bootstrap
    var_d = np.var(boot_stats)
    if var_d < 1e-15:
        return {"statistic": 0.0, "p_value": 0.5, "reject_h0": False}

    t_stat = d_bar / np.sqrt(var_d)

    # Bootstrap p-value under H0 (centering)
    centered_stats = (boot_stats - d_bar) / np.sqrt(var_d)
    p_value = float(np.mean(centered_stats >= t_stat))

    return {
        "statistic": float(t_stat),
        "p_value": p_value,
        "reject_h0": p_value < 0.05,
        "mean_excess": float(d_bar),
        "n_bootstrap": n_bootstrap,
    }


def portfolio_cpcv(
    strategy_returns_df: pd.DataFrame,
    allocation_method: str = "erc",
    covariance_method: str = "shrinkage",
    covariance_halflife: int = 63,
    n_groups: int = 6,
    n_test_groups: int = 2,
    embargo_pct: float = 0.01,
    max_weight: float = 0.50,
    min_weight: float = 0.05,
    target_volatility: float | None = None,
    max_leverage: float = 2.0,
    custom_budgets: list | None = None,
) -> dict:
    """
    Combinatorial Purged Cross-Validation at portfolio level.

    Prado AFML Cap. 12, adapted from strategy-level to combinator:
    instead of training a model, we estimate covariance -> compute weights
    -> compute FDM on the training fold, then evaluate the combined
    portfolio return on the purged test fold.

    This answers: "Does the portfolio allocation generalize OOS, or does
    it overfit the covariance structure of the training period?"

    Algorithm:
    1. Split T bars into N contiguous groups.
    2. For each C(N, n_test) combination of test groups:
       a. Purge: remove `embargo` bars from training at each train/test
          boundary to prevent leakage.
       b. Train: estimate covariance, compute weights+FDM on train set.
       c. Test: combine strategy returns using train-derived weights+FDM.
       d. Record OOS Sharpe, return, max_dd.
    3. Stitch test-set returns across all paths to form complete OOS
       equity curves (Prado AFML Sec. 12.3).
    4. Return distribution of OOS metrics + stitched paths.

    Params:
        strategy_returns_df : DataFrame, one column per strategy, DatetimeIndex.
        allocation_method   : weight method ("erc", "hrp", "inverse_vol", etc.)
        covariance_method   : "shrinkage", "sample", "exponential"
        covariance_halflife : int, for exponential method
        n_groups            : N, number of contiguous groups (K-fold equiv)
        n_test_groups       : how many groups form the test set per path
        embargo_pct         : fraction of T to purge at each boundary
        max_weight          : max single-strategy weight
        min_weight          : min single-strategy weight
        target_volatility   : if set, apply vol targeting on OOS returns
        max_leverage        : cap for vol targeting scalar
        custom_budgets      : for risk_budget method

    Returns:
        dict with keys:
          sharpe_distribution : array of OOS Sharpes per path
          return_distribution : array of OOS annualized returns per path
          max_dd_distribution : array of OOS max drawdowns per path
          mean, std, percentiles : summary stats of Sharpe dist
          paths               : list of OOS equity Series (stitched)
          n_paths             : number of combinatorial paths
          weight_stability    : std of weights across paths (per strategy)
    """
    # Lazy imports to avoid circular dependency
    from portfolio.covariance import estimate_covariance
    from portfolio.risk_budget import (
        equal_weight, inverse_volatility, equal_risk_contribution,
        risk_budget_solve, hierarchical_risk_parity,
    )
    from portfolio.combinator import forecast_diversification_multiplier

    T = len(strategy_returns_df)
    n_strategies = strategy_returns_df.shape[1]
    embargo = max(1, int(T * embargo_pct))

    # 1. Split into N contiguous groups
    group_boundaries = np.array_split(np.arange(T), n_groups)
    group_ranges = [(g[0], g[-1]) for g in group_boundaries]

    # All C(N, n_test) combinations
    all_combos = list(combinations(range(n_groups), n_test_groups))
    n_paths = len(all_combos)

    path_sharpes = np.zeros(n_paths)
    path_returns = np.zeros(n_paths)
    path_max_dds = np.zeros(n_paths)
    path_weights = np.zeros((n_paths, n_strategies))
    path_fdms = np.zeros(n_paths)
    path_oos_series = []

    for path_idx, test_groups in enumerate(all_combos):
        train_groups = [g for g in range(n_groups) if g not in test_groups]

        # Build train and test indices
        test_indices = np.concatenate([group_boundaries[g] for g in test_groups])
        train_indices = np.concatenate([group_boundaries[g] for g in train_groups])

        # 2a. Purge: remove train bars within `embargo` of any test boundary
        test_set = set(test_indices)
        purge_set = set()
        for ti in test_indices:
            for offset in range(-embargo, embargo + 1):
                candidate = ti + offset
                if 0 <= candidate < T and candidate not in test_set:
                    purge_set.add(candidate)
        train_indices = np.array([i for i in train_indices if i not in purge_set])

        if len(train_indices) < 30 or len(test_indices) < 5:
            path_sharpes[path_idx] = np.nan
            path_returns[path_idx] = np.nan
            path_max_dds[path_idx] = np.nan
            continue

        # 2b. Train: estimate cov, weights, FDM
        train_df = strategy_returns_df.iloc[train_indices]
        test_df = strategy_returns_df.iloc[test_indices]

        cov = estimate_covariance(train_df, method=covariance_method,
                                  halflife=covariance_halflife)
        vols = np.sqrt(np.diag(cov))
        corr = np.corrcoef(train_df.values.T)
        # Fix degenerate correlation
        corr = np.nan_to_num(corr, nan=0.0)
        np.fill_diagonal(corr, 1.0)

        # Compute weights
        w = _cpcv_compute_weights(
            allocation_method, cov, corr, vols, n_strategies, custom_budgets,
        )
        # Clip
        w = _cpcv_clip_weights(w, max_weight, min_weight)

        fdm = forecast_diversification_multiplier(w, corr)

        # 2c. Test: combine OOS returns
        oos_combined = test_df.values @ w * fdm

        # Optional vol targeting on OOS
        if target_volatility is not None:
            train_combined = train_df.values @ w * fdm
            realized_vol = float(np.std(train_combined) * np.sqrt(252))
            if realized_vol > 1e-10:
                scalar = min(target_volatility / realized_vol, max_leverage)
                oos_combined = oos_combined * scalar

        # 2d. Record metrics
        path_sharpes[path_idx] = _sharpe(oos_combined)
        path_returns[path_idx] = float(oos_combined.mean() * 252)
        path_max_dds[path_idx] = _max_dd(oos_combined)
        path_weights[path_idx] = w
        path_fdms[path_idx] = fdm

        # Stitch OOS equity
        oos_eq = pd.Series(
            np.cumprod(1 + oos_combined),
            index=test_df.index,
        )
        path_oos_series.append(oos_eq)

    # Filter out nans
    valid = ~np.isnan(path_sharpes)
    valid_sharpes = path_sharpes[valid]
    valid_returns = path_returns[valid]
    valid_max_dds = path_max_dds[valid]
    valid_weights = path_weights[valid]

    # Weight stability: how much do weights vary across paths
    weight_stability = {}
    for i, col in enumerate(strategy_returns_df.columns):
        weight_stability[col] = {
            "mean": float(valid_weights[:, i].mean()),
            "std": float(valid_weights[:, i].std()),
        }

    pcts = {}
    if len(valid_sharpes) > 0:
        for p in [5, 25, 50, 75, 95]:
            pcts[str(p)] = float(np.percentile(valid_sharpes, p))

    return {
        "sharpe_distribution": valid_sharpes,
        "return_distribution": valid_returns,
        "max_dd_distribution": valid_max_dds,
        "mean": float(valid_sharpes.mean()) if len(valid_sharpes) > 0 else 0.0,
        "std": float(valid_sharpes.std()) if len(valid_sharpes) > 0 else 0.0,
        "percentiles": pcts,
        "prob_negative_sharpe": float(np.mean(valid_sharpes < 0)) if len(valid_sharpes) > 0 else 1.0,
        "paths": path_oos_series,
        "n_paths": n_paths,
        "n_valid_paths": int(valid.sum()),
        "fdm_mean": float(path_fdms[valid].mean()) if valid.any() else 0.0,
        "fdm_std": float(path_fdms[valid].std()) if valid.any() else 0.0,
        "weight_stability": weight_stability,
    }


def _cpcv_compute_weights(method, cov, corr, vols, n, custom_budgets):
    """Dispatch weights inside CPCV (avoids importing runner)."""
    from portfolio.risk_budget import (
        equal_weight, inverse_volatility, equal_risk_contribution,
        risk_budget_solve, hierarchical_risk_parity,
    )
    if method == "equal_weight":
        return equal_weight(n)
    elif method == "inverse_vol":
        return inverse_volatility(vols)
    elif method == "erc":
        return equal_risk_contribution(cov)
    elif method == "risk_budget":
        budgets = np.array(custom_budgets) if custom_budgets else equal_weight(n)
        return risk_budget_solve(cov, budgets)
    elif method == "hrp":
        return hierarchical_risk_parity(cov, corr)
    else:
        return equal_weight(n)


def _cpcv_clip_weights(w, max_w, min_w, max_iter=20):
    """Clip and renormalize weights (standalone for CPCV)."""
    w = np.maximum(w, 0)
    for _ in range(max_iter):
        w = np.clip(w, min_w, max_w)
        s = w.sum()
        if s > 0:
            w = w / s
        if w.max() <= max_w + 1e-10 and w.min() >= min_w - 1e-10:
            break
    return w


# --- Internal helpers ---

def _sharpe(returns: np.ndarray, ann_factor: float = 252.0) -> float:
    """Annualized Sharpe from daily returns array."""
    if len(returns) < 2 or returns.std() < 1e-12:
        return 0.0
    return float((returns.mean() / returns.std()) * np.sqrt(ann_factor))


def _max_dd(returns: np.ndarray) -> float:
    """Max drawdown from returns array."""
    equity = np.cumprod(1 + returns)
    running_max = np.maximum.accumulate(equity)
    dd = (equity - running_max) / running_max
    return float(dd.min())


def _block_bootstrap_indices(T: int, block_size: int,
                             rng: np.random.Generator) -> np.ndarray:
    """Circular block bootstrap indices."""
    n_blocks = int(np.ceil(T / block_size))
    starts = rng.integers(0, T, size=n_blocks)
    indices = []
    for s in starts:
        block = np.arange(s, s + block_size) % T
        indices.extend(block)
    return np.array(indices[:T])
