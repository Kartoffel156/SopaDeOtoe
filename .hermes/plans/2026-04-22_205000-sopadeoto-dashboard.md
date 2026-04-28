# Plan: Dashboard SopaDeOto

**Fecha:** 2026-04-22
**Autor:** Hermes Agent
**Tipo:** Proyecto nuevo (dashboard web)
**Ubicación del proyecto:** `/Users/nongo/Documents/Patacon/SopaDeOtoe`

---

## 1. Goal

Construir un dashboard web interactivo y visualmente profesional para el portfolio combinator **SopaDeOtoe** (vive en `SopaDeOtoe/`). El dashboard permite:

- Monitorear el estado del portfolio en tiempo real (backtest)
- Visualizar riesgo, atribución, correlación y orthogonality del cohort de estrategias
- Comparar estrategias graduadas entre sí
- Analizar el resultado del último rebalanceo (risk_budget)
- Entender visualmente si el portfolio está bien construido o tiene problemas (correlación alta, FDM bajo, etc.)
- Tomar decisiones de rebalanceo con datos claros

**Referencia visual:** El dashboard de StrategyParrot v12 (`/Users/nongo/Documents/Patacon/StrategyParrot/v12/dashboard/`) como benchmark de calidad UX/visual. El de SopaDeOto debe ser igual de limpio pero enfocado en la vista de portfolio, no de una sola estrategia.

---

## 2. Current Context / Assumptions

### Lo que existe hoy:

```
SopaDeOtoe/
├── config/portfolio_settings.yaml        # Config del portfolio
├── strategies/graduated_manifest_full.yaml  # 9 estrategias graduadas con métricas
├── results/portfolio/first_cohort_*.json  # Resultados con:
│   #   - portfolio_metrics (sharpe, dsr, max_drawdown, sortino, diversification_ratio, etc.)
│   #   - weights (risk_budget)
│   #   - risk_attribution (marginal_risk, risk_contribution_pct)
│   #   - correlation (9x9 matrix)
│   #   - orthogonality:
│   #       pca: eigenvalues, explained_variance_ratio, cumulative_variance, effective_dimension
│   #       clustering: linkage, distance_matrix, labels
│   #       flags: high-correlation alerts
```

### Assumptions:

1. **Stack:** Next.js + TypeScript + Tailwind + Recharts (misma base que StrategyParrot dashboard, para aprovechar familiaridad)
2. **Ubicación:** `SopaDeOtoe/dashboard/` — app Next.js autocontenida
3. **Data source:** Lee directo de los archivos JSON en `results/portfolio/` y `strategies/graduated_manifest_full.yaml`
4. **No backend próprio:** El dashboard es estático/SSR de lectura. No corre pipelines ni estrategias.
5. **Persistencia:** No necesita base de datos. Los resultados son archivos JSON que se actualizan cuando corre el pipeline.
6. **Puerto:** `localhost:3001` (para no chocar con el de StrategyParrot en 3000)

---

## 3. Proposed Approach

### Tech Stack

| Capa | Herramienta | Razón |
|------|------------|-------|
| Framework | Next.js 14 (App Router) | Misma base que SP dashboard |
| Lenguaje | TypeScript strict | Tipado fuerte para tipos de datos financieros |
| Styling | Tailwind CSS + CSS Variables custom | Consistencia con SP, pero theme propio de SopaDeOto |
| Gráficos | Recharts | Interactivas, animadas, React-native |
| Icons | Lucide React | Limpios, consistente |
| State | React useState/useCallback (no Zustand/Redux necesario) | Simplicidad |
| Fonts | JetBrains Mono para números, Inter para UI | igual que SP |

### Color Palette (Theme SopaDeOto)

```
--background:      #0a0a0f   (negro profundo)
--surface-1:       #111118   (cards)
--surface-2:       #1a1a22   (hover, elevated)
--border:          #2a2a3a   (bordes sutiles)
--foreground:      #e8e8f0   (texto principal)

--sf-green:        #00e5a0   (positivo, Sharpe bueno)
--sf-red:          #ff4060   (negativo, riesgo)
--sf-amber:        #f59e0b   (neutro/警告)
--sf-blue:         #3b82f6   (informativo)
--sf-purple:       #a78bfa   (portfolio, weights)
--sf-cyan:         #22d3ee   (secondary accent)

--grade-excellent: #00e5a0  (Sharpe > 0.5)
--grade-good:      #34d399  (Sharpe 0.3-0.5)
--grade-fair:      #f59e0b  (Sharpe 0.1-0.3)
--grade-poor:      #ff4060  (Sharpe < 0.1)
```

### Scale Reference (cómo interpretar cada métrica)

Se implementa como **Help Tooltip** en cada card/header de sección:

```
SHARPE RATIO:
  >= 1.0  → Excellent  (verde)
  0.5-1.0 → Good      (verde claro)
  0.3-0.5 → Fair      (amarillo)
  0.1-0.3 → Poor      (naranja)
  < 0.1   → Bad       (rojo)

MAX DRAWDOWN:
  >= -5%  → Excellent (verde)
  -5% a -10% → Good   (amarillo)
  -10% a -20% → Fair  (naranja)
  < -20%  → Poor      (rojo)

DIVERSIFICATION RATIO:
  >= 2.0  → Excellent (verde)
  1.5-2.0 → Good     (amarillo)
  1.0-1.5 → Fair     (naranja)
  1.0     → None     (rojo — no diversifica)

DSR (Deflated Sharpe Ratio):
  >= 0.95 → Statistically Significant ✓ (verde)
  0.50-0.95 → Marginal (amarillo)
  < 0.50 → Not significant (rojo)

CORRELATION:
  < 0.3  → Low (bueno — verde)
  0.3-0.6 → Medium (aceptable — amarillo)
  > 0.6  → HIGH (problema — rojo, flagged en orthogonality)

EFFECTIVE DIMENSION RATIO (effective_dim / n_strategies):
  >= 0.80 → Excellent (verde)
  0.60-0.80 → Good    (amarillo)
  0.40-0.60 → Fair   (naranja)
  < 0.40   → Poor    (rojo — demasiadas estrategias redundantes)
```

---

## 4. Dashboard Structure / Pages

### 4.1 Page: `/` (Portfolio Overview)

**Objetivo:** Vista principal — el estado del portfolio actual de un vistazo.

#### Header
- Logo SopaDeOto + nombre del cohort activo (e.g. "first_cohort")
- Badge: `9 estrategias · risk_budget · 2024-01-01 → 2024-12-31`
- Última actualización del result file (timestamp)
- Botón: "Rebalance Analyzer" → abre modal

#### Quick Stats Row (7 cards)

| Card | Valor | Color coding | Tooltip |
|------|-------|-------------|---------|
| Sharpe | 0.6475 | grade-excellent | "Ratio riesgo-retorno ajustado. >1.0 excelente, >0.5 bueno." |
| DSR | 0.7342 | grade-good | "Sharpe deflactado por múltiples tests. >0.95 = significativo." |
| Ann. Return | +14.9% | grade-excellent | "CAGR del portfolio. Compuesto anual." |
| Max DD | -34.1% | grade-fair | "Peor drawdown del período. Ver cómo se compara con B&H." |
| Sortino | 0.9178 | grade-excellent | "Return / downside deviation. Solo penaliza volatilidad negativa." |
| Diversif. Ratio | 2.93 | grade-excellent | "DR = sum(w·σ_i)/σ_portfolio. >2.0 = excelente diversificación." |
| Exposure | 46.1% | — | "% de barras con al menos una posición activa." |

#### Equity Curve Panel
- Área chart: equity del portfolio vs Buy & Hold
- Overlays: drawdown underwater (eje derecho)
- Tooltip interactivo: fecha, valor, drawdown, retorno vs B&H
- Zoom/pan con brush (Recharts Brush component)

#### Drawdown Bands
- Percentiles de drawdown: p5, p25, p50, p75, p95
- Bands animados con color gradient (verde arriba, rojo abajo)

---

### 4.2 Page: `/risk` (Risk Attribution)

**Objetivo:** Entender quién está generando el riesgo.

#### Stacked Bar — Weight vs Risk Contribution
- Eje Y: estrategias (9)
- Barras apiladas: weight% (barra sólida) + risk_contribution_pct% (barra overlay)
- Color: si weight% > risk_contrib% → la estrategia "protege"; si weight% < risk_contrib% → "consume riesgo"
- Línea vertical: 1/n (equal weight) como referencia

#### Risk Attribution Table
Columnas:
| Estrategia | Weight | Marginal Risk | Risk Contrib % | Delta (w% - rc%) | Grade |
- Delta coloreado: negativo = sobre-ponderada en riesgo (rojo), positivo = under-allocated en riesgo (verde)
- Sortable por cualquier columna
- Hover row → highlight en el bar chart

#### Marginal Risk Scatter
- X: weight%, Y: marginal_risk
- Bubble size: risk_contribution_pct
- Línea: marginal_risk = weight × (σ_portfolio / σ_i) — si está sobre la línea → riesgo proporcional al peso

---

### 4.3 Page: `/correlation` (Correlation & Orthogonality)

**Objetivo:** Ver cómo se relacionan las estrategias entre sí.

#### Correlation Heatmap
- Grid 9×9 con celdas coloreadas: azul=negativa, blanco=0, rojo=positiva alta
- Escala de color: `rgb(59, 130, 246)` (negative) → `#e8e8f0` (zero) → `rgb(255, 64, 96)` (positive)
- Hover celda → tooltip: "Estrategia A vs B: ρ = 0.XX"
- Click celda → abre scatter plot de returns de A vs B (lado derecho)
- Flags overlay: triángulo rojo en celdas >0.6 con texto "ρ=0.69"

#### Clustering Dendrogram
- Hierarchical clustering (scipy linkage → Recharts Treegraph o SVG custom)
- Muestra groupings naturales de estrategias
- Colorea por cluster groups

#### PCA Dashboard
- **Scree plot:** eigenvalues (barras) + varianza explicada acumulada (línea)
- **Effective dimension ratio:** gauge chart (n_effective / 9 estrategias)
- **Explained variance table:** PC1-PC9 con %, acumulada, eigenvalue

#### Orthogonality Flags
- Lista de alertas generadas por el pipeline:
  - "High correlation: H110BollingerKyleGate and H167BollingerRangingOFIGate (ρ=0.69 > 0.6)"
- Cada flag es un card clickeable que lleva a la celda relevante en el heatmap

---

### 4.4 Page: `/strategies` (Cohort Manager)

**Objetivo:** Gestionar las 9 estrategias graduadas.

#### Strategy Cards Grid
- 9 cards, una por estrategia
- Cada card muestra:
  - Nombre corto (e.g. "H236 MomRevAsym")
  - Badge: config_hash (últimos 4 chars)
  - Métricas individuales: Sharpe, MaxDD, Sortino, Win Rate, n_trades
  - Weight actual en el portfolio (e.g. "15.9%")
  - Indicador de estado del meta-model: healthy (verde) / collapsed (rojo)
- Cards ordenadas por Sharpe descendente por defecto
- Filtros: por Sharpe > threshold, por win_rate, por estado

#### Strategy Detail Panel (al clickear card)
- Slide-over panel desde la derecha
- Gráfico: equity individual vs. portfolio equity
- Controles: habilitar/deshabilitar estrategia → recalcula portfolio metrics
- Toggle "what-if": removiendo esta estrategia del portfolio, cuánto cae el Sharpe?

#### Comparison Mode
- Seleccionar 2-3 estrategias → comparison view
- Tabla lado a lado: métricas, drawdown, correlation entre sí
- Mini heatmap del subgrupo

---

### 4.5 Page: `/rebalance` (Rebalance Analyzer)

**Objetivo:** Simular qué pasa si cambio el método de allocation.

#### Method Selector
Botones: `equal_weight` · `inverse_vol` · `erc` · `risk_budget` · `hrp`

#### Comparison Table (5 métodos)
| Método | Sharpe | DSR | Max DD | Div. Ratio | Max Weight | Min Weight |
| weight más concentrado? | | | | | | |

#### Weight Distribution Chart
- 5 columnas de mini pie charts (uno por método)
- Misma escala de color por estrategia para comparar

#### Portfolio Metrics Comparison Chart
- Grouped bar chart: Sharpe / DSR / Sortino por método
- Línea: Diversification Ratio como overlay

#### Leverage Analysis
- Slider: "Target Volatility" → 15%, 20%, 25%, 30%
- Calcula: leverage requerido para atingir target, max drawdown proyectado
- Risk budget recalculado con leverage

---

### 4.6 Page: `/montecarlo` (Monte Carlo Validation)

**Objetivo:** Ver robustez del portfolio — no solo del backtest.

#### Bootstrap Cone
- Recharts AreaChart: cone p5/p25/p50/p75/p95 sobre el equity curve
- Área sombreada: rango de incertidumbre

#### Distribution Histograms
- 3 histogramas: distribución de Sharpe, MaxDD, Total Return
- Líneas verticales: valor real del backtest
- Percentile markers: p5, p50, p95

#### Stress Test Table
| Escenario | Sharpe | ΔSharpe | MaxDD | ΔMaxDD | Return | ΔReturn |
Scenarios: vol_inflation (20%, 50%, 100%), gap_counts (3, 5, 10), regime_shift

#### SPA / WRC
- P-value de cada test
- Badge: PASS (verde) / FAIL (rojo) con threshold

---

### 4.7 Page: `/trades` (Trade Log Consolidado)

**Objetivo:** Ver todos los trades de todas las estrategias en un solo lugar.

#### Filters
- Estrategia (multi-select)
- Side: LONG / SHORT / ALL
- Date range
- Barrier hit: profit / stop / time
- Return: >0 / <0 / ALL

#### Trades Table (virtualizada con react-window si >1000 rows)
Columnas:
| Date | Strategy | Side | Entry | Exit | Return | Bars | Barrier | MAE | MFE |
- Color coding: return >0 verde, <0 rojo
- Click row → expand → mini equity curve del trade + annotation

#### P&L Distribution
- Histograma de returns por trade
- Overlay: media, desv. estándar, skewness
- Separado por LONG vs SHORT

#### Temporal Distribution
- Heatmap calendario: días con trades profitability
- Bar chart: monthly returns (ingresos por mes)
- Day-of-week analysis: avg return por weekday

---

## 5. Component Architecture

```
dashboard/
├── app/
│   ├── layout.tsx              # Root layout con fonts y theme
│   ├── page.tsx                # Redirect → /portfolio
│   ├── portfolio/
│   │   └── page.tsx            # Portfolio overview
│   ├── risk/
│   │   └── page.tsx            # Risk attribution
│   ├── correlation/
│   │   └── page.tsx            # Correlation heatmap + PCA
│   ├── strategies/
│   │   └── page.tsx            # Cohort manager
│   ├── rebalance/
│   │   └── page.tsx            # Rebalance analyzer
│   ├── montecarlo/
│   │   └── page.tsx            # Monte Carlo validation
│   └── trades/
│       └── page.tsx            # Trade log consolidado
├── components/
│   ├── ui/                     # Componentes base reutilizables
│   │   ├── card.tsx
│   │   ├── badge.tsx
│   │   ├── tooltip.tsx
│   │   ├── slider.tsx
│   │   └── table.tsx
│   ├── charts/                 # Componentes de gráficos
│   │   ├── EquityChart.tsx
│   │   ├── CorrelationHeatmap.tsx
│   │   ├── RiskContributionBar.tsx
│   │   ├── ScreePlot.tsx
│   │   ├── DrawdownBands.tsx
│   │   ├── StrategyCard.tsx
│   │   ├── MonteCarloCone.tsx
│   │   ├── BootstrapHistogram.tsx
│   │   └── TradeDistribution.tsx
│   ├── MetricCard.tsx          # Card genérica para métricas
│   ├── GradeBadge.tsx           # Badge colorido con threshold
│   ├── ScaleReference.tsx       # Tooltip参考: qué es "bueno"
│   └── StrategyDetailPanel.tsx # Slide-over para detalle
├── lib/
│   ├── types.ts                # Tipos TypeScript (cohort, strategy, portfolio)
│   ├── data-loader.ts           # Lectores de JSON (manifest + results)
│   ├── scales.ts               # Funciones de color/grade por métrica
│   ├── formatters.ts           # formateo de números, fechas, %
│   └── mock-data.ts             # Datos hardcodeados para desarrollo
├── styles/
│   └── globals.css             # Tailwind + CSS variables del theme
└── package.json
```

---

## 6. Step-by-Step Implementation Plan

### Fase 1: Scaffolding y Theme (Días 1-2)

**Goal:** Tener el dashboard corriendo con datos mockeados, tema visual establecido.

1. Crear estructura de directorios `SopaDeOtoe/dashboard/`
2. Inicializar Next.js 14 App Router + TypeScript
3. Instalar dependencias: `recharts`, `lucide-react`, `clsx`, `tailwind-merge`
4. Configurar Tailwind con theme SopaDeOto (CSS variables del section 3)
5. Crear `lib/types.ts` — definir interfaces para:
   - `PortfolioResult` (del JSON de results)
   - `GraduatedStrategy` (del manifest)
   - `StrategyConfig`
6. Crear `lib/mock-data.ts` con datos hardcodeados del `first_cohort_20260420_195502.json`
7. Crear `components/ui/` — Card, Badge, Tooltip, Table
8. Crear `components/MetricCard.tsx` — card genérica con color coding y tooltip
9. Crear `components/GradeBadge.tsx` — badge que cambia de color según thresholds
10. Crear `components/ScaleReference.tsx` — componente reutilizable para tooltips de escala
11. Verificar: `npm run dev` en `localhost:3001` y render del layout con mock data

**Archivos a crear:**
- `dashboard/package.json`, `tsconfig.json`, `next.config.ts`, `tailwind.config.ts`
- `dashboard/app/layout.tsx`, `app/globals.css`
- `dashboard/lib/types.ts`, `dashboard/lib/mock-data.ts`, `dashboard/lib/scales.ts`, `dashboard/lib/formatters.ts`
- `dashboard/components/ui/card.tsx`, `badge.tsx`, `tooltip.tsx`, `table.tsx`
- `dashboard/components/MetricCard.tsx`, `GradeBadge.tsx`, `ScaleReference.tsx`

---

### Fase 2: Portfolio Overview Page (Días 3-5)

**Goal:** Primera página funcional con equity curve, métricas, drawdown.

1. Crear `lib/data-loader.ts` — funciones para leer:
   - `loadPortfolioResults()` — busca el JSON más reciente en `results/portfolio/`
   - `loadGraduatedManifest()` — lee `strategies/graduated_manifest_full.yaml`
2. Crear `components/charts/EquityChart.tsx` — Recharts AreaChart con:
   - Portfolio equity curve
   - Buy & Hold overlay
   - Tooltip interactivo con: fecha, valor, % return, drawdown
   - Brush para zoom
3. Crear `components/charts/DrawdownBands.tsx` — área chart del underwater curve
4. Crear `app/portfolio/page.tsx`:
   - Header con cohort info
   - Quick stats row (7 MetricCards)
   - EquityChart + DrawdownBands lado a lado
5. Implementar color coding en MetricCards con `scales.ts`

**Archivos a crear:**
- `dashboard/lib/data-loader.ts`
- `dashboard/components/charts/EquityChart.tsx`
- `dashboard/components/charts/DrawdownBands.tsx`
- `dashboard/app/portfolio/page.tsx`

**Verificación:** Los datos reales de `first_cohort_20260420_195502.json` cargan correctamente en la página.

---

### Fase 3: Risk Attribution Page (Días 6-8)

**Goal:** Visualizar quién contribuye qué al riesgo del portfolio.

1. Crear `components/charts/RiskContributionBar.tsx`:
   - Horizontal stacked bar chart
   - weight vs risk_contribution lado a lado
   - Línea de 1/n reference
2. Crear Risk Attribution Table:
   - Columnas: strategy, weight, marginal_risk, risk_contrib%, delta
   - Sortable, hoverable rows
3. Crear `app/risk/page.tsx`:
   - RiskContributionBar (panel izquierdo)
   - Risk Attribution Table (panel derecho)
4. Implementar `mock-data.ts` con datos de `risk_attribution` del JSON

**Archivos a crear:**
- `dashboard/components/charts/RiskContributionBar.tsx`
- `dashboard/app/risk/page.tsx`

---

### Fase 4: Correlation & Orthogonality Page (Días 9-12)

**Goal:** Heatmap interactivo + PCA dashboard.

1. Crear `components/charts/CorrelationHeatmap.tsx`:
   - Grid SVG custom o Recharts heatmap
   - Hover: tooltip con ρ exacto
   - Click: guardar selected pair
   - Overlay: flags (triángulos rojos en >0.6)
2. Crear `components/charts/ScreePlot.tsx`:
   - Bar chart (eigenvalues) + línea (cumulative variance %)
   - Anotaciones: effective_dimension = 7
3. Crear `app/correlation/page.tsx`:
   - CorrelationHeatmap (2/3 del ancho)
   - Selected pair scatter plot (1/3) — requiere computar returns de cada par (usar correlation matrix + std)
   - ScreePlot
   - Orthogonality flags cards
4. Implementar clustering dendrogram simple con SVG + linkage data

**Archivos a crear:**
- `dashboard/components/charts/CorrelationHeatmap.tsx`
- `dashboard/components/charts/ScreePlot.tsx`
- `dashboard/app/correlation/page.tsx`

---

### Fase 5: Strategies / Cohort Manager Page (Días 13-16)

**Goal:** Ver y gestionar las 9 estrategias graduadas.

1. Crear `components/charts/StrategyCard.tsx`:
   - Card con métricas individuales
   - Weight badge, meta-model status badge
   - Color coding por Sharpe
2. Crear `components/StrategyDetailPanel.tsx`:
   - Slide-over (offcanvas desde derecha)
   - Equity individual vs portfolio
   - What-if: remove strategy simulation
3. Crear `app/strategies/page.tsx`:
   - Filtros: Sharpe min, estado meta-model
   - Grid de StrategyCards
   - Sort controls
4. Implementar comparison mode: seleccionar 2-3 → mini comparison table

**Archivos a crear:**
- `dashboard/components/charts/StrategyCard.tsx`
- `dashboard/components/StrategyDetailPanel.tsx`
- `dashboard/app/strategies/page.tsx`

---

### Fase 6: Rebalance Analyzer (Días 17-20)

**Goal:** Simular diferentes métodos de allocation.

1. Crear `lib/allocation.ts` — implementaciones de:
   - `equalWeight(n_strategies)`
   - `inverseVol(volatilities)`
   - `erc(covariance)` — Equal Risk Contribution
   - `riskBudget(custom_budgets)` — de config
   - `hrp(returns)` — Hierarchical Risk Parity
2. Crear `lib/portfolio-calculator.ts`:
   - `computePortfolioMetrics(weights, returns_cov, returns_matrix)`
   - `computeRiskAttribution(weights, covariance)`
3. Crear `components/charts/MethodComparisonChart.tsx`:
   - Grouped bar: Sharpe/DSR/Sortino por método
4. Crear `app/rebalance/page.tsx`:
   - Method selector (botones)
   - MethodComparisonChart
   - Weights pie charts grid (5 mini pies)
   - Leverage analysis slider

**Archivos a crear:**
- `dashboard/lib/allocation.ts`
- `dashboard/lib/portfolio-calculator.ts`
- `dashboard/components/charts/MethodComparisonChart.tsx`
- `dashboard/app/rebalance/page.tsx`

---

### Fase 7: Monte Carlo Page (Días 21-24)

**Goal:** Visualizar resultados de Monte Carlo del portfolio.

1. Crear `components/charts/MonteCarloCone.tsx`:
   - AreaChart con p5/p25/p50/p75/p95 bands
   - Equity real overlay
2. Crear `components/charts/BootstrapHistogram.tsx`:
   - Histogram con línea de valor real
   - Percentile markers
3. Crear `app/montecarlo/page.tsx`:
   - BootstrapCone
   - 3 BootstrapHistograms (Sharpe, MaxDD, Return)
   - Stress test table
   - SPA/WRC badges

**Archivos a crear:**
- `dashboard/components/charts/MonteCarloCone.tsx`
- `dashboard/components/charts/BootstrapHistogram.tsx`
- `dashboard/app/montecarlo/page.tsx`

---

### Fase 8: Trades Page (Días 25-28)

**Goal:** Trade log consolidado de todas las estrategias.

1. Crear `lib/trades-loader.ts`:
   - Load trades desde `results/exploration/*/trades.csv` de cada estrategia
   - Normalize columns
2. Crear `components/charts/TradeDistribution.tsx`:
   - Histogram de returns
   - LONG vs SHORT overlay
3. Crear `app/trades/page.tsx`:
   - Filtros (estrategia, side, date, barrier)
   - Virtualized table (react-window si >1000 rows)
   - TradeDistribution chart
   - Calendar heatmap ( opcional — requiere more data)

**Archivos a crear:**
- `dashboard/lib/trades-loader.ts`
- `dashboard/components/charts/TradeDistribution.tsx`
- `dashboard/app/trades/page.tsx`

---

### Fase 9: Navigation + Polish (Días 29-30)

**Goal:** UX final, polish, responsive.

1. Crear `components/Sidebar.tsx` — navegación lateral colapsable
2. Crear `app/layout.tsx` — sidebar + contenido
3. Responsive: mobile-friendly sidebar, cards stack
4. Animaciones: page transitions, hover effects (Tailwind transitions)
5. Empty states: qué mostrar si no hay datos
6. 404 page
7. Production build test: `next build`

---

## 7. Data Flow

```
results/portfolio/*.json         ←  (pipeline genera)
strategies/graduated_manifest_full.yaml
        │
        ▼
lib/data-loader.ts
        │
        ├── loadPortfolioResults()     → PortfolioResult
        ├── loadGraduatedManifest()    → GraduatedStrategy[]
        └── loadTrades()               → Trade[]
        │
        ▼
React Server Components (page.tsx)
        │
        ├── MetricCard
        ├── EquityChart
        ├── CorrelationHeatmap
        └── ...components
        │
        ▼
Page (app/X/page.tsx)
```

---

## 8. Testing Plan

| Qué | Cómo | Criterio |
|-----|------|---------|
| Datos cargan correctamente | Comparar valores en UI vs JSON fuente | Valores exactos match |
| Color coding correcto | Threshold tests: verificar colores en cada rango | Verde/amarillo/rojo según escala |
| Equity chart | Datos del JSON: equity_curve.dates/values | Render sin errores, tooltip muestra valores |
| Correlation heatmap | Todas las 9×9=81 celdas renderizan | Celdas con valores correctos |
| Rebalance calculator | Equal weight de 9 estrategias = 11.1% cada una | Σ weights = 1.0 |
| Responsive | BrowserStack o dev tools mobile | No hay overflow horizontal |
| Build | `next build` exit code 0 | No TypeScript errors |

---

## 9. Files to Create / Modify

### Archivos a crear (nuevos):

```
SopaDeOtoe/dashboard/
├── .gitignore
├── package.json
├── tsconfig.json
├── next.config.ts
├── tailwind.config.ts
├── postcss.config.js
├── app/
│   ├── layout.tsx
│   ├── globals.css
│   ├── page.tsx                     → redirect to /portfolio
│   ├── portfolio/page.tsx
│   ├── risk/page.tsx
│   ├── correlation/page.tsx
│   ├── strategies/page.tsx
│   ├── rebalance/page.tsx
│   ├── montecarlo/page.tsx
│   └── trades/page.tsx
├── components/
│   ├── ui/
│   │   ├── card.tsx
│   │   ├── badge.tsx
│   │   ├── tooltip.tsx
│   │   ├── slider.tsx
│   │   ├── table.tsx
│   │   └── button.tsx
│   ├── charts/
│   │   ├── EquityChart.tsx
│   │   ├── DrawdownBands.tsx
│   │   ├── RiskContributionBar.tsx
│   │   ├── CorrelationHeatmap.tsx
│   │   ├── ScreePlot.tsx
│   │   ├── StrategyCard.tsx
│   │   ├── MethodComparisonChart.tsx
│   │   ├── MonteCarloCone.tsx
│   │   ├── BootstrapHistogram.tsx
│   │   └── TradeDistribution.tsx
│   ├── MetricCard.tsx
│   ├── GradeBadge.tsx
│   ├── ScaleReference.tsx
│   ├── Sidebar.tsx
│   └── StrategyDetailPanel.tsx
└── lib/
    ├── types.ts
    ├── data-loader.ts
    ├── allocation.ts
    ├── portfolio-calculator.ts
    ├── trades-loader.ts
    ├── scales.ts
    ├── formatters.ts
    └── mock-data.ts
```

---

## 10. Risks, Tradeoffs y Open Questions

### Riesgos

| Riesgo | Probabilidad | Mitigation |
|--------|-------------|------------|
| Recharts heatmap no existe tal cual — hay que construirlo custom | Media | Usar SVG grid custom o recharts ScatterChart + custom render |
| Trades CSV no tienen schema consistente entre estrategias | Alta | Normalizer que handlea columnas faltantes y different naming |
| `effective_dimension` se computa diferente entre runs | Baja | Hardcodear fórmula: `sum(eigenvalues > 1.0)` |
| Dashboard pesado con 9 estrategias y 1000+ trades | Media | Virtualized tables (react-window), memoize todo |

### Tradeoffs

1. **Custom heatmap vs library:** No existe un heatmap interactivo decente en React que no sea de pago (no quiero Plotly/Dash).权衡: hacer SVG custom — más trabajo pero control total.
2. **SSR vs CSR:** Los JSON son archivos locales. Puedo leerlos con `fs` en un Server Component y pasarlos como props, en vez de fetch en client. Esto es más rápido y no necesita API route.
3. **HRP implementation:** Roncalli HRP es no-trivial.权衡: usar `sklearn.cluster.AgglomerativeClustering` o implementar linkage a mano. Probablemente linked a la librería `riskparity.py` o similar.

### Open Questions

1. **¿Los resultados del portfolio incluyen equity_curve** o solo métricas agregadas? (Revisando JSON: solo tiene `portfolio_metrics`, no equity curve individual. Necesito reconstruir equity desde los trades o pedir a SopaDeOto que lo exporte.)
2. **¿Hay datos de trades por estrategia** en `results/exploration/*/trades.csv`? (Sí existen en SopaDeOto — ver file listing. Pero el portfolio results JSON no los tiene.)
3. **¿Cómo obtener la equity curve del portfolio** si no está en el JSON? Opciones:
   a. Pedir a SopaDeOto que genere `portfolio_equity_curve` en el result JSON
   b. Reconstruir desde trades individuales (9 archivos × 1 equity curve)
   c. Asumir que el portfolio return = weighted sum de estrategias individuales (aprox. válido si no hay rebalancing)
4. **¿Los archivos de resultados se actualizan in-place** o se crean nuevos cada run? (Parecen nuevos: `first_cohort_YYYYMMDD_HHMMSS.json` — necesito un naming convention stable para "último resultado".)
5. **¿El dashboard vive en Sopadeotoe** o en `StrategyParrot/v12/dashboard` como segunda app? (Spec dice vive en Sopadeotoe — pero comparten estructura. Considerar si es un monorepo o dos apps separadas.)

---

## 11. Priorización

| Prioridad | Fase | Razón |
|-----------|------|-------|
| 🔴 Alta | Fases 1-2 | Scaffolding + Portfolio Overview — primer valor visible |
| 🟡 Alta | Fase 3 | Risk Attribution — core del portfolio combinator |
| 🟡 Alta | Fase 4 | Correlation + Orthogonality — diferenciador principal de SopaDeOto |
| 🟢 Media | Fase 5 | Cohort Manager — útil pero no crítico |
| 🟢 Media | Fase 6 | Rebalance Analyzer — feature estrella pero compleja |
| 🟠 Baja | Fases 7-8 | Monte Carlo + Trades — si hay tiempo |
| 🟠 Baja | Fase 9 | Polish — lo hace bonito pero no funcional |

---

## 12. Definition of Done

- [ ] Dashboard corre en `localhost:3001` sin errores
- [ ] Todas las 7 páginas renderizan datos reales del `first_cohort_20260420_195502.json`
- [ ] Cada métrica tiene tooltip con escala de "qué es bueno / qué es malo"
- [ ] Color coding funciona: verde/amarillo/rojo según thresholds del section 3
- [ ] Correlation heatmap: las 81 celdas renders con los valores correctos
- [ ] Rebalance analyzer: los 5 métodos calculan y muestran pesos
- [ ] Responsive: no hay overflow horizontal en mobile (375px)
- [ ] `next build` succeeds con exit code 0
