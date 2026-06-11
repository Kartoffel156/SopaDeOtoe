# Autoresearch — H236 MomentumReversalAsym (Sharpe boost)

## Objetivo

Maximizar sharpe manteniendo n_trades >= 130 y total_return >= 7%.

## Baseline

| Metrica | Valor |
|---------|-------|
| total_return | 8.63% |
| sharpe | 0.3418 |
| max_drawdown | -4.39% |
| n_trades | 165 |

Config graduado: `configs/graduated/HypothesisH236MomentumReversalAsym_20260411_021821.yaml`

## Restricciones duras

- n_trades >= 130
- total_return >= 0.07 (7%)
- max_drawdown >= -10%
- sharpe > 0.3418 (debe superar baseline)

Si cualquier restriccion falla -> discard y registrar en results_log.csv.

## Variables libres

El agente puede modificar SOLO estos parametros en el config YAML:

- `dn_thresh` (actual: 0.0207, rango sugerido: 0.005-0.06)

Tambien puede ajustar en el config base:
- `pt_sl` (profit target / stop loss ratios)
- `max_holding` (bars)
- `risk_fraction`, `risk_pct`

Nota: esta estrategia tiene un solo param libre (dn_thresh). El espacio de busqueda
principal esta en pt_sl y max_holding que afectan el filtrado de trades.

NO modificar: strategy .py, core/runner.py, portfolio/, v12/.

## Archivos read-only

- strategies/HypothesisH236MomentumReversalAsym.py
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
2. Sweep dn_thresh: 0.01, 0.015, 0.025, 0.03, 0.04
3. Variar pt_sl: subir profit target (3.0, 3.5), ajustar stop loss (1.0, 1.5, 2.0)
4. Probar max_holding mas corto (24, 30) para cortar losers rapido
5. Ajustar risk_fraction para balancear sizing
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
