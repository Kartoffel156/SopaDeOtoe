'use client';

import { useState, useEffect } from 'react';
import { MonteCarloCone } from '@/components/charts/MonteCarloCone';
import { BootstrapHistogram } from '@/components/charts/BootstrapHistogram';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { MetricCard } from '@/components/MetricCard';

interface MonteCarloData {
  montecarlo: {
    permutation: {
      observed_sharpe: number;
      p_value: number;
      mean_perm_sharpe: number;
      std_perm_sharpe: number;
      n_permutations: number;
    };
    bootstrap: {
      sharpe_mean: number;
      sharpe_std: number;
      sharpe_ci_95: [number, number];
      prob_negative_sharpe: number;
      n_bootstrap: number;
      block_size: number;
    };
    cpcv: {
      sharpe_distribution: number[];
    };
  };
  portfolio_metrics: {
    sharpe: number;
    sortino: number;
    max_drawdown: number;
  };
}

export default function MonteCarloPage() {
  const [data, setData] = useState<MonteCarloData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/montecarlo')
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 text-muted-foreground">Loading...</div>;
  if (!data?.montecarlo) return <div className="p-6 text-red-400">No data</div>;

  const mc = data.montecarlo;
  const pm = data.portfolio_metrics;
  const spaPass = mc.permutation.p_value < 0.05;
  const observedSharpe = mc.permutation.observed_sharpe;
  const cpcvAbove = mc.cpcv.sharpe_distribution.filter((s) => s >= observedSharpe).length;
  const cpcvPct = cpcvAbove / mc.cpcv.sharpe_distribution.length;
  const cpcvPass = cpcvPct >= 0.5;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Monte Carlo Validation</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Bootstrap confidence intervals, permutation SPA test, and CPCV walk-forward validation.
        </p>
      </div>

      {/* Top metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <MetricCard label="Observed Sharpe" value={pm.sharpe.toFixed(3)} />
        <MetricCard label="Bootstrap Mean" value={mc.bootstrap.sharpe_mean.toFixed(3)} />
        <MetricCard
          label="Bootstrap CI 95%"
          value={`[${mc.bootstrap.sharpe_ci_95[0].toFixed(2)}, ${mc.bootstrap.sharpe_ci_95[1].toFixed(2)}]`}
        />
        <MetricCard label="Prob. Negative" value={`${(mc.bootstrap.prob_negative_sharpe * 100).toFixed(1)}%`} />
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">SPA Test (p &lt; 0.05)</span>
          <Badge variant={spaPass ? 'success' : 'danger'}>
            {spaPass ? 'PASS' : 'FAIL'} p={mc.permutation.p_value}
          </Badge>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Bootstrap Sharpe Distribution</CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              {mc.bootstrap.n_bootstrap} resamples, block size {mc.bootstrap.block_size}
            </p>
          </CardHeader>
          <CardContent>
            <BootstrapHistogram
              sharpeMean={mc.bootstrap.sharpe_mean}
              sharpeStd={mc.bootstrap.sharpe_std}
              ci95={mc.bootstrap.sharpe_ci_95}
              observed={pm.sharpe}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>CPCV Sharpe Distribution</CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              {cpcvAbove}/{mc.cpcv.sharpe_distribution.length} runs ≥ observed → {cpcvPass ? 'PASS' : 'FAIL'}
            </p>
          </CardHeader>
          <CardContent>
            <MonteCarloCone distribution={mc.cpcv.sharpe_distribution} observed={pm.sharpe} />
          </CardContent>
        </Card>
      </div>

      {/* Permutation test detail */}
      <Card>
        <CardHeader><CardTitle>Permutation SPA Test</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-xs text-muted-foreground">Observed Sharpe</p>
            <p className="text-lg font-mono text-[var(--accent-cyan)]">{mc.permutation.observed_sharpe.toFixed(4)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Mean (null)</p>
            <p className="text-lg font-mono">{mc.permutation.mean_perm_sharpe.toFixed(4)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Std (null)</p>
            <p className="text-lg font-mono">{mc.permutation.std_perm_sharpe.toFixed(4)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">p-value</p>
            <p className="text-lg font-mono">{mc.permutation.p_value}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
