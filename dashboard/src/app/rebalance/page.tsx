"use client";

import { useState, useMemo, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MethodComparisonChart } from "@/components/charts/MethodComparisonChart";
import type { AllocationMethod, AllocationResult } from "@/lib/types";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const METHODS: AllocationMethod[] = [
  "equal_weight",
  "inverse_vol",
  "erc",
  "risk_budget",
  "hrp",
];

const METHOD_LABELS: Record<AllocationMethod, string> = {
  equal_weight: "Equal Weight",
  inverse_vol: "Inverse Volatility",
  erc: "Equal Risk Contribution",
  risk_budget: "Risk Budget",
  hrp: "Hierarchical Risk Parity",
};

interface MethodComparisonApiData {
  timestamp: string;
  methods: Array<{
    method: AllocationMethod;
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
    weights: Record<string, number>;
    equity_curve: Array<{ date: string; equity: number; drawdown: number }>;
    risk_attribution: Array<{
      strategy: string;
      weight: number;
      marginal_risk: number;
      risk_contribution: number;
      risk_contribution_pct: number;
    }>;
    herfindahl_rc: number;
  }>;
}

function buildResultsFromApi(data: MethodComparisonApiData): AllocationResult[] {
  return data.methods.map((m) => {
    const weights = m.weights;
    const max_weight = Math.max(...Object.values(weights));
    const min_weight = Math.min(...Object.values(weights));
    return {
      method: m.method,
      weights,
      sharpe: m.metrics.sharpe,
      dsr: m.metrics.dsr,
      sortino: m.metrics.sortino,
      max_dd: m.metrics.max_drawdown,
      diversification_ratio: m.metrics.diversification_ratio,
      max_weight,
      min_weight,
      equity_curve: m.equity_curve,
      risk_attribution: m.risk_attribution,
    };
  });
}

function formatWeight(w: number): string {
  return (w * 100).toFixed(1) + "%";
}

function formatMetric(v: number | undefined, decimals = 3): string {
  if (v === undefined) return "-";
  return v.toFixed(decimals);
}

export default function RebalancePage() {
  const [selectedMethod, setSelectedMethod] = useState<AllocationMethod>("risk_budget");
  const [leverage, setLeverage] = useState(1.0);
  const [showComparison, setShowComparison] = useState(true);
  const [apiData, setApiData] = useState<MethodComparisonApiData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadApiData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/rebalance", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: MethodComparisonApiData = await res.json();
      setApiData(data);
    } catch (e: any) {
      setError(e.message ?? "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadApiData(); }, []);

  const allResults = useMemo(() => {
    if (!apiData) return [];
    let results = buildResultsFromApi(apiData);

    // Apply leverage to weights
    if (leverage !== 1) {
      results = results.map((r) => {
        const newWeights: Record<string, number> = {};
        for (const [id, w] of Object.entries(r.weights)) {
          newWeights[id] = w * leverage;
        }
        return { ...r, weights: newWeights };
      });
    }

    return results;
  }, [apiData, leverage]);

  const selectedResult = allResults.find((r) => r.method === selectedMethod) ?? allResults[0];

  // Risk attribution from real API data
  const riskAttribution = useMemo(() => {
    if (!apiData) return [];
    const methodData = apiData.methods.find((m) => m.method === selectedMethod);
    return methodData?.risk_attribution ?? [];
  }, [apiData, selectedMethod]);

  const selectedDivRatio = selectedResult?.diversification_ratio ?? 1;

  const weightDistribution = useMemo(() => {
    if (!selectedResult) return [];
    return Object.entries(selectedResult.weights)
      .map(([id, w]) => ({
        strategy: id.split("_")[0].replace("Hypothesis", "H").slice(0, 12),
        weight: w,
      }))
      .sort((a, b) => b.weight - a.weight);
  }, [selectedResult]);

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <p className="text-muted-foreground">Loading rebalance data...</p>
      </div>
    );
  }

  if (error || !apiData) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <p className="text-red-400">Error: {error ?? "No data"}</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Rebalance Analyzer</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Compare allocation methods and simulate leverage effects
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">
            Backtest: {apiData.timestamp}
          </span>
          <button
            onClick={loadApiData}
            className="text-xs px-3 py-1.5 rounded border border-zinc-700 bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Controls Row */}
      <div className="flex flex-wrap gap-4 items-end">
        {/* Method Selector */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-muted-foreground">Allocation Method</label>
          <div className="flex gap-1">
            {METHODS.map((m) => (
              <button
                key={m}
                onClick={() => setSelectedMethod(m)}
                className={`px-3 py-1.5 text-xs rounded border transition-colors ${
                  selectedMethod === m
                    ? "bg-blue-600 border-blue-600 text-white"
                    : "bg-zinc-800 border-zinc-700 text-zinc-300 hover:bg-zinc-700"
                }`}
              >
                {METHOD_LABELS[m]}
              </button>
            ))}
          </div>
        </div>

        {/* Leverage Slider */}
        <div className="flex flex-col gap-1.5 min-w-[200px]">
          <label className="text-xs text-muted-foreground">
            Leverage: <span className="text-zinc-300 font-mono">{leverage.toFixed(2)}x</span>
          </label>
          <input
            type="range"
            min={0.5}
            max={3}
            step={0.05}
            value={leverage}
            onChange={(e) => setLeverage(parseFloat(e.target.value))}
            className="w-full accent-blue-500"
          />
          <div className="flex justify-between text-[10px] text-muted-foreground">
            <span>0.5x</span>
            <span>3.0x</span>
          </div>
        </div>

        {/* Toggle Comparison */}
        <button
          onClick={() => setShowComparison(!showComparison)}
          className={`px-3 py-1.5 text-xs rounded border transition-colors ${
            showComparison
              ? "bg-zinc-700 border-zinc-600 text-white"
              : "bg-zinc-800 border-zinc-700 text-zinc-400"
          }`}
        >
          {showComparison ? "Hide" : "Show"} Comparison
        </button>
      </div>

      {/* Equity Curve + Drawdown Chart */}
      {selectedResult?.equity_curve && selectedResult.equity_curve.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-medium">Equity Curve — {METHOD_LABELS[selectedMethod]}</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={selectedResult.equity_curve} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gradEq" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#22c55e" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "#71717a", fontSize: 9 }}
                    interval={Math.floor(selectedResult.equity_curve.length / 6)}
                    tickFormatter={(v) => v.slice(0, 10)}
                  />
                  <YAxis
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                    tick={{ fill: "#71717a", fontSize: 9 }}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: "6px", fontSize: "11px" }}
                    formatter={(value) => [`${(Number(value) * 100).toFixed(2)}%`, "Equity"]}
                    labelFormatter={(label) => `Date: ${label}`}
                  />
                  <Area
                    type="monotone"
                    dataKey="equity"
                    name="Equity"
                    stroke="#22c55e"
                    strokeWidth={1.5}
                    fill="url(#gradEq)"
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base font-medium">Drawdown — {METHOD_LABELS[selectedMethod]}</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart
                  data={selectedResult.equity_curve.map((p) => ({ ...p, drawdown: Math.min(0, p.drawdown) }))}
                  margin={{ top: 5, right: 5, left: 0, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="gradDD" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0.05} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "#71717a", fontSize: 9 }}
                    interval={Math.floor((selectedResult.equity_curve?.length ?? 1) / 6)}
                    tickFormatter={(v) => v.slice(0, 10)}
                  />
                  <YAxis
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                    tick={{ fill: "#71717a", fontSize: 9 }}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: "6px", fontSize: "11px" }}
                    formatter={(value) => [`${(Number(value) * 100).toFixed(2)}%`, "Drawdown"]}
                    labelFormatter={(label) => `Date: ${label}`}
                  />
                  <Area
                    type="monotone"
                    dataKey="drawdown"
                    name="Drawdown"
                    stroke="#ef4444"
                    strokeWidth={1.5}
                    fill="url(#gradDD)"
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Method Comparison Chart */}
      {showComparison && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium">Method Comparison</CardTitle>
          </CardHeader>
          <CardContent>
            <MethodComparisonChart results={allResults} />
          </CardContent>
        </Card>
      )}

      {/* Metrics Comparison Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium">Metrics Comparison</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-left py-2 px-3 text-zinc-400 font-medium">Method</th>
                  <th className="text-right py-2 px-3 text-zinc-400 font-medium">Sharpe</th>
                  <th className="text-right py-2 px-3 text-zinc-400 font-medium">DSR</th>
                  <th className="text-right py-2 px-3 text-zinc-400 font-medium">Sortino</th>
                  <th className="text-right py-2 px-3 text-zinc-400 font-medium">Max DD</th>
                  <th className="text-right py-2 px-3 text-zinc-400 font-medium">Div Ratio</th>
                  <th className="text-right py-2 px-3 text-zinc-400 font-medium">Max Wt</th>
                  <th className="text-right py-2 px-3 text-zinc-400 font-medium">Min Wt</th>
                </tr>
              </thead>
              <tbody>
                {allResults.map((r) => (
                  <tr
                    key={r.method}
                    className={`border-b border-zinc-800/50 cursor-pointer transition-colors ${
                      selectedMethod === r.method ? "bg-zinc-800/50" : "hover:bg-zinc-800/30"
                    }`}
                    onClick={() => setSelectedMethod(r.method)}
                  >
                    <td className="py-2 px-3 text-zinc-300">{METHOD_LABELS[r.method]}</td>
                    <td className="text-right py-2 px-3 font-mono text-blue-400">
                      {formatMetric(r.sharpe)}
                    </td>
                    <td className="text-right py-2 px-3 font-mono text-green-400">
                      {formatMetric(r.dsr)}
                    </td>
                    <td className="text-right py-2 px-3 font-mono text-emerald-400">
                      {formatMetric(r.sortino)}
                    </td>
                    <td className="text-right py-2 px-3 font-mono text-red-400">
                      {r.max_dd !== undefined ? (r.max_dd * 100).toFixed(1) + "%" : "-"}
                    </td>
                    <td className="text-right py-2 px-3 font-mono text-cyan-400">
                      {formatMetric(r.diversification_ratio, 2)}
                    </td>
                    <td className="text-right py-2 px-3 font-mono text-zinc-400">
                      {formatWeight(r.max_weight ?? 0)}
                    </td>
                    <td className="text-right py-2 px-3 font-mono text-zinc-400">
                      {formatWeight(r.min_weight ?? 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Two Column Layout: Weight Distribution + Risk Attribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Weight Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium">
              Weight Distribution
              <span className="ml-2 text-xs text-[var(--muted-foreground)] font-normal">
                ({Object.keys(selectedResult.weights).length} strategies)
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {weightDistribution.map((item, idx) => {
                const pct = item.weight * 100;
                return (
                  <div key={idx} className="flex items-center gap-3">
                    <span className="text-xs text-zinc-400 w-24 truncate font-mono">
                      {item.strategy}
                    </span>
                    <div className="flex-1 bg-zinc-800 rounded-full h-2">
                      <div
                        className="bg-blue-500 h-2 rounded-full transition-all"
                        style={{ width: `${Math.min(100, pct * 3)}%` }}
                      />
                    </div>
                    <span className="text-xs font-mono text-zinc-300 w-12 text-right">
                      {pct.toFixed(1)}%
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Summary stats */}
            <div className="mt-4 pt-4 border-t border-zinc-800 grid grid-cols-3 gap-4 text-xs">
              <div>
                <p className="text-muted-foreground">Max Weight</p>
                <p className="text-zinc-300 font-mono">
                  {formatWeight(selectedResult.max_weight ?? 0)}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">Min Weight</p>
                <p className="text-zinc-300 font-mono">
                  {formatWeight(selectedResult.min_weight ?? 0)}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">Leverage</p>
                <p className="text-zinc-300 font-mono">{leverage.toFixed(2)}x</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Risk Attribution */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium">Risk Attribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {riskAttribution.slice(0, 8).map((item, idx) => {
                const shortName = item.strategy.split("_")[0].replace("Hypothesis", "H").slice(0, 12);
                const pct = item.risk_contribution_pct * 100;
                const weightPct = item.weight * 100;
                const delta = pct - weightPct;

                return (
                  <div key={idx} className="flex items-center gap-3">
                    <span className="text-xs text-zinc-400 w-24 truncate font-mono">
                      {shortName}
                    </span>
                    <div className="flex-1 bg-zinc-800 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all ${
                          delta >= 0 ? "bg-red-500" : "bg-green-500"
                        }`}
                        style={{ width: `${Math.min(100, pct * 3)}%` }}
                      />
                    </div>
                    <span className="text-xs font-mono text-zinc-300 w-20 text-right">
                      {pct.toFixed(1)}%
                      <span className={`ml-1 ${delta >= 0 ? "text-red-400" : "text-green-400"}`}>
                        {delta >= 0 ? "+" : ""}{delta.toFixed(1)}
                      </span>
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Summary */}
            <div className="mt-4 pt-4 border-t border-zinc-800 grid grid-cols-2 gap-4 text-xs">
              <div>
                <p className="text-muted-foreground">Top Risk Contributor</p>
                <p className="text-zinc-300 font-mono truncate">
                  {riskAttribution[0]?.strategy.split("_")[0].replace("Hypothesis", "H") ?? "-"}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">Diversification Ratio</p>
                <p className="text-cyan-400 font-mono">{selectedDivRatio.toFixed(2)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Leverage Warning */}
      {leverage > 1.5 && (
        <div className="bg-amber-900/20 border border-amber-700/50 rounded px-4 py-3 text-xs text-amber-300">
          <strong>Warning:</strong> Leverage of {leverage.toFixed(2)}x increases risk exposure significantly.
          Max drawdown could reach{" "}
          {((selectedResult.max_dd ?? -0.2) * leverage * 100).toFixed(1)}%
        </div>
      )}
    </div>
  );
}
