/**
 * API route: /api/trades
 * Reads real backtest trades from per-strategy run directories (backtest_trades.csv).
 * v12_run_dir in per_strategy_source points directly to the run directory.
 */

import * as fs from "fs";
import * as path from "path";

const PORTFOLIO_DIR = "/Users/nongo/Documents/Patacon/SopaDeOtoe/results/portfolio";

interface Trade {
  date: string;
  strategy: string;
  side: "LONG" | "SHORT";
  entry_price: number;
  exit_price: number;
  return: number;
  bars: number;
  barrier: "profit" | "stop" | "time";
  mae: number;
  mfe: number;
  bet_size: number;
  pnl: number;
}

export async function GET() {
  try {
    const cohortFiles = fs.readdirSync(PORTFOLIO_DIR)
      .filter((f) => f.startsWith("first_cohort_") && f.endsWith(".json"))
      .sort()
      .reverse();

    if (cohortFiles.length === 0) {
      return Response.json({ error: "No portfolio results found" }, { status: 404 });
    }

    const portfolioRaw = fs.readFileSync(path.join(PORTFOLIO_DIR, cohortFiles[0]), "utf-8");
    const portfolio = JSON.parse(portfolioRaw);

    const weights = portfolio.weights ?? {};
    const perStrategySource: Array<{ name: string; v12_run_dir: string }> =
      portfolio.per_strategy_source ?? [];

    const allTrades: Trade[] = [];

    for (const s of perStrategySource) {
      const strategyName = s.name;
      if (!(strategyName in weights)) continue;

      const runDir = s.v12_run_dir ?? "";
      const tradesFile = path.join(runDir, "backtest_trades.csv");

      // Skip if run dir or trades file doesn't exist
      if (!fs.existsSync(tradesFile)) {
        console.warn(`[/api/trades] No backtest_trades.csv for ${strategyName} at ${runDir}`);
        continue;
      }

      try {
        const content = fs.readFileSync(tradesFile, "utf-8");
        const lines = content.trim().split("\n");
        if (lines.length < 2) continue;

        const headers = lines[0].split(",");
        const entryDateIdx = headers.indexOf("entry_date");
        const sideIdx = headers.indexOf("side");
        const retIdx = headers.indexOf("trade_return");
        const barsIdx = headers.indexOf("holding_bars");
        const maeIdx = headers.indexOf("MAE");
        const mfeIdx = headers.indexOf("MFE");
        const entryPriceIdx = headers.indexOf("entry_price");
        const exitPriceIdx = headers.indexOf("exit_price");
        const betSizeIdx = headers.indexOf("bet_size");

        for (let i = 1; i < lines.length; i++) {
          const cols = lines[i].split(",");
          if (cols.length <= Math.max(entryDateIdx, sideIdx, retIdx, barsIdx, maeIdx, mfeIdx, entryPriceIdx, exitPriceIdx)) continue;

          const entryDateRaw = cols[entryDateIdx];
          const entryDate = entryDateRaw.split(" ")[0];
          const sideVal = parseInt(cols[sideIdx], 10);
          const side: "LONG" | "SHORT" = sideVal >= 1 ? "LONG" : "SHORT";
          const ret = parseFloat(cols[retIdx]);
          const bars = parseInt(cols[barsIdx], 10);
          const mae = parseFloat(cols[maeIdx]);
          const mfe = parseFloat(cols[mfeIdx]);
          const entryPrice = parseFloat(cols[entryPriceIdx]);
          const exitPrice = parseFloat(cols[exitPriceIdx]);
          const betSize = betSizeIdx >= 0 ? parseFloat(cols[betSizeIdx]) : 1.0;
          const pnl = entryPrice * ret * betSize; // absolute PnL in quote currency

          // Infer barrier from return and bars
          let barrier: "profit" | "stop" | "time";
          if (bars <= 3 && Math.abs(ret) > 0.005) barrier = "profit";
          else if (ret > 0.01) barrier = "profit";
          else if (ret < -0.005) barrier = "stop";
          else barrier = "time";

          allTrades.push({
            date: entryDate,
            strategy: strategyName,
            side,
            entry_price: entryPrice,
            exit_price: exitPrice,
            return: Math.round(ret * 10000) / 10000,
            bars,
            barrier,
            mae: Math.round(mae * 10000) / 10000,
            mfe: Math.round(mfe * 10000) / 10000,
            bet_size: Math.round(betSize * 10000) / 10000,
            pnl: Math.round(pnl * 10000) / 10000,
          });
        }
      } catch (err) {
        console.error(`[/api/trades] Error reading trades for ${strategyName} from ${tradesFile}:`, err);
      }
    }

    // Sort by date descending (most recent first)
    allTrades.sort((a, b) => b.date.localeCompare(a.date));

    return Response.json(
      { trades: allTrades, count: allTrades.length },
      { headers: { "Cache-Control": "no-store" } }
    );
  } catch (err) {
    console.error("[/api/trades]", err);
    return Response.json({ error: "Internal error" }, { status: 500 });
  }
}
