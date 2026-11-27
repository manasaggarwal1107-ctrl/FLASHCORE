import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Search, Trash2 } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';

import { OriginBadge, StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { FormField, Input, Select } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { useOptionalAuth } from '@/hooks/useAuth';
import { formatDateTime, formatInteger } from '@/lib/format';
import { formatMoney } from '@/lib/money';
import { getActiveOrganisationId } from '@/services/api/auth';
import {
  createOrder,
  listCatalogProducts,
  listCustomers,
  listInventoryLocations,
  listOrders,
} from '@/services/api/commerceApi';
import { endpoints } from '@/services/api/endpoints';

function nextKey(prefix: string) {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

interface DraftLine {
  productId: string;
  locationId: string;
  quantity: string;
}

export function OrdersPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const auth = useOptionalAuth();
  const orgId = auth?.activeOrganisation?.organisationId ?? getActiveOrganisationId() ?? null;
  const role = auth?.activeRole ?? 'owner';
  const canEdit = role === 'owner' || role === 'admin' || role === 'operator';

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [showForm, setShowForm] = useState(false);

  const [customerId, setCustomerId] = useState('');
  const [discountInr, setDiscountInr] = useState('0');
  const [lines, setLines] = useState<DraftLine[]>([{ productId: '', locationId: '', quantity: '1' }]);
  const [idempotencyKey, setIdempotencyKey] = useState(() => nextKey('ord'));
  const [formError, setFormError] = useState<string | null>(null);

  const ordersQuery = useQuery({
    queryKey: [endpoints.orders.list.id, orgId, search, statusFilter],
    queryFn: () =>
      listOrders({
        search: search.trim() || undefined,
        status: statusFilter || undefined,
      }),
  });

  const productsQuery = useQuery({
    queryKey: [endpoints.catalog.list.id, orgId, 'order-picker'],
    queryFn: () => listCatalogProducts({ pageSize: 100, status: 'active' }),
    enabled: showForm && canEdit,
  });

  const customersQuery = useQuery({
    queryKey: [endpoints.customers.list.id, orgId, 'order-picker'],
    queryFn: () => listCustomers({ pageSize: 100 }),
    enabled: showForm && canEdit,
  });

  const locationsQuery = useQuery({
    queryKey: [endpoints.retailInventory.locations.id, orgId, 'order-picker'],
    queryFn: listInventoryLocations,
    enabled: showForm && canEdit,
  });

  const createMutation = useMutation({
    mutationFn: () => {
      const validLines = lines
        .filter((l) => l.productId && Number(l.quantity) > 0)
        .map((l) => ({
          product_id: Number(l.productId),
          location_id: l.locationId ? Number(l.locationId) : undefined,
          quantity: Number(l.quantity),
        }));

      if (validLines.length === 0) {
        throw new Error('Select at least one active product and positive quantity.');
      }

      const discountMinor = Math.max(0, Math.round((Number(discountInr) || 0) * 100));
      return createOrder(
        {
          customer_id: customerId ? Number(customerId) : undefined,
          discount_minor: discountMinor,
          submit_for_payment: true,
          items: validLines,
        },
        idempotencyKey,
      );
    },
    onSuccess: (created) => {
      setShowForm(false);
      setLines([{ productId: '', locationId: '', quantity: '1' }]);
      setCustomerId('');
      setDiscountInr('0');
      setFormError(null);
      setIdempotencyKey(nextKey('ord'));
      void queryClient.invalidateQueries({ queryKey: [endpoints.orders.list.id, orgId] });
      void queryClient.invalidateQueries({ queryKey: [endpoints.retailInventory.list.id, orgId] });
      navigate(`/orders/${created.id}`);
    },
    onError: (err: Error) => {
      setFormError(err.message || 'Unable to create order.');
    },
  });

  const orders = ordersQuery.data?.items ?? [];
  const products = productsQuery.data?.items ?? [];
  const customers = customersQuery.data?.items ?? [];
  const locations = locationsQuery.data ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Orders"
        description="Tenant-scoped retail orders with live stock reservations, lifecycle transitions, and Razorpay checkout."
        actions={
          canEdit && (
            <Button
              variant="primary"
              icon={<Plus className="h-4 w-4" />}
              onClick={() => {
                setFormError(null);
                setShowForm((prev) => !prev);
              }}
            >
              {showForm ? 'Close form' : 'Create order'}
            </Button>
          )
        }
      />

      {showForm && canEdit && (
        <Panel>
          <PanelHeader
            title="New retail order"
            description="Reserves inventory atomically and prepares the order for Razorpay checkout."
          />
          <PanelBody>
            <form
              className="space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                setFormError(null);
                createMutation.mutate();
              }}
            >
              <div className="grid gap-3 md:grid-cols-2">
                <FormField label="Customer (optional)">
                  {(p) => (
                    <Select {...p} value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
                      <option value="">Walk-in / Unassigned</option>
                      {customers.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name} {c.email ? `(${c.email})` : ''}
                        </option>
                      ))}
                    </Select>
                  )}
                </FormField>
                <FormField label="Order discount (INR)">
                  {(p) => (
                    <Input
                      {...p}
                      type="number"
                      min="0"
                      step="0.01"
                      value={discountInr}
                      onChange={(e) => setDiscountInr(e.target.value)}
                    />
                  )}
                </FormField>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium uppercase text-ink-muted">Order items</span>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={() => setLines((prev) => [...prev, { productId: '', locationId: '', quantity: '1' }])}
                  >
                    Add item
                  </Button>
                </div>

                {lines.map((line, idx) => (
                  <div key={idx} className="grid gap-2 md:grid-cols-12 items-end">
                    <div className="md:col-span-5">
                      <FormField label={idx === 0 ? 'Product' : `Product #${idx + 1}`}>
                        {(p) => (
                          <Select
                            {...p}
                            value={line.productId}
                            onChange={(e) =>
                              setLines((prev) =>
                                prev.map((row, i) => (i === idx ? { ...row, productId: e.target.value } : row)),
                              )
                            }
                          >
                            <option value="">Select active product...</option>
                            {products.map((prod) => (
                              <option key={prod.id} value={prod.id}>
                                {prod.sku} — {prod.name} ({formatMoney(prod.price, prod.currency)} • Avail:{' '}
                                {prod.inventory.available})
                              </option>
                            ))}
                          </Select>
                        )}
                      </FormField>
                    </div>
                    <div className="md:col-span-4">
                      <FormField label={idx === 0 ? 'Location' : 'Location'}>
                        {(p) => (
                          <Select
                            {...p}
                            value={line.locationId}
                            onChange={(e) =>
                              setLines((prev) =>
                                prev.map((row, i) => (i === idx ? { ...row, locationId: e.target.value } : row)),
                              )
                            }
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
                    </div>
                    <div className="md:col-span-2">
                      <FormField label="Qty">
                        {(p) => (
                          <Input
                            {...p}
                            type="number"
                            min="1"
                            value={line.quantity}
                            onChange={(e) =>
                              setLines((prev) =>
                                prev.map((row, i) => (i === idx ? { ...row, quantity: e.target.value } : row)),
                              )
                            }
                          />
                        )}
                      </FormField>
                    </div>
                    <div className="md:col-span-1 flex justify-end">
                      {lines.length > 1 && (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          aria-label="Remove item"
                          onClick={() => setLines((prev) => prev.filter((_, i) => i !== idx))}
                        >
                          <Trash2 className="h-4 w-4 text-danger" />
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {formError && (
                <div role="alert" className="rounded border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
                  {formError}
                </div>
              )}

              <div className="flex justify-end gap-2">
                <Button type="button" variant="secondary" onClick={() => setShowForm(false)}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" loading={createMutation.isPending}>
                  Place order & reserve stock
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
                aria-label="Search orders"
                placeholder="Search by order reference..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-transparent text-sm text-ink placeholder:text-ink-faint focus:outline-none"
              />
            </div>
            <div className="w-48">
              <Select
                aria-label="Filter order status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="">All order statuses</option>
                <option value="PENDING_PAYMENT">Pending Payment</option>
                <option value="PAID">Paid</option>
                <option value="PROCESSING">Processing</option>
                <option value="FULFILLED">Fulfilled</option>
                <option value="CANCELLED">Cancelled</option>
                <option value="EXPIRED">Expired</option>
              </Select>
            </div>
          </div>

          {ordersQuery.isLoading ? (
            <p className="text-sm text-ink-muted">Loading orders...</p>
          ) : ordersQuery.isError ? (
            <div role="alert" className="rounded border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
              {(ordersQuery.error as Error)?.message || 'Failed to load orders.'}
            </div>
          ) : orders.length === 0 ? (
            <p className="py-8 text-center text-sm text-ink-muted">
              No retail orders in this workspace yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase text-ink-muted">
                    <th className="py-2 pr-4">Order Ref</th>
                    <th className="py-2 pr-4">Customer</th>
                    <th className="py-2 pr-4">Order Status</th>
                    <th className="py-2 pr-4">Payment</th>
                    <th className="py-2 pr-4">Items</th>
                    <th className="py-2 pr-4">Total</th>
                    <th className="py-2 pr-4">Placed</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {orders.map((order) => (
                    <tr key={order.id} className="hover:bg-surface-raised/60">
                      <td className="py-3 pr-4">
                        <Link to={`/orders/${order.id}`} className="font-mono font-medium text-accent hover:underline">
                          {order.reference}
                        </Link>
                        <div className="mt-0.5">
                          <OriginBadge origin={order.origin} />
                        </div>
                      </td>
                      <td className="py-3 pr-4 text-ink-muted">
                        {order.customerName ?? 'Walk-in'}
                      </td>
                      <td className="py-3 pr-4">
                        <StatusBadge status={order.status} />
                      </td>
                      <td className="py-3 pr-4">
                        <StatusBadge status={order.paymentStatus} />
                      </td>
                      <td className="py-3 pr-4 font-mono text-ink-muted">
                        {formatInteger(order.itemCount)}
                      </td>
                      <td className="py-3 pr-4 font-mono font-medium text-ink">
                        {formatMoney(order.total, order.currency)}
                      </td>
                      <td className="py-3 pr-4 text-xs text-ink-muted">
                        {formatDateTime(order.placedAt)}
                      </td>
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
