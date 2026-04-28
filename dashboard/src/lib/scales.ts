// ─── Grade Functions ──────────────────────────────────────────────────────────
// Map metric values to a 0–100 grade scale with qualitative labels

export type GradeLabel = "A+" | "A" | "B+" | "B" | "C+" | "C" | "D" | "F";

export interface GradeResult {
  score: number;   // 0–100
  label: GradeLabel;
  color: string;  // hex
}

// Sharpe: higher is better. Typical range: -1 to 3+
export function gradeSharpe(value: number): GradeResult {
  const score = Math.min(100, Math.max(0, ((value + 0.5) / 3.5) * 100));
  return gradeResultFromScore(score);
}

// Max Drawdown: higher (less negative) is better. Range: -1 to 0
export function gradeMaxDrawdown(value: number): GradeResult {
  // value is negative; map -1 → 0, 0 → 100
  const score = Math.min(100, Math.max(0, (1 + value) * 100));
  return gradeResultFromScore(score);
}

// DSR (Downside Deviation Ratio): higher is better. Range: 0 to 2+
export function gradeDSR(value: number): GradeResult {
  const score = Math.min(100, Math.max(0, (value / 1.5) * 100));
  return gradeResultFromScore(score);
}

// Diversification Ratio: higher is better. Range: 1 to 5
export function gradeDiversification(value: number): GradeResult {
  const score = Math.min(100, Math.max(0, ((value - 1) / 4) * 100));
  return gradeResultFromScore(score);
}

// Correlation: lower absolute is better for diversification. Range: -1 to 1
export function gradeCorrelation(value: number): GradeResult {
  // lower absolute correlation is better; 0 → 100, ±1 → 0
  const abs = Math.abs(value);
  const score = (1 - abs) * 100;
  return gradeResultFromScore(score);
}

// Effective Dimension: closer to number of strategies is better. Range: 1 to N
export function gradeEffectiveDim(value: number, nStrategies = 9): GradeResult {
  // ideal is around nStrategies/2 to nStrategies (good diversification, not over-diversified)
  const ideal = nStrategies * 0.6;
  const deviation = Math.abs(value - ideal) / nStrategies;
  const score = Math.max(0, 100 - deviation * 100);
  return gradeResultFromScore(score);
}

// Sortino: higher is better. Range: 0 to 3+
export function gradeSortino(value: number): GradeResult {
  const score = Math.min(100, Math.max(0, (value / 2.5) * 100));
  return gradeResultFromScore(score);
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function gradeResultFromScore(score: number): GradeResult {
  if (score >= 95) return { score, label: "A+", color: gradeToHex(score) };
  if (score >= 85) return { score, label: "A",  color: gradeToHex(score) };
  if (score >= 75) return { score, label: "B+", color: gradeToHex(score) };
  if (score >= 65) return { score, label: "B",  color: gradeToHex(score) };
  if (score >= 55) return { score, label: "C+", color: gradeToHex(score) };
  if (score >= 45) return { score, label: "C",  color: gradeToHex(score) };
  if (score >= 30) return { score, label: "D",  color: gradeToHex(score) };
  return { score, label: "F", color: gradeToHex(score) };
}

// Interpolate between red (#ef4444) → yellow (#eab308) → green (#22c55e)
export function gradeToHex(score: number): string {
  const clamped = Math.min(100, Math.max(0, score));

  if (clamped >= 50) {
    // green (#22c55e) to yellow (#eab308)
    const t = (clamped - 50) / 50;
    const r = Math.round(34  + (234 - 34)  * (1 - t));
    const g = Math.round(197 + (179 - 197) * (1 - t));
    const b = Math.round(94  + (8   - 94)  * (1 - t));
    return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
  } else {
    // yellow (#eab308) to red (#ef4444)
    const t = clamped / 50;
    const r = Math.round(239);
    const g = Math.round(179 * t);
    const b = Math.round(8   + (8   - 8)   * t);
    return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
  }
}
