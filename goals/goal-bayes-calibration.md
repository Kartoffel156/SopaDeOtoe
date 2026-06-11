# Autoresearch — Bayesian Calibration Tuning (all graduated strategies)

## Objetivo

Optimizar la calibracion bayesiana del pivot de bet sizing por regimen.
El pivot_shrinkage controla cuanto confia el sistema en el posterior bayesiano
vs el prior fijo de 0.5. Esto afecta directamente el sizing de cada trade.

## Baseline

Defaults actuales:
- v2.bayes_calibration.enabled: true
- v2.bayes_calibration.fallback_pivot: 0.5
- v2.bayes_calibration.min_obs_per_regime: 10
- v2.bayes_calibration.pivot_shrinkage: 0.5
- calibration_bayes.enabled: true (top-level, mismo efecto)

## Restricciones duras

- n_trades >= 30
- max_drawdown >= -40%
- Registrar TODOS los resultados

## Variables libres

### Variacion A — Full Bayes (sin shrinkage)
- v2.bayes_calibration.pivot_shrinkage: 1.0
- v2.bayes_calibration.min_obs_per_regime: 10

### Variacion B — Full Bayes agresivo (menos obs requeridas)
- v2.bayes_calibration.pivot_shrinkage: 1.0
- v2.bayes_calibration.min_obs_per_regime: 5

### Variacion C — Conservador (mucho shrinkage)
- v2.bayes_calibration.pivot_shrinkage: 0.2
- v2.bayes_calibration.min_obs_per_regime: 20

### Variacion D — Sin calibracion bayesiana (ablation)
- v2.bayes_calibration.enabled: false
- calibration_bayes.enabled: false

### Variacion E — Pivot alternativo (0.55 como fallback)
- v2.bayes_calibration.fallback_pivot: 0.55
- v2.bayes_calibration.pivot_shrinkage: 0.7
- v2.bayes_calibration.min_obs_per_regime: 10

### Variacion F — High shrinkage + muchas obs
- v2.bayes_calibration.pivot_shrinkage: 0.3
- v2.bayes_calibration.min_obs_per_regime: 30

### Variacion G — Mid shrinkage + low obs (adaptativo rapido)
- v2.bayes_calibration.pivot_shrinkage: 0.7
- v2.bayes_calibration.min_obs_per_regime: 5

NO modificar strategy.params, NO modificar archivos .py.

## Estrategias a correr

Todas las 16 en `configs/graduated/` (usar el mas reciente si hay duplicados).

## Archivos read-only

- strategies/*.py
- core/runner.py
- portfolio/
- v12/

## Como correr un experimento

1. Copiar config graduado a configs/temp/ con nombre: `<Strategy>_bayes<variacion>.yaml`
2. Aplicar la variacion de calibracion
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
- Tiempo total > 8 horas

## Estrategia de busqueda sugerida

1. Baseline para todas — confirmar reproducibilidad
2. Variacion D (sin Bayes) — cuantificar el valor de la calibracion
3. Variacion A (full Bayes) — maximo uso del posterior
4. Variacion C (conservador) — cuanto beneficio con poca confianza
5. Variacion G (adaptativo rapido) — ideal para estrategias con pocos trades
6. Variacion B (agresivo) — riesgo de overfit al posterior?
7. Variacion E y F para completar el mapa

Key insight: si D (sin Bayes) es mejor que A (full Bayes), el posterior
esta sobreajustado y necesita mas datos o mas shrinkage.

## NUNCA PARAR

Una vez iniciado el loop, NO pausar para preguntar al usuario.
Continuar hasta completar todos los runs o alcanzar la regla de parada.
