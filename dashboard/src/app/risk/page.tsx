'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { RiskContributionBar } from '@/components/charts/RiskContributionBar';
import { Table, TableHead, TableBody, TableRow, TableCell } from '@/components/ui/table';
import { GradeBadge } from '@/components/GradeBadge';
import { shortStrategyName, pct } from '@/lib/formatters';

interface RiskAttributionItem {
  strategy: string;
  weight: number;
  marginal_risk: number;
  risk_contribution: number;
  risk_contribution_pct: number;
}

type SortKey = keyof RiskAttributionItem;

export default function RiskPage() {
  const [data, setData] = useState<{ risk_attribution: RiskAttributionItem[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState<SortKey>('risk_contribution_pct');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    fetch('/api/risk')
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 text-muted-foreground">Loading...</div>;
  if (!data?.risk_attribution) return <div className="p-6 text-red-400">No data</div>;

  const sorted = [...data.risk_attribution].sort((a, b) => {
    const av = a[sortKey] as number;
    const bv = b[sortKey] as number;
    return sortDir === 'desc' ? bv - av : av - bv;
  });

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir('desc'); }
  };

  const maxPct = Math.max(...data.risk_attribution.map((d) => d.risk_contribution_pct));

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Risk Attribution</h1>
        <p className="text-muted-foreground text-sm mt-1">Who is driving portfolio risk?</p>
      </div>

      {/* Bar chart */}
      <Card>
        <CardHeader><CardTitle>Risk Contribution by Strategy</CardTitle></CardHeader>
        <CardContent>
          <RiskContributionBar data={sorted} />
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader><CardTitle>Risk Decomposition</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHead>
              <TableRow>
                {(['strategy', 'weight', 'risk_contribution_pct', 'marginal_risk'] as SortKey[]).map((k) => (
                  <TableCell key={k} className="cursor-pointer select-none" onClick={() => handleSort(k)}>
                    {k.replace(/_/g, ' ')} {sortKey === k ? (sortDir === 'desc' ? '↓' : '↑') : ''}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {sorted.map((row) => (
                <TableRow key={row.strategy}>
                  <TableCell className="font-mono text-xs">{shortStrategyName(row.strategy)}</TableCell>
                  <TableCell>{pct(row.weight)}</TableCell>
                  <TableCell>
                    <span className="text-[var(--accent-cyan)]">{pct(row.risk_contribution_pct)}</span>
                  </TableCell>
                  <TableCell>{row.marginal_risk.toExponential(2)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
