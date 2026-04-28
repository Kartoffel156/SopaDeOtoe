import pytest
import numpy as np
import pandas as pd
from portfolio.orthogonality import (
    correlation_matrix, overlap_matrix, pca_decomposition,
    hierarchical_clustering, orthogonality_report,
)


def _make_strategy_returns(n_bars=500, seed=42):
    """Helper: create 3 synthetic strategy return series with known correlation structure."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n_bars, freq="D")
    # A and B: correlated (share a common factor)
    common = rng.normal(0, 0.01, n_bars)
    a_returns = common + rng.normal(0, 0.005, n_bars)
    b_returns = common + rng.normal(0, 0.005, n_bars)
    # C: independent
    c_returns = rng.normal(0, 0.01, n_bars)
    # Make them sparse (low exposure) — 20% active
    mask_a = rng.random(n_bars) < 0.20
    mask_b = rng.random(n_bars) < 0.20
    mask_c = rng.random(n_bars) < 0.20
    a_returns[~mask_a] = 0.0
    b_returns[~mask_b] = 0.0
    c_returns[~mask_c] = 0.0

    positions_a = pd.Series(np.where(mask_a, 1.0, 0.0), index=idx)
    positions_b = pd.Series(np.where(mask_b, 1.0, 0.0), index=idx)
    positions_c = pd.Series(np.where(mask_c, 1.0, 0.0), index=idx)

    return {
        "A": {"returns": pd.Series(a_returns, index=idx), "positions": positions_a},
        "B": {"returns": pd.Series(b_returns, index=idx), "positions": positions_b},
        "C": {"returns": pd.Series(c_returns, index=idx), "positions": positions_c},
    }


# --- Correlation matrix ---

def test_correlation_matrix_shape():
    data = _make_strategy_returns()
    returns_df = pd.DataFrame({k: v["returns"] for k, v in data.items()})
    positions_df = pd.DataFrame({k: v["positions"] for k, v in data.items()})
    corr = correlation_matrix(returns_df, positions_df, method="spearman")
    assert corr.shape == (3, 3)
    assert list(corr.columns) == ["A", "B", "C"]
    # Diagonal is 1.0
    for i in range(3):
        assert abs(corr.iloc[i, i] - 1.0) < 1e-10


def test_correlation_a_b_higher_than_a_c():
    """A and B share a common factor; C is independent."""
    data = _make_strategy_returns(n_bars=5000, seed=123)
    returns_df = pd.DataFrame({k: v["returns"] for k, v in data.items()})
    positions_df = pd.DataFrame({k: v["positions"] for k, v in data.items()})
    corr = correlation_matrix(returns_df, positions_df, method="spearman")
    assert abs(corr.loc["A", "B"]) > abs(corr.loc["A", "C"])


# --- Overlap matrix ---

def test_overlap_matrix_shape():
    data = _make_strategy_returns()
    positions_df = pd.DataFrame({k: v["positions"] for k, v in data.items()})
    ov = overlap_matrix(positions_df)
    assert ov.shape == (3, 3)
    # Diagonal = 1.0 (strategy always overlaps with itself)
    for i in range(3):
        assert abs(ov.iloc[i, i] - 1.0) < 1e-10


def test_overlap_values_between_0_and_1():
    data = _make_strategy_returns()
    positions_df = pd.DataFrame({k: v["positions"] for k, v in data.items()})
    ov = overlap_matrix(positions_df)
    assert (ov.values >= 0).all()
    assert (ov.values <= 1.0 + 1e-10).all()


# --- PCA decomposition ---

def test_pca_returns_correct_keys():
    data = _make_strategy_returns(n_bars=1000)
    returns_df = pd.DataFrame({k: v["returns"] for k, v in data.items()})
    corr = correlation_matrix(returns_df)
    result = pca_decomposition(corr)
    assert "eigenvalues" in result
    assert "explained_variance_ratio" in result
    assert "effective_dimension" in result
    assert len(result["eigenvalues"]) == 3


def test_pca_eigenvalues_sum_to_n():
    data = _make_strategy_returns(n_bars=1000)
    returns_df = pd.DataFrame({k: v["returns"] for k, v in data.items()})
    corr = correlation_matrix(returns_df)
    result = pca_decomposition(corr)
    assert abs(sum(result["eigenvalues"]) - 3.0) < 0.1  # sum ≈ N for correlation matrix


def test_pca_effective_dimension_less_than_n():
    data = _make_strategy_returns(n_bars=1000)
    returns_df = pd.DataFrame({k: v["returns"] for k, v in data.items()})
    corr = correlation_matrix(returns_df)
    result = pca_decomposition(corr, variance_threshold=0.95)
    assert result["effective_dimension"] <= 3
    assert result["effective_dimension"] >= 1


# --- Hierarchical clustering ---

def test_hierarchical_clustering_returns_linkage():
    data = _make_strategy_returns(n_bars=1000)
    returns_df = pd.DataFrame({k: v["returns"] for k, v in data.items()})
    corr = correlation_matrix(returns_df)
    result = hierarchical_clustering(corr)
    assert "linkage" in result
    assert "labels" in result
    assert len(result["labels"]) == 3
    # Linkage matrix has (N-1) rows for N items
    assert result["linkage"].shape[0] == 2


# --- Orthogonality report ---

def test_orthogonality_report_keys():
    data = _make_strategy_returns(n_bars=1000)
    returns_df = pd.DataFrame({k: v["returns"] for k, v in data.items()})
    positions_df = pd.DataFrame({k: v["positions"] for k, v in data.items()})
    report = orthogonality_report(returns_df, positions_df)
    assert "correlation_matrix" in report
    assert "overlap_matrix" in report
    assert "pca" in report
    assert "clustering" in report
    assert "flags" in report
    assert isinstance(report["flags"], list)


def test_orthogonality_report_flags_high_correlation():
    """If we make A and B identical, a warning flag should appear."""
    idx = pd.date_range("2023-01-01", periods=500, freq="D")
    rng = np.random.default_rng(42)
    shared = rng.normal(0, 0.01, 500)
    returns_df = pd.DataFrame({
        "A": shared,
        "B": shared + rng.normal(0, 0.0001, 500),  # nearly identical
        "C": rng.normal(0, 0.01, 500),
    }, index=idx)
    positions_df = pd.DataFrame({
        "A": np.ones(500), "B": np.ones(500), "C": np.ones(500),
    }, index=idx)
    report = orthogonality_report(returns_df, positions_df, max_correlation=0.6)
    assert any("A" in f and "B" in f for f in report["flags"])


def test_correlation_matrix_sparse_active_bars_forced_to_zero():
    """When fewer than 10 active bars overlap, correlation is forced to 0.0."""
    idx = pd.date_range("2023-01-01", periods=100, freq="D")
    rng = np.random.default_rng(0)
    returns_df = pd.DataFrame({
        "A": rng.normal(0, 0.01, 100),
        "B": rng.normal(0, 0.01, 100),
    }, index=idx)
    # Only 5 overlapping active bars
    pos_a = np.zeros(100)
    pos_a[:5] = 1.0
    pos_b = np.zeros(100)
    pos_b[:5] = 1.0
    positions_df = pd.DataFrame({"A": pos_a, "B": pos_b}, index=idx)
    corr = correlation_matrix(returns_df, positions_df)
    assert corr.loc["A", "B"] == 0.0


def test_correlation_matrix_pearson_method():
    """pearson branch: ri.corr(rj) is used instead of ranked spearman."""
    idx = pd.date_range("2023-01-01", periods=200, freq="D")
    rng = np.random.default_rng(1)
    a = rng.normal(0, 0.01, 200)
    returns_df = pd.DataFrame({
        "A": a,
        "B": a * 2.0,  # perfectly correlated under pearson
    }, index=idx)
    corr = correlation_matrix(returns_df, positions_df=None, method="pearson")
    assert abs(corr.loc["A", "B"] - 1.0) < 1e-10
