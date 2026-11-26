import { useState } from 'react';
import { StatusBadge } from '@/components/ui/Badge';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { Button } from '@/components/ui/Button';
import { ResourceTable } from '@/components/tables/ResourceTable';
import type { Column } from '@/components/tables/DataTable';
import { formatDateTime, formatText } from '@/lib/format';
import { endpoints } from '@/services/api/endpoints';
import type { AuditEntry } from '@/types/api';

const columns: Column<AuditEntry>[] = [
  { id: 'when', header: 'Timestamp', sortKey: 'occurredAt', cell: (a) => <span className="text-ink-muted">{formatDateTime(a.occurredAt)}</span> },
  { id: 'actor', header: 'Actor', cell: (a) => formatText(a.actor) },
  { id: 'action', header: 'Action', cell: (a) => <span className="font-mono text-xs">{formatText(a.action)}</span> },
  { id: 'entity', header: 'Entity', cell: (a) => formatText(a.entityType), hideOnMobile: true },
  { id: 'ref', header: 'Reference', cell: (a) => <span className="font-mono text-xs text-ink-muted">{formatText(a.entityRef)}</span>, hideOnMobile: true },
  { id: 'outcome', header: 'Outcome', cell: (a) => <StatusBadge status={a.outcome} /> },
];

export function AuditPage() {
  const [selected, setSelected] = useState<AuditEntry | null>(null);
  return (
    <div>
      <PageHeader title="Audit Logs" description="Who did what, to which record, and with what outcome." />
      <ResourceTable<AuditEntry>
        endpoint={endpoints.audit.list}
        caption="Audit log"
        searchPlaceholder="Search actor or reference"
        columns={columns}
        rowKey={(a) => a.id}
        onRowClick={setSelected}
        filters={[
          { key: 'action', label: 'Action', type: 'text' },
          { key: 'entityType', label: 'Entity type', type: 'text' },
          { key: 'outcome', label: 'Outcome', type: 'text' },
          { key: 'from', label: 'From date', type: 'date' },
          { key: 'to', label: 'To date', type: 'date' },
        ]}
        emptyTitle="No audit entries"
      />
      {selected && (
        <Panel className="mt-4">
          <PanelHeader
            title={`Entry ${selected.id}`}
            description="Metadata exactly as recorded"
            actions={
              <Button size="sm" variant="ghost" onClick={() => setSelected(null)}>
                Close
              </Button>
            }
          />
          <PanelBody>
            {selected.metadata && Object.keys(selected.metadata).length > 0 ? (
              <pre className="max-h-80 overflow-auto rounded bg-canvas p-3 font-mono text-xs text-ink-muted">{JSON.stringify(selected.metadata, null, 2)}</pre>
            ) : (
              <p className="text-xs text-ink-muted">No metadata recorded for this entry.</p>
            )}
          </PanelBody>
        </Panel>
      )}
    </div>
  );
}
