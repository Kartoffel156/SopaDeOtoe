"""
Core combination logic: FDM, weighted return combination.

Carver Cap. 8 (FDM), Cap. 11 (IDM).
"""

import numpy as np
import pandas as pd


def forecast_diversification_multiplier(
    weights: np.ndarray,
    correlation: np.ndarray,
    max_fdm: float = 2.5,
) -> float:
    """
    Carver Cap. 8: FDM = 1 / √(w' × ρ_floored × w)

    Floors negative correlations at zero before computation.
    Caps at max_fdm to prevent dangerous leverage.
    """
    corr_floored = np.maximum(correlation, 0.0)
    denominator_sq = weights @ corr_floored @ weights
    if denominator_sq <= 0:
        return 1.0
    fdm = 1.0 / np.sqrt(denominator_sq)
    return min(fdm, max_fdm)


def combine_weighted_returns(
    returns_df: pd.DataFrame,
    weights: np.ndarray,
    fdm: float = 1.0,
) -> pd.Series:
    """
    R_portfolio(t) = FDM × Σ w_i × R_i(t)

    Params:
        returns_df : DataFrame, one column per strategy.
        weights    : array of strategy weights (sum to 1).
        fdm        : forecast diversification multiplier.

    Returns:
        pd.Series — combined portfolio returns.
    """
    weighted = returns_df.values @ weights
    return pd.Series(weighted * fdm, index=returns_df.index, name="combined_return")
