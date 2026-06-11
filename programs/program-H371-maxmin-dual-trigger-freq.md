# Autoresearch — H371 MaxMinDualTriggerFreq (Sharpe boost)

## Objetivo

Maximizar sharpe manteniendo n_trades >= 60 y total_return >= 7%.

## Baseline

| Metrica | Valor |
|---------|-------|
| total_return | 8.72% |
| sharpe | 0.9332 |
| max_drawdown | -2.68% |
| n_trades | 73 |

Config graduado: `configs/graduated/HypothesisH371MaxMinDualTriggerFreq_20260411_040215.yaml`

## Restricciones duras

- n_trades >= 60
- total_return >= 0.07 (7%)
- max_drawdown >= -10%
- sharpe > 0.9332 (debe superar baseline)

Si cualquier restriccion falla -> discard y registrar en results_log.csv.

## Variables libres

El agente puede modificar SOLO estos parametros en el config YAML:

- `long_lb` (actual: 16, rango sugerido: 8-40)
- `short_lb` (actual: 6, rango sugerido: 3-15)
- `lev_floor` (actual: -1.032, rango sugerido: -2.0 a -0.5)

Tambien puede ajustar en el config base:
- `pt_sl` (profit target / stop loss ratios)
- `max_holding` (bars)
- `risk_fraction`, `risk_pct`

NO modificar: strategy .py, core/runner.py, portfolio/, v12/.

## Archivos read-only

- strategies/HypothesisH371MaxMinDualTriggerFreq.py
- core/runner.py
- portfolio/runner.py
- v12/ (todo el directorio)

## Como correr un experimento

1. Copiar el config graduado a configs/temp/ con nombre descriptivo
2. Editar los params en el YAML copiado
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

Tiempo esperado: ~3-5 min por run en M5 Pro.

## Como leer el resultado

Leer el JSON de salida en results/exploration/.
Claves: total_return (cum_return), sharpe, max_drawdown, n_trades, profit_factor.

## Como registrar

Append a results_log.csv (tab-separated):
date	run_id	strategy	total_return	sharpe	max_drawdown	n_trades	description	status	commit

## MINIMO DE ITERACIONES (OBLIGATORIO)

DEBES ejecutar AL MENOS 15 iteraciones completas (baseline + 14 variaciones).
NO puedes parar antes de 15 iteraciones bajo NINGUNA circunstancia.
Cada iteracion = editar config YAML → correr run_exploration → leer resultado → registrar.

Lleva un contador explicito:
```
Iteracion 1/15: baseline run
Iteracion 2/15: dn_thresh 0.015
Iteracion 3/15: dn_thresh 0.03
...
```

## Regla de parada

Solo puedes parar DESPUES de completar las 15 iteraciones minimas Y:
- 30 runs alcanzados, O
- 12 runs consecutivos sin mejora (DESPUES de las 15 obligatorias), O
- Tiempo total > 5 horas

## Estrategia de busqueda sugerida

1. Baseline run (config graduado sin cambios) -> registrar
2. Ajustar ratio long_lb/short_lb (actualmente ~2.7x, probar 2x, 3x, 4x)
3. Sweep lev_floor: -0.7, -1.0, -1.3, -1.5 (controla agresividad en short)
4. Probar short_lb mas alto (8, 10) para filtrar ruido
5. Ajustar pt_sl para mejorar risk/reward
6. Combinar mejores direcciones

## NUNCA PARAR — ESTO ES CRITICO

Una vez iniciado el loop, NO pausar para preguntar al usuario.
El usuario puede estar durmiendo. Continuar indefinidamente
hasta ser interrumpido manualmente o alcanzar la regla de parada.

REPITO: DEBES completar MINIMO 15 iteraciones. Si solo haces 1-2 runs
y paras, el experimento es INUTIL. El valor del autoresearch esta en
explorar el espacio de parametros sistematicamente.

Despues de cada run, SIEMPRE:
1. Leer el resultado JSON
2. Registrar en results_log.csv
3. Decidir la siguiente variacion
4. Crear nuevo config YAML en configs/temp/
5. Ejecutar el siguiente run
6. REPETIR hasta cumplir las 15 iteraciones minimas
