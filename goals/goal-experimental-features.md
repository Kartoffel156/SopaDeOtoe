# Autoresearch — Experimental Meta-Features (all graduated strategies)

## Objetivo

Activar y evaluar meta-features experimentales que estan disponibles en el
pipeline pero desactivadas por defecto. Tambien probar desactivar features
que podrian ser ruido. El objetivo es encontrar el subset optimo de features.

## Baseline

Defaults actuales:
- v2.features.meta_features.enabled_experimental_features: [] (ninguna activa)
- v2.features.meta_features.disabled_meta_features: [] (todas activas)
- v2.features.fracdiff: true
- v2.features.fracdiff_d: auto
- v2.meta_direction_feature: true
- v2.feature_prefilter.enabled: true
- v2.feature_prefilter.threshold: 0.01

## Restricciones duras

- n_trades >= 30
- max_drawdown >= -40%
- Registrar TODOS los resultados

## Variables libres

### Variacion A — Variance ratio features
- v2.features.meta_features.enabled_experimental_features: ['variance_ratio_5', 'variance_ratio_20']

### Variacion B — Vol acceleration + autocorr momentum
- v2.features.meta_features.enabled_experimental_features: ['vol_accel', 'autocorr_momentum']

### Variacion C — Kyle entropy ratio
- v2.features.meta_features.enabled_experimental_features: ['kyle_entropy_ratio']

### Variacion D — ALL experimental features
- v2.features.meta_features.enabled_experimental_features: ['variance_ratio_5', 'variance_ratio_20', 'vol_accel', 'autocorr_momentum', 'kyle_entropy_ratio']

### Variacion E — Desactivar fracdiff (ablation)
- v2.features.fracdiff: false

### Variacion F — Sin direction feature (ablation)
- v2.meta_direction_feature: false

### Variacion G — Feature prefilter mas agresivo
- v2.feature_prefilter.threshold: 0.05
- v2.feature_prefilter.min_features: 3

### Variacion H — Feature prefilter desactivado
- v2.feature_prefilter.enabled: false

### Variacion I — All experimental + no prefilter (maximo features)
- v2.features.meta_features.enabled_experimental_features: ['variance_ratio_5', 'variance_ratio_20', 'vol_accel', 'autocorr_momentum', 'kyle_entropy_ratio']
- v2.feature_prefilter.enabled: false

### Variacion J — Minimal features (solo top predictors)
- v2.feature_prefilter.threshold: 0.10
- v2.feature_prefilter.min_features: 2
- v2.features.meta_features.disabled_meta_features: ['roll_spread', 'parkinson_vol', 'rolling_d_star']

NO modificar strategy.params, NO modificar archivos .py.

## Estrategias a correr

Todas las 16 en `configs/graduated/` (usar el mas reciente si hay duplicados).

## Archivos read-only

- strategies/*.py
- core/runner.py
- portfolio/
- v12/

## Como correr un experimento

1. Copiar config graduado a configs/temp/ con nombre: `<Strategy>_feat<variacion>.yaml`
2. Aplicar la variacion de features
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
2. Variacion D (all experimental) — rapido para ver si hay signal
3. Variacion E (sin fracdiff) — cuanto valor aporta fracdiff?
4. Variacion F (sin direction) — direction feature es clave?
5. Variacion H (sin prefilter) — el filtro esta eliminando features utiles?
6. Variacion A, B, C — desglosar cuales experimental features aportan
7. Variacion G (prefilter agresivo) — menos features = menos overfit?
8. Variacion I (max features) vs J (min features) — contraste extremo

Key insight: comparar D (max) vs J (min) muestra el trade-off bias/varianza
en el meta-modelo. Si J gana, hay mucho ruido en features.

## NUNCA PARAR

Una vez iniciado el loop, NO pausar para preguntar al usuario.
Continuar hasta completar todos los runs o alcanzar la regla de parada.
