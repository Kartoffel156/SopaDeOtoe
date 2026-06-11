# Autoresearch — Feature Windows Optimization (all graduated strategies)

## Objetivo

Optimizar las ventanas de calculo de meta-features para mejorar sharpe.
Los features del meta-modelo (kyle_lambda, amihud, entropy, vol_regime) tienen
ventanas que pueden no ser optimas para BTC dollar bars a 6 bpd.

## Baseline

Defaults actuales:
- v2.features.kyle_lambda_window: 50
- v2.features.amihud_window: 50
- v2.features.entropy_window: 50
- v2.features.entropy_bins: 10
- v2.meta_vol_regime_fast: 20
- v2.meta_vol_regime_slow: 60
- v2.meta_rel_vol_window: 50

## Restricciones duras

- n_trades >= 30
- max_drawdown >= -40%
- Registrar TODOS los resultados

## Variables libres

El agente puede modificar SOLO estos parametros:

### Variacion A — Windows cortas (reactivas)
- v2.features.kyle_lambda_window: 20
- v2.features.amihud_window: 20
- v2.features.entropy_window: 20
- v2.meta_vol_regime_fast: 10
- v2.meta_vol_regime_slow: 30
- v2.meta_rel_vol_window: 20

### Variacion B — Windows medias (default)
- (sin cambios, baseline)

### Variacion C — Windows largas (estables)
- v2.features.kyle_lambda_window: 100
- v2.features.amihud_window: 100
- v2.features.entropy_window: 100
- v2.meta_vol_regime_fast: 30
- v2.meta_vol_regime_slow: 120
- v2.meta_rel_vol_window: 100

### Variacion D — Windows muy largas (macro)
- v2.features.kyle_lambda_window: 200
- v2.features.amihud_window: 200
- v2.features.entropy_window: 200
- v2.meta_vol_regime_fast: 50
- v2.meta_vol_regime_slow: 200
- v2.meta_rel_vol_window: 200

### Variacion E — Asimetrica (vol rapida + microstructure lenta)
- v2.features.kyle_lambda_window: 100
- v2.features.amihud_window: 100
- v2.features.entropy_window: 100
- v2.meta_vol_regime_fast: 10
- v2.meta_vol_regime_slow: 40
- v2.meta_rel_vol_window: 30

### Variacion F — Entropy bins
- v2.features.entropy_bins: 5 (menos granular)
- v2.features.entropy_bins: 20 (mas granular)

NO modificar strategy.params, NO modificar archivos .py.

## Estrategias a correr

Todas las 16 en `configs/graduated/` (usar el mas reciente si hay duplicados).

## Archivos read-only

- strategies/*.py
- core/runner.py
- portfolio/
- v12/

## Como correr un experimento

1. Copiar config graduado a configs/temp/ con nombre: `<Strategy>_fw<variacion>.yaml`
2. Aplicar la variacion de windows
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

1. Correr baseline (variacion B) para todas — confirmar reproducibilidad
2. Correr variacion A (cortas) para todas
3. Correr variacion C (largas) para todas
4. Correr variacion E (asimetrica) para todas
5. Correr variacion D (muy largas) para todas
6. Entropy bins (5 y 20) en las top-3 estrategias
7. Al terminar: tabla strategy x variacion -> sharpe, identificar patron

## NUNCA PARAR

Una vez iniciado el loop, NO pausar para preguntar al usuario.
Continuar hasta completar todos los runs o alcanzar la regla de parada.
