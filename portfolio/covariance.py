"""
Covariance matrix estimation for the portfolio combinator.

Methods: sample, Ledoit-Wolf shrinkage, EWMA.
Roncalli Cap. 1, Sec. 1.2.4.3 — shrinkage interpretation.
"""

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf


def estimate_covariance(returns_df: pd.DataFrame,
                        method: str = "shrinkage",
                        halflife: int = 63) -> np.ndarray:
    """
    Estimate the covariance matrix of strategy returns.

    Params:
        returns_df : DataFrame, one column per strategy, DatetimeIndex.
        method     : "sample", "shrinkage" (Ledoit-Wolf), or "exponential" (EWMA).
        halflife   : int, for EWMA method only (days).

    Returns:
        np.ndarray — N×N covariance matrix.
    """
    clean = returns_df.dropna()
    if method == "sample":
        return clean.cov().values
    elif method == "shrinkage":
        lw = LedoitWolf().fit(clean.values)
        return lw.covariance_
    elif method == "exponential":
        ewma_cov = clean.ewm(halflife=halflife).cov()
        # Take the last complete covariance matrix
        last_date = clean.index[-1]
        cov_slice = ewma_cov.loc[last_date]
        return cov_slice.values
    else:
        raise ValueError(f"method must be 'sample', 'shrinkage', or 'exponential', got '{method}'")
