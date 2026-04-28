# API Documentation

SopaDeOtoe dashboard API routes — implemented as Next.js 16 Route Handlers.

---

## Base URL

```
http://localhost:3001/api
```

---

## Endpoints

---

### GET `/api/portfolio`

Returns the current portfolio state, metrics, and allocation.

**Response:**

```json
{
  "strategy_names": ["H136_...", "H236_..."],
  "weights": [0.18, 0.15, ...],
  "allocation_method": "risk_budget",
  "fdm": 1.234,
  "metrics": {
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
  "correlation": {
    "H136_...": {"H236_...": 0.45, ...},
    ...
  },
  "equity_curve": {
    "dates": ["2024-01-01", ...],
    "values": [100000, 100123, ...]
  }
}
```

---

### GET `/api/strategies`

Returns per-strategy performance data.

**Response:**

```json
{
  "strategies": [
    {
      "name": "HypothesisH136GoldenDeathCrossAsym_a1b2c3d4",
      "sharpe": 0.85,
      "total_return": 0.234,
      "max_drawdown": -0.12,
      "n_trades": 145,
      "profit_factor": 2.1,
      "calmar": 0.89,
      "long_pct": 0.72,
      "weight": 0.18
    },
    ...
  ]
}
```

---

### GET `/api/trades`

Returns recent trades from backtest results.

**Query params:**

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 100 | Max number of trades |
| `strategy` | string | all | Filter by strategy name |

**Response:**

```json
{
  "trades": [
    {
      "entry_date": "2024-03-15",
      "exit_date": "2024-03-18",
      "side": 1,
      "entry_price": 67234.5,
      "exit_price": 68512.3,
      "pnl": 1277.8,
      "pnl_pct": 0.019,
      "bars_held": 4,
      "strategy": "H136_a1b2c3d4"
    },
    ...
  ]
}
```

---

### GET `/api/correlation`

Returns the strategy correlation matrix.

**Response:**

```json
{
  "correlation": {
    "H136_a1b2c3d4": {
      "H136_a1b2c3d4": 1.0,
      "H236_b2c3d4e5": 0.34,
      ...
    },
    ...
  },
  "effective_dimension": 5.2,
  "pass_all_checks": true,
  "max_correlation": 0.45
}
```

---

### GET `/api/rebalance`

Returns rebalance schedule and drift analysis.

**Response:**

```json
{
  "current_weights": [0.18, 0.15, 0.12, ...],
  "target_weights": [0.17, 0.16, 0.13, ...],
  "drift": [0.01, -0.01, -0.01, ...],
  "last_rebalance": "2024-04-01T00:00:00Z",
  "next_scheduled": "2024-05-01T00:00:00Z",
  "rebalance_freq": "monthly",
  "needs_rebalance": false
}
```

---

### GET `/api/risk`

Returns portfolio risk metrics.

**Response:**

```json
{
  "risk_metrics": {
    "portfolio_volatility": 0.234,
    "target_volatility": 0.25,
    "current_volatility": 0.228,
    "vol_ratio": 0.912,
    "max_drawdown": -0.123,
    "dd_current": -0.023,
    "equity_peak": 124500.0,
    "equity_current": 121300.0,
    "var_95": -0.023,
    "es_95": -0.034,
    "leverage": 1.12
  },
  "risk_attribution": [
    {"strategy": "H136_a1b2c3d4", "risk_contribution": 0.21},
    {"strategy": "H236_b2c3d4e5", "risk_contribution": 0.18},
    ...
  ]
}
```

---

### GET `/api/risk/attribution`

Returns Euler risk attribution breakdown (Roncalli method).

**Response:**

```json
{
  "attribution": [
    {"strategy": "H136_a1b2c3d4", "risk_contribution": 0.21, "weight": 0.18},
    {"strategy": "H236_b2c3d4e5", "risk_contribution": 0.18, "weight": 0.15},
    ...
  ],
  "total_risk_contribution": 1.0,
  "method": "roncalli_euler"
}
```

---

### GET `/api/montecarlo`

Returns Monte Carlo validation results.

**Response:**

```json
{
  "permutation": {
    "p_value": 0.045,
    "observed_sharpe": 1.456,
    "n_permutations": 10000,
    "sharpe_distribution": [0.12, 0.34, ...]
  },
  "bootstrap": {
    "sharpe_5pct": 0.89,
    "sharpe_95pct": 2.01,
    "n_bootstrap": 10000,
    "sharpe_distribution": [0.45, 0.78, ...]
  },
  "stress_test": {
    "correlation_shock_10pct": {"sharpe": 1.23, "drawdown": -0.15},
    "correlation_shock_20pct": {"sharpe": 0.89, "drawdown": -0.22}
  },
  "spa": {
    "p_value": 0.123,
    "test_statistic": 1.45
  },
  "cpcv": {
    "sharpe_mean": 1.34,
    "sharpe_std": 0.45,
    "n_groups": 6,
    "n_test_groups": 2,
    "embargo_pct": 0.01
  }
}
```

---

## Data Flow

```
results/portfolio/first_cohort_*.json
        ↓
dashboard/src/app/api/portfolio/route.ts
        ↓
dashboard/src/app/api/strategies/route.ts
        ↓
dashboard/src/app/api/trades/route.ts
        ↓
dashboard/src/app/api/correlation/route.ts
        ↓
dashboard/src/app/api/risk/route.ts
        ↓
dashboard/src/app/api/rebalance/route.ts
        ↓
dashboard/src/app/api/montecarlo/route.ts
```

API routes read from `results/portfolio/` JSON files and serve them as HTTP responses.

---

## Adding New API Routes

1. Create the route file under `dashboard/src/app/api/{resource}/route.ts`
2. Export `GET` (and optionally `POST`, `PUT`, `DELETE`) handlers
3. Read or write data as needed
4. Return `NextResponse.json(data)`

```typescript
// dashboard/src/app/api/example/route.ts
import { NextResponse } from 'next/server';
import { readFileSync } from 'fs';
import { join } from 'path';

export async function GET() {
  const data = JSON.parse(
    readFileSync(join(process.cwd(), 'results/portfolio/latest.json'), 'utf-8')
  );
  return NextResponse.json(data);
}
```
