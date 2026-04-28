'use client';

import { useState, useEffect } from 'react';
import { CorrelationHeatmap } from '@/components/charts/CorrelationHeatmap';
import { ScreePlot } from '@/components/charts/ScreePlot';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface CorrelationData {
  correlation: Record<string, Record<string, number>>;
  orthogonality: {
    pca: {
      eigenvalues: number[];
      explained_variance_ratio: number[];
      cumulative_variance: number[];
      effective_dimension: number;
    };
    clustering: {
      linkage: number[][];
      labels: string[];
      distance_matrix: number[][];
    };
    flags: string[];
  };
}

export default function CorrelationPage() {
  const [data, setData] = useState<CorrelationData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/correlation')
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 text-muted-foreground">Loading...</div>;
  if (!data?.correlation || !data?.orthogonality) return <div className="p-6 text-red-400">No data</div>;

  const { correlation, orthogonality } = data;
  const pca = orthogonality.pca;
  const effDim = pca.effective_dimension;
  const pcaEigenvalues = pca.eigenvalues ?? [];
  const explained = pca.explained_variance_ratio ?? [];
  const cumulative = pca.cumulative_variance ?? [];

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Correlation & Orthogonality</h1>
        <p className="text-muted-foreground text-sm mt-1">Are strategies truly independent?</p>
      </div>

      {/* Correlation Heatmap */}
      <Card>
        <CardHeader><CardTitle>Correlation Matrix</CardTitle></CardHeader>
        <CardContent>
          <div className="flex justify-center overflow-x-auto">
            <CorrelationHeatmap result={data} />
          </div>
        </CardContent>
      </Card>

      {/* Scree Plot + Cumulative */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Scree Plot — PCA Eigenvalues</CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              Effective dimension: <span className="text-[var(--accent-cyan)]">{effDim}</span> (eigenvalues &gt; 1.0)
            </p>
          </CardHeader>
          <CardContent>
            <ScreePlot eigenvalues={pcaEigenvalues} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Cumulative Explained Variance</CardTitle></CardHeader>
          <CardContent className="pt-4">
            <div className="space-y-2">
              {explained.map((v: number, i: number) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="text-xs font-mono text-muted-foreground w-6">PC{i + 1}</span>
                  <div className="flex-1 bg-[var(--border)] rounded-full h-2">
                    <div
                      className="bg-[var(--accent-cyan)] h-2 rounded-full"
                      style={{ width: `${v * 100}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono w-16 text-right">
                    {(v * 100).toFixed(1)}% ({(cumulative[i] * 100).toFixed(1)}%)
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Flags */}
      {orthogonality.flags?.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Orthogonality Flags</CardTitle></CardHeader>
          <CardContent>
            <ul className="space-y-1">
              {orthogonality.flags.map((f: string, i: number) => (
                <li key={i} className="text-sm text-yellow-400">⚠ {f}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
