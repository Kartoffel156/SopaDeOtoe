"""
run_pooled_meta_backtest.py — Layer 1.5 pooled meta-model launcher.

Orchestrates:
  Layer 1   (export):   7 graduated strategies → meta_export/ parquets
  Layer 1.5 (train):    pool → train WF OOS → gate → replay → StrategyResult
  Layer 2   (portfolio): run_portfolio_backtest() unchanged
  Compare:  pooled vs baseline (individual metas) + gates G1-G6

Usage:
    cd Patacon/
    python -m SopaDeOtoe.launchers.run_pooled_meta_backtest --full --n-jobs 4
    python -m SopaDeOtoe.launchers.run_pooled_meta_backtest --export --n-jobs 4
    python -m SopaDeOtoe.launchers.run_pooled_meta_backtest --train --skip-export
    python -m SopaDeOtoe.launchers.run_pooled_meta_backtest --compare --skip-export --skip-run
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

import SopaDeOtoe._path_setup  # noqa: F401
import SopaDeOtoe.strategies  # noqa: F401

from SopaDeOtoe.core.runner import run_exploration, run_export
from portfolio.data_structures import StrategyResult
from portfolio.portfolio_config import load_portfolio_config
from portfolio.runner import run_portfolio_backtest

from meta_pool.dataset import load_strategy_export, load_all_exports, validate_schemas, pool_datasets
from meta_pool.trainer import train_pooled_meta_model, train_null_model, extract_strategy_probas
from meta_pool.gating import load_gating_config, gate_positions
from meta_pool.replay import replay_to_returns, build_strategy_result


_SOPA_DIR = Path(__file__).resolve().parent.parent
_GRADUATED_DIR = _SOPA_DIR / "configs" / "graduated"
_MANIFEST_PATH = _SOPA_DIR / "strategies" / "graduated_manifest.yaml"
_PORTFOLIO_CFG_PATH = _SOPA_DIR / "config" / "portfolio_settings.yaml"
_POOLED_META_CFG_PATH = _SOPA_DIR / "config" / "pooled_meta_settings.yaml"
_EXPLORATION_DIR = _SOPA_DIR / "results" / "exploration"
_META_DATASETS_DIR = _SOPA_DIR / "results" / "exploration" / "meta_datasets"
_PORTFOLIO_OUT_DIR = _SOPA_DIR / "results" / "portfolio"


# ── Helpers ──────────────────────────────────────────────────────────


def _load_graduated_configs():
    """Load the 7 graduated YAML configs as dicts ready for run_exploration."""
    manifest = yaml.safe_load(_MANIFEST_PATH.read_text())
    configs = []
    for entry in manifest["strategies"]:
        yaml_path = _SOPA_DIR / entry["config_file"]
        cfg = yaml.safe_load(yaml_path.read_text())
        cfg["config_id"] = f"{entry['strategy_class']}_{entry['run_id'].split('_')[-1]}_REPRO"
        cfg["_meta_run_id"] = entry["run_id"]
        cfg["_meta_strategy_class"] = entry["strategy_class"]
        cfg["_meta_config_hash"] = entry.get("config_hash", "")
        configs.append(cfg)
    return configs, manifest


def _load_pooled_meta_cfg():
    """Load pooled meta settings YAML."""
    return yaml.safe_load(_POOLED_META_CFG_PATH.read_text())


def _results_to_strategy_result(name, run_dir, n_trials=1):
    """Read a v12 results.json and build a StrategyResult (baseline)."""
    data = json.loads((Path(run_dir) / "results.json").read_text())
    ec = data.get("equity_curve", {})
    dates = ec.get("dates", [])
    values = ec.get("values", [])
    if not values or not dates:
        raise ValueError(f"{name}: equity_curve empty in {run_dir}")

    raw = pd.DataFrame({"date": pd.to_datetime(dates), "eq": values})
    daily_eq = raw.groupby(raw["date"].dt.normalize())["eq"].last().sort_index()
    daily_eq.index.name = None

    returns = daily_eq.pct_change().fillna(0.0).astype(float)
    returns.name = name
    equity = daily_eq.astype(float)
    equity.name = name

    positions = (returns.abs() > 1e-12).astype(int)
    positions.name = name
    signals = positions.copy()
    signals.name = name

    raw_metrics = data.get("metrics", {}) or {}
    trade_stats = data.get("trade_stats", {}) or {}
    metrics = {
        "sharpe": float(raw_metrics.get("sharpe") or 0.0),
        "total_return": float(raw_metrics.get("total_return") or 0.0),
        "max_drawdown": float(raw_metrics.get("max_drawdown") or 0.0),
        "calmar": float(raw_metrics.get("calmar") or 0.0),
        "sortino": float(raw_metrics.get("sortino") or 0.0),
        "n_trades": int(
            trade_stats.get("total_trades")
            or trade_stats.get("n_trades")
            or raw_metrics.get("n_trades")
            or 0
        ),
    }

    return StrategyResult(
        name=name,
        returns=returns,
        equity=equity,
        positions=positions,
        signals=signals,
        metrics=metrics,
        extended_metrics=trade_stats,
        montecarlo=data.get("montecarlo", {}) or {},
        trades=data.get("backtest_trades", []) or [],
        meta={
            "n_trials": n_trials,
            "v12_run_dir": str(run_dir),
            "daily_bars": int(len(daily_eq)),
            "source": "baseline_individual_meta",
        },
    )


# ── Step 1: Export ───────────────────────────────────────────────────


def step_export(n_jobs=4):
    """Layer 1: run export pipeline for all graduated strategies."""
    configs, manifest = _load_graduated_configs()
    print(f"[EXPORT] Loaded {len(configs)} graduated configs")
    results = run_export(configs, n_jobs=n_jobs, output_dir=_EXPLORATION_DIR)

    n_ok = sum(1 for r in results if r.get('status') == 'success')
    print(f"[EXPORT] Done: {n_ok}/{len(results)} succeeded")
    return results, manifest


# ── Step 2: Train + Gate + Replay ────────────────────────────────────


def step_train():
    """
    Layer 1.5: load exports → pool → train WF OOS → gate → replay.

    Returns:
        strategy_results : list[StrategyResult] — one per gated strategy
        clf              : final classifier (trained on all data)
        oos_proba        : pd.Series of OOS probabilities (pooled)
        null_proba       : pd.Series of null-model OOS probabilities
        X_pool           : pooled features (needed for extract_strategy_probas)
        y_pool           : pooled labels (needed for gates)
        pool_metadata    : metadata dict from pool_datasets
    """
    pooled_cfg = _load_pooled_meta_cfg()
    meta_cfg = pooled_cfg.get('pooled_meta', {})

    # 1. Load all exports
    print(f"\n[TRAIN] Loading exports from {_META_DATASETS_DIR}")
    exports = load_all_exports(_META_DATASETS_DIR)
    if not exports:
        print("[TRAIN] ERROR: no exports found. Run --export first.")
        sys.exit(1)
    print(f"[TRAIN] Found {len(exports)} strategy exports: {list(exports.keys())}")

    # 2. Validate and pool
    validate_schemas(exports)
    X_pool, y_pool, w_pool, pool_metadata = pool_datasets(exports)
    n_pooled = len(X_pool)
    print(f"[TRAIN] Pooled dataset: {n_pooled} rows, {len(X_pool.columns)} features")
    print(f"[TRAIN] Rows per strategy: {pool_metadata['n_rows_per_strategy']}")

    # 3. Train pooled meta-model (walk-forward OOS)
    n_splits = meta_cfg.get('n_splits', 5)
    embargo_pct = meta_cfg.get('embargo_pct', 0.01)
    wf_mode = meta_cfg.get('walkforward_mode', 'expanding')

    print(f"[TRAIN] Training pooled meta-model: n_splits={n_splits}, "
          f"embargo={embargo_pct}, mode={wf_mode}")
    clf, oos_proba, fold_clfs = train_pooled_meta_model(
        X_pool, y_pool, w_pool, pooled_cfg,
        n_splits=n_splits,
        embargo_pct=embargo_pct,
        mode=wf_mode,
    )
    print(f"[TRAIN] OOS proba range: [{oos_proba.min():.3f}, {oos_proba.max():.3f}], "
          f"mean={oos_proba.mean():.3f}")

    # 3b. Null model for gate G4
    print("[TRAIN] Training null model (DummyClassifier) for gate G4")
    null_proba = train_null_model(X_pool, y_pool, n_splits=n_splits,
                                  embargo_pct=embargo_pct, mode=wf_mode)

    # 4. Extract per-strategy probas
    strategy_probas = extract_strategy_probas(oos_proba, X_pool, pool_metadata)

    # 5. Gate + replay per strategy
    gating_cfg = load_gating_config(_POOLED_META_CFG_PATH)
    strategy_results = []

    print(f"\n[GATE+REPLAY] Processing {len(exports)} strategies")
    for strat_name in sorted(exports.keys()):
        data = pool_metadata['per_strategy_data'][strat_name]
        pivot = gating_cfg['pivots'].get(strat_name, gating_cfg['pivots']['default'])

        if strat_name in gating_cfg.get('hedge_bypass', []):
            # Bypass: positions = side * 1.0 without meta-model filtering
            print(f"  {strat_name}: BYPASS (hedge_bypass)")
            positions = data['side'].reindex(data['close'].index, method='ffill').fillna(0)
        else:
            positions = gate_positions(
                strategy_probas[strat_name],
                data['side'], data['labels'],
                data['signal_times'], data['close'],
                data['config'], pivot=pivot,
            )

        replay_result = replay_to_returns(positions, data['close'], data['config'])
        sr = build_strategy_result(
            name=strat_name,
            replay_result=replay_result,
            source_meta={'pivot': pivot, 'source': 'pooled_meta'},
        )
        strategy_results.append(sr)

        n_trades = replay_result['n_trades']
        sharpe = sr.metrics['sharpe']
        print(f"  {strat_name}: pivot={pivot:.2f} trades={n_trades} "
              f"sharpe={sharpe:+.3f}")

    return strategy_results, clf, oos_proba, null_proba, X_pool, y_pool, pool_metadata


# ── Step 3: Portfolio ────────────────────────────────────────────────


def step_portfolio(strategy_results, label="pooled", max_leverage_override=None):
    """
    Layer 2: run portfolio backtest on strategy results.

    Args:
        strategy_results  : list[StrategyResult]
        label             : str for logging
        max_leverage_override : float or None

    Returns:
        PortfolioResult
    """
    pcfg = load_portfolio_config(_PORTFOLIO_CFG_PATH)
    pcfg.mode = "backtest"
    pcfg.validation.n_permutations = 1000
    pcfg.validation.n_bootstrap = 1000
    pcfg.validation.run_stress_test = False
    pcfg.validation.run_spa_test = False

    if max_leverage_override is not None:
        pcfg.risk.max_leverage = max_leverage_override

    print(f"\n[PORTFOLIO-{label.upper()}] Running with {len(strategy_results)} strategies, "
          f"max_leverage={pcfg.risk.max_leverage}")
    pr = run_portfolio_backtest(strategy_results, pcfg)
    print(f"[PORTFOLIO-{label.upper()}] Sharpe={pr.metrics.get('sharpe', 0):.4f} "
          f"Calmar={pr.metrics.get('calmar', 0):.4f} "
          f"MaxDD={pr.metrics.get('max_drawdown', 0):.4f}")
    return pr


# ── Step 4: Baseline ────────────────────────────────────────────────


def step_baseline(skip_run=False, n_jobs=4):
    """
    Run baseline portfolio (individual metas, same as run_graduated_backtest).

    Returns:
        PortfolioResult, manifest
    """
    configs, manifest = _load_graduated_configs()

    if skip_run:
        print(f"\n[BASELINE] Loading previous exploration results from {_EXPLORATION_DIR}")
        exploration_results = []
        for cfg in configs:
            cid = cfg["config_id"]
            path = _EXPLORATION_DIR / f"{cid}.json"
            if not path.exists():
                print(f"[BASELINE] ERROR: {path} not found. Run without --skip-run.")
                sys.exit(1)
            exploration_results.append(json.loads(path.read_text()))
    else:
        print(f"\n[BASELINE] Running exploration (Layer 1) with n_jobs={n_jobs}")
        exploration_results = run_exploration(configs, n_jobs=n_jobs,
                                              output_dir=_EXPLORATION_DIR)

    strategy_results = []
    for cfg, res in zip(configs, exploration_results):
        if res.get("status") != "success":
            continue
        run_dir = Path(res["v12_run_dir"])
        cls = cfg["_meta_strategy_class"]
        config_hash = cfg.get("_meta_config_hash", "")
        name = f"{cls}_{config_hash[:8]}" if config_hash else cls
        try:
            sr = _results_to_strategy_result(name, run_dir)
        except Exception as e:
            print(f"  SKIP {cls}: {type(e).__name__}: {e}")
            continue
        strategy_results.append(sr)

    if len(strategy_results) < 2:
        print(f"[BASELINE] ABORT: need >= 2 strategies, got {len(strategy_results)}")
        sys.exit(2)

    pr = step_portfolio(strategy_results, label="baseline",
                        max_leverage_override=None)  # uses portfolio_settings.yaml default
    return pr, manifest


# ── Step 5: Gates ────────────────────────────────────────────────────


def evaluate_gates(pooled_pr, baseline_pr, oos_proba, null_proba,
                   y_pool, X_pool, pool_metadata):
    """
    Evaluate acceptance gates G1-G6.

    Returns:
        dict mapping gate name -> {pass: bool, ...details}
    """
    gates = {}

    # G1: Sanity — end-to-end OK, N pooled >= 1000, no NaN in probas
    n_pooled = len(oos_proba)
    has_nan = bool(oos_proba.isna().any())
    gates['G1'] = {
        'name': 'Sanity',
        'pass': n_pooled >= 1000 and not has_nan,
        'n_pooled': n_pooled,
        'has_nan': has_nan,
    }

    # G2: Learning — AUC OOS pooled > null model
    try:
        from sklearn.metrics import roc_auc_score
        # Align y_pool to oos_proba index
        y_aligned = y_pool.reindex(oos_proba.index)
        valid = y_aligned.notna() & oos_proba.notna()
        auc_pooled = roc_auc_score(y_aligned[valid], oos_proba[valid])
        null_aligned = null_proba.reindex(oos_proba.index)
        auc_null = roc_auc_score(y_aligned[valid], null_aligned[valid])
        gates['G2'] = {
            'name': 'Learning (AUC)',
            'pass': auc_pooled > auc_null,
            'auc_pooled': float(auc_pooled),
            'auc_null': float(auc_null),
        }
    except Exception as e:
        gates['G2'] = {'name': 'Learning (AUC)', 'pass': False, 'error': str(e)}

    # G3: Hedge survives — >= 70% of H86 trades in worst BTC decile approved
    try:
        close = pool_metadata['close_series']
        btc_returns = close.pct_change().dropna()
        worst_n = max(1, len(btc_returns) // 10)
        worst_decile_dates = btc_returns.nsmallest(worst_n).index

        strategy_probas = extract_strategy_probas(oos_proba, X_pool, pool_metadata)
        h86_key = 'HypothesisH86WonhamMarkovRefinado'
        h86_probas = strategy_probas.get(h86_key, pd.Series(dtype=float))

        if len(h86_probas) > 0:
            h86_in_worst = h86_probas.reindex(worst_decile_dates).dropna()
            h86_approved = int((h86_in_worst > 0.40).sum())
            h86_total = len(h86_in_worst)
            approved_pct = h86_approved / max(h86_total, 1)
            gates['G3'] = {
                'name': 'Hedge survives',
                'pass': h86_total > 0 and approved_pct >= 0.70,
                'approved_pct': float(approved_pct),
                'h86_approved': h86_approved,
                'h86_total': h86_total,
            }
        else:
            gates['G3'] = {
                'name': 'Hedge survives',
                'pass': True,  # no H86 = gate N/A
                'note': 'H86 not in pool',
            }
    except Exception as e:
        gates['G3'] = {'name': 'Hedge survives', 'pass': False, 'error': str(e)}

    # G4: Null model — DeltaCalmar(pooled vs baseline) > 0
    pooled_calmar = pooled_pr.metrics.get('calmar', 0)
    baseline_calmar = baseline_pr.metrics.get('calmar', 0)
    delta_calmar = pooled_calmar - baseline_calmar
    gates['G4'] = {
        'name': 'Null model (Calmar)',
        'pass': delta_calmar > 0,
        'pooled_calmar': float(pooled_calmar),
        'baseline_calmar': float(baseline_calmar),
        'delta_calmar': float(delta_calmar),
    }

    # G5: Portfolio wins — Sharpe pooled >= baseline, bootstrap p5 > 0.5
    pooled_sharpe = pooled_pr.metrics.get('sharpe', 0)
    baseline_sharpe = baseline_pr.metrics.get('sharpe', 0)
    bootstrap_p5 = pooled_pr.montecarlo.get('bootstrap', {}).get('sharpe_5pct', 0)
    gates['G5'] = {
        'name': 'Portfolio wins (Sharpe)',
        'pass': pooled_sharpe >= baseline_sharpe and bootstrap_p5 > 0.5,
        'pooled_sharpe': float(pooled_sharpe),
        'baseline_sharpe': float(baseline_sharpe),
        'bootstrap_p5': float(bootstrap_p5),
    }

    # G6: Permutation + CPCV
    perm_pval = pooled_pr.montecarlo.get('permutation', {}).get('p_value', 1.0)
    gates['G6'] = {
        'name': 'Permutation + CPCV',
        'pass': perm_pval < 0.05,
        'permutation_p_value': float(perm_pval),
    }

    return gates


def _print_gates(gates):
    """Print gates table."""
    print("\n" + "=" * 72)
    print("  ACCEPTANCE GATES")
    print("=" * 72)
    all_pass = True
    for gid in sorted(gates.keys()):
        g = gates[gid]
        status = "PASS" if g['pass'] else "FAIL"
        if not g['pass']:
            all_pass = False
        name = g.get('name', gid)
        # Build detail string from non-standard keys
        details = {k: v for k, v in g.items() if k not in ('pass', 'name')}
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        print(f"  [{status:4s}] {gid}: {name} — {detail_str}")

    verdict = "ALL GATES PASSED" if all_pass else "SOME GATES FAILED"
    print(f"\n  Verdict: {verdict}")
    print("=" * 72)


# ── Step 6: Compare + Report ────────────────────────────────────────


def _print_comparison(pooled_pr, baseline_pr):
    """Print side-by-side portfolio comparison."""
    print("\n" + "=" * 72)
    print("  PORTFOLIO COMPARISON: POOLED META vs BASELINE")
    print("=" * 72)

    pm = pooled_pr.metrics
    bm = baseline_pr.metrics

    metrics_to_show = [
        'sharpe', 'dsr', 'annualized_return', 'annualized_volatility',
        'max_drawdown', 'calmar', 'sortino', 'exposure',
    ]

    print(f"  {'Metric':25s} {'Pooled':>10s} {'Baseline':>10s} {'Delta':>10s}")
    print(f"  {'-'*25} {'-'*10} {'-'*10} {'-'*10}")
    for k in metrics_to_show:
        pv = pm.get(k, 0)
        bv = bm.get(k, 0)
        if isinstance(pv, (int, float)) and isinstance(bv, (int, float)):
            delta = pv - bv
            print(f"  {k:25s} {pv:+10.4f} {bv:+10.4f} {delta:+10.4f}")

    # Weights
    print(f"\n  Pooled weights ({len(pooled_pr.strategy_names)} strategies):")
    for nm, wi in sorted(zip(pooled_pr.strategy_names, pooled_pr.weights),
                         key=lambda x: -x[1]):
        print(f"    {wi:6.3f}  {nm}")

    print(f"\n  Baseline weights ({len(baseline_pr.strategy_names)} strategies):")
    for nm, wi in sorted(zip(baseline_pr.strategy_names, baseline_pr.weights),
                         key=lambda x: -x[1]):
        print(f"    {wi:6.3f}  {nm}")

    print("=" * 72)


# ── Save ─────────────────────────────────────────────────────────────


def _save_summary(pooled_pr, baseline_pr, gates, out_dir):
    """Save comparison summary JSON."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"pooled_meta_{ts}.json"

    def _safe(x):
        if isinstance(x, (np.integer,)):
            return int(x)
        if isinstance(x, (np.floating, float)):
            if np.isnan(x) or np.isinf(x):
                return None
            return float(x)
        if isinstance(x, np.ndarray):
            return x.tolist()
        if isinstance(x, pd.DataFrame):
            return x.to_dict()
        if isinstance(x, pd.Series):
            return x.to_dict()
        return x

    def _deep(obj, depth=0):
        if depth > 50:
            return str(obj)
        if isinstance(obj, dict):
            return {str(k): _deep(v, depth + 1) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_deep(v, depth + 1) for v in obj]
        if isinstance(obj, pd.DataFrame):
            return _deep(obj.to_dict(), depth + 1)
        if isinstance(obj, pd.Series):
            return _deep(obj.to_dict(), depth + 1)
        return _safe(obj)

    pm = pooled_pr.metrics
    bm = baseline_pr.metrics

    summary = {
        "timestamp": ts,
        "mode": "pooled_meta",
        "gates": _deep(gates),
        "comparison": {
            "pooled_sharpe": _safe(pm.get('sharpe', 0)),
            "baseline_sharpe": _safe(bm.get('sharpe', 0)),
            "delta_sharpe": _safe(pm.get('sharpe', 0) - bm.get('sharpe', 0)),
            "pooled_calmar": _safe(pm.get('calmar', 0)),
            "baseline_calmar": _safe(bm.get('calmar', 0)),
            "pooled_max_dd": _safe(pm.get('max_drawdown', 0)),
            "baseline_max_dd": _safe(bm.get('max_drawdown', 0)),
        },
        "pooled_portfolio": {
            "allocation_method": pooled_pr.allocation_method,
            "fdm": float(pooled_pr.fdm),
            "weights": {n: float(w) for n, w in
                        zip(pooled_pr.strategy_names, pooled_pr.weights)},
            "metrics": {k: _safe(v) for k, v in pm.items()
                        if k != 'risk_attribution'},
            "montecarlo": {
                mk: {k: _safe(v) for k, v in mv.items()
                      if not isinstance(v, (list, np.ndarray)) or len(v) < 50}
                for mk, mv in pooled_pr.montecarlo.items()
                if isinstance(mv, dict)
            },
        },
        "baseline_portfolio": {
            "allocation_method": baseline_pr.allocation_method,
            "fdm": float(baseline_pr.fdm),
            "weights": {n: float(w) for n, w in
                        zip(baseline_pr.strategy_names, baseline_pr.weights)},
            "metrics": {k: _safe(v) for k, v in bm.items()
                        if k != 'risk_attribution'},
        },
        "per_strategy_pooled": [
            {
                "name": sr.name,
                "metrics": sr.metrics,
                "daily_bars": sr.meta.get("daily_bars"),
                "pivot": sr.meta.get("pivot"),
            }
            for sr in pooled_pr.strategy_results
        ],
    }

    safe_summary = _deep(summary)
    out_path.write_text(json.dumps(safe_summary, indent=2, default=lambda x: str(x)))
    return out_path


# ── Main ─────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser(
        description="Pooled meta-model backtest launcher (Layer 1.5)")
    ap.add_argument("--n-jobs", type=int, default=4)
    ap.add_argument("--output-dir", type=Path, default=_PORTFOLIO_OUT_DIR)

    # Mode flags
    ap.add_argument("--full", action="store_true",
                    help="Run everything: export + train + portfolio + compare")
    ap.add_argument("--export", action="store_true",
                    help="Only run Layer 1 export")
    ap.add_argument("--train", action="store_true",
                    help="Run Layer 1.5 train + gate + replay")
    ap.add_argument("--compare", action="store_true",
                    help="Run comparison and gates")

    # Skip flags
    ap.add_argument("--skip-export", action="store_true",
                    help="Use existing parquets in meta_datasets/")
    ap.add_argument("--skip-run", action="store_true",
                    help="Use existing exploration results for baseline")

    args = ap.parse_args()

    # Default to --full if no mode specified
    if not any([args.full, args.export, args.train, args.compare]):
        args.full = True

    pooled_cfg = _load_pooled_meta_cfg()
    pooled_leverage = pooled_cfg.get('portfolio_overrides', {}).get('max_leverage', 6.0)

    # ── Export ──
    if args.full or args.export:
        if not args.skip_export:
            export_results, manifest = step_export(n_jobs=args.n_jobs)
        else:
            print("[MAIN] --skip-export: using existing parquets")
            _, manifest = _load_graduated_configs()

        if args.export and not args.full:
            print("\n[MAIN] Export complete. Run with --train to continue.")
            return

    # ── Train + Gate + Replay ──
    if args.full or args.train or args.compare:
        if not args.skip_export and not (args.full or args.export):
            # Need to check exports exist
            pass
        _, manifest = _load_graduated_configs()

    if args.full or args.train:
        (strategy_results, clf, oos_proba, null_proba,
         X_pool, y_pool, pool_metadata) = step_train()

        # Layer 2: pooled portfolio
        pooled_pr = step_portfolio(
            strategy_results, label="pooled",
            max_leverage_override=pooled_leverage,
        )

        if args.train and not args.full:
            print(f"\n[MAIN] Train complete. Pooled Sharpe={pooled_pr.metrics.get('sharpe', 0):.4f}")
            return

    # ── Compare ──
    if args.full or args.compare:
        # Need baseline
        baseline_pr, manifest = step_baseline(
            skip_run=args.skip_run or args.skip_export,
            n_jobs=args.n_jobs,
        )

        # If --compare without --train, we need to train first
        if args.compare and not args.full and not args.train:
            (strategy_results, clf, oos_proba, null_proba,
             X_pool, y_pool, pool_metadata) = step_train()
            pooled_pr = step_portfolio(
                strategy_results, label="pooled",
                max_leverage_override=pooled_leverage,
            )

        # Gates
        gates = evaluate_gates(
            pooled_pr, baseline_pr, oos_proba, null_proba,
            y_pool, X_pool, pool_metadata,
        )

        # Reports
        _print_comparison(pooled_pr, baseline_pr)
        _print_gates(gates)

        # Save
        out_path = _save_summary(pooled_pr, baseline_pr, gates, args.output_dir)
        print(f"\n[MAIN] Summary saved to: {out_path}")


if __name__ == "__main__":
    main()
