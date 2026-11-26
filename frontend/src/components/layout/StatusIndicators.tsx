import { cn } from '@/lib/cn';
import { config } from '@/lib/config';
import { useApiConnectivity } from '@/hooks/useApiConnectivity';
import { formatDateTime } from '@/lib/format';

export function EnvironmentBadge() {
  const isProd = config.environment === 'production';
  return (
    <span
      className={cn(
        'inline-flex h-6 items-center gap-1.5 rounded-sm border px-2 text-2xs font-semibold uppercase',
        isProd ? 'border-danger/40 bg-danger/10 text-danger' : 'border-warning/40 bg-warning/10 text-warning',
      )}
      title={`Environment: ${config.environment}`}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full', isProd ? 'bg-danger' : 'bg-warning')} aria-hidden />
      {isProd ? 'Production' : 'Development'}
    </span>
  );
}

/** Reflects real request outcomes only. "Not checked" until the first request completes. */
export function ConnectivityIndicator() {
  const { status, lastChangedAt, lastError } = useApiConnectivity();
  const map = {
    unknown: { label: 'API not checked', dot: 'bg-ink-faint', text: 'text-ink-muted' },
    reachable: { label: 'API reachable', dot: 'bg-success', text: 'text-success' },
    unreachable: { label: 'API unreachable', dot: 'bg-danger', text: 'text-danger' },
  } as const;
  const s = map[status];
  const title =
    status === 'unknown'
      ? 'No API request has been made yet in this session.'
      : `Last change: ${formatDateTime(lastChangedAt ? new Date(lastChangedAt).toISOString() : null)}${lastError ? ` (${lastError})` : ''}`;
  return (
    <span role="status" title={title} className={cn('hidden h-6 items-center gap-1.5 rounded-sm border border-line px-2 text-2xs font-medium uppercase sm:inline-flex', s.text)}>
      <span className={cn('h-1.5 w-1.5 rounded-full', s.dot)} aria-hidden />
      {s.label}
    </span>
  );
}
