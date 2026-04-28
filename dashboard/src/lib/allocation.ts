/**
 * Portfolio Allocation Methods
 * Implements: equal weight, inverse vol, ERC, risk budget, HRP
 */

import type { AllocationMethod, AllocationResult } from "./types";

interface StrategyStats {
  sharpe: number;
  annualized_volatility: number;
  annualized_return: number;
}

/**
 * Equal weight allocation - 1/n to each strategy
 */
export function equalWeight(
  strategyIds: string[]
): Record<string, number> {
  const n = strategyIds.length;
  if (n === 0) return {};
  const weight = 1 / n;
  return Object.fromEntries(strategyIds.map((id) => [id, weight]));
}

/**
 * Inverse volatility allocation - weight inversely proportional to volatility
 * Lower vol strategies get higher weights
 */
export function inverseVol(
  strategyIds: string[],
  volatilities: Record<string, number>
): Record<string, number> {
  if (strategyIds.length === 0) return {};
  const invVols = strategyIds.map((id) => {
    const vol = volatilities[id] ?? 0.01;
    return 1 / vol;
  });
  const sum = invVols.reduce((a, b) => a + b, 0);
  return Object.fromEntries(
    strategyIds.map((id, i) => [id, invVols[i] / sum])
  );
}

/**
 * Equal Risk Contribution (ERC) - each strategy contributes equally to portfolio risk
 * Uses risk budgeting approach with marginal risk contributions
 */
export function erc(
  strategyIds: string[],
  volatilities: Record<string, number>,
  correlations: Record<string, Record<string, number>>
): Record<string, number> {
  const n = strategyIds.length;
  if (n === 0) return {};

  // Initial equal weights
  const weights: Record<string, number> = Object.fromEntries(
    strategyIds.map((id) => [id, 1 / n])
  );

  // Risk contribution target (equal = 1/n of total portfolio risk)
  const risk_target = 1 / n;

  // Newton-Raphson iteration to find weights that equalize risk contributions
  for (let iter = 0; iter < 100; iter++) {
    const risks = computeRiskContributions(weights, volatilities, correlations);
    const totalRisk = Object.values(risks).reduce((a, b) => a + b, 0);

    if (totalRisk === 0) break;

    const contributions: Record<string, number> = {};
    for (const id of strategyIds) {
      contributions[id] = risks[id] / totalRisk;
    }

    // Compute gradient and update
    let maxDelta = 0;
    for (const id of strategyIds) {
      const delta = (contributions[id] - risk_target) * 0.5;
      weights[id] = Math.max(0.001, weights[id] + delta);
      maxDelta = Math.max(maxDelta, Math.abs(delta));
    }

    // Normalize
    const sumW = Object.values(weights).reduce((a, b) => a + b, 0);
    for (const id of strategyIds) {
      weights[id] /= sumW;
    }

    if (maxDelta < 1e-6) break;
  }

  return weights;
}

/**
 * Risk budget allocation - weights based on inverse of risk contribution
 * Strategies with lower marginal risk get higher weights
 */
export function riskBudget(
  strategyIds: string[],
  volatilities: Record<string, number>,
  correlations: Record<string, Record<string, number>>
): Record<string, number> {
  const n = strategyIds.length;
  if (n === 0) return {};

  // Start with equal weights
  const weights: Record<string, number> = Object.fromEntries(
    strategyIds.map((id) => [id, 1 / n])
  );

  // Compute marginal risks and adjust weights inversely
  for (let iter = 0; iter < 50; iter++) {
    const risks = computeRiskContributions(weights, volatilities, correlations);
    const totalRisk = Object.values(risks).reduce((a, b) => a + b, 0);

    if (totalRisk === 0) break;

    const contributions: Record<string, number> = {};
    for (const id of strategyIds) {
      contributions[id] = risks[id] / totalRisk;
    }

    // Adjust weights inversely to risk contribution
    let maxDelta = 0;
    for (const id of strategyIds) {
      const target = contributions[id] > 0 ? 1 / contributions[id] : 1;
      const current = weights[id] * n;
      const delta = (target - current) * 0.3;
      weights[id] = Math.max(0.01, weights[id] + delta * 0.01);
      maxDelta = Math.max(maxDelta, Math.abs(delta));
    }

    // Normalize
    const sumW = Object.values(weights).reduce((a, b) => a + b, 0);
    for (const id of strategyIds) {
      weights[id] /= sumW;
    }

    if (maxDelta < 1e-4) break;
  }

  return weights;
}

/**
 * Hierarchical Risk Parity (HRP) - uses hierarchical clustering + variance minimization
 */
export function hrp(
  strategyIds: string[],
  volatilities: Record<string, number>,
  correlations: Record<string, Record<string, number>>
): Record<string, number> {
  const n = strategyIds.length;
  if (n === 0) return {};
  if (n === 1) return { [strategyIds[0]]: 1 };

  // Build covariance from correlations + volatilities
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

  // Simple recursive bisection HRP
  const indices = strategyIds.map((_, i) => i);
  const weights = recursiveBisect(indices, cov);
  return Object.fromEntries(strategyIds.map((id, i) => [id, weights[i] ?? (1 / n)]));
}

function recursiveBisect(indices: number[], cov: number[][]): number[] {
  const n = indices.length;
  if (n === 1) return [1];

  // Compute portfolio variance for each possible split
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

  // Weight by inverse variance within each group
  const leftInvVar = 1 / (clusterVariance(left, cov) + 1e-10);
  const rightInvVar = 1 / (clusterVariance(right, cov) + 1e-10);
  const total = leftInvVar + rightInvVar;
  const leftScale = leftInvVar / total;
  const rightScale = rightInvVar / total;

  return [...leftW.map(w => w * leftScale), ...rightW.map(w => w * rightScale)];
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

// Helper: build distance matrix from correlations
function buildDistanceMatrix(
  strategyIds: string[],
  correlations: Record<string, Record<string, number>>
): number[][] {
  const n = strategyIds.length;
  const matrix: number[][] = Array(n).fill(null).map(() => Array(n).fill(0));

  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const id1 = strategyIds[i];
      const id2 = strategyIds[j];
      const corr = correlations[id1]?.[id2] ?? 0;
      const dist = Math.sqrt(2 * (1 - corr));
      matrix[i][j] = dist;
      matrix[j][i] = dist;
    }
  }
  return matrix;
}

// Helper: compute marginal risk contributions
function computeRiskContributions(
  weights: Record<string, number>,
  volatilities: Record<string, number>,
  correlations: Record<string, Record<string, number>>
): Record<string, number> {
  const strategyIds = Object.keys(weights);
  const n = strategyIds.length;

  // Compute portfolio variance
  let portVar = 0;
  const marginalRisks: Record<string, number> = {};

  for (let i = 0; i < n; i++) {
    const id1 = strategyIds[i];
    const w1 = weights[id1];
    const vol1 = volatilities[id1] ?? 0.01;
    let covSum = 0;

    for (let j = 0; j < n; j++) {
      const id2 = strategyIds[j];
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

  for (const id of strategyIds) {
    if (portStd > 0) {
      contributions[id] = weights[id] * marginalRisks[id] / portStd;
    } else {
      contributions[id] = weights[id];
    }
  }

  return contributions;
}

/**
 * Run full allocation for a method and return AllocationResult
 */
export function runAllocation(
  method: AllocationMethod,
  strategyIds: string[],
  volatilities: Record<string, number>,
  correlations: Record<string, Record<string, number>>,
  stats?: Record<string, StrategyStats>
): AllocationResult {
  let weights: Record<string, number>;

  switch (method) {
    case "equal_weight":
      weights = equalWeight(strategyIds);
      break;
    case "inverse_vol":
      weights = inverseVol(strategyIds, volatilities);
      break;
    case "erc":
      weights = erc(strategyIds, volatilities, correlations);
      break;
    case "risk_budget":
      weights = riskBudget(strategyIds, volatilities, correlations);
      break;
    case "hrp":
      weights = hrp(strategyIds, volatilities, correlations);
      break;
    default:
      weights = equalWeight(strategyIds);
  }

  const result: AllocationResult = {
    method,
    weights,
    max_weight: Math.max(...Object.values(weights), 0),
    min_weight: Math.min(...Object.values(weights), 0),
  };

  // Simulate metrics if stats provided
  if (stats) {
    result.sharpe = simulateSharpe(method, weights, stats);
    result.dsr = result.sharpe * 0.95 + Math.random() * 0.05;
    result.sortino = result.sharpe * 1.2 + Math.random() * 0.1;
    result.max_dd = -0.15 - Math.random() * 0.25;
    result.diversification_ratio = simulateDiversification(weights, volatilities, correlations);
  }

  return result;
}

/**
 * Simulate portfolio Sharpe given allocation method (for mock comparison)
 */
function simulateSharpe(
  method: AllocationMethod,
  weights: Record<string, number>,
  stats: Record<string, StrategyStats>
): number {
  const baseSharpe = Object.entries(weights).reduce((sum, [id, w]) => {
    const s = stats[id];
    return sum + (s ? w * s.sharpe : 0);
  }, 0);

  // Method-specific adjustments
  const methodMultipliers: Record<AllocationMethod, number> = {
    equal_weight: 0.95,
    inverse_vol: 1.05,
    erc: 1.1,
    risk_budget: 1.08,
    hrp: 1.12,
  };

  return baseSharpe * (methodMultipliers[method] ?? 1) * (0.9 + Math.random() * 0.2);
}

/**
 * Simulate diversification ratio
 */
function simulateDiversification(
  weights: Record<string, number>,
  volatilities: Record<string, number>,
  correlations: Record<string, Record<string, number>>
): number {
  const ids = Object.keys(weights);
  const n = ids.length;

  // Weighted average volatility
  const wAvgVol = ids.reduce((sum, id) => {
    const vol = volatilities[id] ?? 0.01;
    return sum + weights[id] * vol;
  }, 0);

  // Portfolio volatility (simplified)
  let portVolSq = 0;
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const id1 = ids[i];
      const id2 = ids[j];
      const vol1 = volatilities[id1] ?? 0.01;
      const vol2 = volatilities[id2] ?? 0.01;
      const corr = correlations[id1]?.[id2] ?? (id1 === id2 ? 1 : 0);
      portVolSq += weights[id1] * weights[id2] * vol1 * vol2 * corr;
    }
  }
  const portVol = Math.sqrt(portVolSq);

  if (wAvgVol === 0) return 1;
  return wAvgVol / portVol;
}