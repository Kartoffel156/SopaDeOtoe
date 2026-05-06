#!/usr/bin/env python3
"""
portfolio/quantstats_script.py

Lee el último results/portfolio/*.json, construye returns diarios del portfolio,
genera el tearsheet HTML via quantstats y escribe metrics.json.

Uso:
    python3 portfolio/quantstats_script.py \
        --output /path/to/portfolio_tearsheet.html \
        --metrics-output /path/to/metrics.json
"""
import argparse
import json
import os
import sys
from glob import glob
from pathlib import Path

import pandas as pd

# Ensure SopaDeOtoe is on path
_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(_ROOT))

from portfolio.quantstats_report import generate_tearsheet

PORTFOLIO_DIR = _ROOT / "results" / "portfolio"
STRATEGY_MAP = {
    "HypothesisH236MomentumReversalAsym_f7c925d4": "HypothesisH236MomentumReversalAsym_021821",
    "TSIMeanReversion_11c86993": "TSIMeanReversion_095404",
    "HypothesisH110BollingerKyleGate_bc9371eb": "HypothesisH110BollingerKyleGate_160334",
    "HypothesisH203VolExpansionEntry_6edcbb5c": "HypothesisH203VolExpansionEntry_012006",
    "HypothesisH167BollingerRangingOFIGate_a40f8e2c": "HypothesisH167BollingerRangingOFIGate_162324",
    "HypothesisH318TrendlineChannelSqueeze_19e38d5f": "HypothesisH318TrendlineChannelSqueeze_051527",
    "HypothesisH37DynamicGridInformedGate_4b2e513b": "HypothesisH37DynamicGridInformedGate_051820",
    "DualMovingAverageCrossover_767ba598": "DualMovingAverageCrossover_162631",
    "MultiTimeframeTrendSignal_e5ce17eb": "MultiTimeframeTrendSignal_134237",
}


def load_latest_portfolio():
    files = sorted(PORTFOLIO_DIR.glob("first_cohort_*.json"), reverse=True)
    if not files:
        raise FileNotFoundError("No portfolio results found")
    with open(files[0]) as f:
        return json.load(f)


def build_portfolio_returns(portfolio: dict) -> pd.Series:
    """
    Construye daily returns del portfolio desde equity curves en per_strategy_source.
    """
    weights = portfolio.get("weights", {})
    per_strategy_source = portfolio.get("per_strategy_source", [])

    strategy_equities = {}  # name -> {date: equity}

    for src in per_strategy_source:
        name = src["name"]
        if name not in weights or weights[name] == 0:
            continue
        v12_dir = Path(src["v12_run_dir"])
        results_file = v12_dir / "results.json"
        if not results_file.exists():
            continue
        with open(results_file) as f:
            data = json.load(f)

        ec = data.get("equity_curve", {})
        dates = ec.get("dates", [])
        values = ec.get("values", [])
        if not dates or not values:
            continue

        equity_by_date = {}
        for d, v in zip(dates, values):
            day = d.split("T")[0].split(" ")[0]
            equity_by_date[day] = v

        strategy_equities[name] = equity_by_date

    # Union of all dates
    all_dates = set()
    for eq in strategy_equities.values():
        all_dates.update(eq.keys())
    all_dates = sorted(all_dates)

    # Build daily returns per strategy
    strategy_returns = {}  # name -> {date: return}
    for name, eq in strategy_equities.items():
        w = weights[name]
        sorted_days = sorted(eq.keys())
        rets = {}
        prev_eq = eq.get(sorted_days[0], 1)
        for day in sorted_days:
            curr_eq = eq[day]
            ret = (curr_eq - prev_eq) / prev_eq if prev_eq != 0 else 0
            rets[day] = w * ret
            prev_eq = curr_eq
        strategy_returns[name] = rets

    # Sum weighted returns per day
    portfolio_rets = {}
    for day in all_dates:
        total = 0.0
        for name, rets in strategy_returns.items():
            total += rets.get(day, 0.0)
        portfolio_rets[day] = total

    dates = sorted(portfolio_rets.keys())
    values = [portfolio_rets[d] for d in dates]
    idx = pd.DatetimeIndex(pd.to_datetime(dates))
    return pd.Series(values, index=idx, name="portfolio_return")


def build_benchmark_returns() -> pd.Series:
    """
    Construye benchmark BTC buy&hold desde BTCUSDT_daily_bars.csv (StrategyParrot v12 data).
    """
    btc_path = Path("/Users/nongo/Documents/Patacon/StrategyParrot/v12/data/BTCUSDT_daily_bars.csv")
    if not btc_path.exists():
        raise FileNotFoundError(f"BTC bars not found at {btc_path}")

    df = pd.read_csv(btc_path, index_col=0, parse_dates=True)
    df.columns = df.columns.str.lower()
    close = df["close"]
    rets = close.pct_change().dropna()
    return rets


def main():
    parser = argparse.ArgumentParser(description="Generate quantstats tearsheet for portfolio")
    parser.add_argument("--output", required=True, help="Path to output HTML file")
    parser.add_argument("--metrics-output", required=True, help="Path to output metrics JSON")
    args = parser.parse_args()

    portfolio = load_latest_portfolio()
    returns = build_portfolio_returns(portfolio)

    # Build benchmark (BTC B&H)
    try:
        benchmark = build_benchmark_returns()
    except FileNotFoundError:
        benchmark = None

    result = generate_tearsheet(
        returns=returns,
        benchmark=benchmark,
        rf=0.0,
        output_path=args.output,
    )

    # Write metrics JSON (exclude html_path, keep only scalar metrics)
    metrics_out = {k: v for k, v in result.items() if k != "html_path"}
    with open(args.metrics_output, "w") as f:
        json.dump(metrics_out, f, indent=2)

    print(f"Done. HTML: {args.output} ({os.path.getsize(args.output) / 1024:.1f} KB)")
    print(f"Metrics: {args.metrics_output}")


if __name__ == "__main__":
    main()
