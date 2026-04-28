"""
runner.py — Execute v12 pipeline for each generated config (SopaDeOtoe edition).

Bridges SopaDeOtoe configs to v12's main.run(config_path).
Each config gets a full AFML pipeline execution:
  features -> strategy -> triple barrier -> meta-labeling -> bet sizing -> backtest

Parallel execution uses subprocess isolation: each config runs in its
own Python process with independent cwd, sys.modules, and numpy seed.
No shared state between workers.

Mirror of Strategy_lab/core/runner.py — same logic, only path resolution
differs (SopaDeOtoe is not a sibling of v12, so we cross into StrategyParrot/).

Usage:
    from SopaDeOtoe.core.runner import run_exploration
    results = run_exploration(configs, n_jobs=4)
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import yaml
import numpy as np

import SopaDeOtoe._path_setup  # noqa: F401

# Paths
_CORE_DIR = Path(__file__).parent
_SOPA_DIR = _CORE_DIR.parent                                       # SopaDeOtoe/
_PATACON_DIR = _SOPA_DIR.parent                                    # Patacon/
_STRATEGY_PARROT_DIR = _PATACON_DIR / "StrategyParrot"             # StrategyParrot/
_V12_DIR = _STRATEGY_PARROT_DIR / "v12"                            # v12/
_BASE_CONFIG = _SOPA_DIR / "configs" / "base_dollar_btc.yaml"
_RESULTS_DIR = _SOPA_DIR / "results" / "exploration"
_TEMP_CONFIGS_DIR = _SOPA_DIR / "configs" / "temp"

# Parallel limits
MAX_JOBS = 15
DEFAULT_JOBS = 4


def build_run_config(
    strategy_cfg: dict,
    base_config_path: Optional[str] = None,
    data_end_override: Optional[str] = None,
) -> dict:
    """
    Merge a strategy config into the base dollar bar config to produce
    a complete v12-compatible settings dict.

    Params:
        strategy_cfg : dict — must have 'strategy.name', 'strategy.params', 'config_id'.
        base_config_path : str — path to base YAML. Defaults to
                           SopaDeOtoe/configs/base_dollar_btc.yaml.
        data_end_override : str — if set, truncates data for holdout protection.

    Returns:
        dict — complete config ready for v12 main.run().
    """
    base_path = Path(base_config_path) if base_config_path else _BASE_CONFIG
    with open(base_path) as f:
        cfg = yaml.safe_load(f)

    # Merge strategy
    cfg['strategy'] = strategy_cfg['strategy']
    cfg['_config_id'] = strategy_cfg.get('config_id', 'unknown')

    # Holdout protection
    if data_end_override:
        cfg['_data_end_override'] = data_end_override

    return cfg


def _find_latest_run_dir(v12_root: Path, ticker: str) -> Optional[Path]:
    """
    Find the most recently created run directory for a ticker.

    v12 writes to: output/runs/{ticker}_{interval}_{timestamp}/results.json
    We find the latest by sorting directory names (timestamp at the end).
    """
    runs_dir = v12_root / "output" / "runs"
    if not runs_dir.exists():
        return None
    pattern = f"{ticker}_*"
    candidates = sorted(runs_dir.glob(pattern), key=lambda p: p.name, reverse=True)
    for c in candidates:
        if (c / "results.json").exists():
            return c
    return None


def _extract_metrics_from_results_json(results_path: Path) -> dict:
    """
    Read v12's results.json and extract the metrics SopaDeOtoe needs.

    v12 results.json structure:
        metrics: {sharpe, total_return, max_drawdown, n_trades, profit_factor,
                  calmar, annual_return, ...}
        equity_curve: {dates: [...], values: [...]}
        trade_stats: {n_trades, win_rate, avg_win, avg_loss, ...}

    Returns:
        dict with keys: metrics, daily_returns, status
    """
    data = json.loads(results_path.read_text())

    raw_metrics = data.get('metrics', {})
    equity = data.get('equity_curve', {})
    trade_stats = data.get('trade_stats', {})

    # Compute daily returns from equity curve values
    eq_values = equity.get('values', [])
    daily_returns = []
    if len(eq_values) > 1:
        eq_arr = np.array(eq_values, dtype=float)
        daily_returns = (np.diff(eq_arr) / eq_arr[:-1]).tolist()

    # Sanity check: dollar bars should have >50K points
    _expected_min = 50000
    if 0 < len(daily_returns) < _expected_min:
        import warnings
        warnings.warn(
            f"[RUNNER] daily_returns length {len(daily_returns)} < {_expected_min}. "
            f"Possible stale time-bar run. Expected dollar bar equity with ~239K points."
        )

    n_trades = int(trade_stats.get('total_trades', trade_stats.get('n_trades',
                   raw_metrics.get('n_trades', 0))))

    # Compute long_pct from EXECUTED trades (backtest_trades), not raw signals.
    backtest_trades = data.get('backtest_trades', [])
    if isinstance(backtest_trades, list) and len(backtest_trades) > 0:
        n_long = sum(1 for t in backtest_trades if t.get('side', 0) > 0)
        n_short = sum(1 for t in backtest_trades if t.get('side', 0) < 0)
    else:
        n_long = int(trade_stats.get('winning_trades', 0))
        n_short = int(trade_stats.get('losing_trades', 0))
        if n_long == 0 and n_short == 0:
            signals_sparse = data.get('signals', {})
            n_long = sum(1 for v in signals_sparse.values() if float(v) > 0)
            n_short = sum(1 for v in signals_sparse.values() if float(v) < 0)
    n_directional = n_long + n_short
    long_pct = n_long / n_directional if n_directional > 0 else 0.5

    regime_summary = data.get('regime_summary', {})
    v1_vs_v2 = data.get('v1_vs_v2', {})

    return {
        'status': 'success',
        'metrics': {
            'sharpe': float(raw_metrics.get('sharpe') or 0),
            'cum_return': float(raw_metrics.get('total_return') or 0),
            'max_drawdown': float(raw_metrics.get('max_drawdown') or 0),
            'n_trades': n_trades,
            'profit_factor': float(
                raw_metrics.get('profit_factor')
                or trade_stats.get('profit_factor')
                or 0
            ),
            'calmar': float(raw_metrics.get('calmar') or 0),
            'long_pct': round(long_pct, 4),
        },
        'daily_returns': daily_returns,
        'regime_summary': regime_summary,
        'v1_vs_v2': v1_vs_v2,
    }


def _run_single_subprocess(
    config_id: str,
    run_cfg: dict,
    mode: str = 'full',
    output_dir: Optional[Path] = None,
) -> dict:
    """
    Execute a single config in an isolated subprocess via worker.py.

    Params:
        config_id  : str — unique config identifier.
        run_cfg    : dict — complete v12-compatible config.
        mode       : str — 'full' or 'signal'.
        output_dir : Path — where to write result JSON. Defaults to
                     SopaDeOtoe/results/exploration/.

    Returns:
        dict with config_id, strategy, status, metrics, daily_returns,
        regime_summary, v1_vs_v2, v12_run_dir.
    """
    _TEMP_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    out_dir = Path(output_dir) if output_dir else _RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write temp config YAML
    temp_yaml = _TEMP_CONFIGS_DIR / f"{config_id}.yaml"
    with open(temp_yaml, 'w') as f:
        yaml.dump(run_cfg, f, default_flow_style=False)

    # Output JSON path
    result_json = out_dir / f"{config_id}.json"

    strategy_name = run_cfg.get('strategy', {}).get('name', '?')
    fallback_result = {
        'config_id': config_id,
        'strategy': strategy_name,
        'status': 'error',
        'metrics': {},
        'daily_returns': [],
    }

    try:
        worker_module = "SopaDeOtoe.core.worker"
        cmd = [
            sys.executable, "-m", worker_module,
            "--mode", mode,
            "--config", str(temp_yaml),
            "--output", str(result_json),
        ]

        proc = subprocess.run(
            cmd,
            cwd=str(_PATACON_DIR),  # Patacon/ — common parent of SopaDeOtoe and StrategyParrot
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour max per config
        )

        if result_json.exists():
            result = json.loads(result_json.read_text())
            result['config_id'] = config_id
            result['strategy'] = strategy_name
            return result
        else:
            fallback_result['error'] = (
                f"Worker exited with code {proc.returncode}. "
                f"stderr: {proc.stderr[-500:]}"
            )
            return fallback_result

    except subprocess.TimeoutExpired:
        fallback_result['error'] = "subprocess timeout (1h)"
        return fallback_result
    except Exception as e:
        fallback_result['error'] = f"{type(e).__name__}: {str(e)}"
        return fallback_result


def _run_single_config(config_id: str, run_cfg: dict) -> dict:
    """
    Execute v12 main.run() for a single config in-process (legacy).

    Kept for backward compatibility. Parallel mode uses
    _run_single_subprocess() instead.
    """
    return _run_single_subprocess(config_id, run_cfg, mode='full')


def run_exploration(
    configs: list[dict],
    base_config_path: Optional[str] = None,
    data_end_override: Optional[str] = None,
    n_jobs: int = DEFAULT_JOBS,
    output_dir: Optional[Path] = None,
) -> list[dict]:
    """
    Run the full v12 pipeline for each config in parallel subprocesses.

    Params:
        configs          : list[dict] — strategy configs.
        base_config_path : str — path to base YAML template.
        data_end_override: str — holdout protection date cutoff.
        n_jobs           : int — parallel workers (default 4, max 15).
        output_dir       : Path — where to write result JSONs. Defaults to
                           SopaDeOtoe/results/exploration/.

    Returns:
        list[dict] — one result per config, in input order.
    """
    n_jobs = max(1, min(n_jobs, MAX_JOBS))
    total = len(configs)

    print(f"\n{'='*60}")
    _bar_type = configs[0].get('bar_type', 'dollar') if configs else 'dollar'
    print(f"  RUNNER: Executing {total} configs via v12 pipeline")
    print(f"  Bar type: {_bar_type} | Pipeline: full AFML (meta-labeling)")
    print(f"  Workers: {n_jobs} parallel subprocesses")
    print(f"{'='*60}\n")

    # Build all run configs
    # If a config already has 'ticker' (fully built), use as-is.
    # Otherwise merge via build_run_config (strategy-only config).
    run_configs = {}
    for i, cfg in enumerate(configs):
        config_id = cfg.get('config_id', f'config_{i}')
        if 'ticker' in cfg:
            run_cfg = dict(cfg)
        else:
            run_cfg = build_run_config(
                cfg,
                base_config_path=base_config_path,
                data_end_override=data_end_override,
            )
        run_configs[config_id] = run_cfg

    # Execute in parallel using subprocess isolation
    results_map = {}
    completed = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=n_jobs) as executor:
        futures = {}
        for config_id, run_cfg in run_configs.items():
            future = executor.submit(
                _run_single_subprocess, config_id, run_cfg, 'full', output_dir
            )
            futures[future] = config_id

        for future in as_completed(futures):
            config_id = futures[future]
            completed += 1
            try:
                result = future.result()
            except Exception as e:
                result = {
                    'config_id': config_id,
                    'strategy': run_configs[config_id].get(
                        'strategy', {}).get('name', '?'),
                    'status': 'error',
                    'error': f"{type(e).__name__}: {str(e)}",
                    'metrics': {},
                    'daily_returns': [],
                }

            results_map[config_id] = result
            status = result.get('status', '?')
            sharpe = result.get('metrics', {}).get('sharpe', 'N/A')
            elapsed = time.time() - start_time
            print(f"[{completed}/{total}] {config_id}: "
                  f"{status} (Sharpe={sharpe}) [{elapsed:.0f}s elapsed]")

    # Return results in original config order
    results = []
    for i, cfg in enumerate(configs):
        config_id = cfg.get('config_id', f'config_{i}')
        results.append(results_map.get(config_id, {
            'config_id': config_id,
            'status': 'error',
            'error': 'result not found',
            'metrics': {},
            'daily_returns': [],
        }))

    n_success = sum(1 for r in results if r['status'] == 'success')
    n_error = sum(1 for r in results if r['status'] == 'error')
    total_time = time.time() - start_time
    print(f"\n[RUNNER] Done: {n_success} success, {n_error} errors, "
          f"{total - n_success - n_error} failed")
    print(f"[RUNNER] Total time: {total_time:.0f}s ({total_time/60:.1f} min), "
          f"avg {total_time/max(total, 1):.0f}s/config "
          f"(with {n_jobs} workers)")

    return results
