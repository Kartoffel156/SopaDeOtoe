"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Brush,
} from "recharts";
import type { EquityDataPoint } from "@/lib/types";

interface EquityChartProps {
  data: EquityDataPoint[];
}

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
      <p className="text-zinc-400 mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: {(p.value * 100).toFixed(2)}%
        </p>
      ))}
    </div>
  );
}

export function EquityChart({ data }: EquityChartProps) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="gradPortfolio" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#22c55e" stopOpacity={0.02} />
          </linearGradient>
          <linearGradient id="gradBuyHold" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis
          dataKey="date"
          tick={{ fill: "#71717a", fontSize: 10 }}
          tickLine={{ stroke: "#27272a" }}
        />
        <YAxis
          tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
          tick={{ fill: "#71717a", fontSize: 10 }}
          tickLine={{ stroke: "#27272a" }}
        />
        <Tooltip content={<CustomTooltip />} />
        <Area
          type="monotone"
          dataKey="portfolio"
          name="Portfolio"
          stroke="#22c55e"
          strokeWidth={1.5}
          fill="url(#gradPortfolio)"
          dot={false}
        />
        <Area
          type="monotone"
          dataKey="buyHold"
          name="Buy&amp;Hold"
          stroke="#3b82f6"
          strokeWidth={1.5}
          fill="url(#gradBuyHold)"
          dot={false}
        />
        <Brush
          dataKey="date"
          height={30}
          stroke="#52525b"
          fill="#18181b"
          travellerWidth={6}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
