/**
 * API route: /api/mc-paths
 * Returns quantstats Monte Carlo simulation data from mc_results.json.
 * The mc-paths page reads the same structure as the MonteCarlo page.
 */
import * as fs from "fs";
import * as path from "path";

const MC_RESULTS_PATH =
  "/Users/nongo/Documents/Patacon/SopaDeOtoe/dashboard/public/quantstats/mc_results.json";

export async function GET() {
  try {
    if (!fs.existsSync(MC_RESULTS_PATH)) {
      return Response.json(
        { error: "MC results not found. Run the quantstats generation script." },
        { status: 404 }
      );
    }

    const raw = fs.readFileSync(MC_RESULTS_PATH, "utf-8");
    const data = JSON.parse(raw);

    // Normalize to the shape expected by the mc-paths page
    // The page expects: { montecarlo: { qs: MCData }, portfolio_metrics: {...} }
    return Response.json({
      montecarlo: {
        qs: data,
      },
      portfolio_metrics: {
        sharpe: data.median_return != null ? 0 : 0,
        sortino: 0,
        max_drawdown: data.maxdd_stats?.median ?? 0,
      },
    });
  } catch (err) {
    console.error("[/api/mc-paths]", err);
    return Response.json({ error: "Internal error" }, { status: 500 });
  }
}