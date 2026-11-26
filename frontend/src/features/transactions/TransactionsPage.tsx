import { useNavigate } from 'react-router-dom';
import { OriginBadge, StatusBadge } from '@/components/ui/Badge';
import { PageHeader } from '@/components/ui/PageHeader';
import { ResourceTable, originFilter } from '@/components/tables/ResourceTable';
import type { Column } from '@/components/tables/DataTable';
import { formatDateTime, formatText } from '@/lib/format';
import { endpoints } from '@/services/api/endpoints';
import type { Transaction } from '@/types/api';

export const transactionColumns: Column<Transaction>[] = [
  { id: 'status', header: 'Status', cell: (t) => <StatusBadge status={t.status} /> },
  {
    id: 'attempt',
    header: 'Purchase attempt',
    cell: (t) => <span className="font-mono text-xs">{formatText(t.purchaseAttemptId || t.id)}</span>,
  },
  {
    id: 'time',
    header: 'Timestamp',
    sortKey: 'occurredAt',
    cell: (t) => <span className="text-ink-muted">{formatDateTime(t.occurredAt)}</span>,
  },
  {
    id: 'reason',
    header: 'Failure reason',
    cell: (t) => <span className="text-ink-muted">{formatText(t.failureReason)}</span>,
    hideOnMobile: true,
  },
  { id: 'origin', header: 'Source', cell: (t) => <OriginBadge origin={t.origin} /> },
];

export function TransactionsPage() {
  const navigate = useNavigate();

  return (
    <div>
      <PageHeader
        title="Transaction Monitor"
        description="Monitor purchase attempts, their outcomes, timestamps and recorded failure reasons."
      />
      <ResourceTable<Transaction>
        endpoint={endpoints.transactions.list}
        caption="Purchase attempts"
        searchPlaceholder="Search attempt ID or failure reason"
        columns={transactionColumns}
        rowKey={(t) => t.id}
        onRowClick={(t) => navigate(`/transactions/${encodeURIComponent(t.id)}`)}
        filters={[
          {
            key: 'status',
            label: 'Status',
            type: 'select',
            options: [
              { value: 'succeeded', label: 'Succeeded' },
              { value: 'failed', label: 'Failed' },
              { value: 'rejected', label: 'Rejected' },
              { value: 'pending', label: 'Pending' },
            ],
          },
          { key: 'from', label: 'From date', type: 'date' },
          { key: 'to', label: 'To date', type: 'date' },
          originFilter,
        ]}
        emptyTitle="No purchase attempts"
      />
    </div>
  );
}
