"use client";

import { useState, useMemo, useEffect } from "react";
import type { Trade } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { X, ArrowUpRight, ArrowDownRight, RefreshCw } from "lucide-react";

interface TradesApiResponse {
  trades: Trade[];
  count: number;
}

interface Filters {
  side: string;
  barrier: string;
  returnMin: string;
  returnMax: string;
  strategy: string;
}

function ReturnDistributionChart({ trades }: { trades: Trade[] }) {
  const data = useMemo(() => {
    const buckets: Record<string, number> = {};
    const ranges = [
      "<-5%",
      "-5% to -2%",
      "-2% to 0%",
      "0% to 2%",
      "2% to 5%",
      ">5%",
    ];
    ranges.forEach((r) => (buckets[r] = 0));

    trades.forEach((t) => {
      const r = t.return * 100;
      if (r < -5) buckets["<-5%"]++;
      else if (r < -2) buckets["-5% to -2%"]++;
      else if (r < 0) buckets["-2% to 0%"]++;
      else if (r < 2) buckets["0% to 2%"]++;
      else if (r < 5) buckets["2% to 5%"]++;
      else buckets[">5%"]++;
    });

    return ranges.map((label) => ({ label, count: buckets[label] }));
  }, [trades]);

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis dataKey="label" tick={{ fill: "#71717a", fontSize: 10 }} />
        <YAxis tick={{ fill: "#71717a", fontSize: 10 }} />
        <Tooltip
          contentStyle={{
            backgroundColor: "#18181b",
            border: "1px solid #3f3f46",
            borderRadius: "6px",
            fontSize: "12px",
          }}
        />
        <Bar dataKey="count" fill="#22c55e" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function MonthlyReturnsChart({ trades }: { trades: Trade[] }) {
  const data = useMemo(() => {
    const monthly: Record<string, number> = {};
    trades.forEach((t) => {
      const month = t.date.substring(0, 7);
      monthly[month] = (monthly[month] || 0) + t.return;
    });
    return Object.entries(monthly)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([month, returnSum]) => ({
        month,
        return: Math.round(returnSum * 10000) / 10000,
      }));
  }, [trades]);

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis dataKey="month" tick={{ fill: "#71717a", fontSize: 10 }} />
        <YAxis tickFormatter={(v) => `${(v * 100).toFixed(1)}%`} tick={{ fill: "#71717a", fontSize: 10 }} />
        <Tooltip
          contentStyle={{
            backgroundColor: "#18181b",
            border: "1px solid #3f3f46",
            borderRadius: "6px",
            fontSize: "12px",
          }}
          formatter={(value) => [`${((value as number) * 100).toFixed(2)}%`, "Return"]}
        />
        <Bar dataKey="return" radius={[4, 4, 0, 0]}>
          {data.map((entry, index) => (
            <Cell key={index} fill={entry.return >= 0 ? "#22c55e" : "#ef4444"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export default function TradesPage() {
  const [allTrades, setAllTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>({
    side: "ALL",
    barrier: "ALL",
    returnMin: "",
    returnMax: "",
    strategy: "ALL",
  });

  const loadTrades = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/trades", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: TradesApiResponse = await res.json();
      setAllTrades(data.trades);
    } catch (e: any) {
      setError(e.message ?? "Failed to load trades");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTrades(); }, []);

  const strategyNames = useMemo(() => {
    const names = new Set(allTrades.map((t) => t.strategy));
    return Array.from(names).sort();
  }, [allTrades]);

  const filteredTrades = useMemo(() => {
    return allTrades.filter((t) => {
      if (filters.side !== "ALL" && t.side !== filters.side) return false;
      if (filters.barrier !== "ALL" && t.barrier !== filters.barrier) return false;
      if (filters.strategy !== "ALL" && t.strategy !== filters.strategy) return false;
      if (filters.returnMin && t.return < parseFloat(filters.returnMin)) return false;
      if (filters.returnMax && t.return > parseFloat(filters.returnMax)) return false;
      return true;
    });
  }, [allTrades, filters]);

  const handleFilterChange = (key: keyof Filters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const clearFilters = () => {
    setFilters({ side: "ALL", barrier: "ALL", returnMin: "", returnMax: "", strategy: "ALL" });
  };

  const hasActiveFilters =
    filters.side !== "ALL" ||
    filters.barrier !== "ALL" ||
    filters.returnMin !== "" ||
    filters.returnMax !== "" ||
    filters.strategy !== "ALL";

  if (loading) {
    return (
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        <div className="border-b border-border px-6 py-4">
          <h1 className="text-2xl font-semibold text-foreground">Trades</h1>
          <p className="text-sm text-muted-foreground mt-1">Loading...</p>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        <div className="border-b border-border px-6 py-4">
          <h1 className="text-2xl font-semibold text-foreground">Trades</h1>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-red-400">Error: {error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="border-b border-border px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Trades</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {filteredTrades.length} of {allTrades.length} trades
            {hasActiveFilters && " (filtered)"}
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={loadTrades} title="Refresh">
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {/* Filters */}
      <div className="border-b border-border px-6 py-3 flex flex-wrap gap-3 items-center bg-muted/30">
        <select
          className="bg-background border border-border rounded-md px-3 py-1.5 text-sm text-foreground"
          value={filters.side}
          onChange={(e) => handleFilterChange("side", e.target.value)}
        >
          <option value="ALL">All Sides</option>
          <option value="LONG">Long</option>
          <option value="SHORT">Short</option>
        </select>

        <select
          className="bg-background border border-border rounded-md px-3 py-1.5 text-sm text-foreground"
          value={filters.barrier}
          onChange={(e) => handleFilterChange("barrier", e.target.value)}
        >
          <option value="ALL">All Barriers</option>
          <option value="profit">Profit</option>
          <option value="stop">Stop</option>
          <option value="time">Time</option>
        </select>

        <select
          className="bg-background border border-border rounded-md px-3 py-1.5 text-sm text-foreground"
          value={filters.strategy}
          onChange={(e) => handleFilterChange("strategy", e.target.value)}
        >
          <option value="ALL">All Strategies</option>
          {strategyNames.map((s) => (
            <option key={s} value={s}>
              {s.split("_")[0]}
            </option>
          ))}
        </select>

        <div className="flex items-center gap-1 text-sm text-muted-foreground">
          <span>Return:</span>
          <input
            type="number"
            placeholder="Min"
            className="bg-background border border-border rounded-md px-2 py-1 text-sm text-foreground w-20"
            value={filters.returnMin}
            onChange={(e) => handleFilterChange("returnMin", e.target.value)}
          />
          <span>to</span>
          <input
            type="number"
            placeholder="Max"
            className="bg-background border border-border rounded-md px-2 py-1 text-sm text-foreground w-20"
            value={filters.returnMax}
            onChange={(e) => handleFilterChange("returnMax", e.target.value)}
          />
        </div>

        {hasActiveFilters && (
          <Button variant="ghost" size="sm" onClick={clearFilters}>
            <X className="w-4 h-4 mr-1" />
            Clear
          </Button>
        )}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-2 gap-4 px-6 py-4 border-b border-border">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Return Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ReturnDistributionChart trades={filteredTrades} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Monthly Returns</CardTitle>
          </CardHeader>
          <CardContent>
            <MonthlyReturnsChart trades={filteredTrades} />
          </CardContent>
        </Card>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 sticky top-0 text-left">
            <tr className="border-b border-border">
              <th className="px-4 py-2.5 font-medium text-muted-foreground">Date</th>
              <th className="px-4 py-2.5 font-medium text-muted-foreground">Strategy</th>
              <th className="px-4 py-2.5 font-medium text-muted-foreground">Side</th>
              <th className="px-4 py-2.5 font-medium text-muted-foreground">Entry</th>
              <th className="px-4 py-2.5 font-medium text-muted-foreground">Exit</th>
              <th className="px-4 py-2.5 font-medium text-muted-foreground">Return</th>
              <th className="px-4 py-2.5 font-medium text-muted-foreground">Bet Size</th>
              <th className="px-4 py-2.5 font-medium text-muted-foreground">PnL (USD)</th>
              <th className="px-4 py-2.5 font-medium text-muted-foreground">Bars</th>
              <th className="px-4 py-2.5 font-medium text-muted-foreground">Barrier</th>
              <th className="px-4 py-2.5 font-medium text-muted-foreground">MAE</th>
              <th className="px-4 py-2.5 font-medium text-muted-foreground">MFE</th>
            </tr>
          </thead>
          <tbody>
            {filteredTrades.map((trade, i) => (
              <tr
                key={i}
                className="border-b border-border/50 hover:bg-muted/30 transition-colors"
              >
                <td className="px-4 py-2 text-muted-foreground">{trade.date}</td>
                <td className="px-4 py-2 text-foreground font-mono text-xs">
                  {trade.strategy.split("_")[0]}
                </td>
                <td className="px-4 py-2">
                  {trade.side === "LONG" ? (
                    <span className="flex items-center gap-1 text-green-500">
                      <ArrowUpRight className="w-3.5 h-3.5" />
                      LONG
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-red-500">
                      <ArrowDownRight className="w-3.5 h-3.5" />
                      SHORT
                    </span>
                  )}
                </td>
                <td className="px-4 py-2 text-muted-foreground">
                  {trade.entry_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </td>
                <td className="px-4 py-2 text-muted-foreground">
                  {trade.exit_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </td>
                <td
                  className={`px-4 py-2 font-medium ${
                    trade.return >= 0 ? "text-green-500" : "text-red-500"
                  }`}
                >
                  {(trade.return * 100).toFixed(2)}%
                </td>
                <td className="px-4 py-2 text-muted-foreground">
                  {trade.bet_size.toFixed(4)}
                </td>
                <td
                  className={`px-4 py-2 font-medium ${
                    trade.pnl >= 0 ? "text-green-500" : "text-red-500"
                  }`}
                >
                  {trade.pnl >= 0 ? "+" : ""}{trade.pnl.toFixed(2)}
                </td>
                <td className="px-4 py-2 text-muted-foreground">{trade.bars}</td>
                <td className="px-4 py-2 text-muted-foreground capitalize">{trade.barrier}</td>
                <td className="px-4 py-2 text-muted-foreground">
                  {(trade.mae * 100).toFixed(2)}%
                </td>
                <td className="px-4 py-2 text-muted-foreground">
                  {(trade.mfe * 100).toFixed(2)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
