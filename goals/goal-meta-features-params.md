# Autoresearch — Meta-Features Parameter Tuning (all graduated strategies)

## Objetivo

Optimizar los parametros internos de las meta-features (registradas + Kronos v2)
sin overfitear. Cada meta-feature tiene ventanas, thresholds, o hyperparams
que afectan su calidad. El objetivo es encontrar configs que mejoren sharpe/return
de forma robusta (que sobrevivan CPCV y no degraden n_trades).

Foco: parametros de las features, NO del meta-modelo (eso es otro goal).

## Baseline

Defaults actuales de params de meta-features:
- v2.features.amihud_window: 50
- v2.features.entropy_bins: 10
- v2.features.entropy_window: 50
- v2.features.kyle_lambda_window: 50
- v2.meta_rel_vol_window: 50
- v2.meta_vol_regime_fast: 20
- v2.meta_vol_regime_slow: 60
- v2.features.meta_features.roll_spread_window: 50 (default en models.py)
- v2.features.meta_features.parkinson_vol_window: 20 (default en models.py)
- v2.features.meta_features.rolling_d_star_window: 40 (default en models.py)

Kronos v2 params:
- v2.features.meta_features.kronos_features.lookback: 50
- v2.features.meta_features.kronos_features.sample_count: 5
- v2.features.meta_features.kronos_features.temperature: 1.0
- v2.features.meta_features.kronos_features.top_p: 0.9
- v2.features.meta_features.kronos_features.stride: 1
- v2.features.meta_features.kronos_features.batch_chunk_size: 256

## Restricciones duras

- n_trades >= 30
- max_drawdown >= -40%
- sharpe >= 0.8 (anti-overfit: no aceptar sharpe artificialmente alto con pocos trades)
- Registrar TODOS los resultados

## Variables libres

### Variacion BASELINE — Defaults + Kronos + experimentales
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]
- v2.feature_prefilter.enabled: false

### Variacion A — Ventanas cortas (20-bar regime, responsive)
- v2.features.amihud_window: 30
- v2.features.entropy_window: 30
- v2.features.kyle_lambda_window: 30
- v2.meta_rel_vol_window: 30
- v2.meta_vol_regime_fast: 10
- v2.meta_vol_regime_slow: 40
- v2.features.meta_features.roll_spread_window: 30
- v2.features.meta_features.parkinson_vol_window: 10
- v2.features.meta_features.rolling_d_star_window: 25
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]

### Variacion B — Ventanas largas (80-bar regime, smooth)
- v2.features.amihud_window: 80
- v2.features.entropy_window: 80
- v2.features.kyle_lambda_window: 80
- v2.meta_rel_vol_window: 80
- v2.meta_vol_regime_fast: 30
- v2.meta_vol_regime_slow: 100
- v2.features.meta_features.roll_spread_window: 80
- v2.features.meta_features.parkinson_vol_window: 30
- v2.features.meta_features.rolling_d_star_window: 60
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]

### Variacion C — Kronos lookback largo (mas contexto)
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.kronos_features.lookback: 100
- v2.features.meta_features.kronos_features.sample_count: 10
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]

### Variacion D — Kronos lookback corto + mas paths (rapido, mas samples)
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.kronos_features.lookback: 30
- v2.features.meta_features.kronos_features.sample_count: 20
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]

### Variacion E — Kronos temperature baja (mas deterministic)
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.kronos_features.temperature: 0.5
- v2.features.meta_features.kronos_features.top_p: 0.8
- v2.features.meta_features.kronos_features.sample_count: 10
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]

### Variacion F — Kronos temperature alta (mas diverso, mejor uncertainty)
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.kronos_features.temperature: 1.5
- v2.features.meta_features.kronos_features.top_p: 0.95
- v2.features.meta_features.kronos_features.sample_count: 10
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]

### Variacion G — Kronos stride=3 (3x speedup, ffill intermedias)
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.kronos_features.stride: 3
- v2.features.meta_features.kronos_features.sample_count: 10
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]

### Variacion H — Vol regime asimetrico (fast=10, slow=80)
- v2.meta_vol_regime_fast: 10
- v2.meta_vol_regime_slow: 80
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]

### Variacion I — Entropy bins alto (mas granularidad de market uncertainty)
- v2.features.entropy_bins: 20
- v2.features.entropy_window: 80
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]

NO modificar strategy.params, NO modificar archivos .py.

## Estrategias a correr

Todas las graduadas en `configs/graduated/` (usar el mas reciente si hay duplicados).

## Archivos read-only

- strategies/*.py
- core/runner.py
- portfolio/
- v12/

## Como correr un experimento

```bash
cd /Users/nongo/Documents/Patacon
python -m SopaDeOtoe.launchers.run_goal_meta_features_params [--n-jobs 10]
```

## Como registrar

Append a results_log.csv (tab-separated):
date	run_id	strategy	variacion	total_return	sharpe	max_drawdown	n_trades	win_rate	status

## MINIMO DE ITERACIONES (OBLIGATORIO)

16 estrategias x 10 variaciones = 160 runs minimos.

## Regla de parada

- Todos los 160 runs completados, O
- Tiempo total > 14 horas

## Estrategia de busqueda sugerida

1. BASELINE para todas — ancla con todos los params default
2. A vs B — ventanas cortas vs largas (sensibilidad global)
3. C vs D — lookback largo vs corto en Kronos (trade-off contexto/speed)
4. E vs F — temperature baja vs alta (calibracion de uncertainty)
5. G — stride=3 (si sharpe no cae >5%, usar stride=3 en produccion)
6. H, I — ajustes finos de vol regime y entropy

Key insight: Si A (ventanas cortas) gana consistentemente, las features
estan siendo "diluidas" por ventanas demasiado largas. Si B gana, hay
demasiado ruido en ventanas cortas. Para Kronos, el trade-off clave es
lookback vs sample_count: mas contexto vs mas paths muestreados.

CUIDADO con overfit: si una variacion sube sharpe >30% vs baseline pero
n_trades cae >50%, es sospechoso. Preferir variaciones con mejora moderada
y n_trades estable.

## NUNCA PARAR

Una vez iniciado el loop, NO pausar para preguntar al usuario.
Continuar hasta completar todos los runs o alcanzar la regla de parada.
