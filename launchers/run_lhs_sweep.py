"""
run_lhs_sweep.py — Latin Hypercube Sampling para las 3 estrategias
que no reproducen: H236, H203, H37.

Usa los graduated configs como base (misma infra) y solo varía
strategy.params via LHS. Reporta Sharpe/trades/MDD de cada sample.

Uso:
    cd Patacon/
    python -m SopaDeOtoe.launchers.run_lhs_sweep \
        [--n-samples 20] [--n-jobs 4] [--output-dir results/lhs_sweep]
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
_DEFAULT_OUT = _SOPA_DIR / "results" / "lhs_sweep"

# ── Parameter spaces per strategy ──────────────────────────────────
# Each entry: (param_name, low, high, type)
#   type = "float" or "int"

SWEEP_DEFS = {
    "HypothesisH236MomentumReversalAsym": {
        "config_file": "HypothesisH236MomentumReversalAsym_20260411_021821.yaml",
        "params": [
            ("dn_thresh", 0.005, 0.060, "float"),
            ("up_thresh", 0.005, 0.060, "float"),
        ],
    },
    "HypothesisH203VolExpansionEntry": {
        "config_file": "HypothesisH203VolExpansionEntry_20260418_012006.yaml",
        "params": [
            ("ofi_window", 1, 10, "int"),
        ],
    },
    "HypothesisH37DynamicGridInformedGate": {
        "config_file": "HypothesisH37DynamicGridInformedGate_20260419_051820.yaml",
        "params": [
            ("grid_period",        10,   40,  "int"),
            ("grid_mult",          0.8,  2.5, "float"),
            ("atr_period",         10,   30,  "int"),
            ("vpin_pct_thresh",    0.25, 0.70, "float"),
            ("ofi_neutral_thresh", 0.05, 0.30, "float"),
            ("mk_no_trend",       0.5,  2.5,  "float"),
        ],
    },
}


def _lhs_samples(n_samples: int, param_defs: list, seed: int = 42) -> list[dict]:
    """Generate n_samples param dicts via Latin Hypercube Sampling."""
    try:
        from scipy.stats.qmc import LatinHypercube
        sampler = LatinHypercube(d=len(param_defs), seed=seed)
        raw = sampler.random(n=n_samples)  # (n_samples, d) in [0, 1]
    except ImportError:
        # Fallback: stratified random without scipy
        rng = np.random.default_rng(seed)
        d = len(param_defs)
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


def _build_configs(strategy: str, defn: dict, n_samples: int, seed: int) -> list[dict]:
    """Build n_samples configs from base graduated YAML + LHS params."""
    base_path = _GRADUATED_DIR / defn["config_file"]
    base_cfg = yaml.safe_load(base_path.read_text())

    param_samples = _lhs_samples(n_samples, defn["params"], seed=seed)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    configs = []
    for i, params in enumerate(param_samples):
        cfg = copy.deepcopy(base_cfg)
        cfg["strategy"]["params"] = params
        suffix = "_".join(f"{k}={v}" for k, v in params.items())
        cfg["config_id"] = f"{strategy}_LHS{i:03d}_{ts}"
        cfg["_meta_strategy_class"] = strategy
        # Disable heavy montecarlo to speed up sweep
        cfg["montecarlo"]["bootstrap"]["enabled"] = False
        cfg["montecarlo"]["reality_check"]["enabled"] = False
        cfg["montecarlo"]["stress"]["enabled"] = False
        # Keep reshuffling for basic p-value
        cfg["montecarlo"]["reshuffling"]["enabled"] = True
        cfg["montecarlo"]["reshuffling"]["n_permutations"] = 100
        configs.append(cfg)
    return configs, param_samples


def _print_results(strategy: str, param_samples: list[dict], results: list[dict]):
    """Print sorted results table."""
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

    print(f"\n{'='*80}")
    print(f"  LHS SWEEP RESULTS — {strategy}")
    print(f"  {len(rows)} successful / {len(param_samples)} total samples")
    print(f"{'='*80}")
    print(f"  {'Rank':>4}  {'Sharpe':>8}  {'Trades':>7}  {'MaxDD':>8}  {'PF':>6}  {'Return':>8}  Params")
    print(f"  {'─'*4}  {'─'*8}  {'─'*7}  {'─'*8}  {'─'*6}  {'─'*8}  {'─'*30}")

    for i, r in enumerate(rows[:20]):  # top 20
        p_str = ", ".join(f"{k}={v}" for k, v in r["params"].items())
        print(
            f"  {i+1:>4}  {r['sharpe']:>+8.4f}  {r['n_trades']:>7}  "
            f"{r['max_dd']:>+8.4f}  {r['profit_factor']:>6.3f}  "
            f"{r['cum_return']:>+8.4f}  {p_str}"
        )

    if rows:
        best = rows[0]
        print(f"\n  BEST: Sharpe={best['sharpe']:+.4f}  trades={best['n_trades']}  "
              f"MDD={best['max_dd']:+.4f}")
        print(f"  Params: {best['params']}")
    print(f"{'='*80}\n")
    return rows


def main():
    ap = argparse.ArgumentParser(description="LHS parameter sweep for non-reproducing strategies")
    ap.add_argument("--n-samples", type=int, default=20,
                    help="Number of LHS samples per strategy (default: 20)")
    ap.add_argument("--n-jobs", type=int, default=4,
                    help="Parallel workers (default: 4)")
    ap.add_argument("--output-dir", type=Path, default=_DEFAULT_OUT,
                    help="Output directory for result JSONs")
    ap.add_argument("--seed", type=int, default=42,
                    help="Random seed for LHS (default: 42)")
    ap.add_argument("--strategy", type=str, default=None,
                    choices=list(SWEEP_DEFS.keys()),
                    help="Run only one strategy (default: all 3)")
    args = ap.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    strategies = [args.strategy] if args.strategy else list(SWEEP_DEFS.keys())
    all_results_summary = {}

    for strat in strategies:
        defn = SWEEP_DEFS[strat]
        print(f"\n[LHS] Building {args.n_samples} configs for {strat}")
        print(f"[LHS] Params: {[p[0] for p in defn['params']]}")

        configs, param_samples = _build_configs(strat, defn, args.n_samples, args.seed)

        print(f"[LHS] Running exploration with n_jobs={args.n_jobs}")
        results = run_exploration(
            configs,
            n_jobs=args.n_jobs,
            output_dir=args.output_dir,
        )

        rows = _print_results(strat, param_samples, results)
        all_results_summary[strat] = rows

    # Save consolidated summary
    summary_path = args.output_dir / "lhs_summary.json"
    summary_path.write_text(json.dumps(all_results_summary, indent=2, default=str))
    print(f"[LHS] Summary saved to {summary_path}")


if __name__ == "__main__":
    main()
