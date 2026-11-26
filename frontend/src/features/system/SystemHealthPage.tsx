import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { StatusBadge } from '@/components/ui/Badge';
import { AwaitingContractState, EmptyState, ErrorState } from '@/components/ui/States';
import { DataTable } from '@/components/tables/DataTable';
import type { Column } from '@/components/tables/DataTable';
import { LoadingRegion, Skeleton } from '@/components/ui/Skeleton';
import { DetailList } from '@/features/shared/DetailList';
import { useApiConnectivity } from '@/hooks/useApiConnectivity';
import { useResource } from '@/hooks/useResource';
import { config } from '@/lib/config';
import { formatDateTime, formatText } from '@/lib/format';
import { endpoints } from '@/services/api/endpoints';
import type { ServiceStatus, SystemHealth } from '@/types/api';

const serviceColumns: Column<ServiceStatus>[] = [
  { id: 'name', header: 'Service', cell: (s) => <span className="font-medium">{s.name}</span> },
  { id: 'status', header: 'Status', cell: (s) => <StatusBadge status={s.status} /> },
  { id: 'detail', header: 'Detail', cell: (s) => <span className="text-ink-muted">{formatText(s.detail)}</span> },
];

const connectivityText = { unknown: 'Not checked yet', reachable: 'Responding', unreachable: 'Not responding' } as const;

export function SystemHealthPage() {
  const health = useResource<SystemHealth>(endpoints.system.health);
  const conn = useApiConnectivity();

  return (
    <div>
      <PageHeader title="System Health" description="Frontend configuration and backend status. Backend values are shown only when the API reports them." />

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="This frontend" description="Known locally, no API call needed" />
          <PanelBody>
            <DetailList
              columns={2}
              items={[
                { label: 'Frontend version', value: config.appVersion },
                { label: 'Environment', value: config.environment },
                { label: 'API base URL', value: config.apiBaseUrl, mono: true },
                { label: 'Request timeout', value: `${config.apiTimeoutMs / 1000}s` },
                { label: 'API connectivity (observed)', value: connectivityText[conn.status] },
                { label: 'Last observed change', value: conn.lastChangedAt ? formatDateTime(new Date(conn.lastChangedAt).toISOString()) : null },
              ]}
            />
            <p className="mt-4 text-xs text-ink-faint">Connectivity reflects real requests made by this session; it is not a health check.</p>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="Backend" badge={health.data ? <StatusBadge status={health.data.status} /> : undefined} />
          {!health.live ? (
            <AwaitingContractState capability={endpoints.system.health.label} />
          ) : health.isPending ? (
            <LoadingRegion label="Loading health" className="space-y-2 p-4">
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-4 w-1/3" />
            </LoadingRegion>
          ) : health.isError ? (
            <ErrorState error={health.error} onRetry={() => void health.refetch()} />
          ) : (
            <PanelBody>
              <DetailList
                columns={2}
                items={[
                  { label: 'Application version', value: health.data.version },
                  { label: 'Database', value: health.data.database },
                  { label: 'Checked at', value: formatDateTime(health.data.checkedAt) },
                ]}
              />
            </PanelBody>
          )}
        </Panel>
      </div>

      <div className="mt-4">
        <Panel>
          <PanelHeader title="Services" />
          {!health.live ? (
            <AwaitingContractState capability="Service status" compact />
          ) : health.data?.services && health.data.services.length > 0 ? (
            <DataTable caption="Service status" columns={serviceColumns} rows={health.data.services} rowKey={(s) => s.name} />
          ) : health.data ? (
            <EmptyState title="No service details reported" compact />
          ) : null}
        </Panel>
      </div>
    </div>
  );
}
