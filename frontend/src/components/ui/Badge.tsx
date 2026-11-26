import type { ReactNode } from 'react';
import { FlaskConical } from 'lucide-react';
import { cn } from '@/lib/cn';
import { humanize } from '@/lib/format';
import type { DataOrigin } from '@/types/api';

export type Tone = 'neutral' | 'accent' | 'brand' | 'success' | 'warning' | 'danger' | 'simulation';

const tones: Record<Tone, string> = {
  neutral: 'border-line-strong bg-surface-raised text-ink-muted',
  accent: 'border-accent/30 bg-accent/10 text-accent',
  brand: 'border-brand/30 bg-brand/10 text-brand',
  success: 'border-success/30 bg-success/10 text-success',
  warning: 'border-warning/30 bg-warning/10 text-warning',
  danger: 'border-danger/30 bg-danger/10 text-danger',
  simulation: 'border-simulation/40 bg-simulation/10 text-simulation',
};

export function Badge({
  tone = 'neutral',
  children,
  className,
  'aria-label': ariaLabel,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
  'aria-label'?: string;
}) {
  return (
    <span
      aria-label={ariaLabel}
      className={cn(
        'inline-flex h-5 items-center gap-1 whitespace-nowrap rounded-sm border px-1.5 text-2xs font-medium uppercase',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const STATUS_TONES: Record<string, Tone> = {
  active: 'success',
  succeeded: 'success',
  completed: 'success',
  success: 'success',
  ok: 'success',
  healthy: 'success',
  up: 'success',
  scheduled: 'brand',
  queued: 'brand',
  pending: 'warning',
  running: 'accent',
  draft: 'neutral',
  archived: 'neutral',
  cancelled: 'neutral',
  failed: 'danger',
  rejected: 'danger',
  error: 'danger',
  down: 'danger',
  degraded: 'warning',
};

/** Maps a free-form backend status string to a tone; unknown values render neutral, never guessed. */
export function StatusBadge({ status }: { status: string | null | undefined }) {
  if (!status) return <span className="text-ink-faint">—</span>;
  return <Badge tone={STATUS_TONES[status.toLowerCase()] ?? 'neutral'}>{humanize(status)}</Badge>;
}

const ORIGIN_TONE: Record<DataOrigin, Tone> = {
  real: 'success',
  imported: 'brand',
  manual: 'warning',
  simulation: 'simulation',
};

const ORIGIN_LABEL: Record<DataOrigin, string> = {
  real: 'Real',
  imported: 'Imported',
  manual: 'Manual',
  simulation: 'Simulation',
};

/** Visible provenance marker. Records with no origin field are shown as "Origin unknown". */
export function OriginBadge({ origin }: { origin: DataOrigin | null | undefined }) {
  if (!origin) return <Badge tone="neutral">Origin unknown</Badge>;
  return (
    <Badge tone={ORIGIN_TONE[origin]} aria-label={`Data origin: ${ORIGIN_LABEL[origin]}`}>
      {origin === 'simulation' && <FlaskConical className="h-3 w-3" aria-hidden />}
      {ORIGIN_LABEL[origin]}
    </Badge>
  );
}
