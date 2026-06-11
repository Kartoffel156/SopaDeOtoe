"""
run_goal_meta_threshold_sweep.py — Sweep v2.meta_threshold [0.40..0.75]
across all 16 graduated strategies.

Goal: goal-meta-threshold-sweep.md
Runs: 16 strategies x 8 thresholds = 128

Usage:
    cd Patacon/
    python -m SopaDeOtoe.launchers.run_goal_meta_threshold_sweep [--n-jobs 10]
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
_DEFAULT_OUT = _SOPA_DIR / "results" / "goal_meta_threshold_sweep"

THRESHOLDS = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75]


def _load_graduated_configs() -> list[tuple[str, dict]]:
    """Load graduated configs, picking the latest file per strategy name."""
    files = sorted(_GRADUATED_DIR.glob("*.yaml"))
    seen = {}
    for f in files:
        name = f.stem.rsplit("_", 2)[0]
        seen[name] = f
    result = []
    for name, path in sorted(seen.items()):
        cfg = yaml.safe_load(path.read_text())
        result.append((name, cfg))
    return result


def _build_all_configs(strategies, thresholds):
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    configs = []
    meta = []
    for strat_name, base_cfg in strategies:
        for thr in thresholds:
            cfg = copy.deepcopy(base_cfg)
            cfg["v2"]["meta_threshold"] = thr
            cid = f"{strat_name}_mt{thr:.2f}_{ts}"
            cfg["config_id"] = cid
            cfg["_meta_strategy_class"] = strat_name
            # Speed up: disable heavy MC
            cfg["montecarlo"]["bootstrap"]["enabled"] = False
            cfg["montecarlo"]["reality_check"]["enabled"] = False
            cfg["montecarlo"]["stress"]["enabled"] = False
            configs.append(cfg)
            meta.append({"strategy": strat_name, "meta_threshold": thr, "config_id": cid})
    return configs, meta


def _write_csv(results, meta, out_dir):
    csv_path = out_dir / "results_log.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["date", "config_id", "strategy", "meta_threshold",
                     "total_return", "sharpe", "max_drawdown", "n_trades", "status"])
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        for m, r in zip(meta, results):
            metrics = r.get("metrics", {})
            w.writerow([
                now, m["config_id"], m["strategy"], m["meta_threshold"],
                metrics.get("cum_return", ""), metrics.get("sharpe", ""),
                metrics.get("max_drawdown", ""), metrics.get("n_trades", ""),
                r.get("status", "error"),
            ])
    return csv_path


def main():
    ap = argparse.ArgumentParser(description="Meta-threshold sweep for all graduated strategies")
    ap.add_argument("--n-jobs", type=int, default=10)
    ap.add_argument("--output-dir", type=Path, default=_DEFAULT_OUT)
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    strategies = _load_graduated_configs()
    print(f"[GOAL] Loaded {len(strategies)} graduated strategies")
    print(f"[GOAL] Thresholds: {THRESHOLDS}")
    print(f"[GOAL] Total runs: {len(strategies) * len(THRESHOLDS)}")

    configs, meta = _build_all_configs(strategies, THRESHOLDS)
    results = run_exploration(configs, n_jobs=args.n_jobs, output_dir=args.output_dir)

    csv_path = _write_csv(results, meta, args.output_dir)
    print(f"\n[GOAL] Results log: {csv_path}")

    # Summary table: strategy x threshold -> sharpe
    print(f"\n{'Strategy':<50} " + " ".join(f"mt={t:.2f}" for t in THRESHOLDS))
    print("-" * (50 + 9 * len(THRESHOLDS)))
    idx = 0
    for strat_name, _ in strategies:
        row = f"{strat_name:<50} "
        for _ in THRESHOLDS:
            r = results[idx]
            s = r.get("metrics", {}).get("sharpe", None)
            row += f"{s:+7.3f}  " if s is not None else "  ERR    "
            idx += 1
        print(row)

    # Save summary JSON
    summary = {m["config_id"]: {"meta": m, "metrics": r.get("metrics", {}), "status": r.get("status")}
               for m, r in zip(meta, results)}
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"[GOAL] Done. {sum(1 for r in results if r.get('status') == 'success')}/{len(results)} success")


if __name__ == "__main__":
    main()
