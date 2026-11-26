import { useNavigate, useParams } from 'react-router-dom';
import { OriginBadge, StatusBadge } from '@/components/ui/Badge';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { ResourceTable } from '@/components/tables/ResourceTable';
import type { Column } from '@/components/tables/DataTable';
import { DetailList } from '@/features/shared/DetailList';
import { DetailPage } from '@/features/shared/DetailPage';
import { formatDate, formatDateTime, formatInteger, formatText } from '@/lib/format';
import { formatMoney } from '@/lib/money';
import { endpoints } from '@/services/api/endpoints';
import type { Customer, Order } from '@/types/api';

const orderColumns: Column<Order>[] = [
  { id: 'ref', header: 'Order', cell: (o) => <span className="font-mono text-xs">{formatText(o.reference ?? o.id)}</span> },
  { id: 'placed', header: 'Placed', cell: (o) => <span className="text-ink-muted">{formatDateTime(o.placedAt)}</span> },
  { id: 'total', header: 'Total', align: 'right', cell: (o) => formatMoney(o.total, o.currency) },
  { id: 'status', header: 'Status', cell: (o) => <StatusBadge status={o.status} /> },
];

export function CustomerDetailPage() {
  const { id = '' } = useParams<{ id: string }>();
  const navigate = useNavigate();
  return (
    <DetailPage<Customer>
      endpoint={endpoints.customers.get}
      backTo="/customers"
      backLabel="All customers"
      title={(c, cid) => `Customer ${c?.reference ?? cid}`}
    >
      {(c) => (
        <div className="space-y-4">
          <Panel>
            <PanelHeader title="Account" badge={<StatusBadge status={c.status} />} actions={<OriginBadge origin={c.origin} />} />
            <PanelBody>
              <DetailList
                columns={4}
                items={[
                  { label: 'Customer reference', value: c.reference, mono: true },
                  { label: 'Customer since', value: formatDate(c.createdAt) },
                  { label: 'Orders', value: formatInteger(c.orderCount) },
                ]}
              />
              <p className="mt-4 text-xs text-ink-faint">Contact details and other personal data are not shown in this view.</p>
            </PanelBody>
          </Panel>
          <div>
            <h2 className="mb-2 text-sm font-semibold">Order history</h2>
            <ResourceTable<Order>
              endpoint={endpoints.customers.orders}
              pathParams={{ id }}
              caption="Customer orders"
              searchable={false}
              columns={orderColumns}
              rowKey={(o) => o.id}
              onRowClick={(o) => navigate(`/orders/${encodeURIComponent(o.id)}`)}
              emptyTitle="No orders for this customer"
            />
          </div>
        </div>
      )}
    </DetailPage>
  );
}
