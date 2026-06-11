# Autoresearch — TSIMeanReversion (Sharpe boost)

## Objetivo

Maximizar sharpe manteniendo n_trades >= 120 y total_return >= 7%.

## Baseline

| Metrica | Valor |
|---------|-------|
| total_return | 8.33% |
| sharpe | 0.4896 |
| max_drawdown | -5.39% |
| n_trades | 157 |

Config graduado: `configs/graduated/TSIMeanReversion_20260419_095451.yaml`

## Restricciones duras

- n_trades >= 120
- total_return >= 0.07 (7%)
- max_drawdown >= -12%
- sharpe > 0.4896 (debe superar baseline)

Si cualquier restriccion falla -> discard y registrar en results_log.csv.

## Variables libres

El agente puede modificar SOLO estos parametros en el config YAML:

- `rsi_period` (actual: 8, rango sugerido: 5-18)
- `rsi_overbought` (actual: 61, rango sugerido: 55-75)
- `rsi_oversold` (actual: 29, rango sugerido: 20-45)
- `tsi_r` (actual: 5, rango sugerido: 3-15)
- `tsi_s` (actual: 3, rango sugerido: 2-8)
- `tsi_overbought` (actual: 13, rango sugerido: 5-30)
- `tsi_oversold` (actual: -28, rango sugerido: -40 a -10)

Tambien puede ajustar en el config base:
- `pt_sl` (profit target / stop loss ratios)
- `max_holding` (bars)
- `risk_fraction`, `risk_pct`

NO modificar: strategy .py, core/runner.py, portfolio/, v12/.

## Archivos read-only

- strategies/TSIMeanReversion.py
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
2. Ampliar rsi_overbought - rsi_oversold (actualmente 32 pts, probar 40+ pts)
3. Sweep tsi_r: 3, 7, 10, 13 (suavizado del TSI)
4. Hacer tsi_oversold menos extremo (-20, -15) para mas entradas
5. Hacer tsi_overbought mas selectivo (18, 25) para menos falsos positivos
6. Ajustar pt_sl: tighter stop loss para mean-reversion (1.0, 1.2)
7. Probar max_holding mas corto (24) — mean reversion debe revertir rapido
8. Combinar mejores direcciones

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
