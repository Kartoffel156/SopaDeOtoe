"""
worker.py — Subprocess worker for isolated v12 pipeline execution (SopaDeOtoe edition).

Runs a single config through v12's main.run() (or M1-M3 prefilter)
in a completely isolated process. No shared state: each worker has
its own cwd, sys.modules, numpy seed, and file handles.

Communication: reads config from a temp YAML, writes result to a
temp JSON. The parent process (runner.py) coordinates.

Mirror of Strategy_lab/core/worker.py — same logic, only path resolution
differs (SopaDeOtoe is not a sibling of v12, so we cross into StrategyParrot/).

Usage (called by runner.py, not directly):
    python -m SopaDeOtoe.core.worker --mode full   --config /tmp/cfg.yaml --output /tmp/result.json
    python -m SopaDeOtoe.core.worker --mode signal --config /tmp/cfg.yaml --output /tmp/result.json
"""

import json
import os
import sys
import traceback
import warnings
from pathlib import Path

import yaml
import numpy as np


def _setup_paths():
    """Ensure Patacon/, StrategyParrot/, v12/, and SopaDeOtoe/ are in sys.path."""
    core_dir = Path(__file__).resolve().parent          # SopaDeOtoe/core/
    sopa_dir = core_dir.parent                          # SopaDeOtoe/
    patacon_dir = sopa_dir.parent                       # Patacon/
    strategy_parrot_dir = patacon_dir / "StrategyParrot"
    v12_dir = strategy_parrot_dir / "v12"
    for p in [str(patacon_dir), str(strategy_parrot_dir), str(v12_dir), str(sopa_dir)]:
        if p not in sys.path:
            sys.path.insert(0, p)
    return v12_dir


def _serialize(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def run_full_pipeline(config_path: str, output_path: str):
    """
    Execute the full v12 pipeline for a single config.

    Reads config from YAML, runs main.run(), finds results.json,
    extracts metrics, writes result JSON.

    Race-condition safe: snapshots existing run dirs BEFORE execution,
    then finds only the NEW directory created by this worker.
    """
    v12_dir = _setup_paths()

    # Resolve to absolute path BEFORE chdir
    config_path = str(Path(config_path).resolve())
    output_path = str(Path(output_path).resolve())

    with open(config_path) as f:
        run_cfg = yaml.safe_load(f)

    config_id = run_cfg.pop('_config_id', 'unknown')
    data_end = run_cfg.pop('_data_end_override', None)
    strategy_name = run_cfg.get('strategy', {}).get('name', '?')
    ticker = run_cfg.get('ticker', 'BTC-USD')

    result = {
        'config_id': config_id,
        'strategy': strategy_name,
        'status': 'failed',
        'metrics': {},
        'daily_returns': [],
    }

    try:
        os.chdir(str(v12_dir))

        # Snapshot existing run dirs BEFORE execution
        runs_dir = v12_dir / "output" / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        existing_dirs = set(p.name for p in runs_dir.iterdir() if p.is_dir())

        # Register SopaDeOtoe (graduated) strategies
        import SopaDeOtoe.strategies  # noqa

        import importlib
        if 'main' in sys.modules:
            main_mod = importlib.reload(sys.modules['main'])
        else:
            main_mod = importlib.import_module('main')

        # Race-condition fix: v12.main._create_run_dir names output dirs
        # with second-precision timestamps. When N workers start in the
        # same second they all mkdir(exist_ok=True) the same directory
        # and overwrite each other's results.json. Monkey-patch to append
        # a unique per-config suffix so each worker gets its own dir.
        import hashlib as _hashlib
        from datetime import datetime as _dt, timezone as _tz
        _orig_create = getattr(main_mod, "_create_run_dir", None)
        _unique_suffix = _hashlib.md5(
            f"{config_id}:{os.getpid()}".encode()
        ).hexdigest()[:8]

        def _patched_create_run_dir(_cfg):
            ts = _dt.now(_tz.utc).strftime("%Y%m%d_%H%M%S")
            rd = Path(
                f"output/runs/{_cfg['ticker']}_"
                f"{_cfg.get('interval', '1d')}_{ts}_{_unique_suffix}"
            )
            rd.mkdir(parents=True, exist_ok=True)
            return rd

        main_mod._create_run_dir = _patched_create_run_dir
        try:
            main_mod.run(config_path=config_path, data_end_override=data_end)
        finally:
            if _orig_create is not None:
                main_mod._create_run_dir = _orig_create

        # Find the NEW run directory created by THIS worker.
        # Race-condition mitigation: match by (1) strategy name, then
        # (2) config_id embedded in results.json if v12 writes it,
        # (3) newest timestamp as final tiebreaker.
        from SopaDeOtoe.core.runner import _extract_metrics_from_results_json
        current_dirs = set(p.name for p in runs_dir.iterdir() if p.is_dir())
        new_dir_names = current_dirs - existing_dirs
        new_dirs = [
            runs_dir / name for name in new_dir_names
            if name.startswith(f"{ticker}_")
               and (runs_dir / name / "results.json").exists()
        ]

        run_dir = None
        if new_dirs:
            if len(new_dirs) == 1:
                run_dir = new_dirs[0]
            else:
                # Pass 1: strategy name + config_id match
                for d in sorted(new_dirs, key=lambda p: p.name, reverse=True):
                    try:
                        rdata = json.loads((d / "results.json").read_text())
                        rcfg = rdata.get('config', {})
                        rstrat = rcfg.get('strategy', {}).get('name', '')
                        if rstrat != strategy_name:
                            continue
                        r_config_id = rdata.get('config_id', '')
                        if r_config_id and r_config_id not in ('', 'unknown') and r_config_id != config_id:
                            continue
                        run_dir = d
                        break
                    except Exception:
                        continue
                # Pass 2: strategy name only (ignore config_id)
                if run_dir is None:
                    for d in sorted(new_dirs, key=lambda p: p.name, reverse=True):
                        try:
                            rdata = json.loads((d / "results.json").read_text())
                            rcfg = rdata.get('config', {})
                            rstrat = rcfg.get('strategy', {}).get('name', '')
                            if rstrat == strategy_name:
                                run_dir = d
                                break
                        except Exception:
                            continue
                # Pass 3: newest dir regardless of strategy
                if run_dir is None:
                    run_dir = sorted(new_dirs, key=lambda p: p.name, reverse=True)[0]

        if run_dir is not None:
            extracted = _extract_metrics_from_results_json(run_dir / "results.json")
            result['status'] = extracted['status']
            result['metrics'] = extracted['metrics']
            result['daily_returns'] = extracted['daily_returns']
            result['regime_summary'] = extracted.get('regime_summary', {})
            result['v1_vs_v2'] = extracted.get('v1_vs_v2', {})
            result['v12_run_dir'] = str(run_dir)
        else:
            # No new dir with results.json found — pipeline crashed mid-run
            new_incomplete = [
                runs_dir / name for name in new_dir_names
                if name.startswith(f"{ticker}_")
                   and not (runs_dir / name / "results.json").exists()
            ]
            result['status'] = 'error'
            result['error'] = (
                "results.json not found after main.run(). "
                f"New dirs: {len(new_dir_names)}, "
                f"with results: {len(new_dirs)}, "
                f"incomplete: {len(new_incomplete)}"
            )

    except Exception as e:
        result['status'] = 'error'
        result['error'] = f"{type(e).__name__}: {str(e)}"
        result['traceback'] = traceback.format_exc()

    # Write result
    serializable = json.loads(json.dumps(result, default=_serialize))
    Path(output_path).write_text(json.dumps(serializable, indent=2))


def run_signal_check(config_path: str, output_path: str):
    """
    Execute M1-M3 only (data→features→signals) for prefilter.

    Much faster than full pipeline — no triple-barrier, meta-model,
    or MonteCarlo.
    """
    v12_dir = _setup_paths()

    # Resolve to absolute path BEFORE chdir
    config_path = str(Path(config_path).resolve())
    output_path = str(Path(output_path).resolve())

    with open(config_path) as f:
        run_cfg = yaml.safe_load(f)

    config_id = run_cfg.pop('_config_id', 'unknown')
    data_end = run_cfg.pop('_data_end_override', None)

    result = {'config_id': config_id, 'status': 'error'}

    try:
        os.chdir(str(v12_dir))

        import SopaDeOtoe.strategies  # noqa
        from src import data_pipe, features
        from src.strategy import BaseStrategy
        from src.bar_scaling import scaling_config as _scaling_config

        cfg = run_cfg

        # [M1] Data
        df = data_pipe.get_bars(
            cfg['ticker'], cfg['start'], cfg['end'],
            interval=cfg.get('interval', '1d'),
            save_path=f"data/raw/{cfg['ticker']}.csv",
            bar_type=cfg.get('bar_type', 'time'),
            cfg=cfg,
        )

        if data_end:
            import pandas as pd
            df = df[df.index <= pd.Timestamp(data_end)]

        # Auto-BPD
        if cfg.get('bar_type') == 'dollar' and cfg.get('auto_bpd', False):
            bpd_actual = df.resample('D').size()
            bpd_actual = bpd_actual[bpd_actual > 0]
            cfg['bars_per_day'] = int(bpd_actual.median())

        # [M2] Features
        feat = features.base_features(df, cfg)
        feat = features.user_features(df, feat, cfg)
        feat['Close'] = df['Close']
        feat['Volume'] = df['Volume']
        feat['High'] = df['High']
        feat['Low'] = df['Low']

        # [M3] Signals
        strategy_name = cfg['strategy']['name']
        strategy_params = dict(cfg['strategy'].get('params', {}))

        sc = _scaling_config(cfg)
        scale = sc['scale']

        # Scale day-denominated params via the strategy's _scalable_params declaration.
        strategy_cls = BaseStrategy._REGISTRY[strategy_name]
        scalable = getattr(strategy_cls, '_scalable_params', None)

        if scalable is not None:
            for p in scalable:
                if p in strategy_params:
                    strategy_params[p] = scale(strategy_params[p])
        else:
            # Legacy: only scale fast/slow (backward compat)
            if 'fast' in strategy_params:
                strategy_params['fast'] = scale(strategy_params['fast'])
            if 'slow' in strategy_params:
                strategy_params['slow'] = scale(strategy_params['slow'])

        signals = BaseStrategy._REGISTRY[strategy_name](
            **strategy_params
        ).generate_signals(feat)

        n_signals = int((signals != 0).sum())
        n_long = int((signals > 0).sum())
        n_short = int((signals < 0).sum())
        n_bars = len(df)

        result = {
            'config_id': config_id,
            'status': 'success',
            'n_signals': n_signals,
            'n_long': n_long,
            'n_short': n_short,
            'n_bars': n_bars,
            'signal_rate': n_signals / max(n_bars, 1),
            'long_pct': n_long / max(n_signals, 1) if n_signals > 0 else 0.0,
        }

    except Exception as e:
        result['error'] = f"{type(e).__name__}: {str(e)}"
        result['traceback'] = traceback.format_exc()

    Path(output_path).write_text(json.dumps(result, default=_serialize))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='SopaDeOtoe Worker')
    parser.add_argument('--mode', required=True, choices=['full', 'signal'])
    parser.add_argument('--config', required=True, help='Path to config YAML')
    parser.add_argument('--output', required=True, help='Path to write result JSON')
    args = parser.parse_args()

    if args.mode == 'full':
        run_full_pipeline(args.config, args.output)
    else:
        run_signal_check(args.config, args.output)
