/**
 * API route: /api/quantstats-report
 * Generates quantstats tearsheet HTML and returns metrics + report URL.
 * Invokes portfolio/quantstats_script.py as a subprocess.
 */
import { execSync } from "child_process";
import * as fs from "fs";
import * as path from "path";

const SCRIPT = "/Users/nongo/Documents/Patacon/SopaDeOtoe/portfolio/quantstats_script.py";
const OUTPUT_DIR = "/Users/nongo/Documents/Patacon/SopaDeOtoe/dashboard/public/quantstats";

export async function GET() {
  try {
    if (!fs.existsSync(OUTPUT_DIR)) {
      fs.mkdirSync(OUTPUT_DIR, { recursive: true });
    }

    const outputPath = path.join(OUTPUT_DIR, "portfolio_tearsheet.html");
    const metricsPath = path.join(OUTPUT_DIR, "metrics.json");

    // Check cache: if HTML exists and is newer than latest portfolio JSON, skip generation
    const portfolioDir = "/Users/nongo/Documents/Patacon/SopaDeOtoe/results/portfolio";
    const portfolioFiles = fs.readdirSync(portfolioDir).filter((f) => f.startsWith("first_cohort_") && f.endsWith(".json"));
    const latestPortfolioMtime = Math.max(...portfolioFiles.map((f) => fs.statSync(path.join(portfolioDir, f)).mtimeMs));

    if (fs.existsSync(outputPath) && fs.existsSync(metricsPath)) {
      const htmlMtime = fs.statSync(outputPath).mtimeMs;
      if (htmlMtime > latestPortfolioMtime) {
        // Cache is fresh — read existing metrics and return
        const metrics = JSON.parse(fs.readFileSync(metricsPath, "utf-8"));
        return Response.json({
          status: "ready",
          report_url: "/quantstats/portfolio_tearsheet.html",
          metrics,
          cached: true,
        });
      }
    }

    // Generate fresh tearsheet
    execSync(
      `/Users/nongo/Documents/Patacon/SopaDeOtoe/.venv/bin/python3 ${SCRIPT} --output ${outputPath} --metrics-output ${metricsPath}`,
      { timeout: 120_000 }
    );

    const metrics = JSON.parse(fs.readFileSync(metricsPath, "utf-8"));

    return Response.json({
      status: "ready",
      report_url: "/quantstats/portfolio_tearsheet.html",
      metrics,
      cached: false,
    });
  } catch (err) {
    console.error("[/api/quantstats-report]", err);
    return Response.json({ error: "Failed to generate report" }, { status: 500 });
  }
}
