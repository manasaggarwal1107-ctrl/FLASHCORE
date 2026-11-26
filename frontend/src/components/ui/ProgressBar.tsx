import { cn } from '@/lib/cn';
import { formatPercent } from '@/lib/format';

/** Ratio in [0,1]; null renders an explicit "not available" bar rather than 0%. */
export function ProgressBar({ ratio, label, tone = 'accent' }: { ratio: number | null; label: string; tone?: 'accent' | 'warning' | 'danger' }) {
  if (ratio === null) {
    return (
      <div className="flex items-center gap-2" aria-label={`${label}: not available`}>
        <div className="h-1.5 flex-1 rounded-sm bg-surface-overlay" />
        <span className="num w-12 text-right text-xs text-ink-faint">—</span>
      </div>
    );
  }
  const clamped = Math.min(1, Math.max(0, ratio));
  return (
    <div className="flex items-center gap-2">
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(clamped * 100)}
        className="h-1.5 flex-1 overflow-hidden rounded-sm bg-surface-overlay"
      >
        <div className={cn('h-full', tone === 'accent' && 'bg-accent', tone === 'warning' && 'bg-warning', tone === 'danger' && 'bg-danger')} style={{ width: `${clamped * 100}%` }} />
      </div>
      <span className="num w-12 text-right text-xs text-ink-muted">{formatPercent(ratio, 0)}</span>
    </div>
  );
}
