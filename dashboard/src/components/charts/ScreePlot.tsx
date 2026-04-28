"use client";

import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts";

interface ScreePlotProps {
  eigenvalues: number[];
  cumulative_variance?: number[];
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-xs">
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: {p.value.toFixed(4)}
        </p>
      ))}
    </div>
  );
}

export function ScreePlot({ eigenvalues, cumulative_variance = [] }: ScreePlotProps) {
  const chartData = eigenvalues.map((ev, i) => ({
    index: i + 1,
    eigenvalue: ev,
    cumulative: cumulative_variance[i] ?? 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={chartData} margin={{ top: 10, right: 40, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis
          dataKey="index"
          tick={{ fill: "#71717a", fontSize: 10 }}
          tickLine={{ stroke: "#27272a" }}
          label={{ value: "PC", fill: "#71717a", fontSize: 10, position: "insideBottomRight", offset: -5 }}
        />
        <YAxis
          yAxisId="left"
          tick={{ fill: "#71717a", fontSize: 10 }}
          tickLine={{ stroke: "#27272a" }}
        />
        <YAxis
          yAxisId="right"
          orientation="right"
          tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
          tick={{ fill: "#71717a", fontSize: 10 }}
          tickLine={{ stroke: "#27272a" }}
          domain={[0, 1]}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine yAxisId="left" y={1} stroke="#ef4444" strokeDasharray="4 4" label={{ value: "λ=1", fill: "#ef4444", fontSize: 10 }} />
        <Bar
          yAxisId="left"
          dataKey="eigenvalue"
          name="Eigenvalue"
          radius={[3, 3, 0, 0]}
        >
          {chartData.map((entry, idx) => (
            <Cell key={idx} fill={entry.eigenvalue >= 1 ? "#22c55e" : "#3b82f6"} />
          ))}
        </Bar>
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="cumulative"
          name="Cumulative %"
          stroke="#eab308"
          strokeWidth={1.5}
          dot={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
