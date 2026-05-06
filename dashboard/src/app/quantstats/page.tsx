"use client";
import { useEffect, useState } from "react";

interface Metrics {
  sharpe: number;
  sortino: number;
  calmar: number;
  max_drawdown: number;
  win_rate: number;
  profit_factor: number;
  cum_returns: number;
  annual_volatility: number;
  skew: number;
  kurtosis: number;
  tail_ratio: number;
  best_day: number;
  worst_day: number;
  value_at_risk: number;
  conditional_value_at_risk: number;
}

export default function QuantStatsPage() {
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [reportUrl, setReportUrl] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/quantstats-report")
      .then((r) => r.json())
      .then((data) => {
        if (data.status === "ready") {
          setMetrics(data.metrics);
          setReportUrl(data.report_url);
          setStatus("ready");
        } else {
          setStatus("error");
        }
      })
      .catch(() => setStatus("error"));
  }, []);

  if (status === "loading") {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-gray-400">Generando tearsheet con quantstats...</p>
        </div>
      </div>
    );
  }

  if (status === "error" || !reportUrl) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-red-400">Error generando el reporte. Revisa el log del API route.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Metrics summary bar */}
      <div className="bg-gray-900 border-b border-gray-800">
        <div className="grid grid-cols-5 gap-px bg-gray-800">
          <MetricCard label="Sharpe" value={metrics?.sharpe?.toFixed(2) ?? "—"} />
          <MetricCard label="Sortino" value={metrics?.sortino?.toFixed(2) ?? "—"} />
          <MetricCard label="Calmar" value={metrics?.calmar?.toFixed(2) ?? "—"} />
          <MetricCard label="Max DD" value={`${((metrics?.max_drawdown ?? 0) * 100).toFixed(1)}%`} />
          <MetricCard label="Win Rate" value={`${((metrics?.win_rate ?? 0) * 100).toFixed(1)}%`} />
          <MetricCard label="Profit Factor" value={metrics?.profit_factor?.toFixed(2) ?? "—"} />
          <MetricCard label="Cum Return" value={`${((metrics?.cum_returns ?? 0) * 100).toFixed(1)}%`} />
          <MetricCard label="Ann. Vol" value={`${((metrics?.annual_volatility ?? 0) * 100).toFixed(1)}%`} />
          <MetricCard label="Skewness" value={metrics?.skew?.toFixed(3) ?? "—"} />
          <MetricCard label="Kurtosis" value={metrics?.kurtosis?.toFixed(3) ?? "—"} />
          <MetricCard label="Tail Ratio" value={metrics?.tail_ratio?.toFixed(2) ?? "—"} />
          <MetricCard label="Best Day" value={`${((metrics?.best_day ?? 0) * 100).toFixed(2)}%`} />
          <MetricCard label="Worst Day" value={`${((metrics?.worst_day ?? 0) * 100).toFixed(2)}%`} />
          <MetricCard label="VaR (5%)" value={`${((metrics?.value_at_risk ?? 0) * 100).toFixed(2)}%`} />
          <MetricCard label="CVaR (5%)" value={`${((metrics?.conditional_value_at_risk ?? 0) * 100).toFixed(2)}%`} />
        </div>
      </div>

      {/* quantstats tearsheet iframe */}
      <iframe
        src={reportUrl}
        className="w-full border-0"
        style={{ height: "calc(100vh - 160px)" }}
        title="QuantStats Tearsheet"
      />
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-900 px-4 py-3 text-center">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="text-lg font-semibold text-white mt-0.5 tabular-nums">{value}</p>
    </div>
  );
}
