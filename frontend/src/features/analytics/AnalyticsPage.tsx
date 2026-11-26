import { useMemo, useState } from 'react';
import { Download } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { SeriesPanel } from '@/features/shared/SeriesPanel';
import { PromotionAnalysisPanel } from './PromotionAnalysisPanel';
import { formatCompact, formatPercent } from '@/lib/format';
import { endpoints, isEndpointLive } from '@/services/api/endpoints';
import { PERIODS, historicalPeriodRange, periodRange } from './periods';
import type { PeriodKey } from './periods';

export function AnalyticsPage() {
  const [period, setPeriod] = useState<PeriodKey>('7d');
  // Range is frozen per selection so query keys stay stable between renders.
  const historicalParams = useMemo(() => historicalPeriodRange(period), [period]);
  const simulationParams = useMemo(() => periodRange(period), [period]);
  const canExport = isEndpointLive(endpoints.analytics.export);
  const label = PERIODS.find((p) => p.key === period)?.label;

  return (
    <div>
      <PageHeader
        title="Analytics"
        description="Historical Rossmann sales and customer trends, alongside independently sourced retail simulation metrics."
        meta={<Badge tone="success">Historical + simulation</Badge>}
        actions={
          <>
            <Select aria-label="Reporting period" value={period} onChange={(e) => setPeriod(e.target.value as PeriodKey)} className="w-auto">
              {PERIODS.map((p) => (
                <option key={p.key} value={p.key}>
                  {p.label}
                </option>
              ))}
            </Select>
            <Button icon={<Download className="h-3.5 w-3.5" />} disabled={!canExport} title={canExport ? undefined : 'Awaiting API contract: export is not connected'}>
              Export
            </Button>
          </>
        }
      />
      <p className="mb-4 text-xs text-ink-faint">Selected period: {label}. Historical charts use the imported dataset dates; simulation charts use the current reporting window.</p>

      <div className="grid gap-4 lg:grid-cols-2">
        <PromotionAnalysisPanel params={historicalParams} />
        <SeriesPanel title="Sales trend" endpoint={endpoints.analytics.salesTrend} params={historicalParams} formatValue={formatCompact} />
        <SeriesPanel title="Recorded customers" endpoint={endpoints.analytics.orderVolume} params={historicalParams} color="brand" formatValue={formatCompact} />
        <SeriesPanel title="Purchase conversion" description="Successful purchases divided by completed attempts" endpoint={endpoints.analytics.conversion} params={simulationParams} color="success" formatValue={(v) => formatPercent(v)} />
        <SeriesPanel title="Failure rate" description="System failures divided by completed attempts" endpoint={endpoints.analytics.failureRates} params={simulationParams} color="danger" formatValue={(v) => formatPercent(v)} />
        <SeriesPanel title="Current inventory utilisation" description="Share of initial stock sold or currently reserved (current snapshot)" endpoint={endpoints.analytics.inventoryUtilisation} params={simulationParams} formatValue={(v) => formatPercent(v)} />
        <SeriesPanel title="Flash-sale units sold" description="Daily units sold through successful flash-sale purchases" endpoint={endpoints.analytics.flashSalePerformance} params={simulationParams} color="brand" formatValue={formatCompact} />
      </div>
    </div>
  );
}



