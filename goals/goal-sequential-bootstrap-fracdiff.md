# Autoresearch — Sequential Bootstrap & Fracdiff (all graduated strategies)

## Objetivo

Optimizar los parametros de sequential bootstrap (control de autocorrelacion
en labels) y fractional differentiation (stationarity vs memory trade-off).
Estos son fundamentales para la calidad del training set del meta-modelo.

## Baseline

Defaults actuales:
- sequential_bootstrap.enabled: true
- sequential_bootstrap.n_samples: 50
- v2.features.fracdiff: true
- v2.features.fracdiff_d: auto

## Restricciones duras

- n_trades >= 30
- max_drawdown >= -40%
- Registrar TODOS los resultados

## Variables libres

### Variacion A — Mas samples bootstrap (mejor estimacion uniqueness)
- sequential_bootstrap.n_samples: 100

### Variacion B — Muchos samples bootstrap (costoso pero preciso)
- sequential_bootstrap.n_samples: 200

### Variacion C — Pocos samples (rapido, menos preciso)
- sequential_bootstrap.n_samples: 20

### Variacion D — Sin sequential bootstrap (ablation)
- sequential_bootstrap.enabled: false

### Variacion E — Fracdiff fijo d=0.3
- v2.features.fracdiff: true
- v2.features.fracdiff_d: 0.3

### Variacion F — Fracdiff fijo d=0.5
- v2.features.fracdiff: true
- v2.features.fracdiff_d: 0.5

### Variacion G — Fracdiff fijo d=0.7
- v2.features.fracdiff: true
- v2.features.fracdiff_d: 0.7

### Variacion H — Sin fracdiff (raw features)
- v2.features.fracdiff: false

### Variacion I — Bootstrap alto + fracdiff bajo
- sequential_bootstrap.n_samples: 150
- v2.features.fracdiff_d: 0.3

### Variacion J — Sin bootstrap + fracdiff alto
- sequential_bootstrap.enabled: false
- v2.features.fracdiff_d: 0.7

NO modificar strategy.params, NO modificar archivos .py.

## Estrategias a correr

Todas las 16 en `configs/graduated/` (usar el mas reciente si hay duplicados).

## Archivos read-only

- strategies/*.py
- core/runner.py
- portfolio/
- v12/

## Como correr un experimento

1. Copiar config graduado a configs/temp/ con nombre: `<Strategy>_sb<variacion>.yaml`
2. Aplicar la variacion
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

16 estrategias x 10 variaciones = 160 runs minimos.
Correr en batches de 4.

## Regla de parada

- Todos los 160 runs completados, O
- Tiempo total > 12 horas

## Estrategia de busqueda sugerida

1. Baseline para todas — confirmar reproducibilidad
2. Variacion D (sin bootstrap) — cuantificar valor del sequential bootstrap
3. Variacion H (sin fracdiff) — cuantificar valor de fracdiff
4. Variacion A (100 samples) — mas precision en uniqueness
5. Variacion E, F, G — sweep de d para encontrar optimo
6. Variacion I y J — interacciones entre bootstrap y fracdiff
7. Variacion B (200 samples) — solo si hay tiempo, es costoso

Key insight: fracdiff_d controla memoria vs stationarity. d bajo = mas
estacionario (bueno para RF) pero pierde memoria de tendencia. d alto =
mas memoria pero el RF puede no generalizar. El optimo depende de la
frecuencia de trades de cada estrategia.

## NUNCA PARAR

Una vez iniciado el loop, NO pausar para preguntar al usuario.
Continuar hasta completar todos los runs o alcanzar la regla de parada.
