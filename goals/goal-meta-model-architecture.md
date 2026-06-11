# Autoresearch — Meta-Model Architecture Sweep (all graduated strategies)

## Objetivo

Encontrar la arquitectura optima del meta-modelo para cada estrategia.
El RF default puede no ser optimo — probar depth, estimators, method, y class_weight.

## Baseline

Defaults actuales:
- v2.meta_model_method: rf
- v2.meta_model.n_estimators: 100
- v2.meta_model.max_depth: null (ilimitado)
- v2.meta_model.min_samples_leaf: 1
- v2.meta_model.max_features: sqrt
- v2.meta_model_hp_search.n_iter: 10
- v2.meta_model_hp_search.n_splits: 3

## Restricciones duras

- n_trades >= 30
- max_drawdown >= -40%
- Registrar TODOS los resultados

## Variables libres

### Variacion A — RF shallow (anti-overfit)
- v2.meta_model.n_estimators: 50
- v2.meta_model.max_depth: 3
- v2.meta_model.min_samples_leaf: 10
- v2.meta_model.max_features: sqrt

### Variacion B — RF medium depth
- v2.meta_model.n_estimators: 200
- v2.meta_model.max_depth: 5
- v2.meta_model.min_samples_leaf: 5
- v2.meta_model.max_features: sqrt

### Variacion C — RF deep + many trees
- v2.meta_model.n_estimators: 500
- v2.meta_model.max_depth: null
- v2.meta_model.min_samples_leaf: 1
- v2.meta_model.max_features: sqrt

### Variacion D — RF log2 features
- v2.meta_model.n_estimators: 200
- v2.meta_model.max_depth: 5
- v2.meta_model.min_samples_leaf: 5
- v2.meta_model.max_features: log2

### Variacion E — Bagged RF
- v2.meta_model_method: bagged_rf
- v2.meta_model.n_estimators: 100
- v2.meta_model.max_depth: 5
- v2.meta_model.min_samples_leaf: 5

### Variacion F — Aggressive HP search
- v2.meta_model_hp_search.n_iter: 30
- v2.meta_model_hp_search.n_splits: 5
- v2.meta_model_hp_search.scoring: roc_auc

### Variacion G — Class weight balanced vs none
- v2.meta_model.class_weight: null (sin balanceo)
- (baseline usa balanced implicitamente)

NO modificar strategy.params, NO modificar archivos .py.

## Estrategias a correr

Todas las 16 en `configs/graduated/` (usar el mas reciente si hay duplicados).

## Archivos read-only

- strategies/*.py
- core/runner.py
- portfolio/
- v12/

## Como correr un experimento

1. Copiar config graduado a configs/temp/ con nombre: `<Strategy>_arch<variacion>.yaml`
2. Aplicar la variacion de arquitectura
3. Ejecutar:

```bash
cd /Users/nongo/Documents/Patacon
python -c "
from SopaDeOtoe.core.runner import run_exploration
import yaml
with open('SopaDeOtoe/configs/temp/<config>.yaml') as f:
    cfg = yaml.safe_load(f)
results = run_exploration([cfg], n_jobs=1)
print(results)
"
```

## Como registrar

Append a results_log.csv (tab-separated):
date	run_id	strategy	variacion	total_return	sharpe	max_drawdown	n_trades	status

## MINIMO DE ITERACIONES (OBLIGATORIO)

16 estrategias x 7 variaciones = 112 runs minimos.
Correr en batches de 4.

## Regla de parada

- Todos los 112 runs completados, O
- Tiempo total > 10 horas

## Estrategia de busqueda sugerida

1. Baseline (defaults) para todas — confirmar reproducibilidad
2. Variacion A (shallow) — hipotesis: overfit en el meta-modelo actual
3. Variacion B (medium) — balance exploracion/explotacion
4. Variacion E (bagged_rf) — reducir varianza del ensemble
5. Variacion C (deep+many) — si hay suficientes datos, mas capacidad
6. Variacion D (log2) — forzar mas diversidad entre arboles
7. Variacion F (aggressive HP search) — dejar que RandomizedSearch explore mas
8. Variacion G (sin class_weight) — ver si el balanceo ayuda o perjudica

## NUNCA PARAR

Una vez iniciado el loop, NO pausar para preguntar al usuario.
Continuar hasta completar todos los runs o alcanzar la regla de parada.
