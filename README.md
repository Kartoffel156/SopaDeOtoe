# SopaDeOtoe

**Multi-Strategy Quantitative Portfolio Combinator with v12 Backtesting Engine**

SopaDeOtoe is a quantitative trading research platform that combines a **strategy exploration layer** (powered by v12's full AFML pipeline) with a **portfolio combinator layer** that optimally blends graduated strategies using risk-parity methods and cross-validated performance testing.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Strategy Layer (v12 Pipeline)](#strategy-layer-v12-pipeline)
- [Portfolio Combinator Layer](#portfolio-combinator-layer)
- [Dashboard](#dashboard)
- [Configuration Reference](#configuration-reference)
- [Launchers](#launchers)
- [Results](#results)
- [API Documentation](docs/api.md)
- [Strategy Reference](docs/strategies.md)

---

## Overview

SopaDeOtoe operates in two distinct layers:

### Layer 1 — Strategy Exploration (`core/`)
- Runs individual trading strategies through v12's full **AFML pipeline**: features → strategy → triple barrier → meta-labeling → bet sizing → backtest
- Uses **dollar-barred** BTC-USD data (more tradeable signal than time bars)
- Parallel subprocess execution (up to 15 workers) for exploration speed
- Produces per-strategy equity curves, trade statistics, and regime analysis

### Layer 2 — Portfolio Combinator (`portfolio/`)
- Combines graduated strategies into a single portfolio using modern portfolio theory
- Supports multiple allocation methods: Equal Weight, Inverse Vol, ERC, Risk Budget, HRP
- Full **Monte Carlo validation** pipeline: permutation tests, bootstrap, correlation stress tests, SPA, and CPCV
- Volatility targeting overlay with EWMA adjustment
- Circuit breaker risk controls

---

## Architecture

```
Patacon/
├── SopaDeOtoe/                    # Main package
│   ├── core/                      # Strategy execution layer (v12 bridge)
│   │   ├── runner.py              # Parallel exploration orchestrator
│   │   └── worker.py             # Isolated subprocess worker
│   ├── portfolio/                # Portfolio combinator layer
│   │   ├── runner.py             # Backtest & live orchestration
│   │   ├── portfolio_config.py   # Configuration schema
│   │   ├── combinator.py         # Return combination & FDM
│   │   ├── covariance.py          # Covariance estimation
│   │   ├── orthogonality.py      # Strategy orthogonality checks
│   │   ├── risk_budget.py        # Allocation weight solvers
│   │   ├── vol_targeting.py       # Volatility targeting overlay
│   │   ├── rebalancer.py         # Rebalance logic & circuit breakers
│   │   ├── execution.py          # Execution modes (net-position / per-strategy)
│   │   ├── signal_emitter.py     # Signal replay for backtesting
│   │   ├── portfolio_metrics.py  # Portfolio-level performance metrics
│   │   ├── portfolio_montecarlo.py # MC validation tests
│   │   ├── portfolio_plots.py     # Plotting utilities
│   │   ├── strategy_loader.py    # Strategy config loader
│   │   ├── data_structures.py    # StrategyResult, PortfolioSignal dataclasses
│   │   └── tests/                # Unit tests for each module
│   ├── strategies/                # Graduated trading strategies (16 strategies)
│   │   ├── HypothesisH136GoldenDeathCrossAsym.py
│   │   ├── HypothesisH236MomentumReversalAsym.py
│   │   ├── HypothesisH426RSIGarchBullBear.py
│   │   ├── HypothesisH72AsymmetricRSIDrawdownShield.py
│   │   ├── HypothesisH86WonhamMarkovRefinado.py
│   │   ├── HypothesisH371MaxMinDualTriggerFreq.py
│   │   ├── HypothesisH434MaxMinDualHorizon.py
│   │   ├── HypothesisH481GoldenCrossPSAR.py
│   │   ├── HypothesisH110BollingerKyleGate.py
│   │   ├── HypothesisH203VolExpansionEntry.py
│   │   ├── HypothesisH167BollingerRangingOFIGate.py
│   │   ├── HypothesisH318TrendlineChannelSqueeze.py
│   │   ├── HypothesisH37DynamicGridInformedGate.py
│   │   ├── TSIMeanReversion.py
│   │   ├── DualMovingAverageCrossover.py
│   │   ├── MultiTimeframeTrendSignal.py
│   │   └── graduated_manifest.yaml # Strategy registry with metrics
│   ├── configs/                   # Strategy & base configs
│   │   ├── base_dollar_btc.yaml  # Base v12 config template
│   │   ├── graduated/            # Per-strategy graduated configs
│   │   └── temp/                 # Temporary runtime configs
│   ├── dashboard/                # Next.js 16 frontend
│   │   ├── src/app/              # App router pages
│   │   │   ├── page.tsx         # Home overview
│   │   │   ├── portfolio/       # Portfolio performance
│   │   │   ├── strategies/      # Strategy analysis
│   │   │   ├── trades/          # Trade log viewer
│   │   │   ├── correlation/      # Correlation matrix
│   │   │   ├── risk/             # Risk metrics
│   │   │   ├── rebalance/        # Rebalance analysis
│   │   │   ├── montecarlo/       # MC validation results
│   │   │   └── api/              # API routes (Next.js Route Handlers)
│   │   │       ├── portfolio/
│   │   │       ├── strategies/
│   │   │       ├── trades/
│   │   │       ├── correlation/
│   │   │       ├── rebalance/
│   │   │       ├── risk/
│   │   │       └── montecarlo/
│   │   └── package.json          # Next 16.1.6, React 19.2.3, Recharts 3.8
│   ├── launchers/                 # End-to-end execution scripts
│   │   ├── run_graduated_backtest.py   # Full L1+L2 pipeline
│   │   ├── compare_allocation_methods.py
│   │   ├── compare_v2_on_off.py
│   │   └── run_cpcv_validation.py
│   ├── config/
│   │   └── portfolio_settings.yaml  # Default portfolio config
│   └── results/
│       ├── exploration/          # Layer 1 per-strategy results
│       ├── portfolio/            # Layer 2 combined results
│       ├── cpcv_validation/     # CPCV test results
│       └── v2_off/               # v2 ON/OFF comparison results

└── StrategyParrot/v12/           # External dependency — v12 AFML pipeline
```

---

## Quick Start

```bash
# 1. Ensure dependencies are installed
# SopaDeOtoe uses v12 from StrategyParrot/v12/ as an external dependency
# The _path_setup.py module automatically resolves all paths

# 2. Run full pipeline (Layer 1 + Layer 2)
cd ~/Documents/Patacon
python -m SopaDeOtoe.launchers.run_graduated_backtest --n-jobs 4

# 3. Re-run only Layer 2 using existing exploration results
python -m SopaDeOtoe.launchers.run_graduated_backtest --skip-run

# 4. Start the dashboard
cd ~/Documents/Patacon/SopaDeOtoe/dashboard
npm run dev
# → http://localhost:3001

# 5. Run individual strategy via signal-only prefilter
python -m SopaDeOtoe.core.worker \
    --mode signal \
    --config configs/graduated/HypothesisH136GoldenDeathCrossAsym_20260418_160334.yaml \
    --output /tmp/signal_result.json
```

---

## Strategy Layer (v12 Pipeline)

### `core/runner.py` — Exploration Orchestrator

```python
from SopaDeOtoe.core.runner import run_exploration

results = run_exploration(
    configs=[...],           # List of strategy config dicts
    n_jobs=4,                # Parallel workers (max 15)
    output_dir=Path("results/exploration"),
)
```

**Key features:**
- Merges strategy configs with `base_dollar_btc.yaml` template
- Executes each config in an **isolated subprocess** with its own numpy seed
- Race-condition-safe run directory discovery (handles second-precision timestamps)
- Extracts metrics from v12's `results.json` (sharpe, drawdown, trades, equity curve)
- 1-hour timeout per config

### `core/worker.py` — Subprocess Worker

Called by `runner.py`, not directly. Runs `v12.main.run()` in a chrooted subprocess.

Two modes:
- `--mode full` — complete AFML pipeline (M1→M2→M3→triple-barrier→meta-labeling→backtest→MonteCarlo)
- `--mode signal` — M1→M2→M3 only (fast prefilter, no triple barrier)

### Graduated Strategies

16 strategies organized in two cohorts:

**First Cohort (2026-04-11): 8 strategies**
| Strategy | Class | Hypothesis | Type |
|---|---|---|---|
| H136 | `HypothesisH136GoldenDeathCrossAsym` | Golden/death cross with regime-asymmetric shorts | Trend-Following |
| H236 | `HypothesisH236MomentumReversalAsym` | Momentum reversal in asymmetric regimes | Mean-Reversion |
| H426 | `HypothesisH426RSIGarchBullBear` | RSI + GARCH for bull/bear regime detection | Regime |
| H72 | `HypothesisH72AsymmetricRSIDrawdownShield` | Asymmetric RSI protecting against drawdowns | Risk-Managed |
| H86 | `HypothesisH86WonhamMarkovRefinado` | Hidden Markov model for regime inference | Regime |
| H371 | `HypothesisH371MaxMinDualTriggerFreq` | Dual min/max frequency trigger | Oscillator |
| H434 | `HypothesisH434MaxMinDualHorizon` | Multi-horizon min/max signals | Oscillator |
| H481 | `HypothesisH481GoldenCrossPSAR` | Golden cross with parabolic SAR exit | Trend-Following |

**Second Cohort (2026-04-19): 8 strategies**
| Strategy | Class | Hypothesis | Type |
|---|---|---|---|
| H110 | `HypothesisH110BollingerKyleGate` | Bollinger bands with Kyle's gate | Band-based |
| H203 | `HypothesisH203VolExpansionEntry` | Volume expansion as entry signal | Volatility |
| H167 | `HypothesisH167BollingerRangingOFIGate` | Bollinger ranging with OFI gate | Band-based |
| H318 | `HypothesisH318TrendlineChannelSqueeze` | Trendline channel squeeze | Channel |
| H37 | `HypothesisH37DynamicGridInformedGate` | Dynamic grid with informed gate | Grid |
| TSI | `TSIMeanReversion` | TSI indicator for mean reversion | Momentum |
| DMA | `DualMovingAverageCrossover` | Classic dual MA crossover | Trend-Following |
| MTF | `MultiTimeframeTrendSignal` | Multi-timeframe trend alignment | Trend-Following |

---

## Portfolio Combinator Layer

### Allocation Methods

| Method | Module | Description |
|---|---|---|
| `equal_weight` | `risk_budget.py` | Equal weight per strategy |
| `inverse_vol` | `risk_budget.py` | Inverse volatility weighting |
| `erc` | `risk_budget.py` | Equal Risk Contribution (Roncalli) |
| `risk_budget` | `risk_budget.py` | Custom risk budgets via optimization |
| `hrp` | `risk_budget.py` | Hierarchical Risk Parity (Lopez de Prado) |
| `handcraft` | `risk_budget.py` | Manually specified weights |

### Pipeline Steps (`run_portfolio_backtest`)

```
1. Align all strategy return series to common DatetimeIndex
2. Orthogonality check (max correlation 0.60, effective dimension ratio 0.70)
3. Estimate covariance matrix (shrinkage/exponential/sample)
4. Compute weights via allocation method
5. Compute FDM — Forecast Diversification Multiplier (Carver Chapter 8)
6. Combine returns: R_p(t) = FDM × Σ(w_i × R_i(t))
7. Apply vol-targeting overlay (EWMA, target 25% default)
8. Compute portfolio metrics (Sharpe, Sortino, Calmar, DSR, risk attribution)
9. Run Monte Carlo validation (permutation, bootstrap, SPA, CPCV)
10. Package into PortfolioResult dataclass
```

### Volatility Targeting

```python
apply_vol_targeting(
    combined_returns,       # Portfolio return series
    target_vol=0.25,       # Annualized target volatility
    max_leverage=20.0,      # Prado: CPCV p5=+0.51 justifies up to 20×
    ewma_span=63,           # ~3-month lookback (less reactive to spikes)
)
```

### Risk Controls

**Circuit Breakers:**
- Threshold 1 (10% drawdown): monitoring begins
- Threshold 2 (15% drawdown): position reduction
- Kill switch (25% drawdown): cancel all orders

**Weight Constraints:**
- `max_weight_single`: no single strategy > 50%
- `min_weight`: minimum 5% per strategy
- Iterative renormalization until all constraints satisfied

---

## Dashboard

A **Next.js 16.1.6 + React 19.2.3** frontend for interactive portfolio analysis.

### Pages

| Route | Description |
|---|---|
| `/` | Portfolio overview with equity curve |
| `/portfolio` | Full portfolio metrics and weight allocation |
| `/strategies` | Per-strategy performance table |
| `/trades` | Trade log with entry/exit details |
| `/correlation` | Strategy correlation matrix (Spearman) |
| `/risk` | Risk metrics, drawdown, and attribution |
| `/rebalance` | Rebalance schedule and drift analysis |
| `/montecarlo` | MC validation results (permutation, bootstrap, SPA, CPCV) |

### API Routes (Next.js Route Handlers)

All routes live under `/api/` and serve JSON:

| Route | Method | Description |
|---|---|---|
| `/api/portfolio` | GET | Current portfolio state and metrics |
| `/api/strategies` | GET | List of strategies with Sharpe, weights |
| `/api/trades` | GET | Recent trades from backtest results |
| `/api/correlation` | GET | Correlation matrix JSON |
| `/api/rebalance` | GET | Rebalance history and next scheduled |
| `/api/risk` | GET | Risk metrics (VaR, ES, drawdown) |
| `/api/montecarlo` | GET | MC validation results |
| `/api/risk/attribution` | GET | Euler risk attribution breakdown |

### Tech Stack

- **Framework**: Next.js 16.1.6 (App Router)
- **UI**: React 19.2.3, Tailwind CSS 4
- **Charts**: Recharts 3.8.0
- **Icons**: Lucide React
- **Styling**: class-variance-authority, clsx, tailwind-merge
- **Language**: TypeScript 5.9.3

### Development

```bash
cd dashboard
npm install
npm run dev       # → http://localhost:3001
npm run build     # Production build
```

---

## Configuration Reference

### Base Config (`configs/base_dollar_btc.yaml`)

```yaml
ticker: BTC-USD
start: "2020-01-01"
end: "2026-03-17"
interval: 1d
bar_type: dollar            # Dollar-barred bars (more tradeable signal)
bars_per_day: 6
dollar_threshold: 301763406  # ~300M notional per dollar bar
market_type: crypto

# Execution
initial_capital: 100000.0
cost: 0.001                 # Binance spot 0.10% per side
rf_rate: 0.05
pt_sl: [2.5, 1.5]          # Profit target 2.5×, stop-loss 1.5×
max_holding: 36            # 6 days max at 6 bpd

# Risk
risk_fraction: 0.01
risk_pct: 0.02
atr_span: 14
atr_multiplier: 2.0
max_position_pct: 0.2
sizing_method: atr
kelly_half: true
drawdown_threshold_1: 0.10
drawdown_threshold_2: 0.20
scale_1: 0.5
scale_2: 0.25
```

### Portfolio Config (`config/portfolio_settings.yaml`)

```yaml
allocation:
  method: "risk_budget"          # Default: ERC via risk_budget solver
  rebalance_freq: "monthly"
  covariance_method: "shrinkage"
  covariance_halflife: 126       # ~6 months (more stable estimates)
  custom_budgets: [0.634, 0.490, ...]  # Prado CPCV-validated budgets

risk:
  target_volatility: 0.25        # 25% annualized vol target
  max_leverage: 20.0             # CPCV p5=+0.51 justifies 20× leverage
  max_weight_single: 0.50
  min_weight: 0.05
  trading_capital: 100_000.0
  vol_targeting_ewma_span: 63

execution:
  mode: "net_position"           # NetPositionExecutor (aggregated)
  min_rebalance: 0.05            # Rebalance if weight drifts > 5%
  circuit_breaker_enabled: true
  circuit_breaker_threshold_1: 0.10
  circuit_breaker_threshold_2: 0.15
  circuit_breaker_kill: 0.25

validation:
  rf_rate: 0.045
  n_permutations: 10_000
  n_bootstrap: 10_000
  bootstrap_block_size: 21        # ~1 month (21 trading days)
  run_stress_test: true
  run_spa_test: true
  run_cpcv: true
  cpcv_n_groups: 6
  cpcv_n_test_groups: 2
  cpcv_embargo_pct: 0.01         # 1% embargo to prevent look-ahead
  random_state: 42

orthogonality:
  max_correlation: 0.60          # Max pairwise Spearman correlation
  min_effective_dimension_ratio: 0.70  # N_eff ≥ 70% of N strategies
  max_overlap: 0.50

mode: "backtest"
backtest_period:
  start: "2024-01-01"
  end: "2024-12-31"
```

---

## Launchers

### `run_graduated_backtest.py` — Full L1 + L2 Pipeline

```bash
python -m SopaDeOtoe.launchers.run_graduated_backtest \
    [--n-jobs 4] \
    [--skip-run] \
    [--output-dir results/portfolio]
```

**Flow:**
1. Load graduated strategies from `graduated_manifest.yaml`
2. Execute `run_exploration` (Layer 1) — parallel v12 pipeline
3. Build `StrategyResult` objects from results.json
4. Execute `run_portfolio_backtest` (Layer 2) — combinator + MC
5. Print full report and save summary JSON

### `compare_allocation_methods.py` — Allocation Method Comparison

```bash
python -m SopaDeOtoe.launchers.compare_allocation_methods \
    [--strategies 7] \
    [--n-permutations 1000]
```

Compares Equal Weight, Inverse Vol, ERC, Risk Budget, and HRP methods against historical returns. Reports Sharpe, Sortino, Calmar, max drawdown, and DSR for each method.

### `compare_v2_on_off.py` — v2 ON/OFF Comparison

```bash
python -m SopaDeOtoe.launchers.compare_v2_on_off
```

Compares strategy performance with v2 features enabled vs disabled, loading from `results/v2_off/*.json`.

### `run_cpcv_validation.py` — CPCV Validation

```bash
python -m SopaDeOtoe.launchers.run_cpcv_validation \
    [--n-groups 6] \
    [--n-test-groups 2] \
    [--embargo 0.01]
```

Runs Combinatorial Purged Cross-Validation across graduated strategies, loading from `results/cpcv_validation/*.json`.

---

## Results

### Directory Structure

```
results/
├── exploration/           # Layer 1: per-strategy raw results
│   ├── HypothesisH136GoldenDeathCrossAsym_010204_REPRO.json
│   └── ...
├── portfolio/            # Layer 2: combined portfolio summaries
│   ├── first_cohort_20260420_042351.json
│   └── method_comparison_20260412_044839.json
├── cpcv_validation/      # CPCV test outputs
│   └── cpcv_validation_20260414_220152.json
└── v2_off/              # v2 ON/OFF comparison results
    └── v2_comparison_20260414_215056.json
```

### Exploration Result Schema

```json
{
  "config_id": "HypothesisH136GoldenDeathCrossAsym_010204_REPRO",
  "strategy": "HypothesisH136GoldenDeathCrossAsym",
  "status": "success",
  "metrics": {
    "sharpe": 1.234,
    "cum_return": 0.456,
    "max_drawdown": -0.123,
    "n_trades": 89,
    "profit_factor": 2.1,
    "calmar": 0.89,
    "long_pct": 0.72
  },
  "daily_returns": [0.001, -0.002, ...],
  "regime_summary": {...},
  "v1_vs_v2": {...},
  "v12_run_dir": "/path/to/StrategyParrot/v12/output/runs/..."
}
```

### Portfolio Summary Schema

```json
{
  "timestamp": "20260420_042351",
  "cohort": "first_cohort",
  "allocation_method": "risk_budget",
  "fdm": 1.234,
  "weights": {"H136": 0.18, "H236": 0.15, ...},
  "portfolio_metrics": {
    "sharpe": 1.456,
    "dsr": 1.123,
    "annualized_return": 0.345,
    "annualized_volatility": 0.234,
    "max_drawdown": -0.123,
    "calmar": 0.89,
    "sortino": 1.78,
    "diversification_ratio": 1.56,
    "exposure": 0.85
  },
  "correlation": {...},
  "orthogonality": {...},
  "montecarlo": {
    "permutation": {"p_value": 0.045, "observed_sharpe": 1.456},
    "bootstrap": {"sharpe_5pct": 0.89, "sharpe_95pct": 2.01}
  }
}
```

---

## Dependencies

SopaDeOtoe is **not** a standalone package. It depends on:

```
~/Documents/Patacon/
├── StrategyParrot/
│   └── v12/              # External: AFML pipeline (main.run, features, etc.)
```

Path resolution is handled automatically by `SopaDeOtoe._path_setup`:
- `SopaDeOtoe/` → Patacon/SopaDeOtoe/
- `StrategyParrot/` → Patacon/StrategyParrot/
- `v12/` → Patacon/StrategyParrot/v12/

Python packages (from v12 and system):
- `numpy`, `pandas`, `yaml`, `scipy`, `sklearn`
- Dashboard: `next@16.1.6`, `react@19.2.3`, `recharts@3.8.0`, `typescript@5.9.3`

---

## Key References

- **Carver**: "Systematic Trading" — risk parity, FDM, position sizing
- **Roncalli**: "Introduction to Risk Parity and Budgeting" — ERC, covariance estimation
- **Prado**: "Advances in Financial Machine Learning" — CPCV, SPA, bootstrap, meta-labeling
- **Lo & MacKinlay (1999)**: Regime-conditional strategies
