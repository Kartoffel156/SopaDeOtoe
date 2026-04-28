/**
 * API route: /api/portfolio
 * Returns the latest portfolio result with computed equity curve and drawdown.
 */

import * as fs from "fs";
import * as path from "path";

const PORTFOLIO_DIR = "/Users/nongo/Documents/Patacon/SopaDeOtoe/results/portfolio";
const EXPLORATION_DIR = "/Users/nongo/Documents/Patacon/SopaDeOtoe/results/exploration";

const STRATEGY_MAP: Record<string, string> = {
  HypothesisH236MomentumReversalAsym_f7c925d4: "HypothesisH236MomentumReversalAsym_021821",
  TSIMeanReversion_11c86993: "TSIMeanReversion_095404",
  HypothesisH110BollingerKyleGate_bc9371eb: "HypothesisH110BollingerKyleGate_160334",
  HypothesisH203VolExpansionEntry_6edcbb5c: "HypothesisH203VolExpansionEntry_012006",
  HypothesisH167BollingerRangingOFIGate_a40f8e2c: "HypothesisH167BollingerRangingOFIGate_162324",
  HypothesisH318TrendlineChannelSqueeze_19e38d5f: "HypothesisH318TrendlineChannelSqueeze_051527",
  HypothesisH37DynamicGridInformedGate_4b2e513b: "HypothesisH37DynamicGridInformedGate_051820",
  DualMovingAverageCrossover_767ba598: "DualMovingAverageCrossover_162631",
  MultiTimeframeTrendSignal_e5ce17eb: "MultiTimeframeTrendSignal_134237",
};

function gradeFromSharpe(s: number): string {
  if (s >= 1.5) return "Excellent";
  if (s >= 1.0) return "Good";
  if (s >= 0.5) return "Fair";
  return "Poor";
}

export async function GET() {
  try {
    // Load latest portfolio result
    const files = fs.readdirSync(PORTFOLIO_DIR)
      .filter((f) => f.startsWith("first_cohort_") && f.endsWith(".json"))
      .sort()
      .reverse();

    if (files.length === 0) {
      return Response.json({ error: "No portfolio results found" }, { status: 404 });
    }

    const raw = fs.readFileSync(path.join(PORTFOLIO_DIR, files[0]), "utf-8");
    const portfolio = JSON.parse(raw);

    const weights = portfolio.weights ?? {};
    const portfolioMetrics = portfolio.portfolio_metrics ?? {};

    // Build equity curve from per-strategy daily returns
    const repFiles = fs.readdirSync(EXPLORATION_DIR).filter((f) => f.endsWith("_REPRO.json"));
    const series: Record<string, number[]> = {};

    for (const [hashId, filePrefix] of Object.entries(STRATEGY_MAP)) {
      if (!(hashId in weights)) continue;
      const match = repFiles.find((f) => f.startsWith(filePrefix));
      if (!match) continue;
      try {
        const sraw = fs.readFileSync(path.join(EXPLORATION_DIR, match), "utf-8");
        const sdata = JSON.parse(sraw);
        if (sdata.daily_returns) series[hashId] = sdata.daily_returns;
      } catch { /* skip */ }
    }

    const lens = Object.values(series).map((s) => s.length);
    const minLen = Math.min(...lens);
    let equity = 1;
    const equityCurve: { date: string; portfolio: number; buyHold: number; drawdown: number }[] = [{ date: "2023-01-01", portfolio: 1, buyHold: 1, drawdown: 0 }];
    const start = new Date("2023-01-01");

    if (minLen > 0 && minLen !== Infinity) {
      const aligned: Record<string, number[]> = {};
      for (const [k, v] of Object.entries(series)) {
        aligned[k] = v.slice(v.length - minLen);
      }

      for (let i = 0; i < minLen; i++) {
        let r = 0;
        for (const [hashId, rets] of Object.entries(aligned)) {
          r += (weights[hashId] ?? 0) * rets[i];
        }
        equity *= 1 + r;
        const d = new Date(start);
        d.setDate(d.getDate() + i);
        equityCurve.push({ date: d.toISOString().split("T")[0], portfolio: equity, buyHold: 1, drawdown: 0 });
      }
    }

    // Build drawdown
    let peak = equityCurve[0]?.portfolio ?? 1;
    const drawdownBands = equityCurve.map((pt) => {
      if (pt.portfolio > peak) peak = pt.portfolio;
      return { date: pt.date, drawdown: (pt.portfolio - peak) / peak, equity: pt.portfolio };
    });

    // Strategy metrics from per-strategy REPRO files
    const strategyRows = [];
    for (const [hashId, filePrefix] of Object.entries(STRATEGY_MAP)) {
      const match = repFiles.find((f) => f.startsWith(filePrefix));
      if (!match) continue;
      try {
        const sraw = fs.readFileSync(path.join(EXPLORATION_DIR, match), "utf-8");
        const sdata = JSON.parse(sraw) as { metrics?: Record<string, number> };
        const m = sdata.metrics ?? {};
        strategyRows.push({
          name: hashId.replace(/_[a-f0-9]{8}$/, ""),
          sharpe: m.sharpe ?? 0,
          total_return: m.cum_return ?? 0,
          max_drawdown: m.max_drawdown ?? 0,
          calmar: m.calmar ?? 0,
          sortino: 0,
          grade: gradeFromSharpe(m.sharpe ?? 0),
        });
      } catch { /* skip */ }
    }

    // Method comparison for rebalance page
    const mcFiles = fs.readdirSync(PORTFOLIO_DIR)
      .filter((f) => f.startsWith("method_comparison_") && f.endsWith(".json"))
      .sort()
      .reverse();
    let methodComparison: Record<string, unknown>[] = [];
    if (mcFiles.length > 0) {
      try {
        const mcRaw = fs.readFileSync(path.join(PORTFOLIO_DIR, mcFiles[0]), "utf-8");
        methodComparison = JSON.parse(mcRaw).methods ?? [];
      } catch { /* skip */ }
    }

    return Response.json({
      portfolio,
      portfolio_metrics: portfolioMetrics,
      weights,
      risk_attribution: portfolio.risk_attribution ?? [],
      equity_curve: equityCurve,
      drawdown_bands: drawdownBands,
      strategies: strategyRows,
      method_comparison: methodComparison,
    });
  } catch (err) {
    console.error("[/api/portfolio]", err);
    return Response.json({ error: "Internal error" }, { status: 500 });
  }
}
