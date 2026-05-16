"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
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
  const v = payload[0]?.value ?? 0;
  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-xs">
      <p className="text-zinc-400 mb-1">{label}</p>
      <p style={{ color: payload[0]?.color ?? "#ef4444" }}>
        {v !== undefined ? `${(v * 100).toFixed(2)}%` : "N/A"}
      </p>
    </div>
  );
}

export function DrawdownBands({ data }: DrawdownBandsProps) {
  // data: {date, drawdown, equity}
  // Drawdown is negative (loss from peak). Area fills downward from 0 toward negative.
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="gradDD" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.6} />
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
          domain={["auto", 0.005]}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={0} stroke="#52525b" strokeWidth={1} />
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
  );
}