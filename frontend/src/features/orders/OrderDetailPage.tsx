import { OriginBadge, StatusBadge } from '@/components/ui/Badge';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { EmptyState } from '@/components/ui/States';
import { DataTable } from '@/components/tables/DataTable';
import type { Column } from '@/components/tables/DataTable';
import { DetailList } from '@/features/shared/DetailList';
import { DetailPage } from '@/features/shared/DetailPage';
import { formatDateTime, formatInteger, formatText } from '@/lib/format';
import { formatMoney } from '@/lib/money';
import { endpoints } from '@/services/api/endpoints';
import type { Order, OrderLine } from '@/types/api';

const lineColumns = (currency: string | null): Column<OrderLine>[] => [
  { id: 'product', header: 'Product', cell: (l) => formatText(l.productName ?? l.productId) },
  { id: 'qty', header: 'Qty', align: 'right', cell: (l) => formatInteger(l.quantity) },
  { id: 'unit', header: 'Unit price', align: 'right', cell: (l) => formatMoney(l.unitPrice, currency) },
  { id: 'total', header: 'Line total', align: 'right', cell: (l) => formatMoney(l.lineTotal, currency) },
];

export function OrderDetailPage() {
  return (
    <DetailPage<Order>
      endpoint={endpoints.orders.get}
      backTo="/orders"
      backLabel="All orders"
      title={(o, id) => `Order ${o?.reference ?? id}`}
    >
      {(o) => (
        <div className="space-y-4">
          <Panel>
            <PanelHeader title="Summary" badge={<StatusBadge status={o.status} />} actions={<OriginBadge origin={o.origin} />} />
            <PanelBody>
              <DetailList
                columns={4}
                items={[
                  { label: 'Order reference', value: o.reference, mono: true },
                  { label: 'Placed', value: formatDateTime(o.placedAt) },
                  { label: 'Customer reference', value: o.customerRef, mono: true },
                  { label: 'Transaction reference', value: o.transactionRef, mono: true },
                  { label: 'Total', value: formatMoney(o.total, o.currency) },
                ]}
              />
            </PanelBody>
          </Panel>
          <Panel>
            <PanelHeader title="Line items" />
            {o.lines && o.lines.length > 0 ? (
              <DataTable caption="Order line items" columns={lineColumns(o.currency)} rows={o.lines} rowKey={(l) => `${l.productId ?? l.productName ?? 'line'}-${l.quantity ?? ''}-${l.unitPrice ?? ''}`} />
            ) : (
              <EmptyState title={o.lines === null ? 'Line items not provided' : 'No line items'} compact />
            )}
          </Panel>
        </div>
      )}
    </DetailPage>
  );
}
