/**
 * API route: /api/risk
 * Returns risk attribution + decomposition from the latest portfolio result.
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

    // risk_attribution is an array with full attribution data
    const riskAttribution = (portfolio.risk_attribution ?? []).map((r: any) => ({
      strategy: r.strategy,
      weight: r.weight ?? 0,
      marginal_risk: r.marginal_risk ?? 0,
      risk_contribution: r.risk_contribution ?? 0,
      risk_contribution_pct: r.risk_contribution_pct ?? 0,
    }));

    return Response.json({
      risk_attribution: riskAttribution,
      portfolio_metrics: portfolio.portfolio_metrics ?? {},
      weights: portfolio.weights ?? {},
    });
  } catch (err) {
    console.error("[/api/risk]", err);
    return Response.json({ error: "Internal error" }, { status: 500 });
  }
}
