import { ChartPanel } from '@/components/charts/ChartPanel';
import { OriginBadge } from '@/components/ui/Badge';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { useResource } from '@/hooks/useResource';
import { formatInteger, safeRatio } from '@/lib/format';
import { endpoints } from '@/services/api/endpoints';
import type { InventoryAllocation } from '@/types/api';

function Row({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-ink-muted">{label}</span>
      <span className="num text-ink">{formatInteger(value)}</span>
    </div>
  );
}

/**
 * Physical stock and flash-sale allocation are two separate ledgers and are rendered in
 * separate groups on purpose — allocation is never presented as physical inventory.
 */
export function InventoryAllocationPanel() {
  const q = useResource<InventoryAllocation>(endpoints.overview.inventoryAllocation);
  const d = q.data;
  return (
    <ChartPanel
      title="Inventory allocation"
      description="Physical stock vs flash-sale allocation (separate ledgers)"
      endpoint={endpoints.overview.inventoryAllocation}
      isLoading={q.isPending}
      error={q.error}
      isEmpty={!d}
      badge={d ? <OriginBadge origin={d.origin} /> : undefined}
      renderError={(e) => <ErrorState error={e} onRetry={() => void q.refetch()} compact />}
      renderEmpty={() => <EmptyState title="No inventory data" compact />}
    >
      {d && (
        <div className="grid gap-5 sm:grid-cols-2">
          <div className="space-y-2">
            <h3 className="eyebrow">Physical inventory</h3>
            <Row label="On hand" value={d.physical.onHand} />
            <Row label="Reserved" value={d.physical.reserved} />
            <Row label="Sold" value={d.physical.sold} />
            <Row label="Available" value={d.physical.available} />
            <ProgressBar label="Physical stock sold" ratio={safeRatio(d.physical.sold, d.physical.onHand)} />
          </div>
          <div className="space-y-2">
            <h3 className="eyebrow">Flash-sale allocation</h3>
            <Row label="Allocated" value={d.flashSale.allocated} />
            <Row label="Sold" value={d.flashSale.sold} />
            <Row label="Remaining" value={d.flashSale.remaining} />
            <ProgressBar label="Allocation utilised" ratio={safeRatio(d.flashSale.sold, d.flashSale.allocated)} />
          </div>
        </div>
      )}
    </ChartPanel>
  );
}
