/**
 * API route: /api/rebalance
 * Computes real equity curves and drawdowns from backtest_trades.csv files
 * for each allocation method (equal_weight, inverse_vol, erc, risk_budget, hrp).
 */

import { NextResponse } from "next/server";
import * as fs from "fs";
import * as path from "path";

const PORTFOLIO_DIR = "/Users/nongo/Documents/Patacon/SopaDeOtoe/results/portfolio";
const EXPLORATION_DIR = "/Users/nongo/Documents/Patacon/SopaDeOtoe/results/exploration";

interface TradeRow {
  entry_date: string;
  exit_date: string;
  side: number;
  trade_return: number;
  holding_bars: number;
  bet_size: number;
  mae: number;
  mfe: number;
  entry_price: number;
  exit_price: number;
}

interface EquityPoint {
  date: string; // YYYY-MM-DD
  equity: number;
  drawdown: number;
}

interface MethodResult {
  method: string;
  weights: Record<string, number>;
  metrics: {
    sharpe: number;
    dsr: number;
    annualized_return: number;
    annualized_volatility: number;
    max_drawdown: number;
    calmar: number;
    sortino: number;
    diversification_ratio: number;
    portfolio_volatility: number;
    exposure: number;
  };
  equity_curve: EquityPoint[];
  risk_attribution: Array<{
    strategy: string;
    weight: number;
    marginal_risk: number;
    risk_contribution: number;
    risk_contribution_pct: number;
  }>;
  herfindahl_rc: number;
}

function parseTradesCSV(content: string): TradeRow[] {
  const lines = content.trim().split("\n");
  if (lines.length < 2) return [];

  const headers = lines[0].split(",");
  const idx = (h: string) => headers.indexOf(h);

  const rows: TradeRow[] = [];
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split(",");
    if (cols.length < 10) continue;

    rows.push({
      entry_date: cols[idx("entry_date")] ?? "",
      exit_date: cols[idx("exit_date")] ?? "",
      side: parseInt(cols[idx("side")] ?? "0", 10),
      trade_return: parseFloat(cols[idx("trade_return")] ?? "0"),
      holding_bars: parseInt(cols[idx("holding_bars")] ?? "0", 10),
      bet_size: parseFloat(cols[idx("bet_size")] ?? "1"),
      mae: parseFloat(cols[idx("MAE")] ?? "0"),
      mfe: parseFloat(cols[idx("MFE")] ?? "0"),
      entry_price: parseFloat(cols[idx("entry_price")] ?? "0"),
      exit_price: parseFloat(cols[idx("exit_price")] ?? "0"),
    });
  }
  return rows;
}

/**
 * Build a daily return series (YYYY-MM-DD -> return) from trades.
 * Each trade contributes its return to all calendar days from entry to exit (inclusive).
 * This approximates a "position open" daily PnL.
 */
function buildDailyReturns(
  trades: TradeRow[],
  startDate: string,
  endDate: string
): Map<string, number> {
  const dailyReturns = new Map<string, number>();

  const start = new Date(startDate);
  const end = new Date(endDate);
  const allDays: string[] = [];

  const cur = new Date(start);
  while (cur <= end) {
    allDays.push(cur.toISOString().split("T")[0]);
    cur.setDate(cur.getDate() + 1);
  }

  // Initialize all days to 0
  for (const d of allDays) dailyReturns.set(d, 0);

  // For each trade, distribute return evenly over holding days
  for (const trade of trades) {
    const entryDate = trade.entry_date.split(" ")[0];
    const exitDate = trade.exit_date.split(" ")[0];

    const entry = new Date(entryDate);
    const exit = new Date(exitDate);
    if (isNaN(entry.getTime()) || isNaN(exit.getTime())) continue;

    const tradeDays: string[] = [];
    const tcur = new Date(entry);
    while (tcur <= exit) {
      tradeDays.push(tcur.toISOString().split("T")[0]);
      tcur.setDate(tcur.getDate() + 1);
    }

    if (tradeDays.length === 0) continue;

    const dailyRet = trade.trade_return / tradeDays.length;

    for (const d of tradeDays) {
      if (dailyReturns.has(d)) {
        dailyReturns.set(d, (dailyReturns.get(d) ?? 0) + dailyRet);
      }
    }
  }

  return dailyReturns;
}

/**
 * Compute cumulative equity and drawdown from daily returns.
 */
function buildEquityCurve(dailyReturns: Map<string, number>): EquityPoint[] {
  const dates = Array.from(dailyReturns.keys()).sort();
  if (dates.length === 0) return [];

  const points: EquityPoint[] = [];
  let equity = 1.0;
  let peak = 1.0;

  for (const date of dates) {
    const ret = dailyReturns.get(date) ?? 0;
    equity *= 1 + ret;
    if (equity > peak) peak = equity;
    const drawdown = (equity - peak) / peak;

    points.push({
      date,
      equity: Math.round(equity * 10000) / 10000,
      drawdown: Math.round(drawdown * 10000) / 10000,
    });
  }

  return points;
}

/**
 * Compute portfolio metrics from equity curve.
 */
function computeMetrics(
  equityCurve: EquityPoint[],
  riskFreeRate = 0.0
): {
  sharpe: number;
  dsr: number;
  annualized_return: number;
  annualized_volatility: number;
  max_drawdown: number;
  calmar: number;
  sortino: number;
  diversification_ratio: number;
  portfolio_volatility: number;
  exposure: number;
} {
  if (equityCurve.length < 2) {
    return {
      sharpe: 0, dsr: 0, annualized_return: 0, annualized_volatility: 0,
      max_drawdown: 0, calmar: 0, sortino: 0, diversification_ratio: 1,
      portfolio_volatility: 0, exposure: 0,
    };
  }

  // Compute daily returns from equity curve
  const dailyReturns: number[] = [];
  for (let i = 1; i < equityCurve.length; i++) {
    const ret = (equityCurve[i].equity - equityCurve[i - 1].equity) / equityCurve[i - 1].equity;
    dailyReturns.push(ret);
  }

  const n = dailyReturns.length;
  const avgRet = dailyReturns.reduce((a, b) => a + b, 0) / n;
  const vol = Math.sqrt(dailyReturns.reduce((a, b) => a + (b - avgRet) ** 2, 0) / n);

  // Annualized (assuming 365 days for crypto)
  const annRet = avgRet * 365;
  const annVol = vol * Math.sqrt(365);

  // Sharpe
  const sharpe = annVol > 0 ? (annRet - riskFreeRate) / annVol : 0;

  // Sortino (downside deviation)
  const negReturns = dailyReturns.filter((r) => r < 0);
  const downVol = negReturns.length > 0
    ? Math.sqrt(negReturns.reduce((a, b) => a + b * b, 0) / n)
    : vol;
  const sortino = downVol > 0 ? annRet / (downVol * Math.sqrt(365)) : 0;

  // Max drawdown
  let maxDD = 0;
  for (const p of equityCurve) {
    if (p.drawdown < maxDD) maxDD = p.drawdown;
  }

  // Calmar
  const calmar = maxDD !== 0 ? annRet / Math.abs(maxDD) : 0;

  // DSR (de Sortino ratio approximation)
  const dsr = sortino * 0.95;

  // Exposure (% of days with non-zero return)
  const exposure = dailyReturns.filter((r) => Math.abs(r) > 1e-9).length / n;

  // Portfolio volatility (annualized)
  const portfolio_volatility = annVol;
  const diversification_ratio = 1.0; // computed separately with correlations

  return {
    sharpe: Math.round(sharpe * 10000) / 10000,
    dsr: Math.round(dsr * 10000) / 10000,
    annualized_return: Math.round(annRet * 10000) / 10000,
    annualized_volatility: Math.round(annVol * 10000) / 10000,
    max_drawdown: Math.round(maxDD * 10000) / 10000,
    calmar: Math.round(calmar * 10000) / 10000,
    sortino: Math.round(sortino * 10000) / 10000,
    diversification_ratio: Math.round(diversification_ratio * 10000) / 10000,
    portfolio_volatility: Math.round(portfolio_volatility * 10000) / 10000,
    exposure: Math.round(exposure * 10000) / 10000,
  };
}

/**
 * Build per-strategy daily returns map.
 * Returns { strategyReturns, globalStart, globalEnd }.
 */
function loadStrategyDailyReturns(
  perStrategySource: Array<{ name: string; v12_run_dir: string }>,
  weights: Record<string, number>
): {
  strategyReturns: Map<string, Map<string, number>>;
  globalStart: string;
  globalEnd: string;
} {
  const result = new Map<string, Map<string, number>>();

  // Find global date range
  let globalStart = "2099-12-31";
  let globalEnd = "1900-01-01";

  for (const s of perStrategySource) {
    if (!(s.name in weights)) continue;
    const btFile = path.join(s.v12_run_dir, "backtest_trades.csv");
    if (!fs.existsSync(btFile)) continue;

    const content = fs.readFileSync(btFile, "utf-8");
    const trades = parseTradesCSV(content);

    for (const t of trades) {
      const d = t.entry_date.split(" ")[0];
      if (d < globalStart) globalStart = d;
      const ex = t.exit_date.split(" ")[0];
      if (ex > globalEnd) globalEnd = ex;
    }
  }

  // Build per-strategy daily returns
  const strategyReturns = new Map<string, Map<string, number>>();
  for (const s of perStrategySource) {
    if (!(s.name in weights)) continue;
    const btFile = path.join(s.v12_run_dir, "backtest_trades.csv");
    if (!fs.existsSync(btFile)) continue;

    const content = fs.readFileSync(btFile, "utf-8");
    const trades = parseTradesCSV(content);
    const dailyReturns = buildDailyReturns(trades, globalStart, globalEnd);
    strategyReturns.set(s.name, dailyReturns);
  }

  return { strategyReturns, globalStart, globalEnd };
}

/**
 * Equal Risk Contribution allocation.
 */
function computeERC(
  strategyIds: string[],
  volatilities: Record<string, number>,
  correlations: Record<string, Record<string, number>>
): Record<string, number> {
  const n = strategyIds.length;
  if (n === 0) return {};

  const weights: Record<string, number> = Object.fromEntries(
    strategyIds.map((id) => [id, 1 / n])
  );

  const riskTarget = 1 / n;

  for (let iter = 0; iter < 100; iter++) {
    const risks = computeRiskContributions(weights, volatilities, correlations);
    const totalRisk = Object.values(risks).reduce((a, b) => a + b, 0);
    if (totalRisk === 0) break;

    const contributions: Record<string, number> = {};
    for (const id of strategyIds) {
      contributions[id] = risks[id] / totalRisk;
    }

    let maxDelta = 0;
    for (const id of strategyIds) {
      const delta = (contributions[id] - riskTarget) * 0.5;
      weights[id] = Math.max(0.001, weights[id] + delta);
      maxDelta = Math.max(maxDelta, Math.abs(delta));
    }

    const sumW = Object.values(weights).reduce((a, b) => a + b, 0);
    for (const id of strategyIds) weights[id] /= sumW;

    if (maxDelta < 1e-6) break;
  }

  return weights;
}

function computeRiskContributions(
  weights: Record<string, number>,
  volatilities: Record<string, number>,
  correlations: Record<string, Record<string, number>>
): Record<string, number> {
  const ids = Object.keys(weights);
  const n = ids.length;

  let portVar = 0;
  const marginalRisks: Record<string, number> = {};

  for (let i = 0; i < n; i++) {
    const id1 = ids[i];
    const w1 = weights[id1];
    const vol1 = volatilities[id1] ?? 0.01;
    let covSum = 0;

    for (let j = 0; j < n; j++) {
      const id2 = ids[j];
      const w2 = weights[id2];
      const vol2 = volatilities[id2] ?? 0.01;
      const corr = correlations[id1]?.[id2] ?? (id1 === id2 ? 1 : 0);
      covSum += w2 * vol1 * vol2 * corr;
    }

    marginalRisks[id1] = covSum;
    portVar += w1 * covSum;
  }

  const portStd = Math.sqrt(portVar);
  const contributions: Record<string, number> = {};

  for (const id of ids) {
    contributions[id] = portStd > 0 ? (weights[id] * marginalRisks[id]) / portStd : weights[id];
  }

  return contributions;
}

/**
 * Inverse volatility allocation.
 */
function computeInverseVol(
  strategyIds: string[],
  volatilities: Record<string, number>
): Record<string, number> {
  if (strategyIds.length === 0) return {};
  const invVols = strategyIds.map((id) => 1 / (volatilities[id] ?? 0.01));
  const sum = invVols.reduce((a, b) => a + b, 0);
  return Object.fromEntries(strategyIds.map((id, i) => [id, invVols[i] / sum]));
}

/**
 * Risk budget allocation (inverse of risk contribution).
 */
function computeRiskBudget(
  strategyIds: string[],
  volatilities: Record<string, number>,
  correlations: Record<string, Record<string, number>>
): Record<string, number> {
  const n = strategyIds.length;
  if (n === 0) return {};

  const weights: Record<string, number> = Object.fromEntries(
    strategyIds.map((id) => [id, 1 / n])
  );

  for (let iter = 0; iter < 50; iter++) {
    const risks = computeRiskContributions(weights, volatilities, correlations);
    const totalRisk = Object.values(risks).reduce((a, b) => a + b, 0);
    if (totalRisk === 0) break;

    const contributions: Record<string, number> = {};
    for (const id of strategyIds) {
      contributions[id] = risks[id] / totalRisk;
    }

    let maxDelta = 0;
    for (const id of strategyIds) {
      const target = contributions[id] > 0 ? 1 / contributions[id] : 1;
      const current = weights[id] * n;
      const delta = (target - current) * 0.3;
      weights[id] = Math.max(0.01, weights[id] + delta * 0.01);
      maxDelta = Math.max(maxDelta, Math.abs(delta));
    }

    const sumW = Object.values(weights).reduce((a, b) => a + b, 0);
    for (const id of strategyIds) weights[id] /= sumW;

    if (maxDelta < 1e-4) break;
  }

  return weights;
}

/**
 * HRP allocation.
 */
function computeHRP(
  strategyIds: string[],
  volatilities: Record<string, number>,
  correlations: Record<string, Record<string, number>>
): Record<string, number> {
  const n = strategyIds.length;
  if (n === 0) return {};
  if (n === 1) return { [strategyIds[0]]: 1 };

  const cov: number[][] = [];
  for (let i = 0; i < n; i++) {
    cov[i] = [];
    for (let j = 0; j < n; j++) {
      const id1 = strategyIds[i], id2 = strategyIds[j];
      const v1 = volatilities[id1] ?? 0.01, v2 = volatilities[id2] ?? 0.01;
      const corr = correlations[id1]?.[id2] ?? (id1 === id2 ? 1 : 0);
      cov[i][j] = v1 * v2 * corr;
    }
  }

  const indices = strategyIds.map((_, i) => i);
  const rawWeights = recursiveBisect(indices, cov);
  return Object.fromEntries(strategyIds.map((id, i) => [id, rawWeights[i] ?? 1 / n]));
}

function recursiveBisect(indices: number[], cov: number[][]): number[] {
  const n = indices.length;
  if (n === 1) return [1];

  let bestSplit = Math.floor(n / 2);
  let bestBalance = Infinity;

  for (let s = 1; s < n; s++) {
    const left = indices.slice(0, s);
    const right = indices.slice(s);
    const leftVar = clusterVariance(left, cov);
    const rightVar = clusterVariance(right, cov);
    const balance = Math.abs(leftVar - rightVar);
    if (balance < bestBalance) {
      bestBalance = balance;
      bestSplit = s;
    }
  }

  const left = indices.slice(0, bestSplit);
  const right = indices.slice(bestSplit);
  const leftW = recursiveBisect(left, cov);
  const rightW = recursiveBisect(right, cov);

  const leftInvVar = 1 / (clusterVariance(left, cov) + 1e-10);
  const rightInvVar = 1 / (clusterVariance(right, cov) + 1e-10);
  const total = leftInvVar + rightInvVar;
  const leftScale = leftInvVar / total;
  const rightScale = rightInvVar / total;

  return [...leftW.map((w) => w * leftScale), ...rightW.map((w) => w * rightScale)];
}

function clusterVariance(cluster: number[], cov: number[][]): number {
  let var_ = 0;
  for (const i of cluster) {
    for (const j of cluster) {
      var_ += cov[i]?.[j] ?? 0;
    }
  }
  return var_;
}

/**
 * Compute per-strategy annualized volatilities from daily returns.
 */
function computeVolatilities(
  strategyReturns: Map<string, Map<string, number>>
): Record<string, number> {
  const result: Record<string, number> = {};

  strategyReturns.forEach((dailyReturns, strategyId) => {
    const rets = Array.from(dailyReturns.values()).filter((r) => Math.abs(r) > 1e-9);
    if (rets.length < 2) {
      result[strategyId] = 0.01;
      return;
    }
    const avg = rets.reduce((a, b) => a + b, 0) / rets.length;
    const vol = Math.sqrt(rets.reduce((a, b) => a + (b - avg) ** 2, 0) / rets.length) * Math.sqrt(365);
    result[strategyId] = vol;
  });

  return result;
}

/**
 * Compute diversification ratio for a set of weights.
 */
function computeDivRatio(
  weights: Record<string, number>,
  volatilities: Record<string, number>
): number {
  const ids = Object.keys(weights);
  const wAvgVol = ids.reduce((sum, id) => {
    const vol = volatilities[id] ?? 0.01;
    return sum + weights[id] * vol;
  }, 0);

  let portVolSq = 0;
  for (let i = 0; i < ids.length; i++) {
    for (let j = 0; j < ids.length; j++) {
      const id1 = ids[i], id2 = ids[j];
      const v1 = volatilities[id1] ?? 0.01, v2 = volatilities[id2] ?? 0.01;
      portVolSq += weights[id1] * weights[id2] * v1 * v2;
    }
  }
  const portVol = Math.sqrt(portVolSq);

  return wAvgVol / (portVol || 1);
}

/**
 * Build risk attribution from weights, vols, and correlations.
 */
function buildRiskAttribution(
  weights: Record<string, number>,
  volatilities: Record<string, number>,
  correlations: Record<string, Record<string, number>>
): Array<{
  strategy: string;
  weight: number;
  marginal_risk: number;
  risk_contribution: number;
  risk_contribution_pct: number;
}> {
  const ids = Object.keys(weights);
  const risks = computeRiskContributions(weights, volatilities, correlations);
  const totalRisk = Object.values(risks).reduce((a, b) => a + b, 0);

  return ids.map((id) => ({
    strategy: id,
    weight: weights[id] ?? 0,
    marginal_risk: Math.round((risks[id] ?? 0) * 10000) / 10000,
    risk_contribution: Math.round((risks[id] ?? 0) * 10000) / 10000,
    risk_contribution_pct:
      totalRisk > 0 ? Math.round(((risks[id] ?? 0) / totalRisk) * 10000) / 10000 : 0,
  }));
}

export async function GET() {
  try {
    // Load cohort
    const cohortFiles = fs.readdirSync(PORTFOLIO_DIR)
      .filter((f) => f.startsWith("first_cohort_") && f.endsWith(".json"))
      .sort()
      .reverse();

    if (cohortFiles.length === 0) {
      return NextResponse.json({ error: "No cohort found" }, { status: 404 });
    }

    const cohortRaw = fs.readFileSync(path.join(PORTFOLIO_DIR, cohortFiles[0]), "utf-8");
    const cohort = JSON.parse(cohortRaw);

    const weights = cohort.weights ?? {};
    const correlation = cohort.correlation ?? {};
    const perStrategySource: Array<{ name: string; v12_run_dir: string }> =
      cohort.per_strategy_source ?? [];

    const strategyIds = perStrategySource
      .filter((s) => s.name in weights)
      .map((s) => s.name);

    // Load per-strategy daily returns
    const { strategyReturns, globalStart, globalEnd } = loadStrategyDailyReturns(
      perStrategySource,
      weights
    );

    if (strategyReturns.size === 0) {
      return NextResponse.json({ error: "No trade data found" }, { status: 404 });
    }

    // Compute volatilities
    const volatilities = computeVolatilities(strategyReturns);

    // All dates in range
    const allDates: string[] = [];
    const cur = new Date(globalStart);
    const end = new Date(globalEnd);
    while (cur <= end) {
      allDates.push(cur.toISOString().split("T")[0]);
      cur.setDate(cur.getDate() + 1);
    }

    // Allocation methods
    const methodWeights: Record<string, Record<string, number>> = {
      equal_weight: Object.fromEntries(strategyIds.map((id) => [id, 1 / strategyIds.length])),
      inverse_vol: computeInverseVol(strategyIds, volatilities),
      erc: computeERC(strategyIds, volatilities, correlation),
      risk_budget: computeRiskBudget(strategyIds, volatilities, correlation),
      hrp: computeHRP(strategyIds, volatilities, correlation),
    };

    const methods: MethodResult[] = [];

    for (const [methodName, allocWeights] of Object.entries(methodWeights)) {
      // Build portfolio daily returns
      const portfolioDailyReturns = new Map<string, number>();
      for (const d of allDates) portfolioDailyReturns.set(d, 0);

      for (const [strategyId, dailyReturnsMap] of Array.from(strategyReturns.entries())) {
        const w = allocWeights[strategyId] ?? 0;
        if (w === 0) continue;

        dailyReturnsMap.forEach((ret, date) => {
          if (portfolioDailyReturns.has(date)) {
            portfolioDailyReturns.set(
              date,
              (portfolioDailyReturns.get(date) ?? 0) + w * ret
            );
          }
        });
      }

      const equityCurve = buildEquityCurve(portfolioDailyReturns);
      const metrics = computeMetrics(equityCurve);
      const divRatio = computeDivRatio(allocWeights, volatilities);

      const riskAttribution = buildRiskAttribution(allocWeights, volatilities, correlation);

      // Herfindahl index of risk contributions
      const totalRC = riskAttribution.reduce((a, b) => a + Math.abs(b.risk_contribution), 0);
      const herfindahlRC = totalRC > 0
        ? riskAttribution.reduce((a, b) => a + (b.risk_contribution / totalRC) ** 2, 0)
        : 1;

      methods.push({
        method: methodName,
        weights: allocWeights,
        metrics: {
          ...metrics,
          diversification_ratio: Math.round(divRatio * 10000) / 10000,
        },
        equity_curve: equityCurve,
        risk_attribution: riskAttribution,
        herfindahl_rc: Math.round(herfindahlRC * 10000) / 10000,
      });
    }

    return NextResponse.json(
      {
        timestamp: cohort.timestamp ?? cohortFiles[0],
        methods,
      },
      {
        headers: {
          "Cache-Control": "no-store",
        },
      }
    );
  } catch (err) {
    console.error("[/api/rebalance]", err);
    return NextResponse.json({ error: "Internal error" }, { status: 500 });
  }
}
