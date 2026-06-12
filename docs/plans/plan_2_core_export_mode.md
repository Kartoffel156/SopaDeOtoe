# Plan 2 de 5: SopaDeOtoe core `--mode export`

**Objetivo**: Nuevo modo en worker.py que inyecta `meta_model_mode: export_only` y recolecta artefactos parquet.

**Depende de**: Plan 1 (v12 export_only mode debe existir)

**Archivos a modificar**:
- `SopaDeOtoe/core/worker.py`
- `SopaDeOtoe/core/runner.py`

---

## Cambios en worker.py

### Nueva funcion `run_export_pipeline(config_path, output_path)`

Sigue la misma estructura que `run_full_pipeline()` (lines 53-209) con estas diferencias:

1. **Antes de `main_mod.run()`**: inyectar el modo export en el config
   ```python
   run_cfg.setdefault('v2', {})['meta_model_mode'] = 'export_only'
   ```

2. **Despues de encontrar run_dir** (misma logica de 3-pass matching, lines 131-177):
   ```python
   meta_export = run_dir / "meta_export"
   if meta_export.exists():
       result['status'] = 'success'
       result['meta_export_dir'] = str(meta_export)
       result['v12_run_dir'] = str(run_dir)
   else:
       result['status'] = 'error'
       result['error'] = 'meta_export directory not found after export_only run'
   ```

3. **Copiar artefactos** a ubicacion centralizada:
   ```python
   dest = _SOPA_DIR / "results" / "exploration" / "meta_datasets" / strategy_name
   shutil.copytree(meta_export, dest, dirs_exist_ok=True)
   result['local_meta_export'] = str(dest)
   ```

### Actualizar argparse (line 322)

```python
# Antes:
choices=['full', 'signal']

# Despues:
choices=['full', 'signal', 'export']
```

### Agregar dispatch (tras line 330)

```python
elif args.mode == 'export':
    run_export_pipeline(args.config, args.output)
```

---

## Cambios en runner.py

### Nueva funcion `run_export()`

```python
def run_export(
    configs: list[dict],
    base_config_path: str | None = None,
    data_end_override: str | None = None,
    n_jobs: int = DEFAULT_JOBS,
    output_dir: Path | None = None,
) -> list[dict]:
    """
    Run v12 pipeline en export_only mode para cada config.
    Returns list of dicts con 'meta_export_dir' y 'v12_run_dir'.
    """
```

Identica a `run_exploration()` (lines 268-372) pero:
- Pasa `'export'` en vez de `'full'` a `_run_single_subprocess`
- Banner de print cambia a "Executing N configs via v12 pipeline (EXPORT mode)"
- El status check reporta `meta_export_dir` en vez de sharpe

---

## Artefactos resultantes

Tras correr `run_export()` con las 7 graduadas:

```
results/exploration/meta_datasets/
  HypothesisH136GoldenDeathCrossAsym/
    meta_feat.parquet
    meta_labels.parquet
    weights.parquet
    labels.parquet
    side.parquet
    close.parquet
    signal_times.parquet
    config_snapshot.json
  HypothesisH481GoldenCrossPSAR/
    ...
  HypothesisH203VolExpansionEntry/
    ...
  HypothesisH371MaxMinDualTriggerFreq/
    ...
  HypothesisH37DynamicGridInformedGate/
    ...
  HypothesisH86WonhamMarkovRefinado/
    ...
  TSIMeanReversion/
    ...
```

---

## Verificacion

1. Correr: `python -m SopaDeOtoe.core.worker --mode export --config /tmp/test.yaml --output /tmp/result.json`
2. Confirmar que result JSON contiene `meta_export_dir` apuntando a parquets validos
3. Desde Python: `run_export(configs, n_jobs=2)` con 2 configs de test, verificar ambos producen `meta_export_dir`
4. Verificar que `run_exploration()` sigue funcionando sin cambios (regression)
5. Confirmar que los parquets se copiaron a `results/exploration/meta_datasets/<strategy>/`
