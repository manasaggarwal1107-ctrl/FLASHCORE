import { BreakdownBar } from '@/components/charts/BreakdownBar';
import type { Segment } from '@/components/charts/BreakdownBar';
import { ChartPanel } from '@/components/charts/ChartPanel';
import { OriginBadge } from '@/components/ui/Badge';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { useResource } from '@/hooks/useResource';
import { endpoints } from '@/services/api/endpoints';
import type { PurchaseOutcomes } from '@/types/api';

/** Only segments the API returned (non-null) are drawn. */
export function outcomeSegments(o: PurchaseOutcomes): Segment[] {
  const candidates: Array<[string, number | null, Segment['tone']]> = [
    ['Successful', o.successful, 'success'],
    ['Failed', o.failed, 'danger'],
    ['Rejected', o.rejected, 'warning'],
    ['Pending', o.pending, 'brand'],
  ];
  return candidates.flatMap(([label, value, tone]) => (value === null ? [] : [{ label, value, tone }]));
}

export function PurchaseOutcomesPanel() {
  const q = useResource<PurchaseOutcomes>(endpoints.overview.purchaseOutcomes);
  const segments = q.data ? outcomeSegments(q.data) : [];
  const total = segments.reduce((a, s) => a + s.value, 0);
  return (
    <ChartPanel
      title="Purchase outcomes"
      description="Success / failure distribution"
      endpoint={endpoints.overview.purchaseOutcomes}
      isLoading={q.isPending}
      error={q.error}
      isEmpty={segments.length === 0 || total === 0}
      badge={q.data ? <OriginBadge origin={q.data.origin} /> : undefined}
      renderError={(e) => <ErrorState error={e} onRetry={() => void q.refetch()} compact />}
      renderEmpty={() => <EmptyState title="No purchase attempts recorded" compact />}
    >
      <BreakdownBar segments={segments} />
    </ChartPanel>
  );
}
