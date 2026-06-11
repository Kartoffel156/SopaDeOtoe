"""
run_goal_meta_features_params.py — Tune internal parameters of meta-features
(windows, Kronos hyperparams) across all graduated strategies.

Goal: goal-meta-features-params.md
Runs: 16 strategies x 10 variations = 160

Usage:
    cd Patacon/
    python -m SopaDeOtoe.launchers.run_goal_meta_features_params [--n-jobs 10]
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
_DEFAULT_OUT = _SOPA_DIR / "results" / "goal_meta_features_params"

_ALL_EXPERIMENTAL = [
    "variance_ratio_5", "variance_ratio_20", "vol_accel",
    "autocorr_momentum", "kyle_entropy_ratio",
]

# Shared Kronos + experimental base for all variations
_KRONOS_EXP_BASE = {
    "v2.features.meta_features.kronos_features.enabled": True,
    "v2.features.meta_features.enabled_experimental_features": _ALL_EXPERIMENTAL,
    "v2.feature_prefilter.enabled": False,
}

VARIATIONS = {
    "BASELINE": {
        **_KRONOS_EXP_BASE,
    },
    "A_windows_short": {
        **_KRONOS_EXP_BASE,
        "v2.features.amihud_window": 30,
        "v2.features.entropy_window": 30,
        "v2.features.kyle_lambda_window": 30,
        "v2.meta_rel_vol_window": 30,
        "v2.meta_vol_regime_fast": 10,
        "v2.meta_vol_regime_slow": 40,
        "v2.features.meta_features.roll_spread_window": 30,
        "v2.features.meta_features.parkinson_vol_window": 10,
        "v2.features.meta_features.rolling_d_star_window": 25,
    },
    "B_windows_long": {
        **_KRONOS_EXP_BASE,
        "v2.features.amihud_window": 80,
        "v2.features.entropy_window": 80,
        "v2.features.kyle_lambda_window": 80,
        "v2.meta_rel_vol_window": 80,
        "v2.meta_vol_regime_fast": 30,
        "v2.meta_vol_regime_slow": 100,
        "v2.features.meta_features.roll_spread_window": 80,
        "v2.features.meta_features.parkinson_vol_window": 30,
        "v2.features.meta_features.rolling_d_star_window": 60,
    },
    "C_kronos_lookback_long": {
        **_KRONOS_EXP_BASE,
        "v2.features.meta_features.kronos_features.lookback": 100,
        "v2.features.meta_features.kronos_features.sample_count": 10,
    },
    "D_kronos_lookback_short_more_paths": {
        **_KRONOS_EXP_BASE,
        "v2.features.meta_features.kronos_features.lookback": 30,
        "v2.features.meta_features.kronos_features.sample_count": 20,
    },
    "E_kronos_temp_low": {
        **_KRONOS_EXP_BASE,
        "v2.features.meta_features.kronos_features.temperature": 0.5,
        "v2.features.meta_features.kronos_features.top_p": 0.8,
        "v2.features.meta_features.kronos_features.sample_count": 10,
    },
    "F_kronos_temp_high": {
        **_KRONOS_EXP_BASE,
        "v2.features.meta_features.kronos_features.temperature": 1.5,
        "v2.features.meta_features.kronos_features.top_p": 0.95,
        "v2.features.meta_features.kronos_features.sample_count": 10,
    },
    "G_kronos_stride3": {
        **_KRONOS_EXP_BASE,
        "v2.features.meta_features.kronos_features.stride": 3,
        "v2.features.meta_features.kronos_features.sample_count": 10,
    },
    "H_vol_regime_asymmetric": {
        **_KRONOS_EXP_BASE,
        "v2.meta_vol_regime_fast": 10,
        "v2.meta_vol_regime_slow": 80,
    },
    "I_entropy_high_granularity": {
        **_KRONOS_EXP_BASE,
        "v2.features.entropy_bins": 20,
        "v2.features.entropy_window": 80,
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
            cid = f"{strat_name}_prm{var_name}_{ts}"
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
                     "total_return", "sharpe", "max_drawdown", "n_trades", "win_rate", "status"])
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        for m, r in zip(meta, results):
            metrics = r.get("metrics", {})
            w.writerow([
                now, m["config_id"], m["strategy"], m["variation"],
                metrics.get("cum_return", ""), metrics.get("sharpe", ""),
                metrics.get("max_drawdown", ""), metrics.get("n_trades", ""),
                metrics.get("win_rate", ""),
                r.get("status", "error"),
            ])
    return csv_path


def main():
    ap = argparse.ArgumentParser(description="Meta-features parameter tuning sweep")
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
    print(f"\n{'Strategy':<50} " + " ".join(f"{v:>30}" for v in var_names))
    print("-" * (50 + 31 * len(var_names)))
    idx = 0
    for strat_name, _ in strategies:
        row = f"{strat_name:<50} "
        for _ in var_names:
            r = results[idx]
            s = r.get("metrics", {}).get("sharpe", None)
            row += f"{s:+29.3f}  " if s is not None else "                          ERR  "
            idx += 1
        print(row)

    summary = {m["config_id"]: {"meta": m, "metrics": r.get("metrics", {}), "status": r.get("status")}
               for m, r in zip(meta, results)}
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"[GOAL] Done. {sum(1 for r in results if r.get('status') == 'success')}/{len(results)} success")


if __name__ == "__main__":
    main()
