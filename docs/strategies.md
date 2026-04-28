# Strategy Reference

Complete catalog of graduated strategies in SopaDeOtoe.

---

## Strategy Registry

All strategies are registered in `strategies/graduated_manifest.yaml`. Strategies are **auto-registered** to `BaseStrategy._REGISTRY` upon `import SopaDeOtoe.strategies`.

---

## First Cohort (2026-04-11)

---

### HypothesisH136 — GoldenDeathCrossAsym

**File:** `strategies/HypothesisH136GoldenDeathCrossAsym.py`  
**Class:** `HypothesisH136GoldenDeathCrossAsym`  
**Type:** Trend-Following / Regime-Asymmetric

**Theory:**  
Asymmetric SMA cross strategy respecting price-regime context. Golden cross (fast > slow transition) → +1 always when market is bullish OR not in a confirmed bear. Death cross (fast < slow transition) → -1 ONLY when a bear regime is confirmed (rolling sign-of-returns mean < -bear_thresh).

**Rationale:**  
Assets with upward drift (BTC, equities) spend most time in bull/neutral regimes. Unfiltered death crosses produce many false shorts. Restricting shorts to confirmed bear regimes cuts false negatives at the cost of missing early shorts.

**Reference:** Lo & MacKinlay (1999) — regime-conditional strategies outperform in trending assets by aligning bet direction with drift.

**Parameters:**

| Param | Default | Description |
|---|---|---|
| `fast_period` | 5 | Fast SMA window |
| `slow_period` | 20 | Slow SMA window |
| `regime_window` | 20 | Window for regime calculation |
| `bear_thresh` | 0.18 | Bear regime threshold |
| `bull_thresh` | 0.18 | Bull regime threshold |
| `close_col` | `"Close"` | Price column |

**Signal Rules:**  
- **+1** (Golden Cross): fast SMA crosses above slow SMA AND (bull regime OR not confirmed bear)
- **-1** (Death Cross): fast SMA crosses below slow SMA AND bear regime confirmed
- **0** otherwise

---

### HypothesisH236 — MomentumReversalAsym

**File:** `strategies/HypothesisH236MomentumReversalAsym.py`  
**Class:** `HypothesisH236MomentumReversalAsym`  
**Type:** Mean-Reversion / Regime-Asymmetric

**Theory:**  
Momentum reversal plays on short-term dislocations, but only when regime context permits. Asymmetric entry: go long after short-term drawdown in bull/neutral regimes; go short after short-term rally in bear regimes.

**Parameters:**

| Param | Default | Description |
|---|---|---|
| `momentum_span` | 12 | Momentum calculation window |
| `reversal_thresh` | 0.02 | Reversal trigger threshold |
| `regime_window` | 20 | Regime detection window |
| `close_col` | `"Close"` | Price column |

---

### HypothesisH426 — RSIGarchBullBear

**File:** `strategies/HypothesisH426RSIGarchBullBear.py`  
**Class:** `HypothesisH426RSIGarchBullBear`  
**Type:** Regime / Oscillator

**Theory:**  
Combines RSI with a GARCH model for volatility regime detection. RSI levels are interpreted differently in high-vol vs low-vol regimes.

**Parameters:**

| Param | Default | Description |
|---|---|---|
| `rsi_span` | 14 | RSI lookback period |
| `rsi_oversold` | 30 | Oversold threshold |
| `rsi_overbought` | 70 | Overbought threshold |
| `garch_p` | 1 | GARCH p parameter |
| `garch_q` | 1 | GARCH q parameter |
| `close_col` | `"Close"` | Price column |

---

### HypothesisH72 — AsymmetricRSIDrawdownShield

**File:** `strategies/HypothesisH72AsymmetricRSIDrawdownShield.py`  
**Class:** `HypothesisH72AsymmetricRSIDrawdownShield`  
**Type:** Risk-Managed / Oscillator

**Theory:**  
Asymmetric RSI that increases position size when drawdown is detected (aggressive recovery) and reduces in profit-taking phases. Balances mean-reversion signals with drawdown protection.

**Parameters:**

| Param | Default | Description |
|---|---|---|
| `rsi_span` | 14 | RSI calculation window |
| `drawdown_window` | 20 | Drawdown detection window |
| `shield_factor` | 0.5 | Drawdown scaling factor |
| `close_col` | `"Close"` | Price column |

---

### HypothesisH86 — WonhamMarkovRefinado

**File:** `strategies/HypothesisH86WonhamMarkovRefinado.py`  
**Class:** `HypothesisH86WonhamMarkovRefinado`  
**Type:** Regime / Hidden Markov Model

**Theory:**  
Hidden Markov model using the Wonham filter for regime inference. Three regimes: bull, bear, ranging. Strategy adapts position sizing and direction based on the most probable regime.

**Parameters:**

| Param | Default | Description |
|---|---|---|
| `regimes` | 3 | Number of hidden states |
| `lookback` | 60 | Feature lookback for HMM |
| `close_col` | `"Close"` | Price column |

---

### HypothesisH371 — MaxMinDualTriggerFreq

**File:** `strategies/HypothesisH371MaxMinDualTriggerFreq.py`  
**Class:** `HypothesisH371MaxMinDualTriggerFreq`  
**Type:** Oscillator / Frequency

**Theory:**  
Dual min/max frequency trigger. Counts occurrences of price touching rolling min/max over a window. High-frequency touching of either boundary indicates ranging market — avoid entries. Low frequency indicates trending market — take entries in direction of trend.

**Parameters:**

| Param | Default | Description |
|---|---|---|
| `window` | 20 | Rolling window for min/max |
| `freq_thresh` | 0.3 | Frequency threshold for ranging |
| `touch_count` | 3 | Number of touches to trigger |
| `close_col` | `"Close"` | Price column |

---

### HypothesisH434 — MaxMinDualHorizon

**File:** `strategies/HypothesisH434MaxMinDualHorizon.py`  
**Class:** `HypothesisH434MaxMinDualHorizon`  
**Type:** Oscillator / Multi-Horizon

**Theory:**  
Multi-horizon min/max signals — combines short-horizon and long-horizon min/max to distinguish trending vs ranging conditions across time scales.

**Parameters:**

| Param | Default | Description |
|---|---|---|
| `short_window` | 10 | Short horizon window |
| `long_window` | 50 | Long horizon window |
| `threshold` | 0.02 | Signal threshold |
| `close_col` | `"Close"` | Price column |

---

### HypothesisH481 — GoldenCrossPSAR

**File:** `strategies/HypothesisH481GoldenCrossPSAR.py`  
**Class:** `HypothesisH481GoldenCrossPSAR`  
**Type:** Trend-Following / Parabolic SAR

**Theory:**  
Golden cross for entry direction, parabolic SAR (PSAR) for exit timing. Combines moving average trend filter with SAR's time/price stop mechanism for disciplined trend-following.

**Parameters:**

| Param | Default | Description |
|---|---|---|
| `fast_period` | 5 | Fast SMA period |
| `slow_period` | 20 | Slow SMA period |
| `psar_af` | 0.02 | PSAR acceleration factor |
| `psar_max` | 0.2 | PSAR maximum |
| `close_col` | `"Close"` | Price column |

---

## Second Cohort (2026-04-19)

---

### HypothesisH110 — BollingerKyleGate

**File:** `strategies/HypothesisH110BollingerKyleGate.py`  
**Class:** `HypothesisH110BollingerKyleGate`  
**Type:** Band-based / Kyle's Lambda

**Theory:**  
Bollinger Bands combined with Kyle's lambda (liquidity measure) as a gate. When price breaks bands but Kyle's lambda is low (low liquidity), signal is filtered as likely false break.

**Parameters:**

| Param | Default | Description |
|---|---|---|
| `bb_period` | 20 | Bollinger period |
| `bb_std` | 2.0 | Bollinger standard deviations |
| `kyle_window` | 20 | Kyle's lambda lookback |
| `close_col` | `"Close"` | Price column |

---

### HypothesisH203 — VolExpansionEntry

**File:** `strategies/HypothesisH203VolExpansionEntry.py`  
**Class:** `HypothesisH203VolExpansionEntry`  
**Type:** Volatility / Volume

**Theory:**  
Volume expansion as entry signal. Monitors rolling volume vs average volume; sudden expansion indicates institutional involvement and signals potential directional move.

**Parameters:**

| Param | Default | Description |
|---|---|---|
| `volume_window` | 20 | Volume moving average window |
| `expansion_thresh` | 2.0 | Volume expansion multiplier |
| `price_change_thresh` | 0.01 | Minimum price change |
| `close_col` | `"Close"` | Price column |
| `volume_col` | `"Volume"` | Volume column |

---

### HypothesisH167 — BollingerRangingOFIGate

**File:** `strategies/HypothesisH167BollingerRangingOFIGate.py`  
**Class:** `HypothesisH167BollingerRangingOFIGate`  
**Type:** Band-based / OFI

**Theory:**  
Bollinger-based ranging detection gated by Order Flow Imbalance (OFI). When inside Bollinger bands, OFI determines if range is stable (no entry) or unstable (mean-reversion entry).

**Parameters:**

| Param | Default | Description |
|---|---|---|
| `bb_period` | 20 | Bollinger period |
| `bb_std` | 2.0 | Bollinger standard deviations |
| `ofi_window` | 20 | OFI calculation window |
| `close_col` | `"Close"` | Price column |

---

### HypothesisH318 — TrendlineChannelSqueeze

**File:** `strategies/HypothesisH318TrendlineChannelSqueeze.py`  
**Class:** `HypothesisH318TrendlineChannelSqueeze`  
**Type:** Channel / Squeeze

**Theory:**  
Trendline channel where the channel width is used as a squeeze indicator. Narrowing channel (low channel width) followed by expansion signals an imminent move — take position in direction of channel slope.

**Parameters:**

| Param | Default | Description |
|---|---|---|
| `lookback` | 50 | Trendline lookback |
| `squeeze_thresh` | 0.5 | Squeeze threshold |
| `breakout_thresh` | 1.5 | Breakout confirmation threshold |
| `close_col` | `"Close"` | Price column |

---

### HypothesisH37 — DynamicGridInformedGate

**File:** `strategies/HypothesisH37DynamicGridInformedGate.py`  
**Class:** `HypothesisH37DynamicGridInformedGate`  
**Type:** Grid / Informed

**Theory:**  
Dynamic grid with an "informed" gate that uses price microstructure to detect when to enter grid levels vs stay in cash. More selective than naive grid strategies.

**Parameters:**

| Param | Default | Description |
|---|---|---|
| `grid_levels` | 5 | Number of grid levels |
| `grid_spacing` | 0.02 | Grid spacing in percent |
| `informed_thresh` | 0.6 | Informed gate threshold |
| `close_col` | `"Close"` | Price column |

---

### TSIMeanReversion

**File:** `strategies/TSIMeanReversion.py`  
**Class:** `TSIMeanReversion`  
**Type:** Momentum / Mean-Reversion

**Theory:**  
The True Strength Index (TSI) used for mean-reversion signals. TSI crossing above/below signal line in overbought/oversold territory triggers entries.

**Parameters:**

| Param | Default | Description |
|---|---|---|
| `fast` | 13 | TSI fast smoothing |
| `slow` | 25 | TSI slow smoothing |
| `signal` | 13 | Signal line period |
| `overbought` | 25 | Overbought threshold |
| `oversold` | -25 | Oversold threshold |
| `close_col` | `"Close"` | Price column |

---

### DualMovingAverageCrossover

**File:** `strategies/DualMovingAverageCrossover.py`  
**Class:** `DualMovingAverageCrossover`  
**Type:** Trend-Following / Moving Average

**Theory:**  
Classic dual moving average crossover with an optional confirmation filter. Fast MA crossing above slow MA → +1; fast below slow → -1.

**Parameters:**

| Param | Default | Description |
|---|---|---|
| `fast` | 10 | Fast EMA period |
| `slow` | 40 | Slow EMA period |
| `close_col` | `"Close"` | Price column |

---

### MultiTimeframeTrendSignal

**File:** `strategies/MultiTimeframeTrendSignal.py`  
**Class:** `MultiTimeframeTrendSignal`  
**Type:** Trend-Following / Multi-Timeframe

**Theory:**  
Multi-timeframe trend alignment. Aligns short, medium, and long-term trends; only generates signals when all timeframes agree on direction.

**Parameters:**

| Param | Default | Description |
|---|---|---|
| `short_window` | 5 | Short-term window |
| `medium_window` | 20 | Medium-term window |
| `long_window` | 50 | Long-term window |
| `close_col` | `"Close"` | Price column |

---

## Graduated Manifest Schema

Each entry in `strategies/graduated_manifest.yaml`:

```yaml
strategies:
  - strategy_class: HypothesisH136GoldenDeathCrossAsym
    hypothesis_number: 136
    cohort: first_cohort
    graduation_date: "2026-04-11"
    run_id: HypothesisH136GoldenDeathCrossAsym_20260411_010204
    config_file: configs/graduated/HypothesisH136GoldenDeathCrossAsym_20260411_010204.yaml
    type: trend_following
    subtype: regime_asymmetric
    metrics:
      sharpe: 0.85
      total_return: 0.234
      max_drawdown: -0.12
      n_trades: 145
    config_hash: a1b2c3d4
    notes: First cohort graduate
```

---

## Strategy Creation Checklist

To add a new strategy to SopaDeOtoe:

1. **Create the strategy file** in `strategies/` inheriting from `BaseStrategy`
2. **Register in `strategies/__init__.py`** via `from SopaDeOtoe.strategies.{YourStrategy} import ...`
3. **Create a graduated config** in `configs/graduated/{YourStrategy}_{timestamp}.yaml`
4. **Add to `strategies/graduated_manifest.yaml`**
5. **Run the full pipeline** to get exploration results
6. **Add to portfolio** via updating `config/portfolio_settings.yaml`
