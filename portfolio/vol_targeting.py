"""
Volatility targeting overlay.

Carver Cap. 9: Scale positions so portfolio achieves desired vol target.
"""

import numpy as np
import pandas as pd


def vol_target_scalar(target_vol: float,
                      realized_vol: float,
                      max_leverage: float = 2.0) -> float:
    """
    Carver Cap. 9: leverage = target / realized, capped at max.

    Params:
        target_vol   : annualized target volatility (e.g. 0.15).
        realized_vol : annualized realized volatility.
        max_leverage  : hard cap on the scalar.

    Returns:
        float — multiplier for positions.
    """
    if realized_vol <= 1e-10:
        return 1.0
    scalar = target_vol / realized_vol
    return min(scalar, max_leverage)


def apply_vol_targeting(
    combined_returns: pd.Series,
    target_vol: float,
    lookback: int = 25,
    method: str = "ewma",
    ewma_span: int = 36,
    max_leverage: float = 2.0,
    ann_factor: float = 252.0,
) -> pd.Series:
    """
    Apply rolling vol targeting to a return series.

    Carver Cap. 9: Lookback 25 days (simple) or 36 days (EWMA equivalent).
    Returns are scaled bar-by-bar by the vol scalar.

    The scalar is shifted by 1 bar to prevent lookahead.
    """
    if method == "ewma":
        rolling_vol = combined_returns.ewm(span=ewma_span).std() * np.sqrt(ann_factor)
    else:
        rolling_vol = combined_returns.rolling(lookback).std() * np.sqrt(ann_factor)

    # Shift to prevent lookahead: scale at bar t uses vol estimated up to t-1
    rolling_vol = rolling_vol.shift(1)

    scalars = rolling_vol.apply(
        lambda rv: vol_target_scalar(target_vol, rv, max_leverage) if rv > 0 else 1.0
    )

    return combined_returns * scalars
