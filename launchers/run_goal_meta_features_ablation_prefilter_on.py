"""
run_goal_meta_features_ablation_prefilter_on.py — Same 11 meta-feature combinations
as the ablation study, but WITH prefilter ON (threshold=0.01) for all variations.

Goal: same question — which combinations ON/OFF maximize return?
but now the noise-filtration of MI prefilter is active in all runs,
giving us a cleaner signal about what actually helps.

Changes vs run_goal_meta_features_ablation.py:
  - ALL variations set v2.feature_prefilter.enabled: True
  - variation B,C,D,E,F,G,I keep prefilter ON (they had it OFF before)
  - variation A is now ON (previously OFF)
  - variation J and H already had prefilter ON (unchanged)
  - So effectively: prefilter ON everywhere, only feature set changes

Usage:
    cd /Users/nongo/Documents/Patacon
    python -m SopaDeOtoe.launchers.run_goal_meta_features_ablation_prefilter_on [--n-jobs 10]
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
_DEFAULT_OUT = _SOPA_DIR / "results" / "goal_meta_features_ablation_prefilter_on"

_ALL_EXPERIMENTAL = [
    "variance_ratio_5", "variance_ratio_20", "vol_accel",
    "autocorr_momentum", "kyle_entropy_ratio",
]

# Same 11 variations as ablation, but prefilter is ON for all
VARIATIONS = {
    "BASELINE_pfON": {
        # No experimental, no Kronos — WITH prefilter ON (this is the key difference
        # vs ablation's BASELINE which had prefilter OFF)
        "v2.feature_prefilter.enabled": True,
        "v2.feature_prefilter.threshold": 0.01,
        "v2.feature_prefilter.min_features": 2,
    },
    "A_kronos_only_pfON": {
        "v2.features.meta_features.kronos_features.enabled": True,
        "v2.feature_prefilter.enabled": True,
        "v2.feature_prefilter.threshold": 0.01,
        "v2.feature_prefilter.min_features": 2,
    },
    "B_experimental_only_pfON": {
        "v2.features.meta_features.enabled_experimental_features": _ALL_EXPERIMENTAL,
        "v2.feature_prefilter.enabled": True,
        "v2.feature_prefilter.threshold": 0.01,
        "v2.feature_prefilter.min_features": 2,
    },
    "C_kronos_plus_experimental_pfON": {
        "v2.features.meta_features.kronos_features.enabled": True,
        "v2.features.meta_features.enabled_experimental_features": _ALL_EXPERIMENTAL,
        "v2.feature_prefilter.enabled": True,
        "v2.feature_prefilter.threshold": 0.01,
        "v2.feature_prefilter.min_features": 2,
    },
    "D_kronos_plus_vr_pfON": {
        "v2.features.meta_features.kronos_features.enabled": True,
        "v2.features.meta_features.enabled_experimental_features": ["variance_ratio_5", "variance_ratio_20"],
        "v2.feature_prefilter.enabled": True,
        "v2.feature_prefilter.threshold": 0.01,
        "v2.feature_prefilter.min_features": 2,
    },
    "E_kronos_plus_kyle_pfON": {
        "v2.features.meta_features.kronos_features.enabled": True,
        "v2.features.meta_features.enabled_experimental_features": ["kyle_entropy_ratio"],
        "v2.feature_prefilter.enabled": True,
        "v2.feature_prefilter.threshold": 0.01,
        "v2.feature_prefilter.min_features": 2,
    },
    "F_kronos_plus_volaccel_pfON": {
        "v2.features.meta_features.kronos_features.enabled": True,
        "v2.features.meta_features.enabled_experimental_features": ["vol_accel"],
        "v2.feature_prefilter.enabled": True,
        "v2.feature_prefilter.threshold": 0.01,
        "v2.feature_prefilter.min_features": 2,
    },
    "G_all_no_microstructure_pfON": {
        "v2.features.meta_features.kronos_features.enabled": True,
        "v2.features.meta_features.enabled_experimental_features": _ALL_EXPERIMENTAL,
        "v2.features.meta_features.disabled_meta_features": ["roll_spread", "parkinson_vol"],
        "v2.feature_prefilter.enabled": True,
        "v2.feature_prefilter.threshold": 0.01,
        "v2.feature_prefilter.min_features": 2,
    },
    "H_all_prefilter_aggressive_pfON": {
        "v2.features.meta_features.kronos_features.enabled": True,
        "v2.features.meta_features.enabled_experimental_features": _ALL_EXPERIMENTAL,
        "v2.feature_prefilter.enabled": True,
        "v2.feature_prefilter.threshold": 0.05,
        "v2.feature_prefilter.min_features": 3,
    },
    "I_kronos_top2_noprefilter_pfON": {
        "v2.features.meta_features.kronos_features.enabled": True,
        "v2.features.meta_features.enabled_experimental_features": ["variance_ratio_5", "kyle_entropy_ratio"],
        "v2.feature_prefilter.enabled": True,
        "v2.feature_prefilter.threshold": 0.01,
        "v2.feature_prefilter.min_features": 2,
    },
    "J_minimal_kronos_core_pfON": {
        "v2.features.meta_features.kronos_features.enabled": True,
        "v2.features.meta_features.disabled_meta_features": ["roll_spread", "rolling_d_star"],
        "v2.features.meta_features.enabled_experimental_features": [],
        "v2.feature_prefilter.enabled": True,
        "v2.feature_prefilter.threshold": 0.03,
        "v2.feature_prefilter.min_features": 2,
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
            cid = f"{strat_name}_ablpf{var_name}_{ts}"
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
    ap = argparse.ArgumentParser(description="Meta-features ablation — prefilter ON version")
    ap.add_argument("--n-jobs", type=int, default=10)
    ap.add_argument("--output-dir", type=Path, default=_DEFAULT_OUT)
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    strategies = _load_graduated_configs()
    print(f"[GOAL] Loaded {len(strategies)} strategies")
    print(f"[GOAL] Variations: {list(VARIATIONS.keys())}")
    print(f"[GOAL] Total runs: {len(strategies) * len(VARIATIONS)}")
    print("[GOAL] ALL variations run with v2.feature_prefilter.enabled: True")

    configs, meta = _build_all_configs(strategies)
    results = run_exploration(configs, n_jobs=args.n_jobs, output_dir=args.output_dir)

    csv_path = _write_csv(results, meta, args.output_dir)
    print(f"\n[GOAL] Results log: {csv_path}")

    var_names = list(VARIATIONS.keys())
    print(f"\n{'Strategy':<50} " + " ".join(f"{v:>28}" for v in var_names))
    print("-" * (50 + 29 * len(var_names)))
    idx = 0
    for strat_name, _ in strategies:
        row = f"{strat_name:<50} "
        for _ in var_names:
            r = results[idx]
            s = r.get("metrics", {}).get("sharpe", None)
            row += f"{s:+27.3f}  " if s is not None else "                          ERR  "
            idx += 1
        print(row)

    summary = {m["config_id"]: {"meta": m, "metrics": r.get("metrics", {}), "status": r.get("status")}
               for m, r in zip(meta, results)}
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"[GOAL] Done. {sum(1 for r in results if r.get('status') == 'success')}/{len(results)} success")


if __name__ == "__main__":
    main()
