# Autoresearch — H37 DynamicGridInformedGate (Sharpe boost)

## Objetivo

Maximizar sharpe manteniendo n_trades >= 150 y total_return >= 3%.

## Baseline

| Metrica | Valor |
|---------|-------|
| total_return | 3.58% |
| sharpe | 0.1090 |
| max_drawdown | -5.84% |
| n_trades | 219 |

Config graduado: `configs/graduated/HypothesisH37DynamicGridInformedGate_20260419_051820.yaml`

## Restricciones duras

- n_trades >= 150
- total_return >= 0.03 (3%)
- max_drawdown >= -12%
- sharpe > 0.1090 (debe superar baseline)

Si cualquier restriccion falla -> discard y registrar en results_log.csv.

## Variables libres

El agente puede modificar SOLO estos parametros en el config YAML:

- `grid_period` (actual: 23, rango sugerido: 10-40)
- `grid_mult` (actual: 1.3987, rango sugerido: 0.8-2.5)
- `atr_period` (actual: 20, rango sugerido: 10-30)
- `ofi_neutral_thresh` (actual: 0.1792, rango sugerido: 0.05-0.4)
- `vpin_pct_thresh` (actual: 0.5901, rango sugerido: 0.3-0.8)
- `mk_no_trend` (actual: 1.4255, rango sugerido: 0.8-2.5)

Tambien puede ajustar en el config base:
- `pt_sl` (profit target / stop loss ratios)
- `max_holding` (bars)
- `risk_fraction`, `risk_pct`

NO modificar: strategy .py, core/runner.py, portfolio/, v12/.

## Archivos read-only

- strategies/HypothesisH37DynamicGridInformedGate.py
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
2. Subir ofi_neutral_thresh (0.25, 0.3) para filtrar trades sin informacion
3. Subir vpin_pct_thresh (0.65, 0.7) para entrar solo con VPIN alto
4. Bajar mk_no_trend (1.0, 1.2) para activar el grid solo en tendencia
5. Ajustar grid_mult (1.0, 1.2) para grid mas conservador
6. Probar grid_period mas largo (28, 35) para grid mas estable
7. Ajustar pt_sl: tighter stops para este tipo de estrategia grid
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
