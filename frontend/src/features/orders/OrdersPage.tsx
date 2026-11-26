import { Link, useNavigate } from 'react-router-dom';
import { Info } from 'lucide-react';
import { OriginBadge, StatusBadge } from '@/components/ui/Badge';
import { PageHeader } from '@/components/ui/PageHeader';
import { ResourceTable, originFilter } from '@/components/tables/ResourceTable';
import type { Column } from '@/components/tables/DataTable';
import { formatDateTime, formatInteger, formatText } from '@/lib/format';
import { formatMoney } from '@/lib/money';
import { endpoints } from '@/services/api/endpoints';
import type { Order } from '@/types/api';

const columns: Column<Order>[] = [
  { id: 'ref', header: 'Order', sortKey: 'reference', cell: (o) => <span className="font-mono text-xs font-medium">{formatText(o.reference ?? o.id)}</span> },
  { id: 'placed', header: 'Placed', sortKey: 'placedAt', cell: (o) => <span className="text-ink-muted">{formatDateTime(o.placedAt)}</span> },
  { id: 'customer', header: 'Customer ref', cell: (o) => <span className="font-mono text-xs text-ink-muted">{formatText(o.customerRef)}</span>, hideOnMobile: true },
  { id: 'items', header: 'Items', align: 'right', cell: (o) => formatInteger(o.itemCount), hideOnMobile: true },
  { id: 'total', header: 'Total', align: 'right', sortKey: 'total', cell: (o) => formatMoney(o.total, o.currency) },
  { id: 'status', header: 'Status', cell: (o) => <StatusBadge status={o.status} /> },
  { id: 'txn', header: 'Transaction', cell: (o) => <span className="font-mono text-xs text-ink-muted">{formatText(o.transactionRef)}</span>, hideOnMobile: true },
  { id: 'origin', header: 'Source', cell: (o) => <OriginBadge origin={o.origin} /> },
];

export function OrdersPage() {
  const navigate = useNavigate();
  return (
    <div>
      <PageHeader title="Orders" description="Processed orders with their transaction reference and data origin." />

      <div className="mb-4 flex items-start gap-3 rounded-lg border border-line bg-surface-raised p-4 text-xs text-ink-muted">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden />
        <div>
          <span className="font-semibold text-ink">Entity Architecture Notice: </span>
          First-class standalone <code className="font-mono text-ink">orders</code> tables do not exist in the relational database model. Individual customer purchase attempts and inventory transactions are recorded in the{' '}
          <Link to="/transactions" className="font-medium text-accent hover:underline">
            Transaction Monitor
          </Link>
          .
        </div>
      </div>

      <ResourceTable<Order>
        endpoint={endpoints.orders.list}
        caption="Orders"
        searchPlaceholder="Search order or customer reference"
        columns={columns}
        rowKey={(o) => o.id}
        onRowClick={(o) => navigate(`/orders/${encodeURIComponent(o.id)}`)}
        filters={[{ key: 'status', label: 'Status', type: 'text' }, { key: 'from', label: 'From date', type: 'date' }, { key: 'to', label: 'To date', type: 'date' }, originFilter]}
        emptyTitle="No orders"
      />
    </div>
  );
}
