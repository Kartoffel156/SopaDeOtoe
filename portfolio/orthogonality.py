"""
Orthogonality analysis for multi-strategy portfolios.

Evaluates whether strategies are genuinely different before combining.
Roncalli Cap. 1 (correlation/diversification), Prado AFML Cap. 16 (clustering).
"""

import numpy as np
import pandas as pd
from scipy.cluster import hierarchy as sch
from scipy.spatial.distance import squareform


def correlation_matrix(returns_df: pd.DataFrame,
                       positions_df: pd.DataFrame | None = None,
                       method: str = "spearman") -> pd.DataFrame:
    """
    Pairwise correlation between strategy returns, computed on active bars only.

    Active bars: bars where position != 0 for BOTH strategies in a pair.
    Roncalli Cap. 1, Sec. 1.1.3 — Spearman for non-normal distributions.

    Params:
        returns_df   : DataFrame with one column per strategy, DatetimeIndex.
        positions_df : DataFrame with same columns/index. If None, use all bars.
        method       : "spearman" (default, robust) or "pearson".

    Returns:
        DataFrame — N×N correlation matrix.
    """
    names = returns_df.columns.tolist()
    n = len(names)
    corr = pd.DataFrame(np.eye(n), index=names, columns=names)

    for i in range(n):
        for j in range(i + 1, n):
            ri = returns_df.iloc[:, i]
            rj = returns_df.iloc[:, j]
            if positions_df is not None:
                mask = (positions_df.iloc[:, i].fillna(0) != 0) & \
                       (positions_df.iloc[:, j].fillna(0) != 0)
                ri = ri.loc[mask]
                rj = rj.loc[mask]
            if len(ri) < 10:
                corr.iloc[i, j] = corr.iloc[j, i] = 0.0
                continue
            if method == "spearman":
                c = ri.rank().corr(rj.rank())
            else:
                c = ri.corr(rj)
            corr.iloc[i, j] = corr.iloc[j, i] = c

    return corr


def overlap_matrix(positions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Fraction of bars where two strategies are simultaneously active.

    overlap(i,j) = count(pos_i != 0 AND pos_j != 0) / count(pos_i != 0 OR pos_j != 0)

    High overlap + low correlation = genuine diversification.
    High overlap + high correlation = redundancy.
    Low overlap = time diversification.
    """
    names = positions_df.columns.tolist()
    n = len(names)
    ov = pd.DataFrame(np.eye(n), index=names, columns=names)

    for i in range(n):
        for j in range(i + 1, n):
            active_i = positions_df.iloc[:, i].fillna(0) != 0
            active_j = positions_df.iloc[:, j].fillna(0) != 0
            both = (active_i & active_j).sum()
            either = (active_i | active_j).sum()
            val = both / either if either > 0 else 0.0
            ov.iloc[i, j] = ov.iloc[j, i] = val

    return ov


def pca_decomposition(corr_matrix: pd.DataFrame,
                      variance_threshold: float = 0.95) -> dict:
    """
    Eigenvalue decomposition of the strategy correlation matrix.

    Prado AFML Cap. 16, Sec. 16.3: If the first eigenvalue explains >80%
    of variance, strategies are effectively one-dimensional.

    Params:
        corr_matrix        : N×N correlation DataFrame.
        variance_threshold : fraction of variance to determine effective_dimension.

    Returns:
        dict with eigenvalues, eigenvectors, explained_variance_ratio,
        effective_dimension.
    """
    eigenvalues, eigenvectors = np.linalg.eigh(corr_matrix.values)
    # Sort descending
    idx_sort = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx_sort]
    eigenvectors = eigenvectors[:, idx_sort]

    total = eigenvalues.sum()
    explained = eigenvalues / total if total > 0 else eigenvalues * 0
    cumulative = np.cumsum(explained)
    effective_dim = int(np.searchsorted(cumulative, variance_threshold) + 1)
    effective_dim = min(effective_dim, len(eigenvalues))

    return {
        "eigenvalues": eigenvalues.tolist(),
        "eigenvectors": eigenvectors.tolist(),
        "explained_variance_ratio": explained.tolist(),
        "cumulative_variance": cumulative.tolist(),
        "effective_dimension": effective_dim,
    }


def hierarchical_clustering(corr_matrix: pd.DataFrame,
                            method: str = "ward") -> dict:
    """
    AFML Cap. 16, Sec. 16.4.1: Agglomerative clustering on distance matrix.

    d_ij = √(0.5 × (1 − ρ_ij))

    Params:
        corr_matrix : N×N correlation DataFrame.
        method      : linkage method ("ward", "single", "complete", "average").

    Returns:
        dict with linkage (scipy linkage matrix), labels (column names),
        distances (condensed distance matrix).
    """
    n = len(corr_matrix)
    dist = np.sqrt(0.5 * (1 - corr_matrix.values))
    np.fill_diagonal(dist, 0.0)
    condensed = squareform(dist, checks=False)
    linkage = sch.linkage(condensed, method=method)

    return {
        "linkage": linkage,
        "labels": corr_matrix.columns.tolist(),
        "distance_matrix": dist,
    }


def orthogonality_report(returns_df: pd.DataFrame,
                         positions_df: pd.DataFrame | None = None,
                         max_correlation: float = 0.60,
                         max_overlap: float = 0.50,
                         min_dim_ratio: float = 0.70) -> dict:
    """
    Aggregated orthogonality diagnostics.

    Params:
        returns_df       : DataFrame, one column per strategy.
        positions_df     : DataFrame, same shape. None → use all bars.
        max_correlation  : flag pairs above this threshold.
        max_overlap      : flag pairs above this threshold.
        min_dim_ratio    : flag if effective_dimension / n < this.

    Returns:
        dict with correlation_matrix, overlap_matrix, pca, clustering, flags.
    """
    corr = correlation_matrix(returns_df, positions_df)
    ov = overlap_matrix(positions_df) if positions_df is not None else None
    pca = pca_decomposition(corr)
    clust = hierarchical_clustering(corr)

    flags = []
    names = returns_df.columns.tolist()
    n = len(names)

    # Check pairwise correlation
    for i in range(n):
        for j in range(i + 1, n):
            if abs(corr.iloc[i, j]) > max_correlation:
                flags.append(
                    f"High correlation: {names[i]} and {names[j]} "
                    f"(ρ={corr.iloc[i, j]:.2f} > {max_correlation})"
                )

    # Check overlap
    if ov is not None:
        for i in range(n):
            for j in range(i + 1, n):
                if ov.iloc[i, j] > max_overlap:
                    flags.append(
                        f"High overlap: {names[i]} and {names[j]} "
                        f"(overlap={ov.iloc[i, j]:.2f} > {max_overlap})"
                    )

    # Check PCA dimension
    if n > 1 and pca["effective_dimension"] / n < min_dim_ratio:
        flags.append(
            f"Low effective dimension: {pca['effective_dimension']}/{n} "
            f"= {pca['effective_dimension']/n:.2f} < {min_dim_ratio}"
        )

    return {
        "correlation_matrix": corr,
        "overlap_matrix": ov,
        "pca": pca,
        "clustering": clust,
        "flags": flags,
    }
