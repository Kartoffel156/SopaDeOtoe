/**
 * Portfolio Risk Analytics
 * Computes portfolio volatility, risk attribution, diversification ratio
 */

import type { RiskAttributionItem } from "./types";

/**
 * Compute portfolio volatility given weights, volatilities, and correlations
 */
export function portfolioVolatility(
  weights: Record<string, number>,
  volatilities: Record<string, number>,
  correlations: Record<string, Record<string, number>>
): number {
  const ids = Object.keys(weights);
  const n = ids.length;
  if (n === 0) return 0;

  let varSum = 0;

  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const id1 = ids[i];
      const id2 = ids[j];
      const w1 = weights[id1] ?? 0;
      const w2 = weights[id2] ?? 0;
      const v1 = volatilities[id1] ?? 0.01;
      const v2 = volatilities[id2] ?? 0.01;
      const corr = correlations[id1]?.[id2] ?? (id1 === id2 ? 1 : 0);
      varSum += w1 * w2 * v1 * v2 * corr;
    }
  }

  return Math.sqrt(Math.max(0, varSum));
}

/**
 * Compute risk attribution for each strategy
 * Uses Buhl-Marcus (2009) approach for marginal risk contributions
 */
export function computeRiskAttribution(
  weights: Record<string, number>,
  volatilities: Record<string, number>,
  correlations: Record<string, Record<string, number>>
): RiskAttributionItem[] {
  const ids = Object.keys(weights);
  const n = ids.length;

  if (n === 0) return [];

  // Compute portfolio variance
  let portVar = 0;
  const covSums: Record<string, number> = {};
  const vols: Record<string, number> = {};

  for (let i = 0; i < n; i++) {
    const id1 = ids[i];
    const w1 = weights[id1] ?? 0;
    const v1 = volatilities[id1] ?? 0.01;
    vols[id1] = v1;
    let covSum = 0;

    for (let j = 0; j < n; j++) {
      const id2 = ids[j];
      const w2 = weights[id2] ?? 0;
      const v2 = volatilities[id2] ?? 0.01;
      const corr = correlations[id1]?.[id2] ?? (id1 === id2 ? 1 : 0);
      covSum += w2 * v1 * v2 * corr;
    }

    covSums[id1] = covSum;
    portVar += w1 * covSum;
  }

  const portStd = Math.sqrt(Math.max(0, portVar));

  // Marginal risk contribution: d(sigma_p)/d(w_i) = covSum_i / sigma_p
  const marginalRisks: Record<string, number> = {};
  for (const id of ids) {
    marginalRisks[id] = portStd > 0 ? covSums[id] / portStd : 0;
  }

  // Risk contribution = w_i * marginal_risk_i
  const rawRisks: Record<string, number> = {};
  for (const id of ids) {
    rawRisks[id] = (weights[id] ?? 0) * marginalRisks[id];
  }
  const totalRisk = Object.values(rawRisks).reduce((a, b) => a + b, 0);

  // Build result
  return ids.map((id) => {
    const weight = weights[id] ?? 0;
    const marginal = marginalRisks[id] ?? 0;
    const riskContrib = rawRisks[id] ?? 0;
    const pct = totalRisk > 0 ? riskContrib / totalRisk : 0;

    return {
      strategy: id,
      weight,
      marginal_risk: marginal,
      risk_contribution: riskContrib,
      risk_contribution_pct: pct,
    };
  }).sort((a, b) => b.risk_contribution_pct - a.risk_contribution_pct);
}

/**
 * Diversification ratio: weighted avg vol / portfolio vol
 * Ratio > 1 means diversification is helping reduce risk
 */
export function diversificationRatio(
  weights: Record<string, number>,
  volatilities: Record<string, number>,
  correlations: Record<string, Record<string, number>>
): number {
  const ids = Object.keys(weights);

  if (ids.length === 0) return 1;

  // Weighted average volatility
  const wAvgVol = ids.reduce((sum, id) => {
    const w = weights[id] ?? 0;
    const v = volatilities[id] ?? 0.01;
    return sum + w * v;
  }, 0);

  // Portfolio volatility
  const portVol = portfolioVolatility(weights, volatilities, correlations);

  if (portVol === 0) return 1;
  return wAvgVol / portVol;
}

/**
 * Compute annualized volatility from returns
 */
export function annualizedVolatility(returns: number[], periodsPerYear = 252): number {
  if (returns.length < 2) return 0;

  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((sum, r) => sum + (r - mean) ** 2, 0) / (returns.length - 1);

  return Math.sqrt(variance * periodsPerYear);
}

/**
 * Compute Sharpe ratio
 */
export function sharpeRatio(
  returns: number[],
  riskFreeRate = 0,
  periodsPerYear = 252
): number {
  if (returns.length < 2) return 0;

  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const excess = mean - riskFreeRate / periodsPerYear;
  const vol = annualizedVolatility(returns, periodsPerYear);

  if (vol === 0) return 0;
  return excess * Math.sqrt(periodsPerYear) / vol;
}

/**
 * Compute Sortino ratio (downside deviation)
 */
export function sortinoRatio(
  returns: number[],
  riskFreeRate = 0,
  periodsPerYear = 252,
  targetReturn = 0
): number {
  if (returns.length < 2) return 0;

  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const excess = mean - riskFreeRate / periodsPerYear;

  // Downside returns only
  const downsideReturns = returns.filter((r) => r < targetReturn);
  if (downsideReturns.length === 0) return 0;

  const downsideVar = downsideReturns.reduce((sum, r) => sum + (r - targetReturn) ** 2, 0) / returns.length;
  const downsideStd = Math.sqrt(downsideVar * periodsPerYear);

  if (downsideStd === 0) return 0;
  return excess * Math.sqrt(periodsPerYear) / downsideStd;
}

/**
 * Compute maximum drawdown
 */
export function maxDrawdown(equityCurve: number[]): number {
  if (equityCurve.length === 0) return 0;

  let peak = equityCurve[0];
  let maxDD = 0;

  for (const value of equityCurve) {
    if (value > peak) peak = value;
    const dd = (peak - value) / peak;
    if (dd > maxDD) maxDD = dd;
  }

  return maxDD;
}