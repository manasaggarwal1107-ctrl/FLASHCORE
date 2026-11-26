import { MISSING } from './money';

export { MISSING };

type Maybe<T> = T | null | undefined;

export function formatInteger(value: Maybe<number>): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return MISSING;
  return new Intl.NumberFormat().format(value);
}

export function formatCompact(value: Maybe<number>): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return MISSING;
  return new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}

/** Ratio in [0,1] → "12.3%". Returns an em dash for missing values. */
export function formatPercent(ratio: Maybe<number>, digits = 1): string {
  if (ratio === null || ratio === undefined || !Number.isFinite(ratio)) return MISSING;
  return `${(ratio * 100).toFixed(digits)}%`;
}

/** Division that returns null (not NaN/Infinity) when it is undefined. */
export function safeRatio(numerator: Maybe<number>, denominator: Maybe<number>): number | null {
  if (numerator === null || numerator === undefined) return null;
  if (denominator === null || denominator === undefined || denominator === 0) return null;
  const r = numerator / denominator;
  return Number.isFinite(r) ? r : null;
}

export function formatDateTime(iso: Maybe<string>): string {
  if (!iso) return MISSING;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return MISSING;
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'medium' }).format(d);
}

export function formatDate(iso: Maybe<string>): string {
  if (!iso) return MISSING;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return MISSING;
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(d);
}

export function formatDurationMs(ms: Maybe<number>): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms)) return MISSING;
  if (ms < 1) return '<1 ms';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function formatRate(perSecond: Maybe<number>): string {
  if (perSecond === null || perSecond === undefined || !Number.isFinite(perSecond)) return MISSING;
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(perSecond)}/s`;
}

export function formatText(value: Maybe<string>): string {
  return value && value.trim() ? value : MISSING;
}

/** "ORDER_PLACED" / "order-placed" → "Order placed". */
export function humanize(value: Maybe<string>): string {
  if (!value) return MISSING;
  const s = value.replace(/[_-]+/g, ' ').trim().toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}
