import { ChartPanel } from '@/components/charts/ChartPanel';
import { OriginBadge } from '@/components/ui/Badge';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { useResource } from '@/hooks/useResource';
import { formatCompact, formatDate } from '@/lib/format';
import { endpoints } from '@/services/api/endpoints';
import type { PromotionAnalysis, PromotionAnalysisGroup } from '@/types/api';

function ComparisonGroup({
  title,
  group,
  tone,
}: {
  title: string;
  group: PromotionAnalysisGroup;
  tone: 'brand' | 'success';
}) {
  const hasObservations = group.openStoreDays > 0;
  const accent =
    tone === 'success'
      ? 'border-success/30 bg-success/5'
      : 'border-brand/30 bg-brand/5';

  return (
    <section
      className={`rounded-lg border p-4 ${accent}`}
      aria-label={title}
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        <span className="text-xs text-ink-muted">
          {hasObservations
            ? `${formatCompact(group.openStoreDays)} open store-days`
            : 'No observations'}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-ink-muted">
            Average sales / store-day
          </p>
          <p className="mt-1 text-xl font-semibold tabular-nums text-ink">
            {hasObservations
              ? formatCompact(group.averageSalesPerStoreDay)
              : 'â€”'}
          </p>
        </div>

        <div>
          <p className="text-xs text-ink-muted">
            Average customers / store-day
          </p>
          <p className="mt-1 text-xl font-semibold tabular-nums text-ink">
            {hasObservations
              ? formatCompact(group.averageCustomersPerStoreDay)
              : 'â€”'}
          </p>
        </div>

        <div>
          <p className="text-xs text-ink-muted">Total sales</p>
          <p className="mt-1 text-sm font-medium tabular-nums text-ink">
            {hasObservations ? formatCompact(group.totalSales) : 'â€”'}
          </p>
        </div>

        <div>
          <p className="text-xs text-ink-muted">Recorded customers</p>
          <p className="mt-1 text-sm font-medium tabular-nums text-ink">
            {hasObservations
              ? formatCompact(group.totalCustomers)
              : 'â€”'}
          </p>
        </div>
      </div>
    </section>
  );
}

export function PromotionAnalysisPanel({
  params,
}: {
  params?: Record<string, string>;
}) {
  const query = useResource<PromotionAnalysis>(
    endpoints.analytics.promotionAnalysis,
    {},
    params,
  );

  const data = query.data;
  const hasObservations = Boolean(
    data?.promoted &&
      data?.nonPromoted &&
      (data.promoted.openStoreDays > 0 ||
        data.nonPromoted.openStoreDays > 0),
  );

  return (
    <ChartPanel
      title="Promotion impact comparison"
      description="Descriptive comparison of promoted and non-promoted open store-days in the imported Rossmann data."
      endpoint={endpoints.analytics.promotionAnalysis}
      isLoading={query.isPending}
      error={query.error}
      isEmpty={!data || !hasObservations}
      badge={data ? <OriginBadge origin={data.origin} /> : undefined}
      renderError={(error) => (
        <ErrorState
          error={error}
          onRetry={() => void query.refetch()}
          compact
        />
      )}
      renderEmpty={() => (
        <EmptyState
          title="No observations for this period"
          description="No open store-day records were returned for the selected historical period."
          compact
        />
      )}
    >
      {data && hasObservations && (
        <div className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <ComparisonGroup
              title="Promotion active"
              group={data.promoted}
              tone="success"
            />
            <ComparisonGroup
              title="No promotion"
              group={data.nonPromoted}
              tone="brand"
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-ink-faint">
            <span>
              Data period: {formatDate(data.periodStart)} â€“ {formatDate(data.periodEnd)}
            </span>
            <span>Open store-days only Â· Imported historical data</span>
          </div>

          <p className="text-xs text-ink-muted">
            This is an observational comparison, not evidence that
            promotions caused a change in sales or customer counts.
          </p>
        </div>
      )}
    </ChartPanel>
  );
}
