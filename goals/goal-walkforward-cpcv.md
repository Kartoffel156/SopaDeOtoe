# Autoresearch — Walk-Forward & CPCV Configuration (all graduated strategies)

## Objetivo

Optimizar la configuracion de walk-forward y CPCV para reducir overfitting
y mejorar generalizacion out-of-sample. El numero de splits y el modo de
walk-forward afectan cuanto "ve" el meta-modelo durante entrenamiento.

## Baseline

Defaults actuales:
- v2.walkforward_mode: expanding
- v2.wf_prediction_splits: 3
- v2.cpcv_n_splits: 4
- v2.cpcv_n_test_groups: 2
- v2.cpcv_mode: replay
- v2.oos_predictions: true

## Restricciones duras

- n_trades >= 30
- max_drawdown >= -40%
- Registrar TODOS los resultados

## Variables libres

### Variacion A — Mas splits WF (mas OOS, menos datos por fold)
- v2.wf_prediction_splits: 5
- v2.cpcv_n_splits: 6
- v2.cpcv_n_test_groups: 2

### Variacion B — Menos splits WF (mas datos por fold, menos OOS)
- v2.wf_prediction_splits: 2
- v2.cpcv_n_splits: 3
- v2.cpcv_n_test_groups: 1

### Variacion C — Rolling vs Expanding
- v2.walkforward_mode: rolling
- v2.wf_prediction_splits: 4
- v2.cpcv_n_splits: 5
- v2.cpcv_n_test_groups: 2

### Variacion D — High CPCV paths
- v2.wf_prediction_splits: 4
- v2.cpcv_n_splits: 8
- v2.cpcv_n_test_groups: 2

### Variacion E — Conservative (many splits + rolling)
- v2.walkforward_mode: rolling
- v2.wf_prediction_splits: 6
- v2.cpcv_n_splits: 8
- v2.cpcv_n_test_groups: 3

### Variacion F — In-sample predictions (ablation)
- v2.oos_predictions: false
- v2.wf_prediction_splits: 3
- (comparar IS vs OOS para detectar overfit)

NO modificar strategy.params, NO modificar archivos .py.

## Estrategias a correr

Todas las 16 en `configs/graduated/` (usar el mas reciente si hay duplicados).

## Archivos read-only

- strategies/*.py
- core/runner.py
- portfolio/
- v12/

## Como correr un experimento

1. Copiar config graduado a configs/temp/ con nombre: `<Strategy>_wf<variacion>.yaml`
2. Aplicar la variacion de walk-forward/CPCV
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

16 estrategias x 6 variaciones = 96 runs minimos.
Correr en batches de 4.

## Regla de parada

- Todos los 96 runs completados, O
- Tiempo total > 8 horas

## Estrategia de busqueda sugerida

1. Baseline para todas — confirmar reproducibilidad
2. Variacion F (IS predictions) — cuantificar gap IS vs OOS actual
3. Variacion A (mas splits) — mas OOS = mas robusto?
4. Variacion C (rolling) — adaptacion a cambio de regimen?
5. Variacion D (high CPCV) — mas paths = mejor estimacion?
6. Variacion E (conservative) — full anti-overfit
7. Variacion B (menos splits) — ver si el dataset es muy chico para muchos splits
8. Comparar: si IS >> OOS en F, entonces el meta-modelo esta sobreajustado

## NUNCA PARAR

Una vez iniciado el loop, NO pausar para preguntar al usuario.
Continuar hasta completar todos los runs o alcanzar la regla de parada.
