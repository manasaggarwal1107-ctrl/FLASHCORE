import { cn } from '@/lib/cn';
import { formatInteger, formatPercent, safeRatio } from '@/lib/format';

export interface Segment {
  label: string;
  value: number;
  tone: 'success' | 'danger' | 'warning' | 'brand' | 'accent' | 'simulation';
}

const toneBg: Record<Segment['tone'], string> = {
  success: 'bg-success',
  danger: 'bg-danger',
  warning: 'bg-warning',
  brand: 'bg-brand',
  accent: 'bg-accent',
  simulation: 'bg-simulation',
};

/** Proportional stacked bar with a legend that also carries the numbers (not colour alone). */
export function BreakdownBar({ segments }: { segments: Segment[] }) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  return (
    <div>
      <div className="flex h-2 w-full overflow-hidden rounded-sm bg-surface-overlay" role="img" aria-label={segments.map((s) => `${s.label} ${s.value}`).join(', ')}>
        {segments.map((s) => {
          const share = safeRatio(s.value, total) ?? 0;
          return share > 0 ? <div key={s.label} className={cn(toneBg[s.tone])} style={{ width: `${share * 100}%` }} /> : null;
        })}
      </div>
      <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
        {segments.map((s) => (
          <li key={s.label} className="flex items-center gap-2 text-xs">
            <span className={cn('h-2 w-2 rounded-sm', toneBg[s.tone])} aria-hidden />
            <span className="text-ink-muted">{s.label}</span>
            <span className="num ml-auto text-ink">{formatInteger(s.value)}</span>
            <span className="num w-12 text-right text-ink-faint">{formatPercent(safeRatio(s.value, total))}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
