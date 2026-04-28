"use client";

import { Badge } from "@/components/ui/badge";

export type ScaleType =
  | "sharpe"
  | "maxdd"
  | "maxDrawdown"
  | "dsr"
  | "sortino"
  | "diversification"
  | "divRatio"
  | "correlation"
  | "effective_dim";

type Grade = "Excellent" | "Good" | "Fair" | "Poor";

interface GradeBadgeProps {
  scaleType: ScaleType;
  value: number;
  className?: string;
}

const gradeConfig: Record<
  ScaleType,
  { thresholds: number[]; higherIsBetter: boolean }
> = {
  sharpe: { thresholds: [0.5, 1.0, 1.5], higherIsBetter: true },
  maxdd: { thresholds: [20, 10, 5], higherIsBetter: false },
  maxDrawdown: { thresholds: [20, 10, 5], higherIsBetter: false },
  dsr: { thresholds: [1.0, 1.5, 2.0], higherIsBetter: true },
  sortino: { thresholds: [0.5, 1.0, 1.5], higherIsBetter: true },
  diversification: { thresholds: [1.0, 1.2, 1.5], higherIsBetter: true },
  divRatio: { thresholds: [1.0, 1.2, 1.5], higherIsBetter: true },
  correlation: { thresholds: [0.7, 0.5, 0.3], higherIsBetter: false },
  effective_dim: { thresholds: [7, 5, 3], higherIsBetter: false },
};

function getGrade(scaleType: ScaleType, value: number): Grade {
  const { thresholds, higherIsBetter } = gradeConfig[scaleType];
  const [poor, fair, good] = thresholds;

  if (higherIsBetter) {
    if (value >= good) return "Excellent";
    if (value >= fair) return "Good";
    if (value >= poor) return "Fair";
    return "Poor";
  } else {
    if (value <= good) return "Excellent";
    if (value <= fair) return "Good";
    if (value <= poor) return "Fair";
    return "Poor";
  }
}

function getVariant(grade: Grade): "success" | "warning" | "danger" {
  switch (grade) {
    case "Excellent":
    case "Good":
      return "success";
    case "Fair":
      return "warning";
    case "Poor":
      return "danger";
  }
}

export function GradeBadge({ scaleType, value, className }: GradeBadgeProps) {
  const grade = getGrade(scaleType, value);
  return (
    <Badge variant={getVariant(grade)} className={className}>
      {grade}
    </Badge>
  );
}