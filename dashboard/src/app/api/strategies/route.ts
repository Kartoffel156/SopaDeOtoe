/**
 * API route: /api/strategies
 * Returns per-strategy metrics from per_strategy_source in the portfolio JSON,
 * with win_rate computed from daily_returns in the corresponding REPRO file.
 */

import * as fs from "fs";
import * as path from "path";

const PORTFOLIO_DIR = "/Users/nongo/Documents/Patacon/SopaDeOtoe/results/portfolio";
const EXPLORATION_DIR = "/Users/nongo/Documents/Patacon/SopaDeOtoe/results/exploration";

export async function GET() {
  try {
    const files = fs.readdirSync(PORTFOLIO_DIR)
      .filter((f) => f.startsWith("first_cohort_") && f.endsWith(".json"))
      .sort()
      .reverse();

    if (files.length === 0) {
      return Response.json({ error: "No portfolio results found" }, { status: 404 });
    }

    const raw = fs.readFileSync(path.join(PORTFOLIO_DIR, files[0]), "utf-8");
    const portfolio = JSON.parse(raw);

    const strategies = (portfolio.per_strategy_source ?? []).map((s: any) => {
      const m = s.source_metrics ?? {};

      // Try to compute win_rate from daily_returns in the REPRO file
      let win_rate = m.win_rate ?? 0;
      if (win_rate === 0 && s.v12_run_dir) {
        try {
          // Extract strategy name and date prefix from v12_run_dir
          // e.g. /Users/.../BTC-USD_1d_20260420_041905_c6158708
          const dirParts = s.v12_run_dir.split("/");
          const runId = dirParts[dirParts.length - 1]; // e.g. BTC-USD_1d_20260420_041905_c6158708
          // Look for REPRO file matching this pattern
          const reproFiles = fs.readdirSync(EXPLORATION_DIR);
          const strategyBase = s.name.replace(/_[a-f0-9]{8}$/, "");
          const match = reproFiles.find((f) =>
            f.startsWith(strategyBase) && f.endsWith("_REPRO.json")
          );
          if (match) {
            const repro = JSON.parse(
              fs.readFileSync(path.join(EXPLORATION_DIR, match), "utf-8")
            );
            const returns = repro.daily_returns ?? [];
            if (returns.length > 0) {
              const wins = returns.filter((r: number) => r > 0).length;
              const losses = returns.filter((r: number) => r < 0).length;
              const total = wins + losses;
              win_rate = total > 0 ? wins / total : 0;
            }
          }
        } catch { /* skip */ }
      }

      return {
        name: s.name ?? "unknown",
        sharpe: m.sharpe ?? 0,
        total_return: m.total_return ?? 0,
        max_drawdown: m.max_drawdown ?? 0,
        calmar: m.calmar ?? 0,
        sortino: m.sortino ?? 0,
        n_trades: m.n_trades ?? 0,
        profit_factor: m.profit_factor ?? 0,
        win_rate,
        long_pct: m.long_pct ?? 0,
      };
    });

    return Response.json(strategies);
  } catch (err) {
    console.error("[/api/strategies]", err);
    return Response.json({ error: "Internal error" }, { status: 500 });
  }
}
