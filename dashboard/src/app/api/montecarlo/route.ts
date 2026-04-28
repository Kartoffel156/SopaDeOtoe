/**
 * API route: /api/montecarlo
 * Returns permutation, bootstrap, and CPCV data.
 * Monte Carlo in the JSON is NOT paths — it's statistical test results.
 * We compute Sharpe ratio distribution from CPCV sharpe_distribution.
 */

import * as fs from "fs";
import * as path from "path";

const PORTFOLIO_DIR = "/Users/nongo/Documents/Patacon/SopaDeOtoe/results/portfolio";

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

    const mc = portfolio.montecarlo ?? {};
    const cpcv = mc.cpcv ?? {};
    const bootstrap = mc.bootstrap ?? {};

    // Build histogram bins from CPCV Sharpe distribution
    const sharpeDist = cpcv.sharpe_distribution ?? [];
    const min = sharpeDist.length > 0 ? Math.min(...sharpeDist) : 0;
    const max = sharpeDist.length > 0 ? Math.max(...sharpeDist) : 1;
    const binCount = 20;
    const binWidth = (max - min) / binCount || 1;
    const histogram = Array.from({ length: binCount }, (_, i) => ({
      bin: parseFloat((min + i * binWidth).toFixed(4)),
      count: sharpeDist.filter((v: number) => v >= min + i * binWidth && v < min + (i + 1) * binWidth).length,
    }));

    return Response.json({
      montecarlo: {
        permutation: mc.permutation ?? {},
        bootstrap: {
          sharpe_mean: bootstrap.sharpe_mean ?? 0,
          sharpe_std: bootstrap.sharpe_std ?? 0,
          sharpe_ci_95: bootstrap.sharpe_ci_95 ?? [0, 0],
          prob_negative_sharpe: bootstrap.prob_negative_sharpe ?? 0,
        },
        cpcv: {
          mean: cpcv.mean ?? 0,
          std: cpcv.std ?? 0,
          sharpe_distribution: sharpeDist,
          histogram,
        },
      },
      portfolio_metrics: portfolio.portfolio_metrics ?? {},
    });
  } catch (err) {
    console.error("[/api/montecarlo]", err);
    return Response.json({ error: "Internal error" }, { status: 500 });
  }
}
