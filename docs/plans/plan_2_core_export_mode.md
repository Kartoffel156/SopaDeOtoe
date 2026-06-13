# Plan 2 de 5: SopaDeOtoe core `--mode export` (REVISADO — absorbe Plan 1)

**Objetivo**: Nueva funcion `run_export_pipeline()` en worker.py que corre M1-M4 + meta-features inline (sin llamar a `main.run()`) y serializa a parquets. Cero cambios en StrategyParrot.

**Depende de**: Nada (primer plan activo)

**Archivos a modificar**:
- `SopaDeOtoe/core/worker.py`
- `SopaDeOtoe/core/runner.py`

---

## Diseno: por que inline y no main.run()

`run_signal_check()` (worker.py:212) ya establece el patron: importa de v12 (`from src import data_pipe, features`) y corre M1-M3 sin llamar a `main.run()`. Extendemos el mismo patron a M1-M4 + meta-features.

**Ventajas**:
- Cero cambios en StrategyParrot — todo queda en la branch de SopaDeOtoe
- Si v12 cambia una firma, el export falla ruidosamente (ImportError/TypeError), no silenciosamente
- El export es ~60 lines mas que run_signal_check — todo son calls a funciones puras de v12

---

## worker.py: nueva funcion `run_export_pipeline()`

### Estructura

```
run_export_pipeline(config_path, output_path)
│
├── _setup_paths() + os.chdir(v12_dir)     # identico a run_signal_check
├── Imports de v12:
│   ├── from src import data_pipe, features, labeling
│   ├── from src import models                          # NUEVO vs signal_check
│   ├── from src.sample_weights import sample_uniqueness # NUEVO
│   └── from src.strategy import BaseStrategy
│
├── M1: Data     (idéntico a run_signal_check L243-260)
│   └── data_pipe.get_bars() + data_end filter + auto-BPD
│
├── M2: Features (idéntico a run_signal_check L262-268)
│   └── base_features() + user_features() + inyectar Close/Volume/High/Low
│
├── M3: Signals  (idéntico a run_signal_check L270-294)
│   └── scaling + generate_signals()
│
├── M3b: Signal times + side  (NUEVO — replica main.py L333-358)
│   ├── Si CUSUM primary: cusum_filter() → signal_times, side
│   └── Si no: signal_times = signals[!=0].index, side = signals[signal_times]
│
├── M4: Triple-barrier  (NUEVO — replica main.py L362-366)
│   └── labeling.triple_barrier(close, signal_times, pt_sl, max_holding, side, vol_span)
│
├── M4b: Meta-pipeline  (NUEVO — replica main.py L448-491)
│   ├── meta_labels = models.derive_meta_labels(labels, side)
│   ├── weights = sample_uniqueness(labels, df['Close'])
│   ├── feat['signal_side'] = side.reindex(...).ffill()      # BUG-SHORT-01
│   ├── Regime detection (si enabled)
│   ├── meta_feat_raw = models.meta_features(feat, cfg)
│   ├── Alinear: valid_idx → meta_feat, meta_labels_fit, weights_fit
│   └── Guard BUG-14: if len < 10 → error, return
│
└── EXPORT: serializar a parquets
    └── 7 parquets + 1 JSON → results/exploration/meta_datasets/<strategy>/
```

### Codigo clave (M3b + M4 + M4b — las partes nuevas vs run_signal_check)

```python
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

# Regime (si enabled)
_regime_cfg = cfg.get('regime', {})
if _regime_cfg.get('enabled', False):
    from src.regime import classify_regimes
    _regime_labels_df = classify_regimes(feat, cfg)
    if len(_regime_labels_df.columns) > 0:
        feat = pd.concat([feat, _regime_labels_df], axis=1)

# Meta-features
meta_feat_raw = models.meta_features(feat, cfg)

# Alinear
valid_idx = meta_feat_raw.dropna().index
meta_feat = meta_feat_raw.loc[valid_idx]
meta_labels_fit = meta_labels.reindex(valid_idx).dropna()
weights_fit = weights.reindex(meta_labels_fit.index).fillna(weights.mean())

# Guard BUG-14
if len(meta_labels_fit) < 10:
    result['error'] = f"Only {len(meta_labels_fit)} meta-label samples (min 10)"
    Path(output_path).write_text(json.dumps(result, default=_serialize))
    return
```

### Export a parquets

Escribe directamente a `results/exploration/meta_datasets/<strategy_name>/`:

```python
export_dir = _SOPA_DIR / "results" / "exploration" / "meta_datasets" / strategy_name
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
# + config_snapshot.json con cost, slippage_bps, spread_bps, initial_capital, etc.
```

### Cambios al argparse y dispatch (L319-330)

```python
parser.add_argument('--mode', required=True, choices=['full', 'signal', 'export'])

if args.mode == 'full':
    run_full_pipeline(args.config, args.output)
elif args.mode == 'export':
    run_export_pipeline(args.config, args.output)
else:
    run_signal_check(args.config, args.output)
```

---

## runner.py: nueva funcion `run_export()`

Identica a `run_exploration()` (L268-372) con estas diferencias:
- Pasa `'export'` en vez de `'full'` a `_run_single_subprocess`
- Banner: "Executing N configs via v12 pipeline (EXPORT mode)"
- Status report: `n_meta_samples` y `n_features` en vez de sharpe

```python
def run_export(
    configs: list[dict],
    base_config_path: str | None = None,
    data_end_override: str | None = None,
    n_jobs: int = DEFAULT_JOBS,
    output_dir: Path | None = None,
) -> list[dict]:
    """Run v12 pipeline en export mode — produce meta-dataset parquets."""
```

---

## Contrato de parquets (sin cambios)

| Archivo | Contenido | Index |
|---------|-----------|-------|
| `meta_feat.parquet` | Features del meta-modelo (N cols) | DatetimeIndex (t0) |
| `meta_labels.parquet` | col `label` {0,1} | DatetimeIndex |
| `weights.parquet` | col `weight` float (0,1] | DatetimeIndex |
| `labels.parquet` | cols `t1, ret, label, barrier, side` | DatetimeIndex |
| `side.parquet` | col `side` {-1,+1} | DatetimeIndex |
| `close.parquet` | col `Close` (dollar bars) | DatetimeIndex |
| `signal_times.parquet` | col `signal_time` | RangeIndex |
| `config_snapshot.json` | strategy_name, cost, slippage, etc. | N/A |

---

## Codigo replicado de main.py — inventario de riesgo

| Bloque | Lines main.py | Ya existe en worker.py? | Riesgo divergencia |
|--------|--------------|------------------------|-------------------|
| M1 Data | 246-262 | Si (run_signal_check) | Bajo |
| M2 Features | 263-268 | Si (run_signal_check) | Bajo |
| M3 Signals | 293-316 | Si (run_signal_check) | Bajo |
| M3b CUSUM | 333-358 | No — 10 lines nuevas | Bajo (config dispatch) |
| M4 Triple barrier | 362-366 | No — 1 call nueva | Bajo (funcion pura) |
| M4b Meta-pipeline | 448-491 | No — 40 lines nuevas | Medio (logica de alineacion) |

**Total nuevo**: ~60 lines. Todo son calls a funciones importadas de v12 — no hay logica inline compleja.

---

## Impacto en Plans 3-5

**Cero**. Plans 3-5 consumen parquets de `results/exploration/meta_datasets/`. No les importa quien los escribio.

---

## Verificacion

1. `python -m SopaDeOtoe.core.worker --mode export --config /tmp/test.yaml --output /tmp/result.json`
2. Confirmar `results/exploration/meta_datasets/<strategy>/` con 7 parquets + 1 JSON
3. Result JSON: `status: success`, `n_meta_samples > 0`, `feature_columns` no vacio
4. Regression: `run_signal_check()` y `run_full_pipeline()` sin cambios
5. Leer cada parquet: dtypes correctos, DatetimeIndex, no-empty
6. Correr 7 graduadas: `run_export(configs, n_jobs=4)` → 7 directorios
