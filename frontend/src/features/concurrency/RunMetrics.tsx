import { Badge, OriginBadge, StatusBadge } from '@/components/ui/Badge';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { StatTile } from '@/components/ui/StatTile';
import type { MetricState } from '@/components/ui/StatTile';
import { AwaitingContractState, ErrorState } from '@/components/ui/States';
import { LoadingRegion, Skeleton } from '@/components/ui/Skeleton';
import { useResource } from '@/hooks/useResource';
import { formatDateTime, formatDurationMs, formatInteger, formatRate } from '@/lib/format';
import { endpoints } from '@/services/api/endpoints';
import type { SimulationRun } from '@/types/api';

const val = (n: number | null, f: (n: number) => string): MetricState => (n === null ? { kind: 'unavailable' } : { kind: 'value', value: f(n) });

export function RunMetricsView({ run }: { run: SimulationRun }) {
  const oversoldState: MetricState =
    run.oversold === null
      ? { kind: 'unavailable' }
      : { kind: 'value', value: <span className={run.oversold > 0 ? 'text-danger' : 'text-success'}>{formatInteger(run.oversold)}</span>, hint: run.oversold > 0 ? 'Inventory integrity violated' : 'No overselling detected' };

  return (
    <Panel>
      <PanelHeader title={`Run ${run.id}`} description={`Started ${formatDateTime(run.startedAt)} · Finished ${formatDateTime(run.finishedAt)}`} badge={<StatusBadge status={run.status} />} actions={<OriginBadge origin={run.origin ?? 'simulation'} />} />
      <PanelBody className="space-y-4">
        <div className="flex flex-wrap gap-2 text-xs text-ink-muted">
          <Badge>Strategy: {run.strategy ?? '—'}</Badge>
          <Badge>Workers: {formatInteger(run.workers)}</Badge>
          <Badge>Requested: {formatInteger(run.requestedPurchases)}</Badge>
          <Badge>Target inventory: {formatInteger(run.targetInventory)}</Badge>
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatTile label="Successful" state={val(run.successful, formatInteger)} />
          <StatTile label="Failed" state={val(run.failed, formatInteger)} />
          <StatTile label="Oversold" state={oversoldState} />
          <StatTile label="Throughput" state={val(run.throughputPerSec, formatRate)} />
          <StatTile label="Avg latency" state={val(run.avgLatencyMs, formatDurationMs)} />
          <StatTile label="P95 latency" state={val(run.p95LatencyMs, formatDurationMs)} />
          <StatTile label="P99 latency" state={val(run.p99LatencyMs, formatDurationMs)} />
          <StatTile label="Inventory before → after" state={run.inventoryBefore === null && run.inventoryAfter === null ? { kind: 'unavailable' } : { kind: 'value', value: `${formatInteger(run.inventoryBefore)} → ${formatInteger(run.inventoryAfter)}` }} />
        </div>
      </PanelBody>
    </Panel>
  );
}

/** Loads one run by id. Only mounted when a run is selected, so no request is made otherwise. */
export function RunDetail({ id }: { id: string }) {
  const q = useResource<SimulationRun>(endpoints.concurrency.run, { id });
  if (!q.live) return <Panel><AwaitingContractState capability={endpoints.concurrency.run.label} /></Panel>;
  if (q.isPending)
    return (
      <LoadingRegion label="Loading run" className="space-y-3">
        <Skeleton className="h-40 w-full" />
      </LoadingRegion>
    );
  if (q.isError) return <Panel><ErrorState error={q.error} onRetry={() => void q.refetch()} /></Panel>;
  return <RunMetricsView run={q.data} />;
}
