import pytest
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from portfolio.portfolio_plots import (
    plot_combined_equity, plot_correlation_heatmap,
    plot_weight_evolution, plot_drawdown,
    plot_risk_attribution, plot_rolling_sharpe,
)


def _make_returns(n=200, seed=42):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.Series(rng.normal(0.0003, 0.01, n), index=idx)


def _make_returns_df(n=200, seed=42):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "A": rng.normal(0.0003, 0.01, n),
        "B": rng.normal(0.0001, 0.015, n),
        "C": rng.normal(0.0002, 0.008, n),
    }, index=idx)


def test_plot_combined_equity():
    r = _make_returns()
    fig = plot_combined_equity(r)
    assert isinstance(fig, plt.Figure)
    plt.close(fig)


def test_plot_combined_equity_with_strategies():
    r = _make_returns()
    df = _make_returns_df()
    fig = plot_combined_equity(r, strategy_returns_df=df)
    assert isinstance(fig, plt.Figure)
    plt.close(fig)


def test_plot_combined_equity_save(tmp_path):
    r = _make_returns()
    path = tmp_path / "equity.png"
    fig = plot_combined_equity(r, save_path=path)
    assert path.exists()
    plt.close(fig)


def test_plot_correlation_heatmap():
    corr = pd.DataFrame(
        [[1.0, 0.3, -0.1], [0.3, 1.0, 0.5], [-0.1, 0.5, 1.0]],
        index=["A", "B", "C"], columns=["A", "B", "C"],
    )
    fig = plot_correlation_heatmap(corr)
    assert isinstance(fig, plt.Figure)
    plt.close(fig)


def test_plot_weight_evolution():
    idx = pd.date_range("2023-01-01", periods=100, freq="D")
    weights = pd.DataFrame({
        "A": np.linspace(0.4, 0.3, 100),
        "B": np.linspace(0.35, 0.4, 100),
        "C": np.linspace(0.25, 0.3, 100),
    }, index=idx)
    fig = plot_weight_evolution(weights)
    assert isinstance(fig, plt.Figure)
    plt.close(fig)


def test_plot_drawdown():
    r = _make_returns()
    fig = plot_drawdown(r)
    assert isinstance(fig, plt.Figure)
    plt.close(fig)


def test_plot_risk_attribution():
    ra = pd.DataFrame({
        "strategy": ["A", "B", "C"],
        "weight": [0.4, 0.35, 0.25],
        "risk_contribution_pct": [0.38, 0.37, 0.25],
    })
    fig = plot_risk_attribution(ra)
    assert isinstance(fig, plt.Figure)
    plt.close(fig)


def test_plot_rolling_sharpe():
    r = _make_returns(n=200)
    rs = r.rolling(63).mean() / r.rolling(63).std() * np.sqrt(252)
    fig = plot_rolling_sharpe(rs)
    assert isinstance(fig, plt.Figure)
    plt.close(fig)


def test_plot_correlation_heatmap_save(tmp_path):
    corr = pd.DataFrame(
        [[1.0, 0.3], [0.3, 1.0]], index=["A", "B"], columns=["A", "B"],
    )
    path = tmp_path / "heatmap.png"
    fig = plot_correlation_heatmap(corr, save_path=path)
    assert path.exists()
    plt.close(fig)


def test_plot_weight_evolution_save(tmp_path):
    idx = pd.date_range("2023-01-01", periods=20, freq="D")
    weights = pd.DataFrame({
        "A": np.linspace(0.5, 0.4, 20),
        "B": np.linspace(0.5, 0.6, 20),
    }, index=idx)
    path = tmp_path / "weights.png"
    fig = plot_weight_evolution(weights, save_path=path)
    assert path.exists()
    plt.close(fig)


def test_plot_drawdown_save(tmp_path):
    r = _make_returns(n=100)
    path = tmp_path / "dd.png"
    fig = plot_drawdown(r, save_path=path)
    assert path.exists()
    plt.close(fig)


def test_plot_risk_attribution_save(tmp_path):
    ra = pd.DataFrame({
        "strategy": ["A", "B"],
        "weight": [0.5, 0.5],
        "risk_contribution_pct": [0.5, 0.5],
    })
    path = tmp_path / "risk.png"
    fig = plot_risk_attribution(ra, save_path=path)
    assert path.exists()
    plt.close(fig)


def test_plot_rolling_sharpe_save(tmp_path):
    r = _make_returns(n=200)
    rs = r.rolling(63).mean() / r.rolling(63).std() * np.sqrt(252)
    path = tmp_path / "rolling.png"
    fig = plot_rolling_sharpe(rs, save_path=path)
    assert path.exists()
    plt.close(fig)
