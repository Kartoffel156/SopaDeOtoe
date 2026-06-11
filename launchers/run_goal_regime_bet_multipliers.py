"""
run_goal_regime_bet_multipliers.py — Sweep regime bet-size multipliers
across all 16 graduated strategies.

Goal: goal-regime-bet-multipliers.md
Runs: 16 strategies x 7 variations = 112

Usage:
    cd Patacon/
    python -m SopaDeOtoe.launchers.run_goal_regime_bet_multipliers [--n-jobs 10]
"""

import argparse
import copy
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

import SopaDeOtoe._path_setup  # noqa: F401
import SopaDeOtoe.strategies   # noqa: F401

from SopaDeOtoe.core.runner import run_exploration

_SOPA_DIR = Path(__file__).resolve().parent.parent
_GRADUATED_DIR = _SOPA_DIR / "configs" / "graduated"
_DEFAULT_OUT = _SOPA_DIR / "results" / "goal_regime_bet_multipliers"

VARIATIONS = {
    "A_boost_bull": {
        "regime.bet_size_multipliers": {"BULL": 1.3, "BEAR": 1.0, "CYCLIC": 1.0, "CONGESTED": 0.6},
    },
    "B_bull_cyclic": {
        "regime.bet_size_multipliers": {"BULL": 1.3, "BEAR": 0.7, "CYCLIC": 1.2, "CONGESTED": 0.5},
    },
    "C_penalize_congested": {
        "regime.bet_size_multipliers": {"BULL": 1.0, "BEAR": 1.0, "CYCLIC": 1.0, "CONGESTED": 0.4},
    },
    "D_boost_bear": {
        "regime.bet_size_multipliers": {"BULL": 0.8, "BEAR": 1.3, "CYCLIC": 1.1, "CONGESTED": 0.7},
    },
    "E_aggressive_trend": {
        "regime.bet_size_multipliers": {"BULL": 1.5, "BEAR": 1.5, "CYCLIC": 0.8, "CONGESTED": 0.3},
    },
    "F_vol_aware": {
        "regime.volatility.levels": [20, 70, 90],
        "regime.bet_size_multipliers": {"BULL": 1.2, "BEAR": 1.0, "CYCLIC": 1.0, "CONGESTED": 0.5},
    },
    "G_short_qwindow": {
        "regime.volatility.quantile_window": 120,
        "regime.bet_size_multipliers": {"BULL": 1.2, "BEAR": 1.0, "CYCLIC": 1.0, "CONGESTED": 0.6},
    },
}


def _apply_dotted(cfg, key, value):
    parts = key.split(".")
    d = cfg
    for p in parts[:-1]:
        d = d.setdefault(p, {})
    d[parts[-1]] = value


def _load_graduated_configs():
    files = sorted(_GRADUATED_DIR.glob("*.yaml"))
    seen = {}
    for f in files:
        name = f.stem.rsplit("_", 2)[0]
        seen[name] = f
    return [(name, yaml.safe_load(path.read_text())) for name, path in sorted(seen.items())]


def _build_all_configs(strategies):
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    configs, meta = [], []
    for strat_name, base_cfg in strategies:
        for var_name, overrides in VARIATIONS.items():
            cfg = copy.deepcopy(base_cfg)
            for key, val in overrides.items():
                _apply_dotted(cfg, key, val)
            cid = f"{strat_name}_reg{var_name}_{ts}"
            cfg["config_id"] = cid
            cfg["_meta_strategy_class"] = strat_name
            cfg["montecarlo"]["bootstrap"]["enabled"] = False
            cfg["montecarlo"]["reality_check"]["enabled"] = False
            cfg["montecarlo"]["stress"]["enabled"] = False
            configs.append(cfg)
            meta.append({"strategy": strat_name, "variation": var_name, "config_id": cid})
    return configs, meta


def _write_csv(results, meta, out_dir):
    csv_path = out_dir / "results_log.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["date", "config_id", "strategy", "variation",
                     "total_return", "sharpe", "max_drawdown", "n_trades", "status"])
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        for m, r in zip(meta, results):
            metrics = r.get("metrics", {})
            w.writerow([
                now, m["config_id"], m["strategy"], m["variation"],
                metrics.get("cum_return", ""), metrics.get("sharpe", ""),
                metrics.get("max_drawdown", ""), metrics.get("n_trades", ""),
                r.get("status", "error"),
            ])
    return csv_path


def main():
    ap = argparse.ArgumentParser(description="Regime bet multipliers sweep")
    ap.add_argument("--n-jobs", type=int, default=10)
    ap.add_argument("--output-dir", type=Path, default=_DEFAULT_OUT)
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    strategies = _load_graduated_configs()
    print(f"[GOAL] Loaded {len(strategies)} strategies")
    print(f"[GOAL] Variations: {list(VARIATIONS.keys())}")
    print(f"[GOAL] Total runs: {len(strategies) * len(VARIATIONS)}")

    configs, meta = _build_all_configs(strategies)
    results = run_exploration(configs, n_jobs=args.n_jobs, output_dir=args.output_dir)

    csv_path = _write_csv(results, meta, args.output_dir)
    print(f"\n[GOAL] Results log: {csv_path}")

    var_names = list(VARIATIONS.keys())
    print(f"\n{'Strategy':<50} " + " ".join(f"{v:>18}" for v in var_names))
    print("-" * (50 + 19 * len(var_names)))
    idx = 0
    for strat_name, _ in strategies:
        row = f"{strat_name:<50} "
        for _ in var_names:
            r = results[idx]
            s = r.get("metrics", {}).get("sharpe", None)
            row += f"{s:+17.3f}  " if s is not None else "              ERR  "
            idx += 1
        print(row)

    summary = {m["config_id"]: {"meta": m, "metrics": r.get("metrics", {}), "status": r.get("status")}
               for m, r in zip(meta, results)}
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"[GOAL] Done. {sum(1 for r in results if r.get('status') == 'success')}/{len(results)} success")


if __name__ == "__main__":
    main()
