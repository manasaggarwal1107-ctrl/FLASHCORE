import { Link } from 'react-router-dom';
import { ChartPanel } from '@/components/charts/ChartPanel';
import { StatusBadge } from '@/components/ui/Badge';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { useResource } from '@/hooks/useResource';
import { formatInteger, safeRatio } from '@/lib/format';
import { endpoints } from '@/services/api/endpoints';
import type { Collection, FlashSale } from '@/types/api';

export function FlashSalePerformancePanel() {
  const q = useResource<Collection<FlashSale>>(endpoints.overview.flashSalePerformance);
  const items = q.data?.items ?? [];
  return (
    <ChartPanel
      title="Flash sale performance"
      description="Allocation utilisation per sale"
      endpoint={endpoints.overview.flashSalePerformance}
      isLoading={q.isPending}
      error={q.error}
      isEmpty={items.length === 0}
      renderError={(e) => <ErrorState error={e} onRetry={() => void q.refetch()} compact />}
      renderEmpty={() => <EmptyState title="No flash sales to report" compact />}
    >
      <ul className="space-y-3">
        {items.map((sale) => (
          <li key={sale.id}>
            <div className="mb-1 flex items-center justify-between gap-2 text-xs">
              <Link to={`/flash-sales/${encodeURIComponent(sale.id)}`} className="truncate font-medium text-ink hover:text-accent">
                {sale.name}
              </Link>
              <div className="flex items-center gap-2">
                <span className="num text-ink-faint">
                  {formatInteger(sale.sold)} / {formatInteger(sale.allocated)}
                </span>
                <StatusBadge status={sale.status} />
              </div>
            </div>
            <ProgressBar label={`${sale.name} allocation utilised`} ratio={safeRatio(sale.sold, sale.allocated)} />
          </li>
        ))}
      </ul>
    </ChartPanel>
  );
}
