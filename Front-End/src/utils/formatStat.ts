/**
 * Formats a numeric statistic with honest milestone "+" representations:
 * - Returns "0" (no plus) when count is 0 or non-positive.
 * - Shows exact number plus "+" for values < 100 (e.g. 1+, 3+, 7+, 9+, 11+, 99+).
 * - Rounds down to clean milestones for larger values (e.g. 134 -> 100+, 999 -> 900+, 1,000 -> 1K+, 1,280 -> 1K+, 12,500 -> 10K+).
 * - Honest guarantee: the actual value is never less than the number shown.
 */
export function formatStat(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n) || n <= 0) {
    return "0";
  }

  const intVal = Math.floor(n);
  if (intVal < 100) {
    return `${intVal}+`;
  }

  // Determine power of 10 milestone base
  const power = Math.floor(Math.log10(intVal));
  const step = Math.pow(10, power);
  const milestone = Math.floor(intVal / step) * step;

  if (milestone >= 1_000_000) {
    const m = milestone / 1_000_000;
    return `${m}M+`;
  }
  if (milestone >= 1_000) {
    const k = milestone / 1_000;
    return `${k}K+`;
  }
  return `${milestone}+`;
}
