import { ChartPanel } from '@/components/charts/ChartPanel';
import { OriginBadge } from '@/components/ui/Badge';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { useResource } from '@/hooks/useResource';
import { formatDateTime, formatText } from '@/lib/format';
import { endpoints } from '@/services/api/endpoints';
import type { ActivityEvent, Collection } from '@/types/api';

export function ActivityPanel() {
  const q = useResource<Collection<ActivityEvent>>(endpoints.overview.activity);
  const items = q.data?.items ?? [];
  return (
    <ChartPanel
      title="Recent activity"
      description="Transaction activity timeline"
      endpoint={endpoints.overview.activity}
      isLoading={q.isPending}
      error={q.error}
      isEmpty={items.length === 0}
      renderError={(e) => <ErrorState error={e} onRetry={() => void q.refetch()} compact />}
      renderEmpty={() => <EmptyState title="No recent activity" compact />}
    >
      <ol className="divide-y divide-line">
        {items.map((e) => (
          <li key={e.id} className="flex items-center gap-3 py-2 text-xs">
            <time dateTime={e.occurredAt ?? undefined} className="num w-44 shrink-0 text-ink-faint">
              {formatDateTime(e.occurredAt)}
            </time>
            <span className="w-28 shrink-0 truncate font-medium text-ink-muted">{formatText(e.kind)}</span>
            <span className="min-w-0 flex-1 truncate text-ink">{formatText(e.summary)}</span>
            <OriginBadge origin={e.origin} />
          </li>
        ))}
      </ol>
    </ChartPanel>
  );
}
