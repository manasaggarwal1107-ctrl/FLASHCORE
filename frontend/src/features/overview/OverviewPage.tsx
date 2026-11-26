import { useMemo } from 'react';
import {
  Database,
  TrendingUp,
  Users,
  Store,
  BarChart3,
} from 'lucide-react';

import { PageHeader } from '@/components/ui/PageHeader';
import { StatTile } from '@/components/ui/StatTile';
import type { MetricState } from '@/components/ui/StatTile';
import { SeriesPanel } from '@/features/shared/SeriesPanel';
import { PromotionAnalysisPanel } from '@/features/analytics/PromotionAnalysisPanel';
import { historicalPeriodRange } from '@/features/analytics/periods';
import { useResource } from '@/hooks/useResource';
import { formatCompact, formatInteger } from '@/lib/format';
import { endpoints, isEndpointLive } from '@/services/api/endpoints';
import { describeError } from '@/services/api/errors';
import type { RossmannSalesSummary } from '@/types/api';

export function metricState<T extends object, K extends keyof T>(
  query: {
    live: boolean;
    isPending: boolean;
    isError: boolean;
    error: unknown;
    data: T | undefined;
  },
  key: K,
  format: (value: number) => string,
): MetricState {
  if (!query.live) {
    return { kind: 'unavailable', reason: 'Awaiting API contract' };
  }

  if (query.isPending) return { kind: 'loading' };

  if (query.isError) {
    return { kind: 'error', message: describeError(query.error).title };
  }

  const value = query.data?.[key];

  if (value === null || value === undefined) {
    return { kind: 'unavailable' };
  }

  // PostgreSQL Decimal values may be serialized as numeric strings.
  const numericValue = typeof value === 'number'
    ? value
    : typeof value === 'string' && value.trim() !== ''
      ? Number(value)
      : Number.NaN;

  if (!Number.isFinite(numericValue)) {
    return { kind: 'unavailable', reason: 'Invalid numeric value' };
  }

  return { kind: 'value', value: format(numericValue) };
}

export function OverviewPage() {
  const summary = useResource<RossmannSalesSummary>(
    endpoints.overview.summary,
  );

  const data = summary.data;
  const live = isEndpointLive(endpoints.overview.summary);
  const historicalParams = useMemo(() => historicalPeriodRange('7d'), []);

  const queryState = {
    live,
    isPending: summary.isPending,
    isError: summary.isError,
    error: summary.error,
    data,
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Rossmann Retail Intelligence"
        description="Historical retail performance, customer activity and promotion analysis from the imported Rossmann dataset."
      />

      <section aria-label="Rossmann historical dataset metrics">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-ink">Historical overview</h2>
            <p className="mt-0.5 text-xs text-ink-muted">
              Full imported dataset · Recorded store-day observations
            </p>
          </div>
          <span className="rounded-full border border-line bg-surface-raised px-2.5 py-1 text-2xs font-medium text-ink-muted">
            Imported data
          </span>
        </div>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
          <StatTile
            label="Historical Records"
            icon={<Database className="h-4 w-4" />}
            state={metricState(queryState, 'totalRecords', formatCompact)}
          />

          <StatTile
            label="Total Sales"
            icon={<TrendingUp className="h-4 w-4" />}
            state={metricState(queryState, 'totalSales', formatCompact)}
          />

          <StatTile
            label="Average Daily Sales"
            icon={<BarChart3 className="h-4 w-4" />}
            state={metricState(queryState, 'averageSales', formatInteger)}
          />

          <StatTile
            label="Highest Daily Sales"
            icon={<Store className="h-4 w-4" />}
            state={metricState(queryState, 'highestSales', formatCompact)}
          />

          <StatTile
            label="Recorded Customers"
            icon={<Users className="h-4 w-4" />}
            state={metricState(queryState, 'totalCustomers', formatCompact)}
          />
        </div>
      </section>

      <section aria-label="Historical sales and customer trends">
        <div className="mb-3">
          <h2 className="text-sm font-semibold text-ink">Recent historical activity</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            Latest seven calendar days in the imported dataset, ending 31 July 2015
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <SeriesPanel
            title="Daily sales trend"
            description="Combined sales across recorded stores for each date"
            endpoint={endpoints.analytics.salesTrend}
            params={historicalParams}
            formatValue={formatCompact}
          />

          <SeriesPanel
            title="Recorded customer trend"
            description="Sum of daily customer counts across recorded stores"
            endpoint={endpoints.analytics.orderVolume}
            params={historicalParams}
            color="brand"
            formatValue={formatCompact}
          />
        </div>
      </section>

      <section aria-label="Promotion analysis">
        <PromotionAnalysisPanel params={historicalParams} />
      </section>

      <p className="border-t border-line pt-4 text-xs leading-relaxed text-ink-faint">
        Source: Imported Rossmann historical training dataset. Sales values are
        displayed without assuming a currency. Recorded customers represent the
        sum of daily customer counts, not distinct individuals. Historical
        charts show returned observations only; missing store-day records are
        not imputed as zero.
      </p>
    </div>
  );
}
