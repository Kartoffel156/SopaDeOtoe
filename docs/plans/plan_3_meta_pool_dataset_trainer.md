# Plan 3 de 5: `meta_pool/` core — dataset + trainer

**Objetivo**: Nuevo modulo que poolea datasets de las 7 estrategias y entrena el meta-modelo conjunto walk-forward OOS.

**Depende de**: Plan 2 (necesita parquets en `results/exploration/meta_datasets/`)

**Archivos a crear**:
- `SopaDeOtoe/meta_pool/__init__.py`
- `SopaDeOtoe/meta_pool/dataset.py`
- `SopaDeOtoe/meta_pool/trainer.py`

---

## dataset.py

### `load_strategy_export(meta_export_dir: Path) -> dict`

Carga los 7 parquets + 1 JSON de un directorio de export:

```python
return {
    'meta_feat': pd.read_parquet(meta_export_dir / "meta_feat.parquet"),
    'meta_labels': pd.read_parquet(meta_export_dir / "meta_labels.parquet")['label'],
    'weights': pd.read_parquet(meta_export_dir / "weights.parquet")['weight'],
    'labels': pd.read_parquet(meta_export_dir / "labels.parquet"),
    'side': pd.read_parquet(meta_export_dir / "side.parquet")['side'],
    'close': pd.read_parquet(meta_export_dir / "close.parquet")['Close'],
    'signal_times': pd.read_parquet(meta_export_dir / "signal_times.parquet")['signal_time'],
    'config': json.loads((meta_export_dir / "config_snapshot.json").read_text()),
}
```

### `validate_schemas(exports: dict[str, dict]) -> None`

Valida que las feature columns sean compatibles:
- Si difieren, imprime el diff (cuales features faltan en cuales estrategias)
- Si la interseccion es < 50% de la union, raise ValueError (demasiado dispares)
- Warning si difieren pero overlap es razonable (>50%)

Estilo PROD-02 del v12 existente.

### `pool_datasets(exports: dict[str, dict]) -> tuple[DataFrame, Series, Series, dict]`

```python
def pool_datasets(exports: dict[str, dict]) -> tuple[pd.DataFrame, pd.Series, pd.Series, dict]:
    """
    Poolea meta-datasets de multiples estrategias.
    
    Returns:
        X_pool   : pd.DataFrame — features pooled + strategy indicators
        y_pool   : pd.Series {0,1} — labels pooled
        w_pool   : pd.Series — weights normalizados
        metadata : dict — {strategy_id_map, n_rows_per_strategy, feature_columns,
                          close_series, per_strategy_data}
    """
```

**Logica clave**:

1. **Concat features**: `pd.concat([...], join='outer')` + `fillna(0)` para features que no todas las estrategias tienen (ej. `vpin` solo si order flow disponible)

2. **Strategy identity**: 
   - Columna `strategy_id` (int 0..N-1)
   - One-hot: `strat_H136`, `strat_H481`, etc.

3. **Normalizacion de weights**: 
   ```python
   for strat_name, data in exports.items():
       w = data['weights']
       w *= 1.0 / len(w)  # Igualar contribucion por estrategia
   # Normalizar total a len(y_pool)
   w_pool *= len(y_pool) / w_pool.sum()
   ```
   Sin esto, TSIMeanReversion (157 trades) dominaria sobre H86 (41 trades).

4. **Timestamps duplicados**: Diferentes estrategias pueden producir labels en el mismo bar. Jitter +1ms por strategy_id:
   ```python
   new_idx = original_idx + pd.Timedelta(milliseconds=strategy_id)
   ```

5. **Sort temporal**: El pool se ordena por timestamp para que WalkForwardCV funcione correctamente.

6. **Metadata** incluye:
   - `strategy_id_map`: `{name: int_id}`
   - `n_rows_per_strategy`: `{name: count}`
   - `feature_columns`: lista ordenada de features (para validacion PROD-02)
   - `close_series`: `df['Close']` (deberia ser identica entre las 7 estrategias — todas usan `base_dollar_btc.yaml`)
   - `per_strategy_data`: `{name: {side, labels, signal_times, config}}` para gating/replay posterior

---

## trainer.py

Importa de v12 via `_path_setup`:
- `from src.cross_validation import WalkForwardCV` (line 621 de cross_validation.py)
- `from src.models import train_meta_model` (line 314 de models.py)

### `train_pooled_meta_model(X_pool, y_pool, w_pool, cfg, n_splits=5, embargo_pct=0.01, mode='expanding') -> tuple[clf, pd.Series]`

**Walk-forward OOS**:

```python
wfcv = WalkForwardCV(n_splits=n_splits, embargo_pct=embargo_pct, mode=mode)

oos_proba = pd.Series(0.5, index=X_pool.index)  # default neutral

for fold_i, (train_idx, test_idx) in enumerate(wfcv.split(X_pool)):
    X_train, y_train = X_pool.iloc[train_idx], y_pool.iloc[train_idx]
    w_train = w_pool.iloc[train_idx]
    
    fold_clf = train_meta_model(X_train, y_train, w_train, cfg)
    
    proba_test = fold_clf.predict_proba(X_pool.iloc[test_idx])[:, 1]
    oos_proba.iloc[test_idx] = proba_test

# Modelo final entrenado en TODO el pool (para persistencia/produccion)
clf = train_meta_model(X_pool, y_pool, w_pool, cfg)

return clf, oos_proba
```

**Detalles criticos**:
- NUNCA usar predict in-sample (el bug documentado de `pipeline_meta.py` es el anti-ejemplo)
- Rows del primer fold (seed) quedan con P=0.5 (neutral, misma convencion que v12/main.py line 833)
- `feature_prefilter` se **desactiva** con N pooled grande (~1500-2500) como indica el documento
- Guardar `fold_classifiers` lista para auditoria

### `train_null_model(X_pool, y_pool) -> pd.Series`

```python
from sklearn.dummy import DummyClassifier
dummy = DummyClassifier(strategy='prior')
# Mismo walk-forward pero con DummyClassifier
# Returns oos_proba del null model para comparacion G4
```

### `extract_strategy_probas(oos_proba, pool_metadata) -> dict[str, pd.Series]`

Revierte el pooling: para cada estrategia, filtra filas por `strategy_id`, mapea de vuelta a timestamps originales (deshaciendo el jitter).

```python
result = {}
for name, sid in pool_metadata['strategy_id_map'].items():
    mask = strategy_ids == sid
    probas = oos_proba[mask].copy()
    probas.index = probas.index - pd.Timedelta(milliseconds=sid)  # deshacer jitter
    result[name] = probas
return result
```

---

## Verificacion

1. Crear pool sintetico de 2 estrategias (features random, labels random)
2. `pool_datasets()`: verificar shape = suma de individuales, strategy indicators presentes
3. `train_pooled_meta_model()`: verificar `oos_proba` length == `X_pool`, valores en [0, 1]
4. `extract_strategy_probas()`: verificar que cada estrategia recupera su proba series con index original
5. Con `random_state=42`, resultados reproducibles
6. Con las 7 estrategias reales: N pooled >= 1000 (gate G1)
