# Plan 4 de 5: `meta_pool/` output — gating + replay ✅ IMPLEMENTADO

**Objetivo**: Probas del modelo conjunto -> posiciones gateadas -> daily_returns -> StrategyResult listo para Layer 2.

**Depende de**: Plan 3 (necesita modelo entrenado y probas por estrategia)

**Archivos creados**:
- `SopaDeOtoe/meta_pool/gating.py` ✅
- `SopaDeOtoe/meta_pool/replay.py` ✅
- `SopaDeOtoe/config/pooled_meta_settings.yaml` ✅

**Cambios adicionales**:
- `meta_pool/dataset.py`: agregado `close` a `per_strategy_data` (necesario para gating/replay)
- `meta_pool/__init__.py`: actualizado con nuevos modulos

---

## gating.py

Importa de v12 via `_path_setup`:
- `from src.bet_sizing import bet_size_from_probability, average_active_signals, discretize_signal` (bet_sizing.py:24)
- `from src.backtest import run_backtest` (backtest.py:21)

### `load_gating_config(config_path: Path) -> dict`

Lee `config/pooled_meta_settings.yaml` y extrae:
```yaml
pivots:
  default: 0.50
  HypothesisH86WonhamMarkovRefinado: 0.40  # hedge permisivo
hedge_bypass: []  # estrategias que pasan sin filtro
bet_sizing_step: 0.01
```

### `gate_positions(proba, side, labels, signal_times, close, cfg, pivot=0.50) -> pd.Series`

Replica el pipeline de v12/main.py lines 971-1030:

```python
def gate_positions(proba, side, labels, signal_times, close, cfg, pivot=0.50):
    """
    proba       : pd.Series — OOS probability por evento (index = t0)
    side        : pd.Series — {-1, +1} direccion primaria
    labels      : pd.DataFrame — con cols t1, ret
    signal_times: pd.DatetimeIndex — timestamps de senales primarias
    close       : pd.Series — precios Close (dollar bars completos)
    cfg         : dict — config_snapshot de la estrategia
    pivot       : float — umbral de decision (default 0.50)
    
    Returns: pd.Series positions indexada en close.index, valores en [-1, +1]
    """
    # 1. Probabilidad -> tamano de apuesta
    raw_sizes = proba.apply(
        lambda p: bet_size_from_probability(p, pivot=pivot)
    ).clip(lower=0.0)  # solo apuestas positivas (meta aprueba)
    
    # 2. Multiplicar por direccion del side
    sized_signals = raw_sizes * side.reindex(raw_sizes.index, method='ffill')
    
    # 3. Construir DataFrame con t0/t1 para average_active_signals
    signals_df = pd.DataFrame({
        'signal': sized_signals,
        't1': labels['t1'].reindex(sized_signals.index),
    })
    signals_df = signals_df.dropna(subset=['t1'])
    
    # 4. Promediar senales activas (concurrencia temporal)
    avg_signal = average_active_signals(signals_df)
    
    # 5. Discretizar
    positions = discretize_signal(avg_signal, step=cfg.get('bet_sizing_step', 0.01))
    
    # 6. Reindexar a close.index
    positions = positions.reindex(close.index, method='ffill').fillna(0.0)
    
    return positions
```

**Config por estrategia**: El pivot se lee del config de gating. H86WonhamMarkovRefinado usa 0.40 (mas permisivo para que el hedge sobreviva — gate G3).

**Estrategias en `hedge_bypass`**: Pasan con `side * 1.0` sin filtro del meta-modelo.

---

## replay.py

### `replay_to_returns(positions, close, cfg) -> dict`

```python
def replay_to_returns(positions, close, cfg):
    """
    Corre backtest vectorizado con el mismo cost model que v12.
    
    positions : pd.Series — output de gate_positions()
    close     : pd.Series — precios Close
    cfg       : dict — config_snapshot con cost, slippage_bps, spread_bps, initial_capital
    
    Returns: dict con keys: equity (pd.Series), positions, n_trades
    """
    from src.backtest import run_backtest
    
    results = run_backtest(
        prices=close,
        signals=positions,
        cost=cfg['cost'],                    # 0.001
        initial_capital=cfg['initial_capital'],  # 100000.0
        slippage_bps=cfg.get('slippage_bps', 2.0),
        spread_bps=cfg.get('spread_bps', 1.0),
        min_rebalance=cfg.get('min_rebalance', 0.0),
    )
    
    return {
        'equity': results['equity'],       # pd.Series
        'positions': positions,
        'n_trades': int((positions.diff().abs() > 0.01).sum()),
    }
```

### `build_strategy_result(name, replay_result, source_meta) -> StrategyResult`

Agrega equity a daily — misma logica que `run_graduated_backtest.py` lines 96-108:

```python
def build_strategy_result(name, replay_result, source_meta):
    """
    Empaqueta output de replay como StrategyResult para Layer 2.
    Layer 2 no sabe que existio Layer 1.5.
    """
    from portfolio.data_structures import StrategyResult
    
    eq = replay_result['equity']
    
    # Agregar a daily: ultimo valor por dia calendario
    daily_eq = eq.groupby(eq.index.normalize()).last().sort_index()
    daily_eq.index.name = None
    
    returns = daily_eq.pct_change().fillna(0.0).astype(float)
    returns.name = name
    equity = daily_eq.astype(float)
    equity.name = name
    
    # Positions proxy: activity indicator
    positions = (returns.abs() > 1e-12).astype(int)
    positions.name = name
    signals = positions.copy()
    signals.name = name
    
    # Metrics basicos
    ann_factor = 252
    mean_r = returns.mean()
    std_r = returns.std()
    sharpe = (mean_r / std_r * (ann_factor ** 0.5)) if std_r > 0 else 0.0
    cum_ret = (1 + returns).prod() - 1
    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max
    max_dd = float(drawdown.min())
    calmar = float(cum_ret / abs(max_dd)) if abs(max_dd) > 1e-10 else 0.0
    
    metrics = {
        'sharpe': float(sharpe),
        'total_return': float(cum_ret),
        'max_drawdown': max_dd,
        'calmar': calmar,
        'n_trades': replay_result['n_trades'],
    }
    
    return StrategyResult(
        name=name,
        returns=returns,
        equity=equity,
        positions=positions,
        signals=signals,
        metrics=metrics,
        extended_metrics={},
        montecarlo={},
        trades=[],
        meta={
            'source': 'pooled_meta',
            'daily_bars': len(daily_eq),
            **source_meta,
        },
    )
```

---

## Pipeline completo (como se usa desde el launcher)

```python
for strat_name in strategy_names:
    probas = strategy_probas[strat_name]          # de extract_strategy_probas()
    data = pool_metadata['per_strategy_data'][strat_name]
    pivot = gating_cfg['pivots'].get(strat_name, gating_cfg['pivots']['default'])
    
    if strat_name in gating_cfg['hedge_bypass']:
        # Bypass: posiciones = side * 1.0 sin filtro
        positions = data['side'].reindex(data['close'].index, method='ffill').fillna(0)
    else:
        positions = gate_positions(
            probas, data['side'], data['labels'],
            data['signal_times'], data['close'], data['config'],
            pivot=pivot,
        )
    
    replay_result = replay_to_returns(positions, data['close'], data['config'])
    
    sr = build_strategy_result(
        name=strat_name,
        replay_result=replay_result,
        source_meta={'pivot': pivot, 'v12_run_dir': data['config'].get('run_dir')},
    )
    strategy_results.append(sr)
```

---

## Verificacion

1. Con un export real de una estrategia, generar probas sinteticas (uniform 0.4-0.7)
2. `gate_positions()`: output indexado en close.index, valores sparse no-zero, rango [-1, +1]
3. `replay_to_returns()`: equity curve monotonicamente cercana a initial_capital (sin valores absurdos)
4. `build_strategy_result()`: StrategyResult con daily returns
5. Pasar el StrategyResult a `run_portfolio_backtest()` con 1 sola estrategia — confirmar que Layer 2 lo acepta sin error
6. Verificar que H86 con pivot=0.40 pasa mas trades que con pivot=0.50 (gate G3)
