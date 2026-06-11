# Autoresearch — Meta-Threshold Sweep (all graduated strategies)

## Objetivo

Encontrar el meta_threshold optimo para cada estrategia graduada.
Maximizar sharpe ajustando v2.meta_threshold mientras se mantienen los strategy.params fijos.

## Baseline

Usar los configs graduados tal cual estan en `configs/graduated/`.
Todos tienen `v2.meta_threshold: 0.55` como default.

## Restricciones duras

- n_trades >= 30
- sharpe >= 0.0 (permitir explorar, no descartar por sharpe negativo en threshold altos)
- max_drawdown >= -40%
- Registrar TODOS los resultados (incluso los malos) para mapear la curva

## Variables libres

El agente puede modificar SOLO estos parametros en el config YAML:

- `v2.meta_threshold` — sweep: [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75]

NO modificar strategy.params, NO modificar archivos .py.

## Estrategias a correr

Usar TODOS los configs en `configs/graduated/` (uno por estrategia, el mas reciente si hay duplicados):

1. DualMovingAverageCrossover_20260418_162631.yaml
2. HypothesisH110BollingerKyleGate_20260418_160334.yaml
3. HypothesisH136GoldenDeathCrossAsym_20260411_010204.yaml
4. HypothesisH167BollingerRangingOFIGate_20260418_162324.yaml
5. HypothesisH203VolExpansionEntry_20260418_012006.yaml
6. HypothesisH236MomentumReversalAsym_20260516_163700.yaml
7. HypothesisH318TrendlineChannelSqueeze_20260419_051527.yaml
8. HypothesisH37DynamicGridInformedGate_20260419_051820.yaml
9. HypothesisH371MaxMinDualTriggerFreq_20260411_040215.yaml
10. HypothesisH426RSIGarchBullBear_20260411_050222.yaml
11. HypothesisH434MaxMinDualHorizon_20260411_051302.yaml
12. HypothesisH481GoldenCrossPSAR_20260412_153957.yaml
13. HypothesisH72AsymmetricRSIDrawdownShield_20260411_060037.yaml
14. HypothesisH86WonhamMarkovRefinado_20260411_061114.yaml
15. MultiTimeframeTrendSignal_20260419_134237.yaml
16. TSIMeanReversion_20260419_095404.yaml

## Archivos read-only

- strategies/*.py
- core/runner.py
- portfolio/
- v12/

## Como correr un experimento

1. Copiar el config graduado a configs/temp/ con nombre: `<Strategy>_mt<threshold>.yaml`
2. Cambiar SOLO `v2.meta_threshold` al valor del sweep
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

Batch approach (correr varias en paralelo):
```bash
cd /Users/nongo/Documents/Patacon
python -c "
from SopaDeOtoe.core.runner import run_exploration
import yaml, glob

configs = []
for f in sorted(glob.glob('SopaDeOtoe/configs/temp/*_mt*.yaml')):
    with open(f) as fh:
        configs.append(yaml.safe_load(fh))
results = run_exploration(configs, n_jobs=4)
for r in results:
    print(r)
"
```

## Como registrar

Append a results_log.csv (tab-separated):
date	run_id	strategy	meta_threshold	total_return	sharpe	max_drawdown	n_trades	status

## MINIMO DE ITERACIONES (OBLIGATORIO)

16 estrategias x 8 thresholds = 128 runs minimos.
Correr en batches de 4 (n_jobs=4) para velocidad.
Cada batch = una iteracion reportada.

## Regla de parada

- Todos los 128 runs completados, O
- Tiempo total > 8 horas

## Estrategia de busqueda sugerida

1. Correr TODAS las estrategias con threshold=0.55 (baseline, confirmar reproducibilidad)
2. Sweep ascendente: 0.60, 0.65, 0.70, 0.75
3. Sweep descendente: 0.50, 0.45, 0.40
4. Al terminar, reportar tabla: strategy x threshold -> sharpe

## NUNCA PARAR

Una vez iniciado el loop, NO pausar para preguntar al usuario.
Continuar hasta completar todos los runs o alcanzar la regla de parada.
