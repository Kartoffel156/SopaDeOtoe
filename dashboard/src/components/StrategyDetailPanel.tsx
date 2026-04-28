"use client";

import { useState } from "react";
import type { GraduatedStrategy } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from "recharts";
import { X, TrendingUp, TrendingDown, AlertTriangle, Activity } from "lucide-react";

interface StrategyDetailPanelProps {
  strategy: GraduatedStrategy | null;
  onClose: () => void;
  disabled?: boolean;
}

function MetricRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex justify-between items-center py-1.5 border-b border-border/50">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={`text-sm font-medium ${highlight ? "text-foreground" : "text-foreground/80"}`}>
        {value}
      </span>
    </div>
  );
}

function WhatIfSlider({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="text-foreground font-mono">{value.toFixed(2)}x</span>
      </div>
      <input
        type="range"
        min="0"
        max="2"
        step="0.05"
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full accent-[var(--primary)]"
        disabled
      />
    </div>
  );
}

export function StrategyDetailPanel({ strategy, onClose, disabled = false }: StrategyDetailPanelProps) {
  const [weightSlider, setWeightSlider] = useState(1.0);
  const [volatilitySlider, setVolatilitySlider] = useState(1.0);
  const [correlationSlider, setCorrelationSlider] = useState(1.0);

  if (!strategy) return null;

  const whatIfData = [
    { name: "Sharpe", base: strategy.metrics.sharpe },
    { name: "Return", base: strategy.metrics.total_return },
    { name: "MaxDD", base: Math.abs(strategy.metrics.max_drawdown) },
    { name: "Calmar", base: strategy.metrics.calmar },
  ].map((d) => ({
    name: d.name,
    current: d.base,
    adjusted: d.base * (weightSlider * 0.6 + volatilitySlider * 0.3 + correlationSlider * 0.1),
  }));

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-[420px] bg-card border-l border-border z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div>
            <h2 className="text-lg font-semibold text-foreground">
              {strategy.strategy_class}
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {strategy.run_id}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {/* Cohort Badge */}
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-[var(--primary)]/15 text-[var(--primary)] text-xs font-medium rounded">
              {strategy.cohort}
            </span>
            <span className="text-xs text-muted-foreground">
              Graduated {strategy.graduated_on}
            </span>
          </div>

          {/* Metrics */}
          <div>
            <h3 className="text-sm font-medium text-foreground mb-2">Strategy Metrics</h3>
            <div className="bg-muted/30 rounded-lg p-3 space-y-0">
              <MetricRow label="Sharpe Ratio" value={strategy.metrics.sharpe.toFixed(3)} />
              <MetricRow label="Total Return" value={`${(strategy.metrics.total_return * 100).toFixed(2)}%`} />
              <MetricRow label="Max Drawdown" value={`${(strategy.metrics.max_drawdown * 100).toFixed(2)}%`} highlight />
              <MetricRow label="Calmar Ratio" value={strategy.metrics.calmar.toFixed(3)} />
              <MetricRow label="Sortino Ratio" value={strategy.metrics.sortino.toFixed(3)} />
              <MetricRow label="Profit Factor" value={strategy.metrics.profit_factor.toFixed(3)} />
              <MetricRow label="Win Rate" value={`${(strategy.metrics.win_rate * 100).toFixed(1)}%`} />
              <MetricRow label="Number of Trades" value={strategy.metrics.n_trades.toString()} />
            </div>
          </div>

          {/* Risk/Reward Overview */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-muted/30 rounded-lg p-3 text-center">
              <TrendingUp className="w-5 h-5 text-green-500 mx-auto mb-1" />
              <p className="text-xs text-muted-foreground">Win Rate</p>
              <p className="text-lg font-semibold text-foreground">
                {(strategy.metrics.win_rate * 100).toFixed(1)}%
              </p>
            </div>
            <div className="bg-muted/30 rounded-lg p-3 text-center">
              <Activity className="w-5 h-5 text-[var(--primary)] mx-auto mb-1" />
              <p className="text-xs text-muted-foreground">Profit Factor</p>
              <p className="text-lg font-semibold text-foreground">
                {strategy.metrics.profit_factor.toFixed(2)}
              </p>
            </div>
            <div className="bg-muted/30 rounded-lg p-3 text-center">
              <AlertTriangle className="w-5 h-5 text-yellow-500 mx-auto mb-1" />
              <p className="text-xs text-muted-foreground">Max DD</p>
              <p className="text-lg font-semibold text-foreground">
                {(strategy.metrics.max_drawdown * 100).toFixed(1)}%
              </p>
            </div>
            <div className="bg-muted/30 rounded-lg p-3 text-center">
              <TrendingDown className="w-5 h-5 text-blue-500 mx-auto mb-1" />
              <p className="text-xs text-muted-foreground">Calmar</p>
              <p className="text-lg font-semibold text-foreground">
                {strategy.metrics.calmar.toFixed(2)}
              </p>
            </div>
          </div>

          {/* What-If Analysis */}
          <div>
            <h3 className="text-sm font-medium text-foreground mb-3">What-If Analysis</h3>
            <div className="bg-muted/30 rounded-lg p-4 space-y-4">
              <WhatIfSlider
                label="Position Size"
                value={weightSlider}
                onChange={setWeightSlider}
              />
              <WhatIfSlider
                label="Volatility Scaling"
                value={volatilitySlider}
                onChange={setVolatilitySlider}
              />
              <WhatIfSlider
                label="Correlation Assumption"
                value={correlationSlider}
                onChange={setCorrelationSlider}
              />

              <div className="pt-2">
                <p className="text-xs text-muted-foreground mb-2">Projected Impact</p>
                <ResponsiveContainer width="100%" height={120}>
                  <LineChart data={whatIfData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="name" tick={{ fill: "#71717a", fontSize: 10 }} />
                    <YAxis tick={{ fill: "#71717a", fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#18181b",
                        border: "1px solid #3f3f46",
                        borderRadius: "6px",
                        fontSize: "12px",
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="current"
                      stroke="#71717a"
                      strokeWidth={1.5}
                      dot={{ r: 3 }}
                      name="Current"
                    />
                    <Line
                      type="monotone"
                      dataKey="adjusted"
                      stroke="#22c55e"
                      strokeWidth={1.5}
                      dot={{ r: 3 }}
                      name="Adjusted"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Configuration */}
          <div>
            <h3 className="text-sm font-medium text-foreground mb-2">Configuration</h3>
            <div className="bg-muted/30 rounded-lg p-3 space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Config Hash</span>
                <span className="text-foreground font-mono">{strategy.config_hash}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Source Run</span>
                <span className="text-foreground font-mono truncate max-w-[200px]" title={strategy.source_run_dir}>
                  {strategy.source_run_dir.split("/").pop()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Config File</span>
                <span className="text-foreground font-mono truncate max-w-[200px]" title={strategy.config_file}>
                  {strategy.config_file.split("/").pop()}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-border px-5 py-4 flex gap-3">
          <Button variant="outline" className="flex-1" disabled={disabled}>
            Disable Strategy
          </Button>
          <Button className="flex-1" disabled={disabled}>
            Apply Changes
          </Button>
        </div>
      </div>
    </>
  );
}