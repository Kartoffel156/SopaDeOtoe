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
    python -m SopaDeOtoe.core.worker --mode export --config /tmp/cfg.yaml --output /tmp/result.json
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
            f"{config_id}".encode()
        ).hexdigest()[:12]

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


def run_export_pipeline(config_path: str, output_path: str):
    """
    Execute M1-M4 + meta-features inline and export to parquets.

    Extends run_signal_check (M1-M3) with triple-barrier labels,
    meta-labels, sample weights, and meta-features. Serializes
    everything to parquets for downstream pooled meta-model training.
    """
    import pandas as pd

    v12_dir = _setup_paths()
    _sopa_dir = Path(__file__).resolve().parent.parent

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
        from src import data_pipe, features, labeling, models
        from src.strategy import BaseStrategy
        from src.bar_scaling import scaling_config as _scaling_config
        from src.sample_weights import sample_uniqueness

        cfg = run_cfg
        strategy_name = cfg['strategy']['name']

        # ── M1: Data (identical to run_signal_check) ──
        df = data_pipe.get_bars(
            cfg['ticker'], cfg['start'], cfg['end'],
            interval=cfg.get('interval', '1d'),
            save_path=f"data/raw/{cfg['ticker']}.csv",
            bar_type=cfg.get('bar_type', 'time'),
            cfg=cfg,
        )

        if data_end:
            df = df[df.index <= pd.Timestamp(data_end)]

        if cfg.get('bar_type') == 'dollar' and cfg.get('auto_bpd', False):
            bpd_actual = df.resample('D').size()
            bpd_actual = bpd_actual[bpd_actual > 0]
            cfg['bars_per_day'] = int(bpd_actual.median())

        # ── M2: Features (identical to run_signal_check) ──
        feat = features.base_features(df, cfg)
        feat = features.user_features(df, feat, cfg)
        feat['Close'] = df['Close']
        feat['Volume'] = df['Volume']
        feat['High'] = df['High']
        feat['Low'] = df['Low']

        # ── M3: Signals (identical to run_signal_check) ──
        strategy_params = dict(cfg['strategy'].get('params', {}))

        sc = _scaling_config(cfg)
        scale = sc['scale']

        strategy_cls = BaseStrategy._REGISTRY[strategy_name]
        scalable = getattr(strategy_cls, '_scalable_params', None)

        if scalable is not None:
            for p in scalable:
                if p in strategy_params:
                    strategy_params[p] = scale(strategy_params[p])
        else:
            if 'fast' in strategy_params:
                strategy_params['fast'] = scale(strategy_params['fast'])
            if 'slow' in strategy_params:
                strategy_params['slow'] = scale(strategy_params['slow'])

        signals = BaseStrategy._REGISTRY[strategy_name](
            **strategy_params
        ).generate_signals(feat)

        # ── M3b: Signal times + side (main.py L333-358) ──
        cusum_cfg = cfg.get('cusum_filter', {})
        if cusum_cfg.get('enabled', False) and cusum_cfg.get('mode') == 'primary':
            from src.labeling import cusum_filter
            signal_times, side = cusum_filter(
                df['Close'], h=float(cusum_cfg.get('h', 0.02))
            )
        else:
            signal_times = signals[signals != 0].index
            side = signals.loc[signal_times]

        # ── M4: Triple-barrier (main.py L362-366) ──
        labels = labeling.triple_barrier(
            df['Close'], signal_times, cfg['pt_sl'],
            scale(cfg['max_holding']),
            side=side,
            vol_span=scale(100),
        )

        # ── M4b: Meta-labels + weights + meta-features (main.py L448-491) ──
        meta_labels = models.derive_meta_labels(labels, side)
        weights = sample_uniqueness(labels, df['Close'])
        feat['signal_side'] = side.reindex(feat.index, method='ffill').fillna(0)

        # Regime detection (if enabled)
        _regime_cfg = cfg.get('regime', {})
        if _regime_cfg.get('enabled', False):
            from src.regime import classify_regimes
            _regime_labels_df = classify_regimes(feat, cfg)
            if len(_regime_labels_df.columns) > 0:
                feat = pd.concat([feat, _regime_labels_df], axis=1)

        # Meta-features
        meta_feat_raw = models.meta_features(feat, cfg)

        # Align indices
        valid_idx = meta_feat_raw.dropna().index
        meta_feat = meta_feat_raw.loc[valid_idx]
        meta_labels_fit = meta_labels.reindex(valid_idx).dropna()
        weights_fit = weights.reindex(meta_labels_fit.index).fillna(weights.mean())

        # Guard BUG-14: insufficient samples
        if len(meta_labels_fit) < 10:
            result['error'] = f"Only {len(meta_labels_fit)} meta-label samples (min 10)"
            Path(output_path).write_text(json.dumps(result, default=_serialize))
            return

        # ── EXPORT: serialize to parquets ──
        export_dir = _sopa_dir / "results" / "exploration" / "meta_datasets" / strategy_name
        export_dir.mkdir(parents=True, exist_ok=True)

        meta_feat.to_parquet(export_dir / "meta_feat.parquet")
        meta_labels_fit.to_frame("label").to_parquet(export_dir / "meta_labels.parquet")
        weights_fit.to_frame("weight").to_parquet(export_dir / "weights.parquet")
        labels.to_parquet(export_dir / "labels.parquet")
        side.to_frame("side").to_parquet(export_dir / "side.parquet")
        df['Close'].to_frame("Close").to_parquet(export_dir / "close.parquet")
        pd.Series(signal_times, name="signal_time").to_frame().to_parquet(
            export_dir / "signal_times.parquet"
        )

        # Config snapshot
        config_snapshot = {
            'strategy_name': strategy_name,
            'config_id': config_id,
            'ticker': cfg.get('ticker', ''),
            'bar_type': cfg.get('bar_type', ''),
            'cost': cfg.get('cost', 0),
            'slippage_bps': cfg.get('slippage_bps', 0),
            'spread_bps': cfg.get('spread_bps', 0),
            'initial_capital': cfg.get('initial_capital', 0),
            'pt_sl': cfg.get('pt_sl', []),
            'max_holding': cfg.get('max_holding', 0),
            'strategy_params': dict(cfg['strategy'].get('params', {})),
        }
        (export_dir / "config_snapshot.json").write_text(
            json.dumps(config_snapshot, default=_serialize, indent=2)
        )

        n_signals = int((signals != 0).sum())
        result = {
            'config_id': config_id,
            'status': 'success',
            'strategy': strategy_name,
            'n_signals': n_signals,
            'n_meta_samples': len(meta_labels_fit),
            'n_features': len(meta_feat.columns),
            'feature_columns': list(meta_feat.columns),
            'export_dir': str(export_dir),
        }

    except Exception as e:
        result['error'] = f"{type(e).__name__}: {str(e)}"
        result['traceback'] = traceback.format_exc()

    Path(output_path).write_text(json.dumps(result, default=_serialize))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='SopaDeOtoe Worker')
    parser.add_argument('--mode', required=True, choices=['full', 'signal', 'export'])
    parser.add_argument('--config', required=True, help='Path to config YAML')
    parser.add_argument('--output', required=True, help='Path to write result JSON')
    args = parser.parse_args()

    if args.mode == 'full':
        run_full_pipeline(args.config, args.output)
    elif args.mode == 'export':
        run_export_pipeline(args.config, args.output)
    else:
        run_signal_check(args.config, args.output)
