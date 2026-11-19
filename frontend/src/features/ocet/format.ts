/** Full number for tables: 146,410 (spec 7.9). */
export function fmtFull(n: number): string {
  return Math.round(n).toLocaleString('en-US');
}

/** Thousands with one decimal for charts and cards: 146.4k; millions above 1,000k: 1.92M. */
export function fmtK(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  return `${(n / 1000).toFixed(1)}k`;
}

export function fmtSigned(n: number): string {
  return `${n > 0 ? '+' : n < 0 ? '-' : ''}${fmtFull(Math.abs(n))}`;
}

export function fmtPct(p: number | null): string {
  return p === null ? 'n/a' : `${p > 0 ? '+' : ''}${p.toFixed(1)}%`;
}
