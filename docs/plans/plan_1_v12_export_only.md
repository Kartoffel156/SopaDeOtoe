# Plan 1 de 5: v12 `export_only` mode

**Objetivo**: Salida temprana en v12/main.py que serializa meta_feat + labels a parquet sin entrenar el meta-modelo.

**Depende de**: Nada (primer plan)

**Archivo a modificar**: `StrategyParrot/v12/main.py`

---

## Cambios

### 1a. Leer config key (~line 105)

Tras `v2_cfg = cfg.get('v2', {})`:

```python
_meta_model_mode = v2_cfg.get('meta_model_mode', 'full')  # 'full' | 'export_only'
```

No rompe nada: cuando `meta_model_mode` esta ausente o es `'full'`, el comportamiento es identico al actual.

### 1b. Bloque export (tras line 490)

Despues de que `meta_feat`, `meta_labels_fit`, `weights_fit`, `labels`, `side`, `df['Close']` estan alineados, ANTES del guard `_MIN_META_SAMPLES` (line 499):

```python
if _meta_model_mode == 'export_only':
    _export_dir = run_dir / "meta_export"
    _export_dir.mkdir(exist_ok=True)

    meta_feat.to_parquet(_export_dir / "meta_feat.parquet")
    meta_labels_fit.to_frame("label").to_parquet(_export_dir / "meta_labels.parquet")
    weights_fit.to_frame("weight").to_parquet(_export_dir / "weights.parquet")
    labels.to_parquet(_export_dir / "labels.parquet")
    side.to_frame("side").to_parquet(_export_dir / "side.parquet")
    df['Close'].to_frame("Close").to_parquet(_export_dir / "close.parquet")
    pd.Series(signal_times, name="signal_time").to_frame().to_parquet(
        _export_dir / "signal_times.parquet"
    )

    # Config snapshot para audit
    import json as _json
    (_export_dir / "config_snapshot.json").write_text(
        _json.dumps({
            "strategy_name": cfg['strategy']['name'],
            "config_id": cfg.get('_config_id', 'unknown'),
            "ticker": cfg['ticker'],
            "cost": cfg['cost'],
            "slippage_bps": v2_cfg.get('slippage_bps', 0.0),
            "spread_bps": v2_cfg.get('spread_bps', 0.0),
            "initial_capital": cfg['initial_capital'],
            "bet_sizing_step": v2_cfg.get('bet_sizing_step', 0.01),
            "min_rebalance": v2_cfg.get('min_rebalance', 0.0),
        }, indent=2)
    )

    print(f"[EXPORT] meta_export written to {_export_dir} — "
          f"{len(meta_feat)} rows, {len(meta_feat.columns)} features")

    # results.json minimo para que worker.py pueda encontrar el run_dir
    _min_results = {
        "config": _sanitize_for_json(cfg),
        "metrics": {},
        "equity_curve": {"dates": [], "values": []},
        "trade_stats": {},
        "meta_export_dir": str(_export_dir),
        "export_only": True,
    }
    (run_dir / "results.json").write_text(
        json.dumps(_min_results, indent=2, default=_safe_float)
    )
    return  # Salida temprana — saltar M5 backtest, M6 risk, etc.
```

---

## Contrato parquet (`run_dir/meta_export/`)

| Archivo | Contenido | Index |
|---------|-----------|-------|
| `meta_feat.parquet` | Features del meta-modelo (N columnas) | DatetimeIndex (t0) |
| `meta_labels.parquet` | col `label` {0,1} | DatetimeIndex |
| `weights.parquet` | col `weight` float (0,1] | DatetimeIndex |
| `labels.parquet` | cols `t1, ret, label, barrier, side` | DatetimeIndex |
| `side.parquet` | col `side` {-1,+1} | DatetimeIndex |
| `close.parquet` | col `Close` (serie completa de dollar bars) | DatetimeIndex |
| `signal_times.parquet` | col `signal_time` | RangeIndex |
| `config_snapshot.json` | strategy_name, cost, slippage_bps, spread_bps, initial_capital, bet_sizing_step, min_rebalance | N/A |

### Reconciliacion de nombres (doc vs codigo real)

- Doc dice `label_ret` -> en v12 la columna es `labels['ret']`
- Doc dice `close_common` -> en v12 es `df['Close']`
- Doc dice `meta_dataset.parquet` monolitico -> separamos en 7 parquets para debugging

---

## Verificacion

1. Configurar un YAML de test con `v2.meta_model_mode: export_only`
2. Correr `python main.py config/test_export.yaml`
3. Confirmar que `run_dir/meta_export/` contiene 7 parquets + 1 JSON
4. Confirmar que `results.json` existe con `export_only: true`
5. Confirmar que NO se genera output de backtest (equity_curve vacio)
6. Leer cada parquet y verificar dtypes, DatetimeIndex, no-empty
