import type { ReactNode } from 'react';
import { Skeleton } from './Skeleton';
import { cn } from '@/lib/cn';

export type MetricState =
  | { kind: 'value'; value: ReactNode; hint?: ReactNode }
  | { kind: 'loading' }
  | { kind: 'error'; message?: string }
  | { kind: 'unavailable'; reason?: string };

/**
 * KPI tile. It can only display a value that is passed in — there is no default or placeholder
 * number. Missing data renders an explicit state.
 */
export function StatTile({ label, state, icon, className }: { label: string; state: MetricState; icon?: ReactNode; className?: string }) {
  return (
    <div className={cn('panel flex min-w-0 flex-col gap-2 p-4', className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="eyebrow truncate">{label}</span>
        {icon && <span className="text-ink-faint">{icon}</span>}
      </div>
      {state.kind === 'loading' && (
        <div role="status" aria-label={`Loading ${label}`}>
          <Skeleton className="h-7 w-24" />
        </div>
      )}
      {state.kind === 'value' && (
        <div>
          <div className="num text-2xl font-semibold leading-none text-ink">{state.value}</div>
          {state.hint && <div className="mt-1.5 text-xs text-ink-muted">{state.hint}</div>}
        </div>
      )}
      {state.kind === 'error' && <div className="text-xs text-danger">{state.message ?? 'Failed to load'}</div>}
      {state.kind === 'unavailable' && (
        <div>
          <div className="num text-2xl font-semibold leading-none text-ink-faint" aria-label="Not available">
            —
          </div>
          <div className="mt-1.5 text-xs text-ink-faint">{state.reason ?? 'Not provided by the API'}</div>
        </div>
      )}
    </div>
  );
}
