import { ChartPanel } from '@/components/charts/ChartPanel';
import { TimeSeriesChart } from '@/components/charts/TimeSeriesChart';
import { OriginBadge } from '@/components/ui/Badge';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { useResource } from '@/hooks/useResource';
import { formatDateTime } from '@/lib/format';
import type { EndpointSpec } from '@/services/api/endpoints';
import type { TimeSeries } from '@/types/api';

/**
 * One time-series chart bound to one endpoint. Displays the reporting period and data origin
 * exactly as returned by the API.
 */
export function SeriesPanel({
  title,
  description,
  endpoint,
  color,
  formatValue,
  params,
}: {
  title: string;
  description?: string;
  endpoint: EndpointSpec;
  color?: 'accent' | 'brand' | 'success' | 'danger';
  formatValue?: (v: number) => string;
  /** Extra query-string params (reporting period) â€” requires the endpoint to accept them. */
  params?: Record<string, string>;
}) {
  const q = useResource<TimeSeries>(endpoint, {}, params);
  const data = q.data;
  return (
    <ChartPanel
      title={title}
      description={description}
      endpoint={endpoint}
      isLoading={q.isPending}
      error={q.error}
      isEmpty={!data || !Array.isArray(data.points) || data.points.length === 0}
      badge={data ? <OriginBadge origin={data.origin} /> : undefined}
      renderError={(e) => <ErrorState error={e} onRetry={() => void q.refetch()} compact />}
      renderEmpty={() => <EmptyState title="No data for this period" compact />}
    >
      {data && Array.isArray(data.points) && (
        <>
          <TimeSeriesChart data={data.points} seriesLabel={title} color={color} formatValue={formatValue} />
          <p className="mt-2 text-xs text-ink-faint">
            Reporting period: {formatDateTime(data.periodStart)} â†’ {formatDateTime(data.periodEnd)}
          </p>
        </>
      )}
    </ChartPanel>
  );
}

