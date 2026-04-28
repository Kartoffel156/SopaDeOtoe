import pytest
import numpy as np
import pandas as pd
from portfolio.covariance import estimate_covariance


def _make_returns(n=500, k=3, seed=42):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    data = rng.normal(0, 0.01, (n, k))
    return pd.DataFrame(data, index=idx, columns=[f"S{i}" for i in range(k)])


def test_shrinkage_returns_positive_definite():
    df = _make_returns()
    cov = estimate_covariance(df, method="shrinkage")
    eigenvalues = np.linalg.eigvalsh(cov)
    assert (eigenvalues > 0).all()


def test_sample_covariance_shape():
    df = _make_returns()
    cov = estimate_covariance(df, method="sample")
    assert cov.shape == (3, 3)


def test_ewma_covariance_different_from_sample():
    df = _make_returns()
    cov_sample = estimate_covariance(df, method="sample")
    cov_ewma = estimate_covariance(df, method="exponential", halflife=30)
    assert not np.allclose(cov_sample, cov_ewma)


def test_invalid_method_raises():
    df = _make_returns()
    with pytest.raises(ValueError, match="method"):
        estimate_covariance(df, method="invalid")
