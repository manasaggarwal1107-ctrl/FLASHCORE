import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Search } from 'lucide-react';
import { Link } from 'react-router-dom';

import { OriginBadge, StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { FormField, Input, Select } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { useOptionalAuth } from '@/hooks/useAuth';
import { formatDateTime, formatInteger } from '@/lib/format';
import { formatMoney } from '@/lib/money';
import { getActiveOrganisationId } from '@/services/api/auth';
import { createCatalogProduct, listCatalogProducts, updateCatalogProduct } from '@/services/api/commerceApi';
import { endpoints } from '@/services/api/endpoints';
import type { CommerceProduct } from '@/types/api';

const EMPTY_FORM = {
  sku: '',
  name: '',
  category: '',
  priceInr: '',
  taxRatePercent: '18',
  description: '',
};

export function CatalogPage() {
  const queryClient = useQueryClient();
  const auth = useOptionalAuth();
  const orgId = auth?.activeOrganisation?.organisationId ?? getActiveOrganisationId() ?? null;
  const role = auth?.activeRole ?? 'owner';
  const canEdit = role === 'owner' || role === 'admin' || role === 'operator';

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);

  const productsQuery = useQuery({
    queryKey: [endpoints.catalog.list.id, orgId, search, statusFilter],
    queryFn: () =>
      listCatalogProducts({
        search: search.trim() || undefined,
        status: statusFilter || undefined,
      }),
  });

  const createMutation = useMutation({
    mutationFn: () => {
      const parsedPrice = Number(form.priceInr);
      if (!Number.isFinite(parsedPrice) || parsedPrice < 0) {
        throw new Error('Enter a valid non-negative price in INR.');
      }
      const parsedTax = Number(form.taxRatePercent || '0');
      if (!Number.isFinite(parsedTax) || parsedTax < 0 || parsedTax > 100) {
        throw new Error('Tax rate must be between 0 and 100%.');
      }
      return createCatalogProduct({
        sku: form.sku.trim(),
        name: form.name.trim(),
        category: form.category.trim() || undefined,
        description: form.description.trim() || undefined,
        status: 'active',
        price_minor: Math.round(parsedPrice * 100),
        currency: 'INR',
        tax_rate_bps: Math.round(parsedTax * 100),
      });
    },
    onSuccess: () => {
      setForm(EMPTY_FORM);
      setFormError(null);
      setShowForm(false);
      void queryClient.invalidateQueries({ queryKey: [endpoints.catalog.list.id, orgId] });
    },
    onError: (err: Error) => {
      setFormError(err.message || 'Unable to create product.');
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'active' | 'archived' }) =>
      updateCatalogProduct(id, { status }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [endpoints.catalog.list.id, orgId] });
    },
  });

  const items: CommerceProduct[] = productsQuery.data?.items ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Catalog"
        description="Real tenant-scoped retail product catalogue with tax configuration and live stock visibility."
        actions={
          <div className="flex items-center gap-2">
            <Link
              to="/retail-inventory"
              className="inline-flex h-9 items-center rounded border border-line-strong bg-surface-raised px-3 text-sm font-medium text-ink hover:bg-surface-overlay"
            >
              Manage Stock
            </Link>
            {canEdit && (
              <Button
                variant="primary"
                icon={<Plus className="h-4 w-4" />}
                onClick={() => {
                  setFormError(null);
                  setShowForm((prev) => !prev);
                }}
              >
                {showForm ? 'Close form' : 'New catalog SKU'}
              </Button>
            )}
          </div>
        }
      />

      {showForm && canEdit && (
        <Panel>
          <PanelHeader title="Create catalog product" description="Minor-unit pricing stored safely in INR paise." />
          <PanelBody>
            <form
              className="grid gap-3 md:grid-cols-3"
              onSubmit={(e) => {
                e.preventDefault();
                setFormError(null);
                if (!form.sku.trim() || !form.name.trim() || !form.priceInr.trim()) {
                  setFormError('SKU, product name, and price are required.');
                  return;
                }
                createMutation.mutate();
              }}
            >
              <FormField label="SKU">
                {(p) => (
                  <Input
                    {...p}
                    placeholder="SKU-1001"
                    value={form.sku}
                    onChange={(e) => setForm((f) => ({ ...f, sku: e.target.value }))}
                  />
                )}
              </FormField>
              <FormField label="Product name">
                {(p) => (
                  <Input
                    {...p}
                    placeholder="Wireless Barcode Scanner"
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  />
                )}
              </FormField>
              <FormField label="Category">
                {(p) => (
                  <Input
                    {...p}
                    placeholder="POS Hardware"
                    value={form.category}
                    onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
                  />
                )}
              </FormField>
              <FormField label="Unit price (INR)">
                {(p) => (
                  <Input
                    {...p}
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="1499.00"
                    value={form.priceInr}
                    onChange={(e) => setForm((f) => ({ ...f, priceInr: e.target.value }))}
                  />
                )}
              </FormField>
              <FormField label="GST / Tax (%)">
                {(p) => (
                  <Input
                    {...p}
                    type="number"
                    step="0.01"
                    min="0"
                    max="100"
                    value={form.taxRatePercent}
                    onChange={(e) => setForm((f) => ({ ...f, taxRatePercent: e.target.value }))}
                  />
                )}
              </FormField>
              <FormField label="Description">
                {(p) => (
                  <Input
                    {...p}
                    placeholder="Optional internal note"
                    value={form.description}
                    onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  />
                )}
              </FormField>
              {formError && (
                <div role="alert" className="md:col-span-3 rounded border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
                  {formError}
                </div>
              )}
              <div className="md:col-span-3 flex justify-end gap-2">
                <Button type="button" variant="secondary" onClick={() => setShowForm(false)}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" loading={createMutation.isPending}>
                  Create product
                </Button>
              </div>
            </form>
          </PanelBody>
        </Panel>
      )}

      <Panel>
        <PanelBody>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <div className="flex flex-1 min-w-[220px] items-center gap-2 rounded border border-line-strong bg-canvas px-3 h-9">
              <Search className="h-4 w-4 text-ink-muted" aria-hidden />
              <input
                type="search"
                aria-label="Search catalog"
                placeholder="Search by SKU or product name..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-transparent text-sm text-ink placeholder:text-ink-faint focus:outline-none"
              />
            </div>
            <div className="w-44">
              <Select
                aria-label="Filter catalog status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="">All statuses</option>
                <option value="active">Active</option>
                <option value="draft">Draft</option>
                <option value="archived">Archived</option>
              </Select>
            </div>
          </div>

          {productsQuery.isLoading ? (
            <p className="text-sm text-ink-muted">Loading catalog products...</p>
          ) : productsQuery.isError ? (
            <div role="alert" className="rounded border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
              {(productsQuery.error as Error)?.message || 'Failed to load catalog.'}
            </div>
          ) : items.length === 0 ? (
            <p className="py-8 text-center text-sm text-ink-muted">
              No retail catalog products match your filters. Create your first real product SKU to start taking orders.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase text-ink-muted">
                    <th className="py-2 pr-4">SKU / Name</th>
                    <th className="py-2 pr-4">Price</th>
                    <th className="py-2 pr-4">Tax</th>
                    <th className="py-2 pr-4">Available</th>
                    <th className="py-2 pr-4">Reserved</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Updated</th>
                    {canEdit && <th className="py-2 text-right">Action</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {items.map((product) => (
                    <tr key={product.id} className="hover:bg-surface-raised/60">
                      <td className="py-3 pr-4">
                        <div className="font-medium text-ink">{product.name}</div>
                        <div className="mt-0.5 flex items-center gap-2 text-xs text-ink-muted">
                          <span className="font-mono">{product.sku}</span>
                          {product.category && <span>• {product.category}</span>}
                          <OriginBadge origin={product.origin} />
                        </div>
                      </td>
                      <td className="py-3 pr-4 font-mono text-ink">
                        {formatMoney(product.price, product.currency)}
                      </td>
                      <td className="py-3 pr-4 text-ink-muted">
                        {(product.taxRateBps / 100).toFixed(2)}%
                      </td>
                      <td className="py-3 pr-4 font-mono text-ink">
                        {formatInteger(product.inventory.available)}
                      </td>
                      <td className="py-3 pr-4 font-mono text-ink-muted">
                        {formatInteger(product.inventory.reserved)}
                      </td>
                      <td className="py-3 pr-4">
                        <StatusBadge status={product.status} />
                      </td>
                      <td className="py-3 pr-4 text-xs text-ink-muted">
                        {formatDateTime(product.updatedAt)}
                      </td>
                      {canEdit && (
                        <td className="py-3 text-right">
                          <Button
                            size="sm"
                            variant="secondary"
                            loading={statusMutation.isPending}
                            onClick={() =>
                              statusMutation.mutate({
                                id: product.id,
                                status: product.status === 'active' ? 'archived' : 'active',
                              })
                            }
                          >
                            {product.status === 'active' ? 'Archive' : 'Activate'}
                          </Button>
                        </td>
                      )}
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
