// ─── Formatting Utilities ────────────────────────────────────────────────────

/** Multiply by 100 and format as percentage string */
export function pct(value: number, decimals = 2): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

/** Format Sharpe ratio */
export function sharpe(value: number, decimals = 3): string {
  return value.toFixed(decimals);
}

/** Format a generic ratio (Sortino, Calmar, etc.) */
export function ratio(value: number, decimals = 3): string {
  return value.toFixed(decimals);
}

/** Extract H### from strategy name and abbreviate, e.g. "HypothesisH236..." → "H236" */
export function shortStrategyName(name: string): string {
  const match = name.match(/H(\d+)/);
  if (match) return `H${match[1]}`;
  // fallback: truncate class name
  const classPart = name.split("_")[0] ?? name;
  return classPart.length > 12 ? classPart.slice(0, 10) + "…" : classPart;
}

/** Truncate strategy ID to first 8 chars */
export function shortStrategyId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) : id;
}

/** Extract config hash suffix (last 6 chars) */
export function strategyConfigHash(id: string): string {
  const parts = id.split("_");
  return parts[parts.length - 1]?.slice(0, 6) ?? id;
}

/** Format YYYYMMDD timestamp to readable date string */
export function formatDate(timestamp: string): string {
  const s = timestamp.replace(/[_\s:]/g, "");
  if (s.length < 8) return timestamp;
  const year = s.slice(0, 4);
  const month = s.slice(4, 6);
  const day = s.slice(6, 8);
  return `${year}-${month}-${day}`;
}

/** Format timestamp string to full datetime */
export function formatTimestamp(timestamp: string): string {
  const s = timestamp.replace(/_/g, " ").replace(/(\d{8})(\d{6})/, "$1 $2");
  return s;
}
