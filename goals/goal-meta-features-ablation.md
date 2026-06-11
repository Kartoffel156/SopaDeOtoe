# Autoresearch — Meta-Features Ablation & Combination (all graduated strategies)

## Objetivo

Activar y desactivar combinaciones de meta-features (registradas + Kronos v2)
para encontrar el subset optimo que maximiza return ajustado al riesgo.
Cada variacion representa un "perfil de features" diferente.
El foco es en calidad de trades: sharpe, win_rate, calmar_ratio.

A diferencia del Goal 1 (importancia individual), aqui se prueban COMBINACIONES
para detectar interacciones y sinergias entre features.

## Baseline

Defaults actuales (sin experimentales, sin Kronos):
- v2.features.meta_features.enabled_experimental_features: []
- v2.features.meta_features.kronos_features.enabled: false
- v2.feature_prefilter.enabled: true
- v2.feature_prefilter.threshold: 0.01

## Restricciones duras

- n_trades >= 30
- max_drawdown >= -40%
- Registrar TODOS los resultados

## Variables libres

IMPORTANTE: Todas las variaciones A-G desactivan el prefilter (v2.feature_prefilter.enabled: false)
para que las features experimentales/Kronos NO sean eliminadas por el filtro MI antes de llegar
al meta-modelo. Sin esto, el prefilter puede descartar las features nuevas y colapsar los resultados.

### Variacion BASELINE — Defaults (sin experimentales, sin Kronos)
- v2.feature_prefilter.enabled: false

### Variacion A — Kronos only (sin experimentales)
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.enabled_experimental_features: []
- v2.feature_prefilter.enabled: false

### Variacion B — Experimentales only (sin Kronos)
- v2.features.meta_features.kronos_features.enabled: false
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]
- v2.feature_prefilter.enabled: false

### Variacion C — Kronos + experimentales (todo activo)
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]
- v2.feature_prefilter.enabled: false

### Variacion D — Kronos + variance_ratio (prediccion + momentum structure)
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20]
- v2.feature_prefilter.enabled: false

### Variacion E — Kronos + kyle_entropy_ratio (prediccion + informed flow)
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.enabled_experimental_features: [kyle_entropy_ratio]
- v2.feature_prefilter.enabled: false

### Variacion F — Kronos + vol_accel (prediccion + vol expansion)
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.enabled_experimental_features: [vol_accel]
- v2.feature_prefilter.enabled: false

### Variacion G — Todo activo + sin microstructure (ablation ruido)
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]
- v2.features.meta_features.disabled_meta_features: [roll_spread, parkinson_vol]
- v2.feature_prefilter.enabled: false

### Variacion H — Todo activo + prefilter agresivo (anti-overfit)
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, variance_ratio_20, vol_accel, autocorr_momentum, kyle_entropy_ratio]
- v2.feature_prefilter.enabled: true
- v2.feature_prefilter.threshold: 0.05
- v2.feature_prefilter.min_features: 3

### Variacion I — Kronos + top-2 experimentales + sin prefilter
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.enabled_experimental_features: [variance_ratio_5, kyle_entropy_ratio]
- v2.feature_prefilter.enabled: false

### Variacion J — Minimal: solo registradas core + Kronos agreement
- v2.features.meta_features.kronos_features.enabled: true
- v2.features.meta_features.disabled_meta_features: [roll_spread, rolling_d_star]
- v2.features.meta_features.enabled_experimental_features: []
- v2.feature_prefilter.enabled: true
- v2.feature_prefilter.threshold: 0.03

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
python -m SopaDeOtoe.launchers.run_goal_meta_features_ablation [--n-jobs 10]
```

## Como registrar

Append a results_log.csv (tab-separated):
date	run_id	strategy	variacion	total_return	sharpe	max_drawdown	n_trades	win_rate	status

## MINIMO DE ITERACIONES (OBLIGATORIO)

16 estrategias x 11 variaciones = 176 runs minimos.

## Regla de parada

- Todos los 176 runs completados, O
- Tiempo total > 14 horas

## Estrategia de busqueda sugerida

1. BASELINE + A + B + C primero — establece los 4 escenarios base
2. Comparar: Kronos solo (A) vs experimentales solo (B) vs combo (C)
3. Si C > max(A, B) — hay sinergia, las features son complementarias
4. Si C ~ max(A, B) — redundancia, simplificar
5. Variaciones D-F — cual experimental combina mejor con Kronos?
6. Variaciones G-J — fine-tuning del subset ganador

Key insight: El n_trades es critico aqui. Si una combinacion sube sharpe pero
baja n_trades drasticamente, puede ser que el modelo se volvio muy selectivo
(overfitting a high-confidence trades). Buscar el sweet spot sharpe/n_trades.

## NUNCA PARAR

Una vez iniciado el loop, NO pausar para preguntar al usuario.
Continuar hasta completar todos los runs o alcanzar la regla de parada.
