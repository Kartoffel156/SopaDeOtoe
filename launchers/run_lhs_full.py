"""
run_lhs_full.py — LHS sweep completo para las 9 estrategias graduadas.

Corre n_samples LHS por cada estrategia usando su graduated config como
base, variando solo strategy.params. Reporta top Sharpe/trades/MDD.

Uso:
    cd Patacon/
    python -m SopaDeOtoe.launchers.run_lhs_full \
        --n-samples 60 --n-jobs 11 [--strategy X] [--seed 42]
"""

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

import SopaDeOtoe._path_setup  # noqa: F401
import SopaDeOtoe.strategies   # noqa: F401

from SopaDeOtoe.core.runner import run_exploration

_SOPA_DIR = Path(__file__).resolve().parent.parent
_GRADUATED_DIR = _SOPA_DIR / "configs" / "graduated"
_DEFAULT_OUT = _SOPA_DIR / "results" / "lhs_full"

# ── Parameter spaces: (name, low, high, type) ─────────────────────
# Ranges centered around graduated values, widened ~2-3x for exploration.

SWEEP_DEFS = {
    "HypothesisH236MomentumReversalAsym": {
        "config_file": "HypothesisH236MomentumReversalAsym_20260411_021821.yaml",
        "params": [
            ("dn_thresh",  0.003,  0.080, "float"),
            ("up_thresh",  0.003,  0.080, "float"),
        ],
    },
    "TSIMeanReversion": {
        "config_file": "TSIMeanReversion_20260419_095451.yaml",
        "params": [
            ("tsi_r",           2,    12, "int"),
            ("tsi_s",           2,     8, "int"),
            ("tsi_oversold",  -40,    -5, "int"),
            ("tsi_overbought",  5,    40, "int"),
            ("rsi_period",      4,    18, "int"),
            ("rsi_oversold",   15,    45, "int"),
            ("rsi_overbought", 55,    80, "int"),
        ],
    },
    "HypothesisH110BollingerKyleGate": {
        "config_file": "HypothesisH110BollingerKyleGate_20260418_160334.yaml",
        "params": [
            ("bb_period",     10,    40, "int"),
            ("bb_std",       1.5,   3.5, "float"),
            ("bw_percentile", 30,    85, "int"),
            ("lam_thresh",   0.2,   0.9, "float"),
            ("lookback",      15,    60, "int"),
        ],
    },
    "HypothesisH203VolExpansionEntry": {
        "config_file": "HypothesisH203VolExpansionEntry_20260418_012006.yaml",
        "params": [
            ("ofi_window", 1, 12, "int"),
        ],
    },
    "HypothesisH167BollingerRangingOFIGate": {
        "config_file": "HypothesisH167BollingerRangingOFIGate_20260418_162324.yaml",
        "params": [
            ("bb_period",   10,    40, "int"),
            ("bb_std",     1.5,   3.5, "float"),
            ("bw_pct",      15,    70, "int"),
            ("ofi_thresh", 0.05,  0.5, "float"),
            ("ofi_window",   2,    15, "int"),
        ],
    },
    "HypothesisH318TrendlineChannelSqueeze": {
        "config_file": "HypothesisH318TrendlineChannelSqueeze_20260419_051527.yaml",
        "params": [
            ("tl_channel_width", 0.3, 2.5, "float"),
        ],
    },
    "HypothesisH37DynamicGridInformedGate": {
        "config_file": "HypothesisH37DynamicGridInformedGate_20260419_051820.yaml",
        "params": [
            ("grid_period",        10,   40,  "int"),
            ("grid_mult",          0.6,  2.8, "float"),
            ("atr_period",          8,   30,  "int"),
            ("vpin_pct_thresh",    0.20, 0.75, "float"),
            ("ofi_neutral_thresh", 0.04, 0.35, "float"),
            ("mk_no_trend",       0.3,  2.8,  "float"),
        ],
    },
    "DualMovingAverageCrossover": {
        "config_file": "DualMovingAverageCrossover_20260418_162631.yaml",
        "params": [
            ("short_period",  3,   20, "int"),
            ("long_period",  25,  100, "int"),
        ],
    },
    "MultiTimeframeTrendSignal": {
        "config_file": "MultiTimeframeTrendSignal_20260419_134237.yaml",
        "params": [
            ("short_window",  10,   50, "int"),
            ("mid_window",    30,  100, "int"),
            ("long_window",  100,  400, "int"),
            ("vol_window",    20,  120, "int"),
        ],
    },
}


def _lhs_samples(n_samples: int, param_defs: list, seed: int = 42) -> list[dict]:
    """Generate n_samples param dicts via Latin Hypercube Sampling."""
    d = len(param_defs)
    if d == 0:
        return [{}] * n_samples

    try:
        from scipy.stats.qmc import LatinHypercube
        sampler = LatinHypercube(d=d, seed=seed)
        raw = sampler.random(n=n_samples)
    except ImportError:
        rng = np.random.default_rng(seed)
        raw = np.zeros((n_samples, d))
        for j in range(d):
            cuts = np.linspace(0, 1, n_samples + 1)
            for i in range(n_samples):
                raw[i, j] = rng.uniform(cuts[i], cuts[i + 1])
            rng.shuffle(raw[:, j])

    samples = []
    for row in raw:
        params = {}
        for val, (name, lo, hi, ptype) in zip(row, param_defs):
            scaled = lo + val * (hi - lo)
            if ptype == "int":
                scaled = int(round(scaled))
            else:
                scaled = round(float(scaled), 4)
            params[name] = scaled
        samples.append(params)
    return samples


def _build_configs(strategy: str, defn: dict, n_samples: int, seed: int) -> tuple:
    """Build n_samples configs from base graduated YAML + LHS params."""
    base_path = _GRADUATED_DIR / defn["config_file"]
    base_cfg = yaml.safe_load(base_path.read_text())

    param_samples = _lhs_samples(n_samples, defn["params"], seed=seed)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    configs = []
    for i, params in enumerate(param_samples):
        cfg = copy.deepcopy(base_cfg)
        cfg["strategy"]["params"] = params
        cfg["config_id"] = f"{strategy}_LHS{i:03d}_{ts}"
        cfg["_meta_strategy_class"] = strategy
        # Disable heavy montecarlo to speed up sweep
        mc = cfg.get("montecarlo", {})
        if mc:
            mc.setdefault("bootstrap", {})["enabled"] = False
            mc.setdefault("reality_check", {})["enabled"] = False
            mc.setdefault("stress", {})["enabled"] = False
            mc.setdefault("reshuffling", {})["enabled"] = True
            mc["reshuffling"]["n_permutations"] = 100
        configs.append(cfg)
    return configs, param_samples


def _print_results(strategy: str, param_samples: list[dict], results: list[dict]):
    """Print sorted results table and return rows."""
    rows = []
    for params, res in zip(param_samples, results):
        if res.get("status") != "success":
            continue
        m = res.get("metrics", {})
        rows.append({
            "params": params,
            "sharpe": float(m.get("sharpe", 0)),
            "n_trades": int(m.get("n_trades", 0)),
            "max_dd": float(m.get("max_drawdown", 0)),
            "profit_factor": float(m.get("profit_factor", 0)),
            "cum_return": float(m.get("cum_return", m.get("total_return", 0))),
        })

    rows.sort(key=lambda r: r["sharpe"], reverse=True)
    n_positive = sum(1 for r in rows if r["sharpe"] > 0)

    print(f"\n{'='*100}")
    print(f"  LHS SWEEP — {strategy}")
    print(f"  {len(rows)} successful / {len(param_samples)} samples | "
          f"{n_positive} positive Sharpe ({100*n_positive/max(len(rows),1):.0f}%)")
    print(f"{'='*100}")
    print(f"  {'Rank':>4}  {'Sharpe':>8}  {'Trades':>7}  {'MaxDD':>8}  "
          f"{'PF':>6}  {'Return':>8}  Params")
    print(f"  {'─'*4}  {'─'*8}  {'─'*7}  {'─'*8}  {'─'*6}  {'─'*8}  {'─'*40}")

    for i, r in enumerate(rows[:15]):
        p_str = ", ".join(f"{k}={v}" for k, v in r["params"].items())
        print(
            f"  {i+1:>4}  {r['sharpe']:>+8.4f}  {r['n_trades']:>7}  "
            f"{r['max_dd']:>+8.4f}  {r['profit_factor']:>6.3f}  "
            f"{r['cum_return']:>+8.4f}  {p_str}"
        )
    if len(rows) > 15:
        print(f"  ... ({len(rows) - 15} more rows)")

    if rows:
        best = rows[0]
        print(f"\n  BEST: Sharpe={best['sharpe']:+.4f}  trades={best['n_trades']}  "
              f"MDD={best['max_dd']:+.4f}  PF={best['profit_factor']:.3f}")
        print(f"  Params: {best['params']}")
    print(f"{'='*100}\n")
    return rows


def _print_global_summary(all_results: dict):
    """Print a final cross-strategy leaderboard."""
    print(f"\n{'#'*100}")
    print(f"  GLOBAL LEADERBOARD — Best config per strategy")
    print(f"{'#'*100}")
    print(f"  {'Strategy':<45} {'Sharpe':>8} {'Trades':>7} {'MaxDD':>8} "
          f"{'PF':>6} {'%Pos':>5} {'Return':>8}")
    print(f"  {'─'*45} {'─'*8} {'─'*7} {'─'*8} {'─'*6} {'─'*5} {'─'*8}")

    leaderboard = []
    for strat, rows in all_results.items():
        if not rows:
            continue
        best = rows[0]
        n_pos = sum(1 for r in rows if r["sharpe"] > 0)
        pct_pos = 100 * n_pos / len(rows)
        leaderboard.append((strat, best, pct_pos, len(rows)))

    leaderboard.sort(key=lambda x: x[1]["sharpe"], reverse=True)

    for strat, best, pct_pos, n_total in leaderboard:
        print(
            f"  {strat:<45} {best['sharpe']:>+8.4f} {best['n_trades']:>7} "
            f"{best['max_dd']:>+8.4f} {best['profit_factor']:>6.3f} "
            f"{pct_pos:>4.0f}% {best['cum_return']:>+8.4f}"
        )

    print(f"{'#'*100}\n")


def main():
    ap = argparse.ArgumentParser(
        description="LHS parameter sweep for ALL graduated strategies")
    ap.add_argument("--n-samples", type=int, default=60,
                    help="LHS samples per strategy (default: 60)")
    ap.add_argument("--n-jobs", type=int, default=11,
                    help="Parallel workers (default: 11)")
    ap.add_argument("--output-dir", type=Path, default=_DEFAULT_OUT,
                    help="Output directory for result JSONs")
    ap.add_argument("--seed", type=int, default=42,
                    help="Random seed for LHS (default: 42)")
    ap.add_argument("--strategy", type=str, default=None,
                    choices=list(SWEEP_DEFS.keys()),
                    help="Run only one strategy (default: all 9)")
    args = ap.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    strategies = [args.strategy] if args.strategy else list(SWEEP_DEFS.keys())
    all_results = {}

    total_configs = len(strategies) * args.n_samples
    print(f"\n[LHS-FULL] {len(strategies)} strategies x {args.n_samples} samples = "
          f"{total_configs} total configs")
    print(f"[LHS-FULL] Workers: {args.n_jobs} | Output: {args.output_dir}\n")

    for idx, strat in enumerate(strategies, 1):
        defn = SWEEP_DEFS[strat]
        n_params = len(defn["params"])
        print(f"\n[{idx}/{len(strategies)}] {strat} — {n_params} params, "
              f"{args.n_samples} samples")
        print(f"  Params: {[p[0] for p in defn['params']]}")

        configs, param_samples = _build_configs(
            strat, defn, args.n_samples, args.seed)

        results = run_exploration(
            configs,
            n_jobs=args.n_jobs,
            output_dir=args.output_dir,
        )

        rows = _print_results(strat, param_samples, results)
        all_results[strat] = rows

    # Global leaderboard
    _print_global_summary(all_results)

    # Save consolidated summary
    summary_path = args.output_dir / "lhs_full_summary.json"
    summary_path.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"[LHS-FULL] Summary saved to {summary_path}")


if __name__ == "__main__":
    main()
