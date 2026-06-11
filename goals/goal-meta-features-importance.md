# Autoresearch — Meta-Features Importance Ranking (all graduated strategies)

## Objetivo

Determinar cuales meta-features (registradas + Kronos v2) aportan mas al
meta-modelo. Correr ablation studies: cada variacion desactiva UNA meta-feature
o grupo, comparando sharpe/return vs baseline con todas activas (incluyendo Kronos).
El delta de cada ablation revela la importancia marginal de esa feature.

Metricas a comparar: sharpe, total_return, max_drawdown, n_trades.
Features con mayor caida de sharpe al desactivarse = mas importantes.

## Baseline

Todas las meta-features activas + Kronos habilitado:
- Meta-features registradas (siempre activas por defecto):
  - vol_regime, vol_of_vol, autocorr_1, rel_volume, roll_spread,
    parkinson_vol, rolling_d_star
- Meta-features experimentales (todas activadas para baseline):
  - variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum,
    kyle_entropy_ratio
- Kronos v2 features (habilitadas):
  - kronos_pred_prob_up, kronos_pred_magnitude, kronos_pred_uncertainty,
    kronos_pred_spread, kronos_agreement
- v2.meta_direction_feature: true
- v2.features.fracdiff: true
- v2.feature_prefilter.enabled: false (desactivado para medir importancia real)

## Restricciones duras

- n_trades >= 30
- max_drawdown >= -40%
- Registrar TODOS los resultados (keep y discard)

## Variables libres

### Variacion BASELINE — Todo activo (Kronos + experimentales + registradas)
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]
- v2.features.meta_features.kronos_features.enabled: true
- v2.feature_prefilter.enabled: false

### Variacion A — Sin Kronos (ablation completa Kronos)
- v2.features.meta_features.kronos_features.enabled: false
- (todo lo demas igual que BASELINE)

### Variacion B — Sin variance_ratio (ablation VR)
- v2.features.meta_features.enabled_experimental_features: [vol_accel, autocorr_momentum, kyle_entropy_ratio]
- v2.features.meta_features.kronos_features.enabled: true

### Variacion C — Sin vol_accel + autocorr_momentum (ablation momentum-vol)
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, kyle_entropy_ratio]
- v2.features.meta_features.kronos_features.enabled: true

### Variacion D — Sin kyle_entropy_ratio (ablation informed flow)
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum]
- v2.features.meta_features.kronos_features.enabled: true

### Variacion E — Sin roll_spread + parkinson_vol (ablation microstructure)
- v2.features.meta_features.disabled_meta_features: [roll_spread, parkinson_vol]
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]
- v2.features.meta_features.kronos_features.enabled: true

### Variacion F — Sin rolling_d_star (ablation stationarity)
- v2.features.meta_features.disabled_meta_features: [rolling_d_star]
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]
- v2.features.meta_features.kronos_features.enabled: true

### Variacion G — Sin fracdiff (ablation fractional differencing)
- v2.features.fracdiff: false
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]
- v2.features.meta_features.kronos_features.enabled: true

### Variacion H — Sin direction feature (ablation regime direction)
- v2.meta_direction_feature: false
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]
- v2.features.meta_features.kronos_features.enabled: true

### Variacion I — Solo Kronos (solo Kronos features, nada mas)
- v2.features.meta_features.disabled_meta_features: [roll_spread, parkinson_vol, rolling_d_star, vol_regime, vol_of_vol, autocorr_1, rel_volume]
- v2.features.meta_features.enabled_experimental_features: []
- v2.features.meta_features.kronos_features.enabled: true
- v2.meta_direction_feature: false
- v2.features.fracdiff: false

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
python -m SopaDeOtoe.launchers.run_goal_meta_features_importance [--n-jobs 10]
```

## Como registrar

Append a results_log.csv (tab-separated):
date	run_id	strategy	variacion	total_return	sharpe	max_drawdown	n_trades	status

## MINIMO DE ITERACIONES (OBLIGATORIO)

16 estrategias x 10 variaciones = 160 runs minimos.

## Regla de parada

- Todos los 160 runs completados, O
- Tiempo total > 12 horas

## Estrategia de busqueda sugerida

1. BASELINE (todo activo) para todas — ancla de comparacion
2. Variacion A (sin Kronos) — cuanto aporta Kronos al meta-modelo?
3. Variacion I (solo Kronos) — puede Kronos predecir solo?
4. Variaciones B-D — desglosar experimentales una a una
5. Variaciones E-F — microstructura y stationarity
6. Variaciones G-H — fracdiff y direction

Key insight: comparar BASELINE vs A muestra el valor marginal de Kronos.
Comparar BASELINE vs I muestra si Kronos es suficiente solo.
El ranking de importancia se obtiene ordenando |sharpe_BASELINE - sharpe_variacion|.

## NUNCA PARAR

Una vez iniciado el loop, NO pausar para preguntar al usuario.
Continuar hasta completar todos los runs o alcanzar la regla de parada.
