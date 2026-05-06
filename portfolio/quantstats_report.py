"""
portfolio/quantstats_report.py
Genera tearsheet HTML y métricas clave via quantstats.
"""
import quantstats as qs
import pandas as pd
from typing import Optional


def generate_tearsheet(
    returns: pd.Series,
    benchmark: Optional[pd.Series] = None,
    rf: float = 0.0,
    output_path: Optional[str] = None,
) -> dict:
    """
    Genera tearsheet HTML y métricas clave.

    Args:
        returns: daily returns of the portfolio (index = dates)
        benchmark: optional benchmark returns for comparison
        rf: risk-free rate (annual, default 0.0)
        output_path: if provided, saves HTML to this path

    Returns:
        dict con métricas clave y path al HTML
    """
    qs.extend_pandas()

    # Normalize timezone-aware indices
    if hasattr(returns.index, "tz") and returns.index.tz is not None:
        returns = returns.copy()
        returns.index = returns.index.tz_localize(None)

    if benchmark is not None:
        if hasattr(benchmark.index, "tz") and benchmark.index.tz is not None:
            benchmark = benchmark.copy()
            benchmark.index = benchmark.index.tz_localize(None)

    metrics = {
        "sharpe": round(float(qs.stats.sharpe(returns, rf=rf)), 4),
        "sortino": round(float(qs.stats.sortino(returns, rf=rf)), 4),
        "calmar": round(float(qs.stats.calmar(returns)), 4),
        "max_drawdown": round(float(qs.stats.max_drawdown(returns)), 4),
        "win_rate": round(float(qs.stats.win_rate(returns)), 4),
        "avg_win": round(float(qs.stats.avg_win(returns)), 4),
        "avg_loss": round(float(qs.stats.avg_loss(returns)), 4),
        "profit_factor": round(float(qs.stats.profit_factor(returns)), 4),
        "skew": round(float(qs.stats.skew(returns)), 4),
        "kurtosis": round(float(qs.stats.kurtosis(returns)), 4),
        "tail_ratio": round(float(qs.stats.tail_ratio(returns)), 4),
        "cum_returns": round(float(qs.stats.comp(returns)), 4),
        "annual_volatility": round(float(qs.stats.volatility(returns)), 4),
        "best_day": round(float(qs.stats.best(returns)), 6),
        "worst_day": round(float(qs.stats.worst(returns)), 6),
        "value_at_risk": round(float(qs.stats.value_at_risk(returns)), 4),
        "conditional_value_at_risk": round(float(qs.stats.conditional_value_at_risk(returns)), 4),
        "cvar": round(float(qs.stats.cvar(returns)), 4),
        "omega": round(float(qs.stats.omega(returns, rf=rf)), 4),
        "ror": round(float(qs.stats.ror(returns)), 4),  # rate of return
        "n_days": int(len(returns)),
    }

    html = qs.reports.html(
        returns=returns,
        benchmark=benchmark,
        rf=rf,
        output=output_path,
        title="SopaDeOtoe Portfolio Tearsheet",
    )

    return {**metrics, "html_path": output_path}
