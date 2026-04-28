"use client";

import { Tooltip } from "@/components/ui/tooltip";
import { ScaleType } from "@/components/GradeBadge";

interface ScaleReferenceProps {
  type: ScaleType;
}

const scaleDescriptions: Record<ScaleType, string> = {
  sharpe: "Sharpe Ratio: Risk-adjusted return measure. >1.5 excellent, >1.0 good, >0.5 fair, ≤0.5 poor",
  maxdd: "Max Drawdown: Maximum peak-to-trough decline. <5% excellent, <10% good, <20% fair, ≥20% poor",
  maxDrawdown: "Max Drawdown: Maximum peak-to-trough decline. <5% excellent, <10% good, <20% fair, ≥20% poor",
  dsr: "Dynamic Sharpe Ratio: Adjusted Sharpe for serial correlation. >2.0 excellent, >1.5 good, >1.0 fair, ≤1.0 poor",
  sortino: "Sortino Ratio: Downside risk-adjusted return. >1.5 excellent, >1.0 good, >0.5 fair, ≤0.5 poor",
  diversification:
    "Diversification Ratio: Portfolio diversification strength. >1.5 excellent, >1.2 good, >1.0 fair, ≤1.0 poor",
  divRatio:
    "Diversification Ratio: Portfolio diversification strength. >1.5 excellent, >1.2 good, >1.0 fair, ≤1.0 poor",
  correlation:
    "Average Pairwise Correlation: Portfolio component correlation. <0.3 excellent, <0.5 good, <0.7 fair, ≥0.7 poor",
  effective_dim:
    "Effective Dimension: Number of independent sources. <3 excellent, <5 good, <7 fair, ≥7 poor",
};

export function ScaleReference({ type }: ScaleReferenceProps) {
  return (
    <Tooltip content={scaleDescriptions[type]}>
      <span className="inline-flex items-center cursor-help text-muted-foreground hover:text-foreground">
        ⓘ
      </span>
    </Tooltip>
  );
}