/**
 * API route: /api/correlation
 * Returns correlation matrix and orthogonality analysis from portfolio JSON.
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

    const orthogonality = portfolio.orthogonality ?? {};
    const pca = orthogonality.pca ?? {};

    // Compute effective dimension (eigenvalues > 1.0)
    const eigenvalues = pca.eigenvalues ?? [];
    const effective_dimension = eigenvalues.filter((v: number) => v > 1.0).length;

    // Compute explained_variance_ratio and cumulative_variance from eigenvalues
    const totalVar = eigenvalues.reduce((s: number, v: number) => s + v, 0) || 1;
    const explained_variance_ratio = eigenvalues.map((v: number) => v / totalVar);
    let cum = 0;
    const cumulative_variance = explained_variance_ratio.map((v: number) => { cum += v; return cum; });

    // flags (if any)
    const flags: string[] = [];
    if (effective_dimension > 5) flags.push(`Effective dimension ${effective_dimension} > 5 — portfolio may lack diversification`);
    if (eigenvalues[0] > 4) flags.push(`PC1 explains ${((eigenvalues[0] / totalVar) * 100).toFixed(1)}% of variance — dominant factor`);

    return Response.json({
      correlation: portfolio.correlation ?? {},
      orthogonality: {
        pca: {
          eigenvalues,
          explained_variance_ratio,
          cumulative_variance,
          effective_dimension,
        },
        clustering: orthogonality.clustering ?? { linkage: [], labels: [], distance_matrix: [] },
        flags,
      },
    });
  } catch (err) {
    console.error("[/api/correlation]", err);
    return Response.json({ error: "Internal error" }, { status: 500 });
  }
}
