# Autoresearch — H86 WonhamMarkovRefinado (Sharpe boost)

## Objetivo

Maximizar sharpe manteniendo n_trades >= 35 y total_return >= 0%.
Nota: baseline es NEGATIVA (-0.63%, sharpe -0.09). El primer objetivo es
volverla rentable y luego maximizar sharpe. n_trades muy bajo (41).

## Baseline

| Metrica | Valor |
|---------|-------|
| total_return | -0.63% |
| sharpe | -0.0875 |
| max_drawdown | -5.14% |
| n_trades | 41 |

Config graduado: `configs/graduated/HypothesisH86WonhamMarkovRefinado_20260411_061114.yaml`

## Restricciones duras

- n_trades >= 35
- total_return >= 0.00 (0% — al menos breakeven)
- max_drawdown >= -10%
- sharpe > -0.0875 (debe superar baseline, idealmente > 0)

Si cualquier restriccion falla -> discard y registrar en results_log.csv.

## Variables libres

El agente puede modificar SOLO estos parametros en el config YAML:

- `markov_lookback` (actual: 17, rango sugerido: 8-40)
- `w_thresh` (actual: 0.6858, rango sugerido: 0.4-0.9)
- `m_thresh` (actual: 0.6952, rango sugerido: 0.4-0.9)
- `alpha_w` (actual: 0.1376, rango sugerido: 0.05-0.3)
- `vol_max` (actual: 2, rango sugerido: 1-4)

Tambien puede ajustar en el config base:
- `pt_sl` (profit target / stop loss ratios)
- `max_holding` (bars)
- `risk_fraction`, `risk_pct`

NO modificar: strategy .py, core/runner.py, portfolio/, v12/.

## Archivos read-only

- strategies/HypothesisH86WonhamMarkovRefinado.py
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
2. Bajar w_thresh y m_thresh (0.5, 0.6) para permitir mas trades
3. Subir alpha_w (0.2, 0.25) para suavizar transiciones Wonham
4. Acortar markov_lookback (10, 12) para regimenes mas rapidos
5. Bajar vol_max (1.5) para reducir exposicion en vol extrema
6. Ajustar pt_sl: tighter stop loss para proteger ganancias
7. Combinar mejores direcciones

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
