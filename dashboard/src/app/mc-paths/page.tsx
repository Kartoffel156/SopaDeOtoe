"use client";

import { useState, useEffect } from "react";
import { EquityConeChart } from "@/components/charts/EquityConeChart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MetricCard } from "@/components/MetricCard";

interface QSMonteCarlo {
  bust_probability: number;
  goal_probability: number;
  bust_threshold: number;
  goal_threshold: number;
  sims: number;
  initial_capital: number;
  n_steps: number;
  path_count: number;
  final_p10: number;
  final_p50: number;
  final_p90: number;
  median_return: number;
  sample_days: number[];
  equity_sample: Record<string, number[]>;
  maxdd_stats: Record<string, number>;
}

interface ApiResponse {
  montecarlo: {
    qs: QSMonteCarlo | null;
  };
  portfolio_metrics: {
    sharpe: number;
    sortino: number;
    max_drawdown: number;
  };
}

export default function MCPathsPage() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/montecarlo")
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin h-8 w-8 border-4 border-[var(--accent-cyan)] border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-muted-foreground text-sm">Running Monte Carlo simulation...</p>
        </div>
      </div>
    );
  }

  const qs = data?.montecarlo?.qs;

  if (!qs) {
    return (
      <div className="p-6 text-red-400">
        No quantstats Monte Carlo data available. Run the pipeline first.
      </div>
    );
  }

  const bustPct = (qs.bust_probability * 100).toFixed(1);
  const goalPct = (qs.goal_probability * 100).toFixed(1);
  const bustColor = qs.bust_probability < 0.1 ? "success" : qs.bust_probability < 0.25 ? "warning" : "danger";
  const goalColor = qs.goal_probability > 0.7 ? "success" : qs.goal_probability > 0.4 ? "warning" : "danger";

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold">Monte Carlo Paths</h1>
        <p className="text-muted-foreground text-sm mt-1">
          quantstats Monte Carlo simulation — {qs.sims.toLocaleString()} paths, {qs.n_steps} days
        </p>
      </div>

      {/* Summary metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <Card>
          <CardContent className="pt-4">
            <p className="text-xs text-muted-foreground mb-1">Bust Prob.</p>
            <p className={`text-2xl font-mono font-bold ${qs.bust_probability < 0.1 ? "text-green-400" : qs.bust_probability < 0.25 ? "text-yellow-400" : "text-red-400"}`}>
              {bustPct}%
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-xs text-muted-foreground mb-1">Goal Prob.</p>
            <p className={`text-2xl font-mono font-bold ${qs.goal_probability > 0.7 ? "text-green-400" : qs.goal_probability > 0.4 ? "text-yellow-400" : "text-red-400"}`}>
              {goalPct}%
            </p>
          </CardContent>
        </Card>
        <MetricCard label="Final P10" value={`$${(qs.final_p10 / 1000).toFixed(0)}k`} />
        <MetricCard label="Final P50" value={`$${(qs.final_p50 / 1000).toFixed(0)}k`} />
        <MetricCard label="Final P90" value={`$${(qs.final_p90 / 1000).toFixed(0)}k`} />
        <MetricCard label="Median Return" value={`${(qs.median_return * 100).toFixed(1)}%`} />
      </div>

      {/* Bust / Goal badges */}
      <div className="flex gap-4">
        <Card className="flex-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Bust Threshold</CardTitle>
            <p className="text-2xl font-mono text-red-400">
              {(qs.bust_threshold * 100).toFixed(0)}%
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Probability of exceeding drawdown of {(qs.bust_threshold * 100).toFixed(0)}%
            </p>
          </CardHeader>
          <CardContent>
            <Badge variant={bustColor as "success" | "warning" | "danger"} className="text-sm">
              {bustPct}% bust probability
            </Badge>
          </CardContent>
        </Card>

        <Card className="flex-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Goal Threshold</CardTitle>
            <p className="text-2xl font-mono text-green-400">
              +{(qs.goal_threshold * 100).toFixed(0)}%
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Probability of reaching return of +{(qs.goal_threshold * 100).toFixed(0)}%
            </p>
          </CardHeader>
          <CardContent>
            <Badge variant={goalColor as "success" | "warning" | "danger"} className="text-sm">
              {goalPct}% goal probability
            </Badge>
          </CardContent>
        </Card>

        <Card className="flex-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Max Drawdown (Sims)</CardTitle>
            <p className="text-2xl font-mono text-yellow-400">
              {(qs.maxdd_stats?.median * 100).toFixed(1)}%
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Median max DD across {qs.sims.toLocaleString()} paths
            </p>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              P5: {(qs.maxdd_stats?.percentile_5 * 100).toFixed(1)}% · P95: {(qs.maxdd_stats?.percentile_95 * 100).toFixed(1)}%
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Equity cone chart */}
      <Card>
        <CardHeader>
          <CardTitle>Equity Cone — P10 / P50 / P90</CardTitle>
          <p className="text-xs text-muted-foreground mt-1">
            {qs.path_count.toLocaleString()} simulated paths · P50 median path highlighted
          </p>
        </CardHeader>
        <CardContent>
          <EquityConeChart
            sampleDays={qs.sample_days}
            equitySample={qs.equity_sample}
            initialCapital={qs.initial_capital}
            bustThreshold={qs.bust_threshold}
            goalThreshold={qs.goal_threshold}
            finalP10={qs.final_p10}
            finalP50={qs.final_p50}
            finalP90={qs.final_p90}
          />
        </CardContent>
      </Card>
    </div>
  );
}
