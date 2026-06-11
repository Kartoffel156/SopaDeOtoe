#!/usr/bin/env python3
"""
Run graduated strategies with KRONOS enabled, compare vs graduated vs fresh.
Saves to results/kronos_compare/

Usage:
    python -m SopaDeOtoe.scripts.run_kronos_compare
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

import SopaDeOtoe._path_setup  # noqa: F401
import SopaDeOtoe.strategies  # noqa: F401

from SopaDeOtoe.core.runner import run_exploration
from portfolio.data_structures import StrategyResult


_SOPA_DIR = Path(__file__).resolve().parent.parent
_GRADUATED_DIR = _SOPA_DIR / "configs" / "graduated"
_MANIFEST_PATH = _SOPA_DIR / "strategies" / "graduated_manifest.yaml"
_EXPLORATION_DIR = _SOPA_DIR / "results" / "exploration"
_KRONOS_OUT_DIR = _SOPA_DIR / "results" / "kronos_compare"
_VENV_PY = _SOPA_DIR / ".venv" / "bin" / "python3"

# Graduated results (ground truth)
GRADUATED = {
    "HypothesisH236MomentumReversalAsym":  dict(sharpe=0.6337, trades=159, cumret=+0.152, maxdd=None, pf=None),
    "TSIMeanReversion":                      dict(sharpe=0.4896, trades=157, cumret=+0.083, maxdd=-0.054, pf=1.354),
    "HypothesisH110BollingerKyleGate":       dict(sharpe=0.4337, trades=130, cumret=+0.066, maxdd=-0.068, pf=1.276),
    "HypothesisH203VolExpansionEntry":        dict(sharpe=0.2120, trades=109, cumret=+0.040, maxdd=-0.076, pf=1.154),
    "HypothesisH167BollingerRangingOFIGate": dict(sharpe=0.1961, trades=117, cumret=+0.036, maxdd=-0.043, pf=1.189),
    "HypothesisH318TrendlineChannelSqueeze":  dict(sharpe=0.1546, trades=152, cumret=+0.026, maxdd=-0.054, pf=1.107),
    "HypothesisH37DynamicGridInformedGate":  dict(sharpe=0.1090, trades=219, cumret=+0.036, maxdd=-0.058, pf=1.082),
    "DualMovingAverageCrossover":             dict(sharpe=0.0974, trades=111, cumret=+0.013, maxdd=-0.076, pf=1.061),
    "MultiTimeframeTrendSignal":             dict(sharpe=0.0686, trades=147, cumret=+0.003, maxdd=-0.043, pf=1.019),
}

# Mapping: strategy_class in manifest → graduated YAML filename
_YAML_MAP = {
    "HypothesisH236MomentumReversalAsym":  "HypothesisH236MomentumReversalAsym_20260411_021821.yaml",
    "TSIMeanReversion":                     "TSIMeanReversion_20260419_095404.yaml",
    "HypothesisH110BollingerKyleGate":      "HypothesisH110BollingerKyleGate_20260418_160334.yaml",
    "HypothesisH203VolExpansionEntry":       "HypothesisH203VolExpansionEntry_20260418_012006.yaml",
    "HypothesisH167BollingerRangingOFIGate": "HypothesisH167BollingerRangingOFIGate_20260418_162324.yaml",
    "HypothesisH318TrendlineChannelSqueeze": "HypothesisH318TrendlineChannelSqueeze_20260419_051527.yaml",
    "HypothesisH37DynamicGridInformedGate":  "HypothesisH37DynamicGridInformedGate_20260419_051820.yaml",
    "DualMovingAverageCrossover":            "DualMovingAverageCrossover_20260418_162631.yaml",
    "MultiTimeframeTrendSignal":             "MultiTimeframeTrendSignal_20260419_134237.yaml",
}


def enable_kronos(cfg: dict) -> dict:
    """Inject KRONOS feature flag into a config dict."""
    cfg = dict(cfg)  # shallow copy
    cfg.setdefault("v2", {})
    cfg["v2"].setdefault("features", {})
    cfg["v2"]["features"].setdefault("meta_features", {})
    cfg["v2"]["features"]["meta_features"]["kronos_features"] = {"enabled": True}
    return cfg


def load_kronos_configs():
    """Load graduated configs with KRONOS enabled."""
    manifest = yaml.safe_load(_MANIFEST_PATH.read_text())
    configs = []
    for entry in manifest["strategies"]:
        strat_class = entry["strategy_class"]
        yaml_name = _YAML_MAP.get(strat_class)
        if not yaml_name:
            print(f"  [SKIP] {strat_class}: no YAML mapping")
            continue
        yaml_path = _GRADUATED_DIR / yaml_name
        if not yaml_path.exists():
            print(f"  [SKIP] {strat_class}: {yaml_path} not found")
            continue

        cfg = yaml.safe_load(yaml_path.read_text())
        cfg_kronos = enable_kronos(cfg)
        cfg_kronos["config_id"] = f"{strat_class}_KRONOS"
        cfg_kronos["_meta_strategy_class"] = strat_class

        grad_info = GRADUATED.get(strat_class, {})
        configs.append({
            "config": cfg_kronos,
            "strat_class": strat_class,
            "grad_sharpe": grad_info.get("sharpe"),
            "grad_trades": grad_info.get("trades"),
        })
        print(f"  {strat_class}: grad Sharpe={grad_info.get('sharpe')}, KRONOS YAML={yaml_name}")
    return configs


def run_and_compare(n_jobs: int, skip_run: bool):
    """Run KRONOS configs and compare to graduated ground truth."""
    configs_info = load_kronos_configs()
    print(f"\nTotal configs to run with KRONOS: {len(configs_info)}")

    kronos_dir = _KRONOS_OUT_DIR / "kronos_runs"
    kronos_dir.mkdir(parents=True, exist_ok=True)

    if skip_run:
        print("[SKIP-RUN] Reading existing results from kronos_runs dir")
    else:
        print(f"\n[RUN] Dispatching {len(configs_info)} configs with KRONOS (n_jobs={n_jobs})...")
        config_dicts = [c["config"] for c in configs_info]

        run_exploration(
            configs=config_dicts,
            output_dir=str(kronos_dir),
            n_jobs=n_jobs,
        )

    # ── Collect results ────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  COMPARISON TABLE: Graduated vs Fresh (no KRONOS) vs KRONOS")
    print("=" * 70)
    print(f"{'Strategy':<40} {'Grad Sharpe':>11} {'Fresh Sharpe':>12} {'KRONOS':>8} {'Trades':>6}")
    print("-" * 70)

    # Load fresh results from exploration dir
    fresh_results = {}
    for f in (_EXPLORATION_DIR).glob("*.json"):
        try:
            d = json.loads(f.read_text())
            cid = d.get("config_id", "")
            strat = d.get("strategy_class", "")
            sharpe = d.get("sharpe")
            trades = d.get("n_trades")
            if sharpe is not None:
                fresh_results[strat] = {"sharpe": sharpe, "trades": trades}
        except Exception:
            pass

    # Load KRONOS results
    kronos_results = {}
    for f in kronos_dir.glob("**/results.json"):
        try:
            d = json.loads(f.read_text())
            cid = d.get("config_id", "")
            strat = d.get("strategy_class", "")
            sharpe = d.get("sharpe")
            trades = d.get("n_trades")
            if sharpe is not None:
                kronos_results[strat] = {"sharpe": sharpe, "trades": trades}
        except Exception:
            pass

    for info in configs_info:
        strat = info["strat_class"]
        grad = info["grad_sharpe"]
        fresh = fresh_results.get(strat, {}).get("sharpe")
        kronos = kronos_results.get(strat, {}).get("sharpe")
        grad_t = info["grad_trades"]
        fresh_t = fresh_results.get(strat, {}).get("trades")
        kronos_t = kronos_results.get(strat, {}).get("trades")

        grad_s = f"{grad:.4f}" if grad else "N/A"
        fresh_s = f"{fresh:.4f}" if fresh else "N/A"
        kronos_s = f"{kronos:.4f}" if kronos else "N/A"
        grad_t_s = f"{grad_t}" if grad_t else "-"
        fresh_t_s = f"{fresh_t}" if fresh_t else "-"
        kronos_t_s = f"{kronos_t}" if kronos_t else "-"

        # flag divergences
        flag = ""
        if kronos and grad and abs(kronos - grad) < 0.01:
            flag = "  ✓ MATCH"
        elif kronos and grad:
            delta = kronos - grad
            flag = f"  Δ={delta:+.4f}"

        print(f"{strat:<40} {grad_s:>11} {fresh_s:>12} {kronos_s:>8}{flag}")
        if fresh_t and kronos_t:
            print(f"{'':>40} trades: grad={grad_t_s}, fresh={fresh_t_s}, kronos={kronos_t_s}")

    print("=" * 70)
    summary_path = _KRONOS_OUT_DIR / "kronos_compare_summary.json"
    with open(summary_path, "w") as f:
        json.dump({
            "graduated": {k: {**v, "source": "user_table"}
                          for k, v in GRADUATED.items()},
            "fresh": fresh_results,
            "kronos": kronos_results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2, default=str)
    print(f"\nSummary saved: {summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KRONOS comparison runner")
    parser.add_argument("--n-jobs", type=int, default=9)
    parser.add_argument("--skip-run", action="store_true",
                        help="Skip dispatch, just compare existing results")
    args = parser.parse_args()
    run_and_compare(n_jobs=args.n_jobs, skip_run=args.skip_run)