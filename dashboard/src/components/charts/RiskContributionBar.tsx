"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts";
import type { RiskAttributionItem } from "@/lib/types";
import { shortStrategyName } from "@/lib/formatters";

interface RiskContributionBarProps {
  data: RiskAttributionItem[];
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
}) {
  if (!active || !payload?.length) return null;
  const delta = payload[0].value - (payload[1]?.value ?? 0);
  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-xs">
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: {(p.value * 100).toFixed(2)}%
        </p>
      ))}
      <p className="text-zinc-400 mt-1">
        Delta: {delta > 0 ? "+" : ""}{(delta * 100).toFixed(2)}%
      </p>
    </div>
  );
}

export function RiskContributionBar({ data }: RiskContributionBarProps) {
  const chartData = data.map((d) => ({
    strategy: shortStrategyName(d.strategy),
    weight: d.weight,
    risk_contribution: d.risk_contribution_pct,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart
        data={chartData}
        layout="vertical"
        margin={{ top: 10, right: 10, left: 60, bottom: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis
          type="number"
          tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
          tick={{ fill: "#71717a", fontSize: 10 }}
          tickLine={{ stroke: "#27272a" }}
        />
        <YAxis
          type="category"
          dataKey="strategy"
          tick={{ fill: "#71717a", fontSize: 10 }}
          tickLine={{ stroke: "#27272a" }}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine x={1 / data.length} stroke="#52525b" strokeDasharray="4 4" label={{ value: "1/n", fill: "#71717a", fontSize: 10 }} />
        <Bar dataKey="weight" name="Weight" fill="#3b82f6" radius={[0, 2, 2, 0]}>
          {chartData.map((entry, idx) => {
            const delta = entry.weight - entry.risk_contribution;
            return <Cell key={idx} fill={delta >= 0 ? "#22c55e" : "#ef4444"} />;
          })}
        </Bar>
        <Bar dataKey="risk_contribution" name="Risk Contribution" fill="#3b82f6" radius={[0, 2, 2, 0]} opacity={0.6} />
      </BarChart>
    </ResponsiveContainer>
  );
}
