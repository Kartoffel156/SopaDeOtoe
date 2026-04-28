"use client";

import { useState } from "react";
import { shortStrategyName } from "@/lib/formatters";

interface CorrelationHeatmapProps {
  result: {
    correlation: Record<string, Record<string, number>>;
    orthogonality?: { flags?: string[] };
  };
}

function corrColor(value: number): string {
  if (value >= 0) {
    const t = Math.min(1, value);
    const r = Math.round(255 * t);
    const g = Math.round(255 * (1 - t));
    const b = Math.round(255 * (1 - t));
    return `rgb(${r},${g},${b})`;
  } else {
    const t = Math.min(1, -value);
    const r = Math.round(255 * (1 - t));
    const g = Math.round(255 * (1 - t));
    const b = Math.round(255 * t);
    return `rgb(${r},${g},${b})`;
  }
}

export function CorrelationHeatmap({ result }: CorrelationHeatmapProps) {
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    a: string;
    b: string;
    value: number;
  } | null>(null);

  const strategies = Object.keys(result.correlation);
  const n = strategies.length;
  const cellSize = 48;
  const labelOffset = 90;
  const width = labelOffset + n * cellSize + 10;
  const height = labelOffset + n * cellSize + 10;

  return (
    <div className="relative inline-block">
      <svg width={width} height={height}>
        {/* Row labels */}
        {strategies.map((s, i) => (
          <text
            key={`rl-${i}`}
            x={labelOffset - 4}
            y={labelOffset + i * cellSize + cellSize / 2 + 4}
            textAnchor="end"
            fill="#71717a"
            fontSize={10}
          >
            {shortStrategyName(s)}
          </text>
        ))}
        {/* Col labels */}
        {strategies.map((s, i) => (
          <text
            key={`cl-${i}`}
            x={labelOffset + i * cellSize + cellSize / 2}
            y={labelOffset - 4}
            textAnchor="middle"
            fill="#71717a"
            fontSize={10}
            transform={`rotate(-45, ${labelOffset + i * cellSize + cellSize / 2}, ${labelOffset - 4})`}
          >
            {shortStrategyName(s)}
          </text>
        ))}
        {/* Cells */}
        {strategies.map((sA, i) =>
          strategies.map((sB, j) => {
            const val = result.correlation[sA]?.[sB] ?? 0;
            const isFlagged = Math.abs(val) > 0.6 && i < j;
            const cx = labelOffset + j * cellSize + cellSize / 2;
            const cy = labelOffset + i * cellSize + cellSize / 2;
            return (
              <g
                key={`cell-${i}-${j}`}
                onMouseEnter={(e) => {
                  const rect = (e.target as SVGElement).closest("svg")!.getBoundingClientRect();
                  setTooltip({
                    x: e.clientX - rect.left,
                    y: e.clientY - rect.top,
                    a: shortStrategyName(sA),
                    b: shortStrategyName(sB),
                    value: val,
                  });
                }}
                onMouseLeave={() => setTooltip(null)}
                style={{ cursor: "crosshair" }}
              >
                <rect
                  x={labelOffset + j * cellSize + 1}
                  y={labelOffset + i * cellSize + 1}
                  width={cellSize - 2}
                  height={cellSize - 2}
                  fill={corrColor(val)}
                />
                {isFlagged && (
                  <polygon
                    points={`${cx},${cy - cellSize / 2 + 4} ${cx - 4},${cy - cellSize / 2 + 10} ${cx + 4},${cy - cellSize / 2 + 10}`}
                    fill="#fbbf24"
                  />
                )}
              </g>
            );
          })
        )}
      </svg>
      {tooltip && (
        <div
          className="absolute bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-xs pointer-events-none z-10"
          style={{ left: tooltip.x + 10, top: tooltip.y - 40 }}
        >
          <p className="text-zinc-400">
            {tooltip.a} / {tooltip.b}
          </p>
          <p style={{ color: corrColor(tooltip.value) }}>ρ = {tooltip.value.toFixed(3)}</p>
        </div>
      )}
    </div>
  );
}
