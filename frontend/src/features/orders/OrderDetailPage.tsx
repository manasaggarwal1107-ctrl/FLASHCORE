import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, CreditCard, ShieldAlert } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';

import { OriginBadge, StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { DetailList } from '@/features/shared/DetailList';
import { useOptionalAuth } from '@/hooks/useAuth';
import { formatDateTime, formatInteger } from '@/lib/format';
import { formatMoney } from '@/lib/money';
import { getActiveOrganisationId } from '@/services/api/auth';
import {
  getOrder,
  initiateOrderCheckout,
  transitionOrder,
  verifyRazorpayPayment,
} from '@/services/api/commerceApi';
import { endpoints } from '@/services/api/endpoints';
import { openRazorpayStandardCheckout } from '@/services/payments/razorpayCheckout';

type CheckoutPhase = 'idle' | 'creating_order' | 'awaiting_modal' | 'verifying' | 'verified' | 'cancelled' | 'failed';

export function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const auth = useOptionalAuth();
  const orgId = auth?.activeOrganisation?.organisationId ?? getActiveOrganisationId() ?? null;
  const role = auth?.activeRole ?? 'owner';
  const canOperate = role === 'owner' || role === 'admin' || role === 'operator';

  const [checkoutPhase, setCheckoutPhase] = useState<CheckoutPhase>('idle');
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [checkoutMessage, setCheckoutMessage] = useState<string | null>(null);
  const [checkoutIdempKey, setCheckoutIdempKey] = useState(() => `chk-${id ?? '0'}-${Date.now()}`);

  const orderQuery = useQuery({
    queryKey: [endpoints.orders.get.id, orgId, id],
    queryFn: () => getOrder(id!),
    enabled: Boolean(id),
  });

  const transitionMutation = useMutation({
    mutationFn: (target: 'PENDING_PAYMENT' | 'PROCESSING' | 'FULFILLED' | 'CANCELLED') =>
      transitionOrder(id!, target),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [endpoints.orders.get.id, orgId, id] });
      void queryClient.invalidateQueries({ queryKey: [endpoints.orders.list.id, orgId] });
      void queryClient.invalidateQueries({ queryKey: [endpoints.retailInventory.list.id, orgId] });
    },
  });

  async function handleRazorpayCheckout() {
    if (!order) return;
    setCheckoutError(null);
    setCheckoutMessage(null);
    setCheckoutPhase('creating_order');

    try {
      const paymentOrder = await initiateOrderCheckout(order.id, checkoutIdempKey);
      setCheckoutPhase('awaiting_modal');

      const callback = await openRazorpayStandardCheckout(paymentOrder, {
        orderReference: order.reference,
      });

      setCheckoutPhase('verifying');
      const verification = await verifyRazorpayPayment(paymentOrder.id, {
        razorpay_order_id: callback.razorpay_order_id,
        razorpay_payment_id: callback.razorpay_payment_id,
        razorpay_signature: callback.razorpay_signature,
      });

      setCheckoutPhase('verified');
      setCheckoutMessage(
        `Payment verified server-side (${verification.providerPaymentId}). Order status is now ${verification.orderStatus}.`,
      );
      setCheckoutIdempKey(`chk-${order.id}-${Date.now()}`);
      await queryClient.invalidateQueries({ queryKey: [endpoints.orders.get.id, orgId, id] });
      await queryClient.invalidateQueries({ queryKey: [endpoints.orders.list.id, orgId] });
      await queryClient.invalidateQueries({ queryKey: [endpoints.payments.transactions.id, orgId] });
      await queryClient.invalidateQueries({ queryKey: [endpoints.retailInventory.list.id, orgId] });
    } catch (err) {
      const msg = (err as Error)?.message || 'Checkout failed.';
      if (msg.toLowerCase().includes('closed before payment')) {
        setCheckoutPhase('cancelled');
      } else {
        setCheckoutPhase('failed');
      }
      setCheckoutError(msg);
    }
  }

  const order = orderQuery.data;

  return (
    <div className="space-y-4">
      <PageHeader
        title={order ? order.reference : `Order ${id ?? ''}`}
        description={order ? `Order status: ${order.status} • Payment: ${order.paymentStatus}` : 'Order detail'}
        meta={
          <Link to="/orders" className="text-xs text-accent hover:underline">
            Back to orders
          </Link>
        }
        actions={
          order && canOperate ? (
            <div className="flex flex-wrap items-center gap-2">
              {order.status === 'PENDING_PAYMENT' && (
                <Button
                  variant="primary"
                  icon={<CreditCard className="h-4 w-4" />}
                  loading={checkoutPhase === 'creating_order' || checkoutPhase === 'awaiting_modal' || checkoutPhase === 'verifying'}
                  onClick={() => void handleRazorpayCheckout()}
                >
                  {checkoutPhase === 'verifying'
                    ? 'Verifying signature...'
                    : checkoutPhase === 'failed' || checkoutPhase === 'cancelled'
                      ? 'Retry Razorpay Test Checkout'
                      : 'Pay with Razorpay (Test Mode)'}
                </Button>
              )}
              {order.status === 'PAID' && (
                <Button
                  variant="primary"
                  loading={transitionMutation.isPending}
                  onClick={() => transitionMutation.mutate('PROCESSING')}
                >
                  Mark Processing
                </Button>
              )}
              {order.status === 'PROCESSING' && (
                <Button
                  variant="primary"
                  loading={transitionMutation.isPending}
                  onClick={() => transitionMutation.mutate('FULFILLED')}
                >
                  Mark Fulfilled
                </Button>
              )}
              {(order.status === 'PENDING_PAYMENT' || order.status === 'DRAFT') && (
                <Button
                  variant="danger"
                  loading={transitionMutation.isPending}
                  onClick={() => transitionMutation.mutate('CANCELLED')}
                >
                  Cancel Order
                </Button>
              )}
            </div>
          ) : null
        }
      />

      {checkoutMessage && (
        <div
          role="status"
          className="flex items-center gap-2 rounded border border-success/40 bg-success/10 px-4 py-3 text-sm text-success"
        >
          <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden />
          <span>{checkoutMessage}</span>
        </div>
      )}

      {checkoutError && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger"
        >
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <div>
            <div className="font-medium">
              {checkoutPhase === 'cancelled' ? 'Checkout cancelled' : 'Payment verification did not complete'}
            </div>
            <div className="text-xs opacity-90">{checkoutError}</div>
          </div>
        </div>
      )}

      {transitionMutation.isError && (
        <div role="alert" className="rounded border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
          {(transitionMutation.error as Error)?.message || 'Order status transition failed.'}
        </div>
      )}

      {orderQuery.isLoading ? (
        <p className="text-sm text-ink-muted">Loading order...</p>
      ) : orderQuery.isError ? (
        <div role="alert" className="rounded border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
          {(orderQuery.error as Error)?.message || 'Order not found.'}
        </div>
      ) : order ? (
        <>
          <Panel>
            <PanelHeader
              title="Order summary"
              badge={<OriginBadge origin={order.origin} />}
            />
            <PanelBody>
              <DetailList
                columns={3}
                items={[
                  { label: 'Reference', value: order.reference, mono: true },
                  {
                    label: 'Customer',
                    value: order.customerId ? (
                      <Link to={`/customers/${order.customerId}`} className="text-accent hover:underline">
                        {order.customerName ?? order.customerRef ?? `Customer #${order.customerId}`}
                      </Link>
                    ) : (
                      'Walk-in customer'
                    ),
                  },
                  { label: 'Order Status', value: <StatusBadge status={order.status} /> },
                  { label: 'Payment Status', value: <StatusBadge status={order.paymentStatus} /> },
                  { label: 'Subtotal', value: formatMoney(order.subtotal, order.currency), mono: true },
                  { label: 'Tax', value: formatMoney(order.tax, order.currency), mono: true },
                  { label: 'Discount', value: formatMoney(order.discount, order.currency), mono: true },
                  { label: 'Total', value: formatMoney(order.total, order.currency), mono: true },
                  {
                    label: 'Reservation Expiry',
                    value: order.reservationExpiresAt ? formatDateTime(order.reservationExpiresAt) : 'Confirmed / Released',
                  },
                ]}
              />
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Order line items" />
            <PanelBody>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-line text-xs uppercase text-ink-muted">
                      <th className="py-2 pr-4">SKU / Product</th>
                      <th className="py-2 pr-4">Qty</th>
                      <th className="py-2 pr-4">Unit price</th>
                      <th className="py-2 pr-4">Tax</th>
                      <th className="py-2 pr-4">Line total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {order.lines.map((line) => (
                      <tr key={line.id}>
                        <td className="py-2.5 pr-4">
                          <div className="font-medium text-ink">{line.productName}</div>
                          <div className="font-mono text-xs text-ink-muted">{line.sku}</div>
                        </td>
                        <td className="py-2.5 pr-4 font-mono">{formatInteger(line.quantity)}</td>
                        <td className="py-2.5 pr-4 font-mono">{formatMoney(line.unitPrice, order.currency)}</td>
                        <td className="py-2.5 pr-4 font-mono text-ink-muted">
                          {(line.taxRateBps / 100).toFixed(2)}%
                        </td>
                        <td className="py-2.5 pr-4 font-mono font-medium">
                          {formatMoney(line.lineTotal, order.currency)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Order event log" />
            <PanelBody>
              {!order.events || order.events.length === 0 ? (
                <p className="text-sm text-ink-muted">No lifecycle events recorded yet.</p>
              ) : (
                <div className="space-y-2">
                  {order.events.map((ev) => (
                    <div key={ev.id} className="flex flex-wrap items-center justify-between gap-2 rounded border border-line bg-canvas px-3 py-2 text-xs">
                      <div className="flex items-center gap-2">
                        <StatusBadge status={ev.toStatus} />
                        <span className="font-medium text-ink">{ev.eventType}</span>
                        {ev.actorRef && <span className="text-ink-muted">by {ev.actorRef}</span>}
                      </div>
                      <span className="text-ink-faint">{formatDateTime(ev.createdAt)}</span>
                    </div>
                  ))}
                </div>
              )}
            </PanelBody>
          </Panel>
        </>
      ) : null}
    </div>
  );
}
