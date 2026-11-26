import { useState } from 'react';
import { OriginBadge, StatusBadge } from '@/components/ui/Badge';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelHeader } from '@/components/ui/Panel';
import { AwaitingContractState, EmptyState } from '@/components/ui/States';
import { isEndpointLive, endpoints } from '@/services/api/endpoints';
import { ResourceTable } from '@/components/tables/ResourceTable';
import type { Column } from '@/components/tables/DataTable';
import { formatDateTime, formatDurationMs, formatInteger, formatText } from '@/lib/format';
import type { SimulationRun } from '@/types/api';
import { RunDetail } from './RunMetrics';
import { SimulationBanner } from './SimulationBanner';
import { SimulationForm } from './SimulationForm';

const runColumns: Column<SimulationRun>[] = [
  { id: 'id', header: 'Run', cell: (r) => <span className="font-mono text-xs">{r.id}</span> },
  { id: 'status', header: 'Status', cell: (r) => <StatusBadge status={r.status} /> },
  { id: 'strategy', header: 'Strategy', cell: (r) => formatText(r.strategy) },
  { id: 'workers', header: 'Workers', align: 'right', cell: (r) => formatInteger(r.workers), hideOnMobile: true },
  { id: 'ok', header: 'OK', align: 'right', cell: (r) => formatInteger(r.successful) },
  { id: 'fail', header: 'Failed', align: 'right', cell: (r) => formatInteger(r.failed) },
  { id: 'oversold', header: 'Oversold', align: 'right', cell: (r) => (r.oversold === null ? '—' : <span className={r.oversold > 0 ? 'font-semibold text-danger' : ''}>{formatInteger(r.oversold)}</span>) },
  { id: 'p95', header: 'P95', align: 'right', cell: (r) => formatDurationMs(r.p95LatencyMs), hideOnMobile: true },
  { id: 'started', header: 'Started', cell: (r) => <span className="text-ink-muted">{formatDateTime(r.startedAt)}</span>, hideOnMobile: true },
  { id: 'origin', header: 'Source', cell: (r) => <OriginBadge origin={r.origin ?? 'simulation'} /> },
];

export function ConcurrencyPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  return (
    <div>
      <PageHeader title="Concurrency Lab" description="Stress-test purchase flows under simulated concurrent load and inspect correctness, latency and throughput." />
      <SimulationBanner />

      <SimulationForm onStarted={(run) => setSelectedId(run.id)} />

      <div className="mt-4">
        {selectedId ? (
          <RunDetail id={selectedId} />
        ) : (
          <Panel>
            <EmptyState title="No run selected" description="Start a simulation or choose a run from the history to see its metrics." compact />
          </Panel>
        )}
      </div>

      <h2 className="mb-2 mt-6 text-sm font-semibold">Run history</h2>
      <ResourceTable<SimulationRun>
        endpoint={endpoints.concurrency.runs}
        caption="Simulation run history"
        searchable={false}
        columns={runColumns}
        rowKey={(r) => r.id}
        onRowClick={(r) => setSelectedId(r.id)}
        emptyTitle="No simulation runs yet"
      />

      <div className="mt-4">
        <Panel>
          <PanelHeader title="Strategy comparison" description="Side-by-side comparison of concurrency strategies" />
          {isEndpointLive(endpoints.concurrency.strategies) ? (
            <EmptyState title="Comparison not provided" description="The backend has not exposed comparison results. Select individual runs above." compact />
          ) : (
            <AwaitingContractState capability="Strategy comparison" compact />
          )}
        </Panel>
      </div>
    </div>
  );
}
