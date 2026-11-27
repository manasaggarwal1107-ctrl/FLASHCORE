import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Warehouse } from 'lucide-react';

import { OriginBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { FormField, Input, Select } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { useOptionalAuth } from '@/hooks/useAuth';
import { formatDateTime, formatInteger } from '@/lib/format';
import { getActiveOrganisationId } from '@/services/api/auth';
import {
  adjustRetailStock,
  createInventoryLocation,
  listCatalogProducts,
  listInventoryLocations,
  listRetailInventory,
  listRetailMovements,
} from '@/services/api/commerceApi';
import { endpoints } from '@/services/api/endpoints';

export function RetailInventoryPage() {
  const queryClient = useQueryClient();
  const auth = useOptionalAuth();
  const orgId = auth?.activeOrganisation?.organisationId ?? getActiveOrganisationId() ?? null;
  const role = auth?.activeRole ?? 'owner';
  const canEdit = role === 'owner' || role === 'admin' || role === 'operator';

  const [tab, setTab] = useState<'balances' | 'movements'>('balances');
  const [selectedLocId, setSelectedLocId] = useState<string>('');
  const [locForm, setLocForm] = useState({ code: '', name: '', location_type: 'warehouse' as const });
  const [showLocForm, setShowLocForm] = useState(false);

  const [adjForm, setAdjForm] = useState({
    product_id: '',
    location_id: '',
    quantity_delta: '',
    reason: 'opening_stock',
  });
  const [actionError, setActionError] = useState<string | null>(null);

  const locationsQuery = useQuery({
    queryKey: [endpoints.retailInventory.locations.id, orgId],
    queryFn: listInventoryLocations,
  });

  const productsQuery = useQuery({
    queryKey: [endpoints.catalog.list.id, orgId, 'inventory-picker'],
    queryFn: () => listCatalogProducts({ pageSize: 100 }),
  });

  const balancesQuery = useQuery({
    queryKey: [endpoints.retailInventory.list.id, orgId, selectedLocId],
    queryFn: () =>
      listRetailInventory({
        locationId: selectedLocId ? Number(selectedLocId) : undefined,
      }),
  });

  const movementsQuery = useQuery({
    queryKey: [endpoints.retailInventory.movements.id, orgId],
    queryFn: () => listRetailMovements({ pageSize: 50 }),
    enabled: tab === 'movements',
  });

  const createLocMutation = useMutation({
    mutationFn: () => createInventoryLocation(locForm),
    onSuccess: () => {
      setLocForm({ code: '', name: '', location_type: 'warehouse' });
      setShowLocForm(false);
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: [endpoints.retailInventory.locations.id, orgId] });
    },
    onError: (err: Error) => setActionError(err.message || 'Unable to create location.'),
  });

  const adjustMutation = useMutation({
    mutationFn: () => {
      const productId = Number(adjForm.product_id);
      const delta = Number(adjForm.quantity_delta);
      if (!productId || !Number.isInteger(delta) || delta === 0) {
        throw new Error('Select a product and enter a non-zero integer stock delta.');
      }
      return adjustRetailStock({
        product_id: productId,
        location_id: adjForm.location_id ? Number(adjForm.location_id) : undefined,
        quantity_delta: delta,
        reason: adjForm.reason.trim() || 'manual_adjustment',
      });
    },
    onSuccess: () => {
      setAdjForm((f) => ({ ...f, quantity_delta: '' }));
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: [endpoints.retailInventory.list.id, orgId] });
      void queryClient.invalidateQueries({ queryKey: [endpoints.retailInventory.movements.id, orgId] });
      void queryClient.invalidateQueries({ queryKey: [endpoints.catalog.list.id, orgId] });
    },
    onError: (err: Error) => setActionError(err.message || 'Stock adjustment failed.'),
  });

  const locations = locationsQuery.data ?? [];
  const products = productsQuery.data?.items ?? [];
  const balances = balancesQuery.data?.items ?? [];
  const movements = movementsQuery.data?.items ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Retail Inventory"
        description="Multi-location warehouse stock, reservations held by pending orders, and immutable stock movements."
        actions={
          canEdit && (
            <Button
              variant="secondary"
              icon={<Plus className="h-4 w-4" />}
              onClick={() => setShowLocForm((v) => !v)}
            >
              Add location
            </Button>
          )
        }
      />

      {actionError && (
        <div role="alert" className="rounded border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
          {actionError}
        </div>
      )}

      {showLocForm && canEdit && (
        <Panel>
          <PanelHeader title="New inventory location" />
          <PanelBody>
            <form
              className="grid gap-3 md:grid-cols-4"
              onSubmit={(e) => {
                e.preventDefault();
                createLocMutation.mutate();
              }}
            >
              <FormField label="Code">
                {(p) => (
                  <Input
                    {...p}
                    placeholder="BLR-WH-01"
                    value={locForm.code}
                    onChange={(e) => setLocForm((f) => ({ ...f, code: e.target.value }))}
                  />
                )}
              </FormField>
              <FormField label="Location name">
                {(p) => (
                  <Input
                    {...p}
                    placeholder="Bengaluru Central Warehouse"
                    value={locForm.name}
                    onChange={(e) => setLocForm((f) => ({ ...f, name: e.target.value }))}
                  />
                )}
              </FormField>
              <FormField label="Type">
                {(p) => (
                  <Select
                    {...p}
                    value={locForm.location_type}
                    onChange={(e) =>
                      setLocForm((f) => ({
                        ...f,
                        location_type: e.target.value as 'warehouse',
                      }))
                    }
                  >
                    <option value="warehouse">Warehouse</option>
                    <option value="store">Store</option>
                    <option value="fulfilment_centre">Fulfilment Centre</option>
                  </Select>
                )}
              </FormField>
              <div className="flex items-end">
                <Button type="submit" variant="primary" loading={createLocMutation.isPending} className="w-full">
                  Save location
                </Button>
              </div>
            </form>
          </PanelBody>
        </Panel>
      )}

      {canEdit && (
        <Panel>
          <PanelHeader title="Record stock adjustment" description="All changes write an audited ledger movement." />
          <PanelBody>
            <form
              className="grid gap-3 md:grid-cols-5"
              onSubmit={(e) => {
                e.preventDefault();
                adjustMutation.mutate();
              }}
            >
              <FormField label="Product">
                {(p) => (
                  <Select
                    {...p}
                    value={adjForm.product_id}
                    onChange={(e) => setAdjForm((f) => ({ ...f, product_id: e.target.value }))}
                  >
                    <option value="">Select product...</option>
                    {products.map((prod) => (
                      <option key={prod.id} value={prod.id}>
                        {prod.sku} — {prod.name}
                      </option>
                    ))}
                  </Select>
                )}
              </FormField>
              <FormField label="Location">
                {(p) => (
                  <Select
                    {...p}
                    value={adjForm.location_id}
                    onChange={(e) => setAdjForm((f) => ({ ...f, location_id: e.target.value }))}
                  >
                    <option value="">Default location</option>
                    {locations.map((loc) => (
                      <option key={loc.id} value={loc.id}>
                        {loc.code} — {loc.name}
                      </option>
                    ))}
                  </Select>
                )}
              </FormField>
              <FormField label="Quantity delta">
                {(p) => (
                  <Input
                    {...p}
                    type="number"
                    placeholder="+25 or -5"
                    value={adjForm.quantity_delta}
                    onChange={(e) => setAdjForm((f) => ({ ...f, quantity_delta: e.target.value }))}
                  />
                )}
              </FormField>
              <FormField label="Reason">
                {(p) => (
                  <Input
                    {...p}
                    placeholder="Restock PO-104"
                    value={adjForm.reason}
                    onChange={(e) => setAdjForm((f) => ({ ...f, reason: e.target.value }))}
                  />
                )}
              </FormField>
              <div className="flex items-end">
                <Button type="submit" variant="primary" loading={adjustMutation.isPending} className="w-full">
                  Apply adjustment
                </Button>
              </div>
            </form>
          </PanelBody>
        </Panel>
      )}

      <div className="flex items-center justify-between gap-3">
        <div className="flex gap-2">
          <Button
            variant={tab === 'balances' ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setTab('balances')}
          >
            Balances
          </Button>
          <Button
            variant={tab === 'movements' ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setTab('movements')}
          >
            Movement ledger
          </Button>
        </div>

        {tab === 'balances' && (
          <div className="flex items-center gap-2">
            <Warehouse className="h-4 w-4 text-ink-muted" aria-hidden />
            <Select
              aria-label="Filter by location"
              value={selectedLocId}
              onChange={(e) => setSelectedLocId(e.target.value)}
            >
              <option value="">All locations</option>
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.code} — {loc.name}
                </option>
              ))}
            </Select>
          </div>
        )}
      </div>

      <Panel>
        <PanelBody>
          {tab === 'balances' ? (
            balancesQuery.isLoading ? (
              <p className="text-sm text-ink-muted">Loading inventory balances...</p>
            ) : balances.length === 0 ? (
              <p className="py-6 text-center text-sm text-ink-muted">No stock balances recorded yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-line text-xs uppercase text-ink-muted">
                      <th className="py-2 pr-4">SKU / Product</th>
                      <th className="py-2 pr-4">Location</th>
                      <th className="py-2 pr-4">On hand</th>
                      <th className="py-2 pr-4">Reserved</th>
                      <th className="py-2 pr-4">Available</th>
                      <th className="py-2 pr-4">Origin</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {balances.map((b) => (
                      <tr key={b.id}>
                        <td className="py-3 pr-4">
                          <div className="font-medium text-ink">{b.productName}</div>
                          <div className="font-mono text-xs text-ink-muted">{b.sku}</div>
                        </td>
                        <td className="py-3 pr-4 text-ink-muted">
                          {b.locationCode} — {b.locationName}
                        </td>
                        <td className="py-3 pr-4 font-mono text-ink">{formatInteger(b.onHand)}</td>
                        <td className="py-3 pr-4 font-mono text-warning">{formatInteger(b.reserved)}</td>
                        <td className="py-3 pr-4 font-mono font-semibold text-success">
                          {formatInteger(b.available)}
                        </td>
                        <td className="py-3 pr-4">
                          <OriginBadge origin={b.origin} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          ) : movementsQuery.isLoading ? (
            <p className="text-sm text-ink-muted">Loading movement ledger...</p>
          ) : movements.length === 0 ? (
            <p className="py-6 text-center text-sm text-ink-muted">No stock movements recorded yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase text-ink-muted">
                    <th className="py-2 pr-4">Occurred</th>
                    <th className="py-2 pr-4">SKU</th>
                    <th className="py-2 pr-4">Type</th>
                    <th className="py-2 pr-4">Delta</th>
                    <th className="py-2 pr-4">Reserved Δ</th>
                    <th className="py-2 pr-4">Balance after</th>
                    <th className="py-2 pr-4">Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {movements.map((m) => (
                    <tr key={m.id}>
                      <td className="py-2.5 pr-4 text-xs text-ink-muted">{formatDateTime(m.occurredAt)}</td>
                      <td className="py-2.5 pr-4 font-mono text-xs text-ink">{m.sku}</td>
                      <td className="py-2.5 pr-4 text-xs font-medium text-ink">{m.type}</td>
                      <td className="py-2.5 pr-4 font-mono text-xs text-ink">{m.quantityDelta}</td>
                      <td className="py-2.5 pr-4 font-mono text-xs text-ink-muted">{m.reservedDelta}</td>
                      <td className="py-2.5 pr-4 font-mono text-xs text-ink">{m.balanceAfter}</td>
                      <td className="py-2.5 pr-4 text-xs text-ink-muted">{m.reason ?? '—'}</td>
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
