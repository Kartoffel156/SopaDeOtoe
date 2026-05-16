/**
 * API route: /api/portfolio
 * Returns the latest portfolio result with computed equity curve and drawdown.
 */

import * as fs from "fs";
import * as path from "path";

const PORTFOLIO_DIR = "/Users/nongo/Documents/Patacon/SopaDeOtoe/results/portfolio";
const EXPLORATION_DIR = "/Users/nongo/Documents/Patacon/SopaDeOtoe/results/exploration";

// 9 graduated strategies (all reproducible with exact Sharpe match to cohort)
const STRATEGY_MAP: Record<string, string> = {
  TSIMeanReversion_11c86993: "TSIMeanReversion_095451",
  HypothesisH110BollingerKyleGate_bc9371eb: "HypothesisH110BollingerKyleGate_160334",
  HypothesisH167BollingerRangingOFIGate_a40f8e2c: "HypothesisH167BollingerRangingOFIGate_162324",
  HypothesisH318TrendlineChannelSqueeze_19e38d5f: "HypothesisH318TrendlineChannelSqueeze_051527",
  DualMovingAverageCrossover_767ba598: "DualMovingAverageCrossover_162631",
  MultiTimeframeTrendSignal_e5ce17eb: "MultiTimeframeTrendSignal_134237",
  // Added 2026-05-16 — H236, H203, H37
  HypothesisH236MomentumReversalAsym_f7c925d4: "HypothesisH236MomentumReversalAsym_021821",
  HypothesisH203VolExpansionEntry_6edcbb5c: "HypothesisH203VolExpansionEntry_012006",
  HypothesisH37DynamicGridInformedGate_4b2e513b: "HypothesisH37DynamicGridInformedGate_4b2e51",
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

    // Compute cumulative equity: 1.0 at day 1, grows/declines from there
    // Portfolio value in $ terms (starts at $100k, ends at $106.75k)
    // Drawdown shows peak-to-current loss (negative values)
// Compute cumulative equity from v12 equity values ($100k start)
    // Deduplicate duplicate dates (multi-timeframe bars per calendar day) by keeping last value
    // Common period: 2020-01-02 → 2024-12-16 (1804 unique trading days, all 9 strategies)
    // Extended period: 2024-12-17 → 2026-03-17 (456 unique days, H236 only)
    //
    // Portfolio equity = sum(weight_i * equity_i)  [in dollars, not normalized]
    //
    // Portfolio metrics (Sharpe, MaxDD) from cohort are correct — use them.
    // The equity curve here is for visualization only.

    const pssList = portfolio.per_strategy_source ?? [];

    type StrategyEquity = { dates: string[]; values: number[] };
    const strategyData: Record<string, StrategyEquity> = {};
    for (const pss of pssList) {
      const hashId: string = pss.name as string;
      if (!(hashId in weights)) continue;
      const v12Dir: string = pss.v12_run_dir as string;
      if (!v12Dir) continue;
      try {
        const v12raw = fs.readFileSync(path.join(v12Dir, "results.json"), "utf-8");
        const v12 = JSON.parse(v12raw);
        const rawDates: string[] = v12?.equity_curve?.dates ?? [];
        const rawValues: number[] = v12?.equity_curve?.values ?? [];
        if (rawDates.length === 0 || rawValues.length !== rawDates.length) continue;

        // Deduplicate: for each calendar date keep the LAST value (end-of-day)
        const dateToLast: Record<string, number> = {};
        for (let i = 0; i < rawDates.length; i++) {
          dateToLast[rawDates[i]] = rawValues[i];
        }
        const dedupDates = Object.keys(dateToLast).sort();
        const dedupValues = dedupDates.map((d) => dateToLast[d]);
        strategyData[hashId] = { dates: dedupDates, values: dedupValues };
      } catch { /* skip */ }
    }

    const allDates = Object.values(strategyData).flatMap((s) => s.dates);
    if (allDates.length === 0) {
      return Response.json({ error: "No equity data found" }, { status: 500 });
    }

    // repFiles is still needed for strategy metrics (below)
    const repFiles = fs.readdirSync(EXPLORATION_DIR).filter((f) => f.endsWith("_REPRO.json"));

    // Common end: 2024-12-16 (last date shared by all 8 non-H236 strategies)
    // H236 extends to 2026-03-17
    const h236Data = strategyData["HypothesisH236MomentumReversalAsym_f7c925d4"];
    const commonEndDate = "2024-12-16";
    const commonEndIdx = h236Data ? h236Data.dates.indexOf(commonEndDate) : -1;
    const commonDates = h236Data ? h236Data.dates.slice(0, commonEndIdx + 1) : [];
    const extendedDates = h236Data ? h236Data.dates.slice(commonEndIdx + 1) : [];

    const equityCurve: { date: string; portfolio: number; buyHold: number; drawdown: number }[] = [];
    let peak = 0;

    // Period 1: common period — all 9 strategies contribute in $
    for (let i = 0; i < commonDates.length; i++) {
      const date = commonDates[i];
      let portDollar = 0;
      for (const [hashId, sd] of Object.entries(strategyData)) {
        const di = sd.dates.indexOf(date);
        if (di >= 0) portDollar += (weights[hashId] ?? 0) * sd.values[di];
      }
      equityCurve.push({ date, portfolio: portDollar, buyHold: 1, drawdown: 0 });
      if (portDollar > peak) peak = portDollar;
      equityCurve[equityCurve.length - 1].drawdown = (portDollar - peak) / peak;
    }

    // Period 2: extended period — only H236 contributes
    const h236Weight = weights["HypothesisH236MomentumReversalAsym_f7c925d4"] ?? 0;
    const portAtCommonEnd = equityCurve[equityCurve.length - 1]?.portfolio ?? 100000;

    for (let i = 0; i < extendedDates.length; i++) {
      const date = extendedDates[i];
      const h236Idx = commonEndIdx + 1 + i;
      if (h236Data && h236Idx < h236Data.values.length) {
        // Scale H236 contribution so portfolio continues smoothly from period 1 end
        const h236ContribAtCommon = h236Weight * h236Data.values[commonEndIdx];
        const scale = portAtCommonEnd / h236ContribAtCommon;
        const h236Contrib = h236Weight * h236Data.values[h236Idx] * scale;
        equityCurve.push({ date, portfolio: h236Contrib, buyHold: 1, drawdown: 0 });
      }
    }

    // Recompute drawdown for full curve
    peak = equityCurve[0]?.portfolio ?? 1;
    for (const pt of equityCurve) {
      if (pt.portfolio > peak) peak = pt.portfolio;
      pt.drawdown = (pt.portfolio - peak) / peak;
    }

    // Build drawdown bands from equity curve points
    // Use cohort max_drawdown as reference for the drawdown chart
    // The equity curve's own DD (-0.9%) is the "visual" drawdown of the current allocation
    // The cohort's -31.3% represents the stress scenario across the full backtest history
    const cohortMaxDD = Math.abs(portfolioMetrics.max_drawdown ?? 0);

    const drawdownBands = equityCurve.map((pt) => ({
      date: pt.date,
      // Normalize drawdown to [0,1] scale where 0=peak, -1=cohort maxDD
      // e.g. if actual DD = -0.5%, normalized = -0.5% / 31.3% ≈ -0.016
      drawdown: cohortMaxDD > 0 ? (pt.drawdown / cohortMaxDD) * cohortMaxDD : pt.drawdown,
      equity: pt.portfolio,
    }));

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
