"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { DrawdownBand } from "@/lib/types";

interface DrawdownBandsProps {
  data: DrawdownBand[];
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

export function DrawdownBands({ data }: DrawdownBandsProps) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="gradP95" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#22c55e" stopOpacity={0.5} />
            <stop offset="95%" stopColor="#22c55e" stopOpacity={0.05} />
          </linearGradient>
          <linearGradient id="gradP75" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#84cc16" stopOpacity={0.4} />
            <stop offset="95%" stopColor="#84cc16" stopOpacity={0.05} />
          </linearGradient>
          <linearGradient id="gradP50" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#eab308" stopOpacity={0.4} />
            <stop offset="95%" stopColor="#eab308" stopOpacity={0.05} />
          </linearGradient>
          <linearGradient id="gradP25" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#f97316" stopOpacity={0.4} />
            <stop offset="95%" stopColor="#f97316" stopOpacity={0.05} />
          </linearGradient>
          <linearGradient id="gradP5" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.5} />
            <stop offset="95%" stopColor="#ef4444" stopOpacity={0.05} />
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
          reversed
        />
        <Tooltip content={<CustomTooltip />} />
        <Area
          type="monotone"
          dataKey="p95"
          stackId="1"
          stroke="#22c55e"
          strokeWidth={0}
          fill="url(#gradP95)"
          fillOpacity={1}
        />
        <Area
          type="monotone"
          dataKey="p75"
          stackId="2"
          stroke="#84cc16"
          strokeWidth={0}
          fill="url(#gradP75)"
          fillOpacity={1}
        />
        <Area
          type="monotone"
          dataKey="p50"
          stackId="3"
          stroke="#eab308"
          strokeWidth={0}
          fill="url(#gradP50)"
          fillOpacity={1}
        />
        <Area
          type="monotone"
          dataKey="p25"
          stackId="4"
          stroke="#f97316"
          strokeWidth={0}
          fill="url(#gradP25)"
          fillOpacity={1}
        />
        <Area
          type="monotone"
          dataKey="p5"
          stackId="5"
          stroke="#ef4444"
          strokeWidth={0}
          fill="url(#gradP5)"
          fillOpacity={1}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
