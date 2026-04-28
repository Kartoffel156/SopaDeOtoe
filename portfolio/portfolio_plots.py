"""
Visualization for the combined portfolio.

Combined equity curves, correlation heatmaps, weight evolution,
drawdown charts, risk attribution.
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
from pathlib import Path


def plot_combined_equity(combined_returns: pd.Series,
                         strategy_returns_df: pd.DataFrame | None = None,
                         title: str = "Combined Portfolio Equity",
                         save_path: Path | str | None = None) -> plt.Figure:
    """
    Plot combined equity curve with optional individual strategy curves.
    """
    fig, ax = plt.subplots(figsize=(12, 6))

    combined_equity = (1 + combined_returns).cumprod()
    ax.plot(combined_equity.index, combined_equity.values,
            linewidth=2, color="black", label="Combined")

    if strategy_returns_df is not None:
        for col in strategy_returns_df.columns:
            eq = (1 + strategy_returns_df[col]).cumprod()
            ax.plot(eq.index, eq.values, linewidth=0.8, alpha=0.6, label=col)

    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("Equity")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if save_path:
        fig.savefig(str(save_path), dpi=150, bbox_inches="tight")

    return fig


def plot_correlation_heatmap(corr_matrix: pd.DataFrame,
                             title: str = "Strategy Correlation Matrix",
                             save_path: Path | str | None = None) -> plt.Figure:
    """
    Heatmap of pairwise strategy correlations.
    """
    fig, ax = plt.subplots(figsize=(8, 6))
    n = len(corr_matrix)
    im = ax.imshow(corr_matrix.values, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(corr_matrix.columns, rotation=45, ha="right")
    ax.set_yticklabels(corr_matrix.index)

    # Annotate cells
    for i in range(n):
        for j in range(n):
            ax.text(j, i, f"{corr_matrix.iloc[i, j]:.2f}",
                    ha="center", va="center", fontsize=9,
                    color="white" if abs(corr_matrix.iloc[i, j]) > 0.5 else "black")

    fig.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title(title)
    fig.tight_layout()

    if save_path:
        fig.savefig(str(save_path), dpi=150, bbox_inches="tight")

    return fig


def plot_weight_evolution(weight_history: pd.DataFrame,
                          title: str = "Strategy Weight Evolution",
                          save_path: Path | str | None = None) -> plt.Figure:
    """
    Stacked area chart of strategy weights over time.

    weight_history: DataFrame with DatetimeIndex, one column per strategy.
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.stackplot(weight_history.index, weight_history.values.T,
                 labels=weight_history.columns, alpha=0.8)
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("Weight")
    ax.set_ylim(0, 1.05)
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if save_path:
        fig.savefig(str(save_path), dpi=150, bbox_inches="tight")

    return fig


def plot_drawdown(combined_returns: pd.Series,
                  title: str = "Portfolio Drawdown",
                  save_path: Path | str | None = None) -> plt.Figure:
    """
    Drawdown chart from combined return series.
    """
    equity = (1 + combined_returns).cumprod()
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True,
                                    gridspec_kw={"height_ratios": [2, 1]})

    # Equity
    ax1.plot(equity.index, equity.values, color="black", linewidth=1.5)
    ax1.fill_between(equity.index, running_max.values, equity.values,
                     color="red", alpha=0.2)
    ax1.set_ylabel("Equity")
    ax1.set_title(title)
    ax1.grid(True, alpha=0.3)

    # Drawdown
    ax2.fill_between(dd.index, dd.values, 0, color="red", alpha=0.4)
    ax2.set_ylabel("Drawdown")
    ax2.set_xlabel("Date")
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()

    if save_path:
        fig.savefig(str(save_path), dpi=150, bbox_inches="tight")

    return fig


def plot_risk_attribution(risk_attr_df: pd.DataFrame,
                          title: str = "Risk Attribution",
                          save_path: Path | str | None = None) -> plt.Figure:
    """
    Bar chart of risk contribution per strategy.
    """
    fig, ax = plt.subplots(figsize=(8, 5))
    x = range(len(risk_attr_df))
    bars = ax.bar(x, risk_attr_df["risk_contribution_pct"].values,
                  color="steelblue", alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(risk_attr_df["strategy"].values, rotation=45, ha="right")
    ax.set_ylabel("Risk Contribution (%)")
    ax.set_title(title)
    ax.axhline(y=1.0 / len(risk_attr_df), color="red", linestyle="--",
               alpha=0.5, label="Equal contribution")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()

    if save_path:
        fig.savefig(str(save_path), dpi=150, bbox_inches="tight")

    return fig


def plot_rolling_sharpe(rolling_sr: pd.Series,
                        title: str = "Rolling Sharpe Ratio",
                        save_path: Path | str | None = None) -> plt.Figure:
    """
    Rolling Sharpe ratio with zero line for regime detection.
    """
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(rolling_sr.index, rolling_sr.values, color="steelblue", linewidth=1)
    ax.axhline(y=0, color="red", linestyle="--", alpha=0.5)
    ax.fill_between(rolling_sr.index, rolling_sr.values, 0,
                    where=rolling_sr.values > 0, color="green", alpha=0.1)
    ax.fill_between(rolling_sr.index, rolling_sr.values, 0,
                    where=rolling_sr.values < 0, color="red", alpha=0.1)
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("Sharpe Ratio")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if save_path:
        fig.savefig(str(save_path), dpi=150, bbox_inches="tight")

    return fig
