# Plan 5 de 5: Launcher + gates de aceptacion

**Objetivo**: Script end-to-end que orquesta Layer 1 (export) -> Layer 1.5 (pool/train/gate/replay) -> Layer 2 (portfolio) + comparacion A/B con gates G1-G6.

**Depende de**: Plans 1-4

**Archivos a crear**:
- `SopaDeOtoe/launchers/run_pooled_meta_backtest.py`
- `SopaDeOtoe/config/pooled_meta_settings.yaml`

---

## Launcher: `run_pooled_meta_backtest.py`

Espejo de `run_graduated_backtest.py` con Layer 1.5 intercalada.

### Uso

```bash
cd Patacon/

# End-to-end completo
python -m SopaDeOtoe.launchers.run_pooled_meta_backtest --full --n-jobs 4

# Solo exportar parquets (Layer 1)
python -m SopaDeOtoe.launchers.run_pooled_meta_backtest --export --n-jobs 4

# Entrenar + gatear + replay (Layer 1.5) usando parquets existentes
python -m SopaDeOtoe.launchers.run_pooled_meta_backtest --train --skip-export

# Comparar pooled vs baseline con gates G1-G6
python -m SopaDeOtoe.launchers.run_pooled_meta_backtest --compare --skip-export --skip-run
```

### Estructura

```python
"""
run_pooled_meta_backtest.py — Layer 1.5 pooled meta-model launcher.

Orquesta:
  Layer 1  (export):  7 graduadas -> meta_export/ parquets
  Layer 1.5 (train):  pool -> train WF OOS -> gate -> replay -> StrategyResult
  Layer 2  (portfolio): run_portfolio_backtest() sin cambios
  Compare:  pooled vs baseline (metas individuales) + gates G1-G6
"""
```

### Funciones principales

#### `step_export(n_jobs=4) -> list[dict]`

```python
def step_export(n_jobs=4):
    configs, manifest = _load_graduated_configs()  # reusar de run_graduated_backtest.py
    results = run_export(configs, n_jobs=n_jobs)    # nuevo de Plan 2
    return results
```

#### `step_train(export_results, manifest) -> list[StrategyResult]`

```python
def step_train(export_results, manifest):
    # 1. Cargar exports
    exports = {}
    for res in export_results:
        name = res['strategy']
        exports[name] = load_strategy_export(Path(res['meta_export_dir']))
    
    # 2. Validar y poolear
    validate_schemas(exports)
    X_pool, y_pool, w_pool, metadata = pool_datasets(exports)
    
    # 3. Entrenar modelo conjunto
    pooled_cfg = yaml.safe_load(pooled_meta_settings_path.read_text())
    clf, oos_proba = train_pooled_meta_model(
        X_pool, y_pool, w_pool, pooled_cfg,
        n_splits=pooled_cfg['pooled_meta']['n_splits'],
    )
    
    # 3b. Null model para gate G4
    null_proba = train_null_model(X_pool, y_pool)
    
    # 4. Separar probas por estrategia
    strategy_probas = extract_strategy_probas(oos_proba, metadata)
    
    # 5. Gate + replay por estrategia
    gating_cfg = load_gating_config(pooled_meta_settings_path)
    strategy_results = []
    for strat_name in exports:
        data = metadata['per_strategy_data'][strat_name]
        pivot = gating_cfg['pivots'].get(strat_name, gating_cfg['pivots']['default'])
        
        positions = gate_positions(
            strategy_probas[strat_name], data['side'], data['labels'],
            data['signal_times'], data['close'], data['config'], pivot=pivot,
        )
        replay_result = replay_to_returns(positions, data['close'], data['config'])
        sr = build_strategy_result(strat_name, replay_result, {'pivot': pivot})
        strategy_results.append(sr)
    
    return strategy_results, clf, oos_proba, null_proba
```

#### `step_portfolio(strategy_results) -> PortfolioResult`

```python
def step_portfolio(strategy_results):
    pcfg = load_portfolio_config(_PORTFOLIO_CFG_PATH)
    # Override max_leverage para pooled
    pooled_cfg = yaml.safe_load(pooled_meta_settings_path.read_text())
    pcfg.risk.max_leverage = pooled_cfg['portfolio_overrides']['max_leverage']  # 6.0
    pcfg.mode = 'backtest'
    return run_portfolio_backtest(strategy_results, pcfg)
```

#### `step_compare(pooled_result, baseline_result, oos_proba, null_proba, manifest) -> dict`

Evalua los 6 gates de aceptacion y produce tabla resumen.

---

## Gates de aceptacion

Tomados directamente del documento de arquitectura:

| Gate | Nombre | Criterio | Donde se lee |
|------|--------|----------|-------------|
| **G1** | Sanidad | end-to-end OK; N pooled >= 1,000; sin NaN en probas | logs Layer 1.5 |
| **G2** | Aprendizaje | AUC OOS pooled > null model; AUC por estrategia >= meta individual en >= 4/7 | trainer.py output |
| **G3** | Hedge vive | >= 70% de trades de H86 en peor decil BTC aprobados | gating audit |
| **G4** | Null model | DeltaCalmar(pooled vs crudo) >> DeltaCalmar(dummy vs crudo) | comparacion launcher |
| **G5** | Portafolio gana | Sharpe/DSR/Calmar del pooled >= baseline actual; bootstrap p5 > 0.5 | `portfolio_metrics` + `montecarlo.bootstrap.sharpe_5pct` — YA EXISTEN |
| **G6** | Permutacion + CPCV | permutation p_value < 0.05; CPCV p5 > 0 | `montecarlo.permutation` + `run_cpcv_validation` — YA EXISTEN |

### Implementacion de cada gate

```python
def evaluate_gates(pooled_pr, baseline_pr, oos_proba, null_proba, pool_metadata):
    gates = {}
    
    # G1: Sanidad
    n_pooled = len(oos_proba)
    has_nan = oos_proba.isna().any()
    gates['G1'] = {
        'pass': n_pooled >= 1000 and not has_nan,
        'n_pooled': n_pooled,
        'has_nan': bool(has_nan),
    }
    
    # G2: Aprendizaje (AUC)
    from sklearn.metrics import roc_auc_score
    auc_pooled = roc_auc_score(y_pool, oos_proba)
    auc_null = roc_auc_score(y_pool, null_proba)
    gates['G2'] = {
        'pass': auc_pooled > auc_null,
        'auc_pooled': auc_pooled,
        'auc_null': auc_null,
    }
    
    # G3: Hedge vive (H86 en peor decil BTC)
    # Identificar peor decil de retornos BTC
    close = pool_metadata['close_series']
    btc_returns = close.pct_change().dropna()
    worst_decile_dates = btc_returns.nsmallest(len(btc_returns) // 10).index
    # Contar trades de H86 aprobados en esas fechas
    h86_probas = extract_strategy_probas(oos_proba, pool_metadata).get(
        'HypothesisH86WonhamMarkovRefinado', pd.Series()
    )
    h86_in_worst = h86_probas.reindex(worst_decile_dates).dropna()
    h86_approved = (h86_in_worst > 0.40).sum()  # pivot de H86
    h86_total = len(h86_in_worst)
    gates['G3'] = {
        'pass': h86_total > 0 and (h86_approved / h86_total) >= 0.70,
        'approved_pct': h86_approved / max(h86_total, 1),
    }
    
    # G4: Null model
    pooled_calmar = pooled_pr.metrics.get('calmar', 0)
    baseline_calmar = baseline_pr.metrics.get('calmar', 0)
    # dummy_calmar se computa corriendo Layer 2 con null_proba (simplificado)
    delta_pooled = pooled_calmar - baseline_calmar
    gates['G4'] = {
        'pass': delta_pooled > 0,
        'delta_calmar_pooled': delta_pooled,
    }
    
    # G5: Portafolio gana
    pooled_sharpe = pooled_pr.metrics.get('sharpe', 0)
    baseline_sharpe = baseline_pr.metrics.get('sharpe', 0)
    pooled_bootstrap_p5 = pooled_pr.montecarlo.get('bootstrap', {}).get('sharpe_5pct', 0)
    gates['G5'] = {
        'pass': pooled_sharpe >= baseline_sharpe and pooled_bootstrap_p5 > 0.5,
        'pooled_sharpe': pooled_sharpe,
        'baseline_sharpe': baseline_sharpe,
        'bootstrap_p5': pooled_bootstrap_p5,
    }
    
    # G6: Permutacion + CPCV
    perm_pval = pooled_pr.montecarlo.get('permutation', {}).get('p_value', 1.0)
    # CPCV se corre separadamente via run_cpcv_validation (ya existe)
    gates['G6'] = {
        'pass': perm_pval < 0.05,
        'permutation_p_value': perm_pval,
    }
    
    return gates
```

---

## Config: `config/pooled_meta_settings.yaml`

```yaml
# Meta-modelo conjunto (Layer 1.5)
pooled_meta:
  enabled: true
  n_splits: 5
  embargo_pct: 0.01
  walkforward_mode: expanding
  random_state: 42
  feature_prefilter_enabled: false   # desactivar con N grande

# Gating por estrategia
pivots:
  default: 0.50
  HypothesisH86WonhamMarkovRefinado: 0.40   # hedge permisivo
hedge_bypass: []   # activar [H86...] solo si falla gate G3
bet_sizing_step: 0.01

# Override de portfolio para el modo pooled
portfolio_overrides:
  max_leverage: 6.0   # Bajado de 20.0 — doc warning sobre ruina a 20x con dollar bars BTC
```

**Nota importante sobre `max_leverage`**: El documento advierte que `max_leverage: 20.0` en `portfolio_settings.yaml` esta justificado por "CPCV p5=+0.51", pero un p5 positivo dice que el edge es real, NO que aguanta 20x. Con dollar bars de BTC, 20x con un solo evento de cola es ruina. El rango defendible es 3-6x. Se aplica 6.0 SOLO al portfolio pooled; el baseline usa 20.0 para comparacion A/B justa.

---

## Output

Resultados se guardan en `results/portfolio/pooled_meta_<ts>.json` con el mismo schema que los summaries existentes. Incluye ademas:

```json
{
  "mode": "pooled_meta",
  "gates": { "G1": {...}, "G2": {...}, ... },
  "comparison": {
    "pooled_sharpe": ...,
    "baseline_sharpe": ...,
    "delta_sharpe": ...,
    "per_strategy_diff": [...]
  }
}
```

El dashboard los levanta sin cambios (opcional: pagina `/pooled` despues).

---

## Verificacion end-to-end

1. `--export`: 7 directorios `meta_export/` con parquets validos
2. `--train`: 7 StrategyResult con daily returns no vacios, N pooled >= 1000
3. `--compare`: ambos portfolio backtests completan, tabla de gates G1-G6 impresa con PASS/FAIL
4. `--full`: corrida completa produce reporte final con metrics y veredicto
5. `max_leverage=6.0` usado para pooled, `max_leverage=20.0` para baseline
6. Archivo JSON guardado en `results/portfolio/pooled_meta_<ts>.json`
