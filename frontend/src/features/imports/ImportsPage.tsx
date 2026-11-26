import { useNavigate } from 'react-router-dom';
import { StatusBadge } from '@/components/ui/Badge';
import { PageHeader } from '@/components/ui/PageHeader';
import { ResourceTable } from '@/components/tables/ResourceTable';
import type { Column } from '@/components/tables/DataTable';
import { formatDateTime, formatInteger, formatText } from '@/lib/format';
import { endpoints } from '@/services/api/endpoints';
import type { DataImport } from '@/types/api';
import { UploadPanel } from './UploadPanel';

const columns: Column<DataImport>[] = [
  { id: 'file', header: 'File', cell: (i) => <span className="font-medium">{formatText(i.filename)}</span> },
  { id: 'status', header: 'Status', cell: (i) => <StatusBadge status={i.status} /> },
  { id: 'source', header: 'Dataset source', cell: (i) => formatText(i.datasetSource), hideOnMobile: true },
  { id: 'imported', header: 'Imported', align: 'right', cell: (i) => formatInteger(i.importedRows) },
  { id: 'rejected', header: 'Rejected', align: 'right', cell: (i) => formatInteger(i.rejectedRows) },
  { id: 'dupes', header: 'Duplicates', align: 'right', cell: (i) => formatInteger(i.duplicateRows), hideOnMobile: true },
  { id: 'by', header: 'Uploaded by', cell: (i) => formatText(i.uploadedBy), hideOnMobile: true },
  { id: 'when', header: 'Uploaded', sortKey: 'createdAt', cell: (i) => <span className="text-ink-muted">{formatDateTime(i.createdAt)}</span> },
];

export function ImportsPage() {
  const navigate = useNavigate();
  return (
    <div>
      <PageHeader title="Data Imports" description="Upload CSV datasets and review import outcomes, rejected rows and provenance." />
      <UploadPanel />
      <h2 className="mb-2 mt-6 text-sm font-semibold">Import history</h2>
      <ResourceTable<DataImport>
        endpoint={endpoints.imports.list}
        caption="Import history"
        searchPlaceholder="Search file or source"
        columns={columns}
        rowKey={(i) => i.id}
        onRowClick={(i) => navigate(`/imports/${encodeURIComponent(i.id)}`)}
        emptyTitle="No imports yet"
        emptyDescription="Uploaded datasets and their results will be listed here."
      />
    </div>
  );
}
