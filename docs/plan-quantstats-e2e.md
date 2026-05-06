# Plan: quantstats end-to-end en SopaDeOtoe

## Contexto

SopaDeOtoe tiene un dashboard Next.js (`/portfolio`) que calcula métricas manualmente en TypeScript (`computeMetrics` en `route.ts`). quantstats es la librería estándar de facto en Python para analytics de estrategias — provee Sharpe, Sortino, Calmar, max drawdown, win rate, skewness, kurtosis, tail ratio, y reportes HTML interactivos (tearsheet).

Este plan implementa quantstats end-to-end:
1. Instala `quantstats` en el venv de SopaDeOtoe
2. Crea un módulo Python `portfolio/quantstats_report.py` que genera el tearsheet HTML desde los resultados del portfolio
3. Expone un endpoint API `/api/quantstats-report` que sirve el HTML
4. Añade una página `/quantstats` en el dashboard que muestra el reporte

---

## Tarea 1: Instalar quantstats

**Archivo:** `SopaDeOtoe`

**Acción:** Añadir `quantstats` al venv y a requirements.txt

```bash
cd /Users/nongo/Documents/Patacon/SopaDeOtoe
.venv/bin/pip install quantstats
.venv/bin/pip freeze | grep quantstats >> requirements.txt
```

Verificar:
```bash
.venv/bin/python3 -c "import quantstats as qs; print(qs.__version__)"
```

---

## Tarea 2: Módulo de generación de reporte

**Archivo:** `SopaDeOtoe/portfolio/quantstats_report.py` (nuevo)

Recibe:
- `returns`: pd.Series con returns diarios del portfolio
- `benchmark`: pd.Series opcional (BTC buy&hold)
- `rf`: risk-free rate (default 0.0)

Genera:
- HTML del tearsheet completo via `qs.report(html=True)`
- Métricas clave como dict (sharpe, sortino, calmar, max_dd, win_rate, skew, kurtosis, tail_ratio, etc.)

```python
"""
portfolio/quantstats_report.py
Genera quantstats tearsheet HTML desde returns del portfolio.
"""
import quantstats as qs
import pandas as pd
from typing import Optional

def generate_tearsheet(
    returns: pd.Series,
    benchmark: Optional[pd.Series] = None,
    rf: float = 0.0,
    output_path: Optional[str] = None,
) -> dict:
    """
    Genera tearsheet HTML y métricas clave.

    Args:
        returns: daily returns of the portfolio (index = dates, tz-aware OK)
        benchmark: optional benchmark returns for comparison
        rf: risk-free rate (annual, default 0.0)
        output_path: if provided, saves HTML to this path

    Returns:
        dict con métricas clave y path al HTML
    """
    qs.extend_pandas()

    # Ensure tz-aware DatetimeIndex is handled
    if hasattr(returns.index, 'tz') and returns.index.tz is not None:
        returns.index = returns.index.tz_localize(None)

    if benchmark is not None:
        if hasattr(benchmark.index, 'tz') and benchmark.index.tz is not None:
            benchmark.index = benchmark.index.tz_localize(None)

    metrics = {
        "sharpe": qs.sharpe(returns, rf=rf),
        "sortino": qs.sortino(returns, rf=rf),
        "calmar": qs.calmar(returns),
        "max_drawdown": qs.max_drawdown(returns),
        "win_rate": qs.win_rate(returns),
        "avg_win": qs.avg_win(returns),
        "avg_loss": qs.avg_loss(returns),
        "profit_factor": qs.profit_factor(returns),
        "skew": returns.skew(),
        "kurtosis": returns.kurtosis(),
        "tail_ratio": qs.tail_ratio(returns),
        "annual_return": qs.comp(returns),
        "annual_volatility": qs.volatility(returns),
        "cum_returns": qs.cum_returns_final(returns),
        "best_day": returns.max(),
        "worst_day": returns.min(),
        "volatility": qs.volatility(returns),
        "value_at_risk": qs.value_at_risk(returns),
        "conditional_value_at_risk": qs.conditional_value_at_risk(returns),
    }

    html = qs.report(html=True, returns=returns, benchmark=benchmark, rf=rf)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

    return {**metrics, "html_path": output_path}
```

---

## Tarea 3: Endpoint API `/api/quantstats-report`

**Archivo:** `SopaDeOtoe/dashboard/src/app/api/quantstats-report/route.ts` (nuevo)

Llama al módulo Python desde el API route de Next.js (usando `child_process` o mejor: un script Python separado que lee los resultados y escribe el HTML, luego el TS lo sirve).

**Diseño elegido:** Script Python que se invoca desde el API route y escribe el HTML a un archivo temporal, luego se lee y se devuelve como Response HTML.

**Alternativa más limpia:** Crear un script Python standalone `/portfolio/quantstats_script.py` que:
1. Lee los resultados del portfolio (igual que `route.ts`)
2. Calcula returns diarios
3. Genera el tearsheet HTML a `/public/quantstats/portfolio_tearsheet.html`
4. El API route simplemente devuelve un JSON con la URL del HTML y las métricas

```typescript
// dashboard/src/app/api/quantstats-report/route.ts
import { execSync } from "child_process";
import * as fs from "fs";
import * as path from "path";

const SCRIPT = "/Users/nongo/Documents/Patacon/SopaDeOtoe/portfolio/quantstats_script.py";
const OUTPUT_DIR = "/Users/nongo/Documents/Patacon/SopaDeOtoe/dashboard/public/quantstats";

export async function GET() {
  try {
    // Ensure output dir exists
    if (!fs.existsSync(OUTPUT_DIR)) {
      fs.mkdirSync(OUTPUT_DIR, { recursive: true });
    }

    const outputPath = path.join(OUTPUT_DIR, "portfolio_tearsheet.html");
    const metricsPath = path.join(OUTPUT_DIR, "metrics.json");

    // Run Python script (detached so it doesn't block)
    execSync(
      `. /Users/nongo/Documents/Patacon/SopaDeOtoe/.venv/bin/activate && \
       python3 ${SCRIPT} --output ${outputPath} --metrics-output ${metricsPath}`,
      { timeout: 60000 }
    );

    const metrics = JSON.parse(fs.readFileSync(metricsPath, "utf-8"));
    const htmlExists = fs.existsSync(outputPath);

    return Response.json({
      status: "ready",
      report_url: htmlExists ? "/quantstats/portfolio_tearsheet.html" : null,
      metrics,
    });
  } catch (err) {
    console.error("[/api/quantstats-report]", err);
    return Response.json({ error: "Failed to generate report" }, { status: 500 });
  }
}
```

**Script Python** (`portfolio/quantstats_script.py`):
- Lee `results/portfolio/first_cohort_*.json` más reciente
- Construye `returns` pd.Series desde las equity curves (igual lógica que `route.ts`)
- Opcionalmente construye benchmark (BTC buy&hold)
- Llama `generate_tearsheet()`
- Escribe HTML y metrics.json

---

## Tarea 4: Página `/quantstats` en el dashboard

**Archivo:** `SopaDeOtoe/dashboard/src/app/quantstats/page.tsx` (nuevo)

Página Next.js que:
1. Hace fetch a `/api/quantstats-report`
2. Muestra estado de carga
3. Si `report_url` existe: `<iframe src={report_url} />` a pantalla completa
4. También muestra las métricas clave en cards encima del iframe

```tsx
// dashboard/src/app/quantstats/page.tsx
"use client";
import { useEffect, useState } from "react";

interface Metrics {
  sharpe: number;
  sortino: number;
  calmar: number;
  max_drawdown: number;
  win_rate: number;
  profit_factor: number;
  cum_returns: number;
  annual_volatility: number;
}

export default function QuantStatsPage() {
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [reportUrl, setReportUrl] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/quantstats-report")
      .then((r) => r.json())
      .then((data) => {
        if (data.status === "ready") {
          setMetrics(data.metrics);
          setReportUrl(data.report_url);
          setStatus("ready");
        } else {
          setStatus("error");
        }
      })
      .catch(() => setStatus("error"));
  }, []);

  if (status === "loading") {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-gray-500">Generando tearsheet con quantstats...</p>
        </div>
      </div>
    );
  }

  if (status === "error" || !reportUrl) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-red-500">Error generando el reporte. Intenta más tarde.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Metrics summary bar */}
      <div className="grid grid-cols-4 gap-4 p-6 bg-gray-900 border-b border-gray-800">
        <MetricCard label="Sharpe" value={metrics?.sharpe?.toFixed(2) ?? "—"} />
        <MetricCard label="Sortino" value={metrics?.sortino?.toFixed(2) ?? "—"} />
        <MetricCard label="Calmar" value={metrics?.calmar?.toFixed(2) ?? "—"} />
        <MetricCard label="Max DD" value={`${((metrics?.max_drawdown ?? 0) * 100).toFixed(1)}%`} />
        <MetricCard label="Win Rate" value={`${((metrics?.win_rate ?? 0) * 100).toFixed(1)}%`} />
        <MetricCard label="Profit Factor" value={metrics?.profit_factor?.toFixed(2) ?? "—"} />
        <MetricCard label="Cum Return" value={`${((metrics?.cum_returns ?? 0) * 100).toFixed(1)}%`} />
        <MetricCard label="Ann. Vol" value={`${((metrics?.annual_volatility ?? 0) * 100).toFixed(1)}%`} />
      </div>

      {/* quantstats tearsheet iframe */}
      <iframe
        src={reportUrl}
        className="w-full border-0"
        style={{ height: "calc(100vh - 120px)" }}
        title="QuantStats Tearsheet"
      />
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-800 rounded p-4 text-center">
      <p className="text-xs text-gray-400 uppercase">{label}</p>
      <p className="text-xl font-bold text-white mt-1">{value}</p>
    </div>
  );
}
```

Añadir a `navbar` o sidebar para acceder — **aprobar con usuario antes de implementar navegación**.

---

## Tarea 5: Requirements y lock del venv

**Archivos:**
- `SopaDeOtoe/requirements.txt` — añadir `quantstats`
- `SopaDeOtoe/.venv/requirements.txt` (si existe)

---

## Archivos a crear/modificar

| Archivo | Acción |
|---------|--------|
| `portfolio/quantstats_report.py` | Crear |
| `portfolio/quantstats_script.py` | Crear |
| `dashboard/src/app/api/quantstats-report/route.ts` | Crear |
| `dashboard/src/app/quantstats/page.tsx` | Crear |
| `requirements.txt` | Modificar |
| `dashboard/next.config.ts` | Modificar (solo si hay config de CSP para iframe) |
| `dashboard/src/app/quantstats/page.tsx` (navbar link) | **Pendiente aprobación** |

---

## Verificación

```bash
# 1. quantstats instalado
.venv/bin/python3 -c "import quantstats as qs; print('qs OK', qs.__version__)"

# 2. Script genera tearsheet
.venv/bin/python3 portfolio/quantstats_script.py --output /tmp/test_tearsheet.html --metrics-output /tmp/metrics.json
# Verificar /tmp/test_tearsheet.html existe y tiene > 10KB

# 3. API route responde
curl -s http://localhost:3000/api/quantstats-report | python3 -m json.tool

# 4. Página /quantstats carga sin errores en el browser
```

---

## Notas

- `quantstats` requiere `matplotlib` y `seaborn` para los gráficos — se instalan como deps automáticamente
- El tearsheet HTML pesa ~500KB–1MB — el iframe lo maneja bien
- El script Python tarda ~10-30s en generar el report (montecarlo sampling interno de quantstats)
- Para cachear: el script puede escribir el HTML solo si el `results/portfolio/*.json` más reciente es más nuevo que el HTML generado. Añadir logic de cache en `quantstats_script.py`
