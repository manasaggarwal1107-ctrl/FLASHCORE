import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Plus, Search } from 'lucide-react';

import { Button } from '@/components/ui/Button';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody } from '@/components/ui/Panel';
import { apiRequest } from '@/services/api/client';
import { endpoints } from '@/services/api/endpoints';

interface SimulationProduct {
  id: number;
  sku: string;
  name: string;
  description: string | null;
  createdAt?: string;
}

export function ProductsPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');

  const query = useQuery({
    queryKey: [endpoints.products.list.id],
    queryFn: () => apiRequest<SimulationProduct[]>('/simulations/products'),
  });

  const products = useMemo(() => {
    const rows = query.data ?? [];
    const term = search.trim().toLowerCase();

    if (!term) return rows;

    return rows.filter((product) =>
      [product.name, product.sku, product.description ?? '']
        .some((value) => value.toLowerCase().includes(term)),
    );
  }, [query.data, search]);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Products"
        description="Simulation product catalogue. These records are separate from the historical Rossmann dataset."
        actions={
          <Button
            variant="primary"
            icon={<Plus className="h-4 w-4" />}
            onClick={() => navigate('/products/new')}
          >
            New product
          </Button>
        }
      />

      <Panel>
        <PanelBody>
          <div className="mb-4 flex items-center gap-2">
            <Search className="h-4 w-4 text-ink-muted" aria-hidden />
            <input
              type="search"
              aria-label="Search products"
              placeholder="Search product name, SKU or description"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="min-h-9 w-full rounded-md border border-line bg-surface px-3 text-sm outline-none focus:border-ink-muted"
            />
          </div>

          {query.isPending && (
            <p className="py-8 text-center text-sm text-ink-muted">Loading products…</p>
          )}

          {query.isError && (
            <div className="py-6 text-sm text-danger" role="alert">
              Could not load products: {query.error.message}
              <div className="mt-2">
                <Button size="sm" onClick={() => void query.refetch()}>Retry</Button>
              </div>
            </div>
          )}

          {query.isSuccess && products.length === 0 && (
            <p className="py-8 text-center text-sm text-ink-muted">
              {query.data.length === 0
                ? 'No simulation products have been created yet.'
                : 'No products match your search.'}
            </p>
          )}

          {products.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs text-ink-muted">
                    <th className="px-3 py-3 font-medium">Product</th>
                    <th className="px-3 py-3 font-medium">SKU</th>
                    <th className="px-3 py-3 font-medium">Description</th>
                    <th className="px-3 py-3 text-right font-medium">ID</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((product) => (
                    <tr key={product.id} className="border-b border-line last:border-0">
                      <td className="px-3 py-3 font-medium">{product.name}</td>
                      <td className="px-3 py-3 font-mono text-xs">{product.sku}</td>
                      <td className="px-3 py-3 text-ink-muted">
                        {product.description || '—'}
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums">{product.id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </PanelBody>
      </Panel>
    </div>
  );
}