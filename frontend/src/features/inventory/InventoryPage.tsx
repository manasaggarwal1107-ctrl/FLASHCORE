import { useState } from 'react';
import { SlidersHorizontal } from 'lucide-react';

import { Badge, OriginBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel } from '@/components/ui/Panel';
import { ResourceTable } from '@/components/tables/ResourceTable';
import type { Column } from '@/components/tables/DataTable';
import { formatDateTime, formatInteger, formatText, humanize } from '@/lib/format';
import { endpoints, isEndpointLive } from '@/services/api/endpoints';
import { useResourceList } from '@/hooks/useResourceList';
import type { InventoryMovement } from '@/types/api';

import { StockAdjustmentForm } from './StockAdjustmentForm';
import type { InventoryOption } from './StockAdjustmentForm';

const stockColumns: Column<InventoryOption>[] = [
  {
    id: 'product',
    header: 'Product',
    cell: (item) => (
      <span className="font-medium">{formatText(item.productName)}</span>
    ),
  },
  {
    id: 'sku',
    header: 'SKU',
    cell: (item) => (
      <span className="font-mono text-xs text-ink-muted">
        {formatText(item.sku)}
      </span>
    ),
    hideOnMobile: true,
  },
  {
    id: 'store',
    header: 'Store',
    cell: (item) => formatText(String(item.storeId)),
  },
  {
    id: 'onHand',
    header: 'On hand',
    align: 'right',
    sortKey: 'quantity',
    cell: (item) => formatInteger(item.quantity),
  },
  {
    id: 'reserved',
    header: 'Reserved',
    align: 'right',
    cell: (item) => formatInteger(item.reservedQuantity),
    hideOnMobile: true,
  },
  {
    id: 'available',
    header: 'Available',
    align: 'right',
    cell: (item) =>
      formatInteger(item.quantity - item.reservedQuantity),
  },
  {
    id: 'level',
    header: 'Level',
    cell: (item) => {
      const available = item.quantity - item.reservedQuantity;

      return available <= 0 ? (
        <Badge tone="warning">Unavailable</Badge>
      ) : (
        <Badge tone="success">Available</Badge>
      );
    },
  },
  {
    id: 'origin',
    header: 'Source',
    cell: () => <OriginBadge origin="simulation" />,
    hideOnMobile: true,
  },
];

const movementColumns: Column<InventoryMovement>[] = [
  {
    id: 'when',
    header: 'When',
    sortKey: 'occurredAt',
    cell: (movement) => (
      <span className="text-ink-muted">
        {formatDateTime(movement.occurredAt)}
      </span>
    ),
  },
  {
    id: 'product',
    header: 'Product',
    cell: (movement) =>
      formatText(movement.productName ?? movement.productId),
  },
  {
    id: 'type',
    header: 'Type',
    cell: (movement) => humanize(movement.type),
  },
  {
    id: 'delta',
    header: 'Change',
    align: 'right',
    cell: (movement) => {
      if (movement.quantityDelta === null) return '—';

      return (
        <span
          className={
            movement.quantityDelta > 0
              ? 'text-success'
              : movement.quantityDelta < 0
                ? 'text-danger'
                : ''
          }
        >
          {movement.quantityDelta > 0 ? '+' : ''}
          {formatInteger(movement.quantityDelta)}
        </span>
      );
    },
  },
  {
    id: 'balance',
    header: 'Balance after',
    align: 'right',
    cell: (movement) => formatInteger(movement.balanceAfter),
    hideOnMobile: true,
  },
  {
    id: 'reason',
    header: 'Reason',
    cell: (movement) => formatText(movement.reason),
    hideOnMobile: true,
  },
  {
    id: 'actor',
    header: 'Actor',
    cell: (movement) => formatText(movement.actor),
    hideOnMobile: true,
  },
  {
    id: 'origin',
    header: 'Source',
    cell: (movement) => <OriginBadge origin={movement.origin} />,
  },
];

type Tab = 'stock' | 'movements';

export function InventoryPage() {
  const [tab, setTab] = useState<Tab>('stock');
  const [adjusting, setAdjusting] = useState(false);

  const canAdjust = isEndpointLive(endpoints.inventory.adjust);

  const inventoryQuery = useResourceList<InventoryOption>(
    endpoints.inventory.list,
    { page: 1, pageSize: 25 },
  );

  const inventoryItems = inventoryQuery.data?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Inventory"
        description="Physical stock levels and movement history. Flash-sale allocations are tracked separately and are never counted as physical stock."
        actions={
          <Button
            icon={<SlidersHorizontal className="h-3.5 w-3.5" />}
            onClick={() => setAdjusting((current) => !current)}
            aria-expanded={adjusting}
            disabled={!canAdjust}
            title={
              canAdjust
                ? undefined
                : 'Stock adjustment is not connected'
            }
          >
            Adjust stock
          </Button>
        }
      />

      {adjusting && (
        <Panel className="mb-4">
          <StockAdjustmentForm
            inventoryItems={inventoryItems}
            onCancel={() => setAdjusting(false)}
          />
        </Panel>
      )}

      <div
        role="tablist"
        aria-label="Inventory views"
        className="mb-3 inline-flex rounded border border-line bg-surface p-0.5"
      >
        {(['stock', 'movements'] as const).map((value) => (
          <button
            key={value}
            role="tab"
            type="button"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={`h-7 rounded-sm px-3 text-xs font-medium transition-colors ${
              tab === value
                ? 'bg-surface-overlay text-ink'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            {value === 'stock' ? 'Stock levels' : 'Movement history'}
          </button>
        ))}
      </div>

      {tab === 'stock' ? (
        <ResourceTable<InventoryOption>
          endpoint={endpoints.inventory.list}
          caption="Inventory stock levels"
          searchable={false}
          columns={stockColumns}
          rowKey={(item) => item.id}
          emptyTitle="No inventory records"
          pageSize={25}
        />
      ) : (
        <ResourceTable<InventoryMovement>
          endpoint={endpoints.inventory.movements}
          caption="Inventory movements"
          searchPlaceholder="Search product or reason"
          columns={movementColumns}
          rowKey={(movement) => movement.id}
          emptyTitle="No inventory movements"
        />
      )}
    </div>
  );
}