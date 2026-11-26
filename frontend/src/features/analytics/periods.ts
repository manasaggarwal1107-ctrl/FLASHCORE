export type PeriodKey = '24h' | '7d' | '30d' | '90d';

export const PERIODS: { key: PeriodKey; label: string; ms: number }[] = [
  { key: '24h', label: '24 hours', ms: 24 * 3600_000 },
  { key: '7d', label: '7 days', ms: 7 * 24 * 3600_000 },
  { key: '30d', label: '30 days', ms: 30 * 24 * 3600_000 },
  { key: '90d', label: '90 days', ms: 90 * 24 * 3600_000 },
];

/**
 * Current-time reporting window.
 * Used by simulation analytics.
 */
export function periodRange(
  key: PeriodKey,
  now: Date = new Date(),
): { from: string; to: string } {
  const preset = PERIODS.find((p) => p.key === key) ?? PERIODS[1]!;

  return {
    from: new Date(now.getTime() - preset.ms).toISOString(),
    to: now.toISOString(),
  };
}

/**
 * Historical Rossmann reporting window.
 * The imported dataset ends on 31 July 2015.
 */
export function historicalPeriodRange(
  key: PeriodKey,
): { from: string; to: string } {
  const days = {
    '24h': 1,
    '7d': 7,
    '30d': 30,
    '90d': 90,
  }[key];

  const end = Date.UTC(2015, 6, 31);
  const start = end - (days - 1) * 24 * 60 * 60 * 1000;

  return {
    from: new Date(start).toISOString(),
    to: new Date(end + 24 * 60 * 60 * 1000 - 1).toISOString(),
  };
}
