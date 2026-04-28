"use client";

import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { AllocationMethod, AllocationResult } from "@/lib/types";

interface ComparisonDataPoint {
  method: string;
  sharpe: number;
  dsr: number;
  sortino: number;
  diversification_ratio: number;
  displayName: string;
}

interface MethodComparisonChartProps {
  results: AllocationResult[];
}

// Color palette for bars
const METHOD_COLORS: Record<string, string> = {
  equal_weight: "#6366f1",
  inverse_vol: "#22c55e",
  erc: "#f59e0b",
  risk_budget: "#ef4444",
  hrp: "#8b5cf6",
};

const METHOD_LABELS: Record<AllocationMethod, string> = {
  equal_weight: "Equal",
  inverse_vol: "Inv Vol",
  erc: "ERC",
  risk_budget: "Risk Bud",
  hrp: "HRP",
};

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-xs">
      <p className="text-zinc-300 font-medium mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: {typeof p.value === "number" ? p.value.toFixed(3) : p.value}
        </p>
      ))}
    </div>
  );
}

export function MethodComparisonChart({ results }: MethodComparisonChartProps) {
  const chartData: ComparisonDataPoint[] = results.map((r) => ({
    method: r.method,
    displayName: METHOD_LABELS[r.method] ?? r.method,
    sharpe: r.sharpe ?? 0,
    dsr: r.dsr ?? 0,
    sortino: r.sortino ?? 0,
    diversification_ratio: r.diversification_ratio ?? 1,
  }));

  return (
    <ResponsiveContainer width="100%" height={350}>
      <ComposedChart
        data={chartData}
        margin={{ top: 20, right: 30, left: 0, bottom: 5 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis
          dataKey="displayName"
          tick={{ fill: "#71717a", fontSize: 11 }}
          tickLine={{ stroke: "#27272a" }}
        />
        <YAxis
          yAxisId="left"
          tick={{ fill: "#71717a", fontSize: 11 }}
          tickLine={{ stroke: "#27272a" }}
          tickFormatter={(v) => v.toFixed(2)}
        />
        <YAxis
          yAxisId="right"
          orientation="right"
          tick={{ fill: "#71717a", fontSize: 11 }}
          tickLine={{ stroke: "#27272a" }}
          tickFormatter={(v) => v.toFixed(1)}
          domain={[0, 4]}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: 11, paddingTop: 10 }}
          formatter={(value) => <span style={{ color: "#a1a1aa" }}>{value}</span>}
        />

        {/* Diversification Ratio - Line */}
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="diversification_ratio"
          name="Div Ratio"
          stroke="#06b6d4"
          strokeWidth={2}
          dot={{ fill: "#06b6d4", r: 4 }}
          activeDot={{ r: 6 }}
        />

        {/* Sharpe - Bar */}
        <Bar
          yAxisId="left"
          dataKey="sharpe"
          name="Sharpe"
          fill={METHOD_COLORS.equal_weight}
          opacity={0.85}
          radius={[2, 2, 0, 0]}
        />

        {/* DSR - Bar */}
        <Bar
          yAxisId="left"
          dataKey="dsr"
          name="DSR"
          fill="#3b82f6"
          opacity={0.65}
          radius={[2, 2, 0, 0]}
        />

        {/* Sortino - Bar */}
        <Bar
          yAxisId="left"
          dataKey="sortino"
          name="Sortino"
          fill="#10b981"
          opacity={0.5}
          radius={[2, 2, 0, 0]}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}