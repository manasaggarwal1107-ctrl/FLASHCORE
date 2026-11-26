import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';

import { OriginBadge, StatusBadge } from '@/components/ui/Badge';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { DetailList } from '@/features/shared/DetailList';
import { useOptionalAuth } from '@/hooks/useAuth';
import { formatDateTime, formatInteger } from '@/lib/format';
import { formatMoney } from '@/lib/money';
import { getActiveOrganisationId } from '@/services/api/auth';
import { getCustomer, listCustomerOrders } from '@/services/api/commerceApi';
import { endpoints } from '@/services/api/endpoints';

export function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const auth = useOptionalAuth();
  const orgId = auth?.activeOrganisation?.organisationId ?? getActiveOrganisationId() ?? null;

  const customerQuery = useQuery({
    queryKey: [endpoints.customers.get.id, orgId, id],
    queryFn: () => getCustomer(id!),
    enabled: Boolean(id),
  });

  const ordersQuery = useQuery({
    queryKey: [endpoints.customers.orders.id, orgId, id],
    queryFn: () => listCustomerOrders(id!),
    enabled: Boolean(id),
  });

  const customer = customerQuery.data;
  const orders = ordersQuery.data?.items ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        title={customer ? customer.name : `Customer ${id ?? ''}`}
        description={customer ? `Reference ${customer.reference}` : 'Customer profile'}
        meta={
          <Link to="/customers" className="text-xs text-accent hover:underline">
            Back to customers
          </Link>
        }
      />

      {customerQuery.isLoading ? (
        <p className="text-sm text-ink-muted">Loading customer profile...</p>
      ) : customerQuery.isError ? (
        <div role="alert" className="rounded border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
          {(customerQuery.error as Error)?.message || 'Customer not found.'}
        </div>
      ) : customer ? (
        <>
          <Panel>
            <PanelHeader
              title="Customer details"
              badge={<OriginBadge origin={customer.origin} />}
            />
            <PanelBody>
              <DetailList
                columns={3}
                items={[
                  { label: 'Reference', value: customer.reference, mono: true },
                  { label: 'Email', value: customer.email ?? '—' },
                  { label: 'Phone', value: customer.phone ?? '—' },
                  { label: 'Status', value: <StatusBadge status={customer.status} /> },
                  { label: 'Order count', value: formatInteger(customer.orderCount) },
                  { label: 'Created', value: formatDateTime(customer.createdAt) },
                ]}
              />
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Order history" />
            <PanelBody>
              {ordersQuery.isLoading ? (
                <p className="text-sm text-ink-muted">Loading order history...</p>
              ) : orders.length === 0 ? (
                <p className="text-sm text-ink-muted">This customer has not placed any orders yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-line text-xs uppercase text-ink-muted">
                        <th className="py-2 pr-4">Order</th>
                        <th className="py-2 pr-4">Status</th>
                        <th className="py-2 pr-4">Payment</th>
                        <th className="py-2 pr-4">Total</th>
                        <th className="py-2 pr-4">Placed</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {orders.map((order) => (
                        <tr key={order.id}>
                          <td className="py-2.5 pr-4 font-mono">
                            <Link to={`/orders/${order.id}`} className="text-accent hover:underline">
                              {order.reference}
                            </Link>
                          </td>
                          <td className="py-2.5 pr-4">
                            <StatusBadge status={order.status} />
                          </td>
                          <td className="py-2.5 pr-4">
                            <StatusBadge status={order.paymentStatus} />
                          </td>
                          <td className="py-2.5 pr-4 font-mono">
                            {formatMoney(order.total, order.currency)}
                          </td>
                          <td className="py-2.5 pr-4 text-xs text-ink-muted">
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
        </>
      ) : null}
    </div>
  );
}
