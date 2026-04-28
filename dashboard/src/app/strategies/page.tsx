'use client';

import { useMemo, useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { shortStrategyName, pct } from '@/lib/formatters';
import { Slider } from '@/components/ui/slider';

interface StrategyMetrics {
  name: string;
  sharpe: number;
  total_return: number;
  max_drawdown: number;
  calmar: number;
  sortino: number;
  n_trades: number;
  profit_factor: number;
  win_rate: number;
  long_pct: number;
}

interface PortfolioApiResponse {
  weights: Record<string, number>;
}

type SortKey = 'sharpe' | 'weight' | 'max_drawdown' | 'win_rate' | 'n_trades';

function StrategyCard({
  strategy,
  weight,
  maxWeight,
}: {
  strategy: StrategyMetrics;
  weight: number;
  maxWeight: number;
}) {
  const sharpeGrade =
    strategy.sharpe >= 0.5
      ? 'excellent'
      : strategy.sharpe >= 0.3
        ? 'fair'
        : 'poor';

  const borderColor =
    sharpeGrade === 'excellent'
      ? 'var(--sf-green)'
      : sharpeGrade === 'fair'
        ? 'var(--sf-amber)'
        : 'var(--sf-red)';

  const isHealthy = true;

  return (
    <Card
      hover
      className="p-4 cursor-pointer"
      style={{ borderColor, borderWidth: 1 }}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="text-sm font-medium text-foreground">
            {shortStrategyName(strategy.name)}
          </div>
          <Badge variant="purple" className="mt-0.5 text-[10px]">
            {strategy.name.split('_').pop()?.slice(0, 8) ?? 'unknown'}
          </Badge>
        </div>
        <Badge variant={weight > 0.12 ? 'success' : 'secondary'}>
          {pct(weight)}
        </Badge>
      </div>

      <div className="grid grid-cols-5 gap-2 mb-3">
        {[
          {
            label: 'Sharpe',
            value: strategy.sharpe.toFixed(2),
            grade: sharpeGrade,
          },
          {
            label: 'MaxDD',
            value: pct(strategy.max_drawdown),
            grade:
              strategy.max_drawdown > -0.1
                ? 'excellent'
                : strategy.max_drawdown > -0.2
                  ? 'fair'
                  : 'poor',
          },
          {
            label: 'Sortino',
            value: strategy.sortino.toFixed(2),
            grade: 'fair',
          },
          {
            label: 'Win%',
            value: pct(strategy.win_rate, 1),
            grade: 'fair',
          },
          {
            label: 'Trades',
            value: strategy.n_trades.toString(),
            grade: 'fair',
          },
        ].map(({ label, value, grade }) => (
          <div key={label} className="text-center">
            <div className="text-[10px] text-muted-foreground uppercase">
              {label}
            </div>
            <div className={`text-xs font-mono font-medium grade-${grade}`}>
              {value}
            </div>
          </div>
        ))}
      </div>

      {/* Mini weight bar */}
      <div className="mt-2">
        <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
          <span>Portfolio weight</span>
          <span className="flex items-center gap-1">
            <span
              className={`w-1.5 h-1.5 rounded-full ${isHealthy ? 'bg-green-500' : 'bg-red-500'}`}
            />
            {isHealthy ? 'healthy' : 'collapsed'}
          </span>
        </div>
        <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
          <div
            className="h-full bg-[var(--sf-purple)] rounded-full transition-all"
            style={{
              width: `${maxWeight > 0 ? Math.min((weight / maxWeight) * 100, 100) : 0}%`,
            }}
          />
        </div>
      </div>
    </Card>
  );
}

export default function StrategiesPage() {
  const [sharpeMin, setSharpeMin] = useState(0);
  const [sortKey, setSortKey] = useState<SortKey>('sharpe');
  const [sortAsc, setSortAsc] = useState(false);
  const [strategies, setStrategies] = useState<StrategyMetrics[]>([]);
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        // Load both in parallel
        const [stratRes, portRes] = await Promise.all([
          fetch('/api/strategies', { cache: 'no-store' }),
          fetch('/api/portfolio', { cache: 'no-store' }),
        ]);

        if (!stratRes.ok || !portRes.ok) {
          throw new Error('Failed to load data');
        }

        const stratData: StrategyMetrics[] = await stratRes.json();
        const portData: PortfolioApiResponse = await portRes.json();

        setStrategies(stratData);
        setWeights(portData.weights ?? {});
      } catch (e: any) {
        setError(e.message ?? 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const maxWeight = useMemo(() => {
    return Math.max(...Object.values(weights), 0);
  }, [weights]);

  // Build strategy + weight list
  const strategyList = useMemo(() => {
    return strategies.map((s) => {
      const weight = weights[s.name] ?? 0;
      return { strategy: s, weight };
    });
  }, [strategies, weights]);

  // Filter and sort
  const filtered = useMemo(() => {
    let list = strategyList.filter(
      ({ strategy, weight }) =>
        strategy.sharpe >= sharpeMin / 100 && weight > 0
    );

    list.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case 'sharpe':
          cmp = a.strategy.sharpe - b.strategy.sharpe;
          break;
        case 'weight':
          cmp = a.weight - b.weight;
          break;
        case 'max_drawdown':
          cmp = a.strategy.max_drawdown - b.strategy.max_drawdown;
          break;
        case 'win_rate':
          cmp = a.strategy.win_rate - b.strategy.win_rate;
          break;
        case 'n_trades':
          cmp = a.strategy.n_trades - b.strategy.n_trades;
          break;
      }
      return sortAsc ? cmp : -cmp;
    });

    return list;
  }, [strategyList, sharpeMin, sortKey, sortAsc]);

  const count = filtered.length;

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <p className="text-muted-foreground">Loading strategies...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <p className="text-red-400">Error: {error}</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Cohort Manager</h1>
          <p className="text-muted-foreground text-sm mt-1">
            {count} graduated strategies
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-6">
        {/* Sharpe min slider */}
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground whitespace-nowrap">
            Sharpe min:
          </span>
          <Slider
            value={sharpeMin}
            min={0}
            max={100}
            step={1}
            onChange={(v) => setSharpeMin(v)}
            className="w-40"
            fillColor="var(--sf-purple)"
          />
          <span className="text-sm font-mono w-10">
            {(sharpeMin / 100).toFixed(2)}
          </span>
        </div>

        {/* Sort dropdown */}
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground whitespace-nowrap">
            Sort by:
          </span>
          <select
            className="bg-background border border-border rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
          >
            <option value="sharpe">Sharpe</option>
            <option value="weight">Weight</option>
            <option value="max_drawdown">Max Drawdown</option>
            <option value="win_rate">Win Rate</option>
            <option value="n_trades">Trades</option>
          </select>
          <button
            className="text-muted-foreground hover:text-foreground transition-colors text-sm"
            onClick={() => setSortAsc((v) => !v)}
            title={sortAsc ? 'Ascending' : 'Descending'}
          >
            {sortAsc ? '↑' : '↓'}
          </button>
        </div>
      </div>

      {/* Strategy Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map(({ strategy, weight }) => (
          <StrategyCard
            key={strategy.name}
            strategy={strategy}
            weight={weight}
            maxWeight={maxWeight}
          />
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          No strategies match the current filters.
        </div>
      )}
    </div>
  );
}
