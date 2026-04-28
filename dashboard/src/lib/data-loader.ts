import * as fs from "fs";
import * as path from "path";
import type { PortfolioResult, GraduatedStrategy } from "./types";

// ─── Data Loader ─────────────────────────────────────────────────────────────

const PORTFOLIO_DIR = path.join(
  process.cwd(),
  "..",
  "..",
  "results",
  "portfolio"
);

const MANIFEST_PATH = path.join(
  process.cwd(),
  "..",
  "..",
  "strategies",
  "graduated_manifest.yaml"
);

/**
 * Load the latest first_cohort JSON result file.
 * Files are named: first_cohort_YYYYMMDD_HHmmss.json
 */
export function loadPortfolioResults(): PortfolioResult | null {
  try {
    const files = fs
      .readdirSync(PORTFOLIO_DIR)
      .filter((f) => f.startsWith("first_cohort_") && f.endsWith(".json"))
      .sort()
      .reverse();

    if (files.length === 0) return null;

    const latest = files[0];
    const raw = fs.readFileSync(path.join(PORTFOLIO_DIR, latest), "utf-8");
    return JSON.parse(raw) as PortfolioResult;
  } catch (err) {
    console.error("[data-loader] loadPortfolioResults failed:", err);
    return null;
  }
}

/**
 * Load and parse the graduated manifest YAML.
 */
export function loadGraduatedManifest(): GraduatedStrategy[] | null {
  try {
    // Minimal YAML parser for the known structure
    const raw = fs.readFileSync(MANIFEST_PATH, "utf-8");
    return parseGraduatedYaml(raw);
  } catch (err) {
    console.error("[data-loader] loadGraduatedManifest failed:", err);
    return null;
  }
}

/**
 * Convert a correlation matrix (Record<string, Record<string, number>>)
 * into a flat array of [strategyA, strategyB, correlation] triples.
 */
export function correlationMatrixToArray(
  matrix: Record<string, Record<string, number>>
): Array<[string, string, number]> {
  const result: Array<[string, string, number]> = [];
  const keys = Object.keys(matrix);
  for (let i = 0; i < keys.length; i++) {
    for (let j = i + 1; j < keys.length; j++) {
      const a = keys[i];
      const b = keys[j];
      result.push([a, b, matrix[a][b]]);
    }
  }
  return result;
}

// ─── Minimal YAML Parser ──────────────────────────────────────────────────────

function parseGraduatedYaml(raw: string): GraduatedStrategy[] {
  const strategies: GraduatedStrategy[] = [];
  const lines = raw.split("\n");
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    // Detect start of a new strategy entry
    if (line.match(/^-\s+run_id:/)) {
      const entry: Partial<GraduatedStrategy> = {};
      i++;
      while (i < lines.length && !lines[i].match(/^-\s+run_id:/)) {
        const keyMatch = lines[i].match(/^\s+(\w+):\s*(.*)/);
        if (keyMatch) {
          const [, key, val] = keyMatch;
          if (key === "metrics") {
            // Parse nested metrics block
            const metrics: Record<string, number> = {};
            i++;
            while (i < lines.length && lines[i].match(/^\s{4}\w+:/)) {
              const mMatch = lines[i].match(/^\s{4}(\w+):\s*(.*)/);
              if (mMatch) {
                metrics[mMatch[1]] = parseFloat(mMatch[2]);
              }
              i++;
            }
            entry.metrics = metrics as unknown as GraduatedStrategy["metrics"];
            continue;
          } else {
            (entry as Record<string, string>)[key] = val.trim().replace(/^['"]|['"]$/g, "");
          }
        }
        i++;
      }
      if (entry.run_id) strategies.push(entry as GraduatedStrategy);
      continue;
    }
    i++;
  }
  return strategies;
}
