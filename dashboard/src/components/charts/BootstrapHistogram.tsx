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

interface BootstrapHistogramProps {
  sharpeMean: number;
  sharpeStd: number;
  ci95: [number, number];
  observed: number;
  bins?: number;
}

function buildHistogramData(mean: number, std: number, bins = 20): { bucket: number; count: number }[] {
  const data: { bucket: number; count: number }[] = [];
  const min = mean - 4 * std;
  const max = mean + 4 * std;
  const step = (max - min) / bins;
  for (let i = 0; i < bins; i++) {
    const lo = min + i * step;
    data.push({ bucket: (lo + step / 2), count: Math.exp(-0.5 * Math.pow((lo + step / 2 - mean) / std, 2)) });
  }
  return data;
}

export function BootstrapHistogram({ sharpeMean, sharpeStd, ci95, observed, bins = 20 }: BootstrapHistogramProps) {
  const data = buildHistogramData(sharpeMean, sharpeStd, bins);

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis
          dataKey="bucket"
          tick={{ fill: "#71717a", fontSize: 10 }}
          tickFormatter={(v) => v.toFixed(2)}
        />
        <YAxis tick={{ fill: "#71717a", fontSize: 10 }} />
        <Tooltip
          contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: 6, fontSize: 12 }}
          formatter={(value) => [Number(value).toFixed(4), "density"]}
        />
        <ReferenceLine x={observed} stroke="#22d3ee" strokeDasharray="4 4" label={{ value: `observed=${observed.toFixed(3)}`, fill: "#22d3ee", fontSize: 10 }} />
        <ReferenceLine x={ci95[0]} stroke="#ef4444" strokeDasharray="2 2" />
        <ReferenceLine x={ci95[1]} stroke="#ef4444" strokeDasharray="2 2" />
        <Bar dataKey="count" radius={[2, 2, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.bucket >= ci95[0] && entry.bucket <= ci95[1] ? "#22c55e" : "#3b82f6"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
