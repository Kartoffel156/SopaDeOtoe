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

interface MonteCarloConeProps {
  distribution: number[];
  observed: number;
}

export function MonteCarloCone({ distribution, observed }: MonteCarloConeProps) {
  if (!distribution || distribution.length === 0) return null;

  const sorted = [...distribution].sort((a, b) => a - b);
  const n = sorted.length;
  const p5 = sorted[Math.floor(n * 0.05)];
  const p25 = sorted[Math.floor(n * 0.25)];
  const p50 = sorted[Math.floor(n * 0.5)];
  const p75 = sorted[Math.floor(n * 0.75)];
  const p95 = sorted[Math.floor(n * 0.95)];

  const data = distribution.map((sharpe, i) => ({ iteration: i + 1, sharpe }));
  data.sort((a, b) => a.sharpe - b.sharpe);

  const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-xs">
        <p className="text-zinc-400 mb-1">Rank {label}</p>
        <p className="text-[var(--accent-cyan)]">Sharpe: {payload[0].value.toFixed(4)}</p>
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="gradObs" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#22d3ee" stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis
          dataKey="iteration"
          tick={{ fill: "#71717a", fontSize: 10 }}
          tickLine={{ stroke: "#27272a" }}
          label={{ value: "Run rank", fill: "#71717a", fontSize: 10, position: "insideBottomRight", offset: -5 }}
        />
        <YAxis
          tickFormatter={(v) => v.toFixed(2)}
          tick={{ fill: "#71717a", fontSize: 10 }}
          tickLine={{ stroke: "#27272a" }}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine
          x={distribution.findIndex((d) => d === observed) + 1}
          stroke="#22d3ee"
          strokeDasharray="4 4"
          label={{ value: `observed=${observed.toFixed(3)}`, fill: "#22d3ee", fontSize: 10 }}
        />
        <ReferenceLine y={p5} stroke="#ef4444" strokeDasharray="2 2" label={{ value: `p5=${p5.toFixed(2)}`, fill: "#ef4444", fontSize: 9 }} />
        <ReferenceLine y={p95} stroke="#22c55e" strokeDasharray="2 2" label={{ value: `p95=${p95.toFixed(2)}`, fill: "#22c55e", fontSize: 9 }} />
        <ReferenceLine y={p50} stroke="#eab308" strokeDasharray="2 2" label={{ value: `p50=${p50.toFixed(2)}`, fill: "#eab308", fontSize: 9 }} />
        <Area type="monotone" dataKey="sharpe" stroke="#22d3ee" strokeWidth={1.5} fill="url(#gradObs)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
