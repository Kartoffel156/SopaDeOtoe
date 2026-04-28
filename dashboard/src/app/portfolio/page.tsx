'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { MetricCard } from '@/components/MetricCard';
import { EquityChart } from '@/components/charts/EquityChart';
import { DrawdownBands } from '@/components/charts/DrawdownBands';
import { ScaleType } from '@/components/GradeBadge';
import type { EquityDataPoint, DrawdownBand } from '@/lib/types';

interface PortfolioData {
  portfolio: { timestamp?: string; cohort?: string };
  portfolio_metrics: {
    sharpe: number;
    dsr: number;
    annualized_return: number;
    max_drawdown: number;
    sortino: number;
    diversification_ratio: number;
    exposure: number;
    annualized_volatility: number;
  };
  equity_curve: EquityDataPoint[];
  drawdown_bands: DrawdownBand[];
}

export default function PortfolioPage() {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/portfolio')
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, []);

  if (loading) return <div className="p-6 text-muted-foreground">Loading real data...</div>;
  if (error || !data) return <div className="p-6 text-red-400">Error: {error}</div>;

  const m = data.portfolio_metrics;
  const cohort = data.portfolio?.cohort ?? 'first_cohort';
  const timestamp = data.portfolio?.timestamp ?? '';

  const metrics = [
    { label: 'Sharpe', value: m.sharpe.toFixed(3), numericValue: m.sharpe, scaleType: 'sharpe' as ScaleType },
    { label: 'DSR', value: m.dsr.toFixed(3), numericValue: m.dsr, scaleType: 'dsr' as ScaleType },
    { label: 'Ann. Return', value: `${(m.annualized_return * 100).toFixed(1)}%` },
    { label: 'Max DD', value: `${(m.max_drawdown * 100).toFixed(1)}%`, numericValue: m.max_drawdown, scaleType: 'maxDrawdown' as ScaleType },
    { label: 'Sortino', value: m.sortino.toFixed(3), numericValue: m.sortino, scaleType: 'sortino' as ScaleType },
    { label: 'Diversif. Ratio', value: m.diversification_ratio.toFixed(2), numericValue: m.diversification_ratio, scaleType: 'divRatio' as ScaleType },
    { label: 'Exposure', value: `${(m.exposure * 100).toFixed(1)}%` },
  ];

  // equity_curve from API already has { date, portfolio, buyHold, drawdown }
  const equityData = data.equity_curve;

  const drawdownBands = data.drawdown_bands;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Portfolio Overview</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Cohort: <span className="font-mono text-zinc-300">{cohort}</span>
          </p>
        </div>
        <div className="text-right">
          <p className="text-sm text-muted-foreground">Timestamp</p>
          <p className="font-mono text-zinc-300">{timestamp}</p>
        </div>
      </div>

      {/* Metric Cards Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
        {metrics.map((metric) => (
          <MetricCard
            key={metric.label}
            label={metric.label}
            value={metric.value}
            numericValue={metric.numericValue}
            scaleType={metric.scaleType}
          />
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium">Equity Curve</CardTitle>
          </CardHeader>
          <CardContent>
            <EquityChart data={equityData} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium">Drawdown</CardTitle>
          </CardHeader>
          <CardContent>
            <DrawdownBands data={drawdownBands} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
