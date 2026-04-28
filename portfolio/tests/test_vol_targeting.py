import pytest
import numpy as np
import pandas as pd
from portfolio.vol_targeting import vol_target_scalar, apply_vol_targeting


def test_vol_scalar_doubles_when_half_target():
    """If realized vol is half of target, scalar should be ~2."""
    target = 0.20
    realized = 0.10
    scalar = vol_target_scalar(target, realized, max_leverage=3.0)
    assert abs(scalar - 2.0) < 0.01


def test_vol_scalar_capped_at_max_leverage():
    target = 0.20
    realized = 0.01  # very low vol -> wants 20x leverage
    scalar = vol_target_scalar(target, realized, max_leverage=2.0)
    assert scalar <= 2.0


def test_vol_scalar_is_1_when_at_target():
    scalar = vol_target_scalar(0.15, 0.15)
    assert abs(scalar - 1.0) < 0.01


def test_apply_vol_targeting():
    idx = pd.date_range("2024-01-01", periods=100, freq="D")
    rng = np.random.default_rng(42)
    returns = pd.Series(rng.normal(0, 0.01, 100), index=idx)
    result = apply_vol_targeting(returns, target_vol=0.15, lookback=25)
    assert len(result) == 100
    assert isinstance(result, pd.Series)


def test_vol_scalar_zero_realized_returns_one():
    """When realized vol is essentially zero, scalar defaults to 1.0."""
    assert vol_target_scalar(target_vol=0.15, realized_vol=0.0) == 1.0
    assert vol_target_scalar(target_vol=0.15, realized_vol=1e-15) == 1.0


def test_apply_vol_targeting_rolling_method():
    """Non-ewma branch uses simple rolling window."""
    idx = pd.date_range("2024-01-01", periods=100, freq="D")
    rng = np.random.default_rng(7)
    returns = pd.Series(rng.normal(0, 0.01, 100), index=idx)
    result = apply_vol_targeting(
        returns, target_vol=0.15, lookback=25,
        method="rolling", max_leverage=2.0,
    )
    assert len(result) == 100
    # First lookback bars cannot compute a rolling std → scalar NaN → product NaN
    # Later bars should produce finite values
    assert result.iloc[50:].notna().all()
