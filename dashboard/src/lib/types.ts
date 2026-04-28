// ─── Portfolio Data Types ────────────────────────────────────────────────

export interface PortfolioMetrics {
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
}

export interface RiskAttributionItem {
  strategy: string;
  weight: number;
  marginal_risk: number;
  risk_contribution: number;
  risk_contribution_pct: number;
}

export interface PCAData {
  eigenvalues: number[];
  eigenvectors: number[][];
  explained_variance_ratio: number[];
  cumulative_variance: number[];
  effective_dimension: number;
}

export interface ClusteringData {
  linkage: number[][];
  labels: string[];
  distance_matrix: number[][];
}

export interface OrthogonalityData {
  pca: PCAData;
  clustering: ClusteringData;
  flags: string[];
}

export interface MonteCarloData {
  permutation: {
    observed_sharpe: number;
    p_value: number;
    mean_perm_sharpe: number;
    std_perm_sharpe: number;
    n_permutations: number;
  };
  bootstrap: {
    sharpe_mean: number;
    sharpe_std: number;
    sharpe_ci_95: [number, number];
    prob_negative_sharpe: number;
    max_dd_ci_95: [number, number];
  };
  cpcv: {
    sharpe_distribution: number[];
  };
}

export interface PortfolioResult {
  timestamp: string;
  cohort: string;
  allocation_method: string;
  fdm: number;
  weights: Record<string, number>;
  portfolio_metrics: PortfolioMetrics;
  risk_attribution: RiskAttributionItem[];
  correlation: Record<string, Record<string, number>>;
  orthogonality: OrthogonalityData;
  montecarlo: MonteCarloData;
  per_strategy_source: unknown[];
}

// ─── Strategy Types ──────────────────────────────────────────────────────

export interface StrategyMetrics {
  sharpe: number;
  total_return: number;
  max_drawdown: number;
  calmar: number;
  sortino: number;
  profit_factor: number;
  n_trades: number;
  win_rate: number;
}

export interface GraduatedStrategy {
  run_id: string;
  strategy_class: string;
  config_hash: string;
  config_file: string;
  source_run_dir: string;
  metrics: StrategyMetrics;
  graduated_on: string;
  cohort: string;
}

// ─── Trade Types ─────────────────────────────────────────────────────────

export interface Trade {
  date: string;
  strategy: string;
  side: "LONG" | "SHORT";
  entry_price: number;
  exit_price: number;
  return: number;
  bars: number;
  barrier: "profit" | "stop" | "time";
  mae: number;
  mfe: number;
  bet_size: number;  // position size in BTC
  pnl: number;       // absolute PnL in quote currency (USD)
}

// ─── Chart Data Types ────────────────────────────────────────────────────

export interface EquityDataPoint {
  date: string;
  portfolio: number;
  buyHold: number;
  drawdown: number;
}

export interface DrawdownBand {
  date: string;
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
}

// ─── Allocation Types ─────────────────────────────────────────────────────

export type AllocationMethod = "equal_weight" | "inverse_vol" | "erc" | "risk_budget" | "hrp";

export interface AllocationResult {
  method: AllocationMethod;
  weights: Record<string, number>;
  sharpe?: number;
  dsr?: number;
  max_dd?: number;
  sortino?: number;
  diversification_ratio?: number;
  max_weight?: number;
  min_weight?: number;
  equity_curve?: Array<{ date: string; equity: number; drawdown: number }>;
  risk_attribution?: Array<{
    strategy: string;
    weight: number;
    marginal_risk: number;
    risk_contribution: number;
    risk_contribution_pct: number;
  }>;
}
