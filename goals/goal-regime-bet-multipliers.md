# Autoresearch — Regime Bet Size Multipliers (all graduated strategies)

## Objetivo

Optimizar los multiplicadores de bet size por regimen de mercado.
Actualmente todos estan en {} (sin multiplicador = 1.0 para todos los regimenes).
La hipotesis es que ciertas estrategias funcionan mejor en ciertos regimenes
y deberian tener sizing asimetrico.

## Baseline

Defaults actuales:
- regime.enabled: true
- regime.direction.mode: gmm
- regime.bet_size_multipliers: {} (equivalente a 1.0 para todo)
- regime.volatility.levels: [25, 75, 95]
- regime.volatility.quantile_window: 252

## Restricciones duras

- n_trades >= 30
- max_drawdown >= -40%
- Registrar TODOS los resultados

## Variables libres

### Variacion A — Boost BULL, penalizar CONGESTED
- regime.bet_size_multipliers:
    BULL: 1.3
    BEAR: 1.0
    CYCLIC: 1.0
    CONGESTED: 0.6

### Variacion B — Boost BULL + CYCLIC, penalizar resto
- regime.bet_size_multipliers:
    BULL: 1.3
    BEAR: 0.7
    CYCLIC: 1.2
    CONGESTED: 0.5

### Variacion C — Solo penalizar CONGESTED (conservador)
- regime.bet_size_multipliers:
    BULL: 1.0
    BEAR: 1.0
    CYCLIC: 1.0
    CONGESTED: 0.4

### Variacion D — Boost BEAR (para estrategias mean-reversion)
- regime.bet_size_multipliers:
    BULL: 0.8
    BEAR: 1.3
    CYCLIC: 1.1
    CONGESTED: 0.7

### Variacion E — Agresivo en tendencia
- regime.bet_size_multipliers:
    BULL: 1.5
    BEAR: 1.5
    CYCLIC: 0.8
    CONGESTED: 0.3

### Variacion F — Vol-regime aware (reducir en alta vol)
- regime.volatility.levels: [20, 70, 90]
- regime.bet_size_multipliers:
    BULL: 1.2
    BEAR: 1.0
    CYCLIC: 1.0
    CONGESTED: 0.5

### Variacion G — Quantile window corta (adaptacion rapida)
- regime.volatility.quantile_window: 120
- regime.bet_size_multipliers:
    BULL: 1.2
    BEAR: 1.0
    CYCLIC: 1.0
    CONGESTED: 0.6

NO modificar strategy.params, NO modificar archivos .py.

## Estrategias a correr

Todas las 16 en `configs/graduated/` (usar el mas reciente si hay duplicados).

## Archivos read-only

- strategies/*.py
- core/runner.py
- portfolio/
- v12/

## Como correr un experimento

1. Copiar config graduado a configs/temp/ con nombre: `<Strategy>_reg<variacion>.yaml`
2. Aplicar la variacion de regime multipliers
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
2. Variacion C (solo penalizar CONGESTED) — apuesta segura
3. Variacion A (boost BULL) — trend-followers deberian beneficiarse
4. Variacion D (boost BEAR) — mean-reversion deberia beneficiarse
5. Variacion E (agresivo tendencia) — alto riesgo alto reward
6. Variacion B y F para completar
7. Variacion G (quantile window corta) — efecto de la adaptacion

Key insight: las estrategias trend-following (DualMA, H136, H481, MultiTimeframe)
deberian beneficiarse de boost BULL. Las mean-reversion (TSI, H110, H167)
deberian beneficiarse de boost BEAR/CYCLIC.

## NUNCA PARAR

Una vez iniciado el loop, NO pausar para preguntar al usuario.
Continuar hasta completar todos los runs o alcanzar la regla de parada.
