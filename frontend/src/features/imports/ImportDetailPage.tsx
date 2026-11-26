import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { StatTile } from '@/components/ui/StatTile';
import type { MetricState } from '@/components/ui/StatTile';
import { EmptyState } from '@/components/ui/States';
import { DataTable } from '@/components/tables/DataTable';
import type { Column } from '@/components/tables/DataTable';
import { DetailList } from '@/features/shared/DetailList';
import { DetailPage } from '@/features/shared/DetailPage';
import { formatDateTime, formatInteger, formatText } from '@/lib/format';
import { endpoints } from '@/services/api/endpoints';
import type { DataImportDetail, ImportRowError } from '@/types/api';

const errorColumns: Column<ImportRowError>[] = [
  { id: 'row', header: 'Row', align: 'right', cell: (e) => formatInteger(e.row) },
  { id: 'field', header: 'Field', cell: (e) => <span className="font-mono text-xs">{formatText(e.field)}</span> },
  { id: 'message', header: 'Problem', cell: (e) => formatText(e.message) },
];

const count = (n: number | null): MetricState => (n === null ? { kind: 'unavailable' } : { kind: 'value', value: formatInteger(n) });

export function ImportDetailPage() {
  return (
    <DetailPage<DataImportDetail>
      endpoint={endpoints.imports.get}
      backTo="/imports"
      backLabel="All imports"
      title={(i, id) => i?.filename ?? `Import ${id}`}
    >
      {(i) => (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <StatTile label="Imported rows" state={count(i.importedRows)} />
            <StatTile label="Rejected rows" state={count(i.rejectedRows)} />
            <StatTile label="Duplicate rows" state={count(i.duplicateRows)} />
          </div>
          <Panel>
            <PanelHeader title="Provenance" badge={<><StatusBadge status={i.status} /><Badge tone="warning">Unverified</Badge></>} />
            <PanelBody>
              <DetailList
                items={[
                  { label: 'Dataset source (as stated)', value: i.datasetSource },
                  { label: 'Provenance notes (as stated)', value: i.provenance },
                  { label: 'Uploaded by', value: i.uploadedBy },
                  { label: 'Uploaded', value: formatDateTime(i.createdAt) },
                ]}
              />
              <p className="mt-4 text-xs text-ink-faint">Source and provenance are supplied by the uploader. Uploading a file does not make a dataset authentic.</p>
            </PanelBody>
          </Panel>
          <Panel>
            <PanelHeader title="Error report" description="Rows that were rejected during import" />
            {i.errors === null ? (
              <EmptyState title="Error report not provided" compact />
            ) : i.errors.length === 0 ? (
              <EmptyState title="No row errors reported" compact />
            ) : (
              <DataTable caption="Import errors" columns={errorColumns} rows={i.errors} rowKey={(e) => `${e.row ?? 'r'}-${e.field ?? 'f'}-${e.message ?? 'm'}`} />
            )}
          </Panel>
        </div>
      )}
    </DetailPage>
  );
}
