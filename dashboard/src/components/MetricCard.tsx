"use client";

import { Card, CardContent } from "@/components/ui/card";
import { ScaleType } from "@/components/GradeBadge";
import { GradeBadge } from "@/components/GradeBadge";
import { ScaleReference } from "@/components/ScaleReference";

interface MetricCardProps {
  label: string;
  value: string | number;
  subValue?: string;
  scaleType?: ScaleType;
  numericValue?: number;
  tooltipContent?: string;
  icon?: React.ReactNode;
  className?: string;
}

export function MetricCard({
  label,
  value,
  subValue,
  scaleType,
  numericValue,
  tooltipContent,
  icon,
  className,
}: MetricCardProps) {
  return (
    <Card className={className}>
      <CardContent className="pt-6">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium text-muted-foreground">{label}</p>
            <div className="flex items-baseline gap-2">
              <p className="text-2xl font-semibold">{value}</p>
              {subValue && (
                <p className="text-sm text-muted-foreground">{subValue}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {icon && <div className="text-muted-foreground">{icon}</div>}
            {scaleType !== undefined && numericValue !== undefined && (
              <GradeBadge scaleType={scaleType} value={numericValue} />
            )}
            {tooltipContent && <ScaleReference type={scaleType!} />}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}