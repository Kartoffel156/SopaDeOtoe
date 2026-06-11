#!/usr/bin/env python3
"""
run_graduated_jpm.py — Run all graduated strategies on JPM with JPM GMM.

Usage:
    cd /Users/nongo/Documents/Patacon/SopaDeOtoe
    python -m launchers.run_graduated_jpm [--n-jobs 4] [--skip-run]

Adaptations from BTC graduated configs -> JPM:
  - ticker: BTC-USD -> JPM
  - bar_type: dollar -> time (JPM uses daily equity bars from cache)
  - start: 2020-01-01 (keep same)
  - end: 2026-05-27 (JPM data end)
  - cost: 0.001 (equity ~0.10% per side)
  - pt_sl: [2.0, 1.5] (equity-friendly)
  - max_holding: 15 (3 weeks, not 36 bars ~6 days)
  - GMM: models/gmm_regime_jpm.pkl (JPM-specific, not BTC)
  - features_csv: output/features_jpm.csv
  - slippage_bps: 5.0 (wider than crypto)
  - spread_bps: 2.0

The base config for all is configs/base_jpm_gmm.yaml.
Strategy params are copied from configs/graduated/*.yaml.
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml
import numpy as np

import SopaDeOtoe._path_setup  # noqa: F401
import SopaDeOtoe.strategies  # noqa: F401 — triggers BaseStrategy._REGISTRY

from SopaDeOtoe.core.runner import _run_single_subprocess


_SOPA_DIR = Path(__file__).resolve().parent.parent
_GRADUATED_DIR = _SOPA_DIR / "configs" / "graduated"
_BASE_JPM_CFG = _SOPA_DIR / "configs" / "base_jpm_gmm.yaml"
_RESULTS_DIR = _SOPA_DIR / "results" / "exploration_jpm"
_TEMP_DIR = _SOPA_DIR / "configs" / "temp_jpm"


def load_graduated_configs_jpm():
    """Load all graduated configs adapted for JPM."""
    configs = []
    yaml_files = sorted(_GRADUATED_DIR.glob("*.yaml"))

    for yf in yaml_files:
        grad_cfg = yaml.safe_load(yf.read_text())

        # Start from base JPM config
        base_cfg = yaml.safe_load(_BASE_JPM_CFG.read_text())

        # Merge strategy (preserves strategy class + params from graduated)
        base_cfg['strategy'] = grad_cfg['strategy']

        # Stamp with unique config_id
        strategy_name = grad_cfg['strategy']['name']
        strategy_hash = grad_cfg.get('config_hash', yf.stem[-8:])
        base_cfg['config_id'] = f"jpm_{strategy_name}_{strategy_hash}_REPRO"

        # Store original class name for reference
        base_cfg['_strategy_class'] = strategy_name

        configs.append(base_cfg)

    return configs


def run_all_jpm(n_jobs=4, skip_run=False, output_dir=None):
    """Run all graduated strategies on JPM."""
    configs = load_graduated_configs_jpm()
    total = len(configs)

    out_dir = Path(output_dir) if output_dir else _RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    _TEMP_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  JPM GRADUATED RUN — {total} strategies")
    print(f"  Base: configs/base_jpm_gmm.yaml")
    print(f"  GMM: models/gmm_regime_jpm.pkl (K=4: BEAR/CONGESTED/CYCLIC/BULL)")
    print(f"  Workers: {n_jobs} parallel")
    print(f"  Output: {out_dir}")
    print(f"{'='*60}\n")

    results = []
    completed = 0

    if skip_run:
        print("[SKIP-RUN] Loading existing results from", out_dir)
        for cfg in configs:
            cid = cfg['config_id']
            result_json = out_dir / f"{cid}.json"
            if result_json.exists():
                results.append(json.loads(result_json.read_text()))
                print(f"  [LOADED] {cid}")
            else:
                print(f"  [MISSING] {cid} — will run")
        # Re-run missing
        configs_to_run = [c for c in configs if c['config_id'] not in [r.get('config_id') for r in results]]
        if configs_to_run:
            print(f"\n  Running {len(configs_to_run)} missing configs...")
    else:
        configs_to_run = configs

    n_jobs = max(1, min(n_jobs, 15))
    completed = 0
    total_run = len(configs_to_run)

    with ThreadPoolExecutor(max_workers=n_jobs) as executor:
        futures = {
            executor.submit(
                _run_single_subprocess,
                cfg['config_id'],
                cfg,
                'full',
                str(out_dir),
            ): cfg
            for cfg in configs_to_run
        }

        for future in as_completed(futures):
            cfg = futures[future]
            try:
                result = future.result()
            except Exception as e:
                result = {
                    'config_id': cfg['config_id'],
                    'strategy': cfg.get('strategy', {}).get('name', '?'),
                    'status': 'error',
                    'error': str(e),
                    'metrics': {},
                }
            results.append(result)
            completed += 1
            status = result.get('status', '?')
            sid = result.get('config_id', '?')
            m = result.get('metrics', {})
            sharpe = m.get('sharpe')
            ret = m.get('total_return', m.get('cum_return'))
            n_trades = m.get('n_trades')

            s_str = f"{sharpe:.3f}" if sharpe is not None else "N/A"
            r_str = f"{ret:.3f}" if ret is not None else "N/A"
            n_str = f"{n_trades}" if n_trades is not None else "N/A"
            print(f"  [{completed}/{total}] {status.upper()} | {sid}")
            print(f"           Sharpe={s_str} | Ret={r_str} | Trades={n_str}")
            if result.get('error'):
                print(f"           ERROR: {result['error'][:100]}")

    # Write results
    for r in results:
        cid = r.get('config_id', 'unknown')
        (out_dir / f"{cid}.json").write_text(json.dumps(r, indent=2, default=str))

    # Print summary
    print(f"\n{'='*60}")
    print(f"  RESULTS SUMMARY — JPM Graduated ({len(results)} strategies)")
    print(f"{'='*60}")
    print(f"{'Strategy':<45} {'Sharpe':>7} {'Return':>8} {'MaxDD':>7} {'Trades':>6} {'Win%':>5}")
    print("-" * 80)

    sorted_results = sorted(
        [r for r in results if r.get('status') == 'success'],
        key=lambda x: x.get('metrics', {}).get('sharpe', -999),
        reverse=True
    )

    for r in sorted_results:
        m = r.get('metrics', {})
        sid = r.get('config_id', '?')
        strategy_name = r.get('strategy', '?')
        sharpe = m.get('sharpe', 0)
        ret = m.get('total_return', 0)
        max_dd = m.get('max_drawdown', 0)
        n_trades = m.get('n_trades', 0)
        win_rate = m.get('win_rate', 0)

        print(f"  {strategy_name:<43} {sharpe:>7.3f} {ret:>8.3f} {max_dd:>7.3f} {n_trades:>6} {win_rate:>5.1%}")

    # Portfolio summary
    if sorted_results:
        print(f"\n  Top 3 by Sharpe:")
        for r in sorted_results[:3]:
            print(f"    {r.get('strategy')}: Sharpe={r['metrics'].get('sharpe', 0):.3f}")

    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run graduated strategies on JPM')
    parser.add_argument('--n-jobs', type=int, default=4)
    parser.add_argument('--skip-run', action='store_true', help='Load existing results, skip execution')
    parser.add_argument('--output-dir', type=str, default=None)
    args = parser.parse_args()

    run_all_jpm(n_jobs=args.n_jobs, skip_run=args.skip_run, output_dir=args.output_dir)