import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ExternalLink, Link2, RefreshCw } from 'lucide-react';

import { StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { FormField, Input, Select } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { useOptionalAuth } from '@/hooks/useAuth';
import { formatDateTime } from '@/lib/format';
import { formatMoney } from '@/lib/money';
import { getActiveOrganisationId } from '@/services/api/auth';
import { listOrders } from '@/services/api/commerceApi';
import { endpoints } from '@/services/api/endpoints';
import { cancelPaymentLink, createPaymentLink, listPaymentLinks, syncPaymentLink } from '@/services/api/financeApi';

export function PaymentLinksPage() {
  const queryClient = useQueryClient();
  const auth = useOptionalAuth();
  const orgId = auth?.activeOrganisation?.organisationId ?? getActiveOrganisationId() ?? null;
  const role = auth?.activeRole ?? 'owner';
  const canOperate = role === 'owner' || role === 'admin' || role === 'operator';

  const [statusFilter, setStatusFilter] = useState('');
  const [orderId, setOrderId] = useState('');
  const [description, setDescription] = useState('');
  const [expiresHours, setExpiresHours] = useState('72');
  const [idempKey, setIdempKey] = useState(() => `pl-${Date.now()}`);
  const [feedback, setFeedback] = useState<{ tone: 'error' | 'success'; text: string } | null>(null);

  const linksQuery = useQuery({
    queryKey: [endpoints.payments.links.id, orgId, statusFilter],
    queryFn: () => listPaymentLinks({ status: statusFilter || undefined }),
  });

  const ordersQuery = useQuery({
    queryKey: [endpoints.orders.list.id, orgId, 'pending-for-links'],
    queryFn: () => listOrders({ status: 'PENDING_PAYMENT', pageSize: 100 }),
    enabled: canOperate,
  });

  const createMutation = useMutation({
    mutationFn: () => {
      if (!orderId) throw new Error('Select a pending-payment order.');
      if (description.trim().length < 3) throw new Error('Enter a description (min 3 chars).');
      return createPaymentLink(
        {
          order_id: Number(orderId),
          description: description.trim(),
          expires_in_hours: expiresHours ? Number(expiresHours) : undefined,
        },
        idempKey,
      );
    },
    onSuccess: (created) => {
      setOrderId('');
      setDescription('');
      setIdempKey(`pl-${Date.now()}`);
      setFeedback({ tone: 'success', text: `Payment link ${created.providerLinkId} created.` });
      void queryClient.invalidateQueries({ queryKey: [endpoints.payments.links.id, orgId] });
      void queryClient.invalidateQueries({ queryKey: [endpoints.payments.overview.id, orgId] });
    },
    onError: (err: Error) => setFeedback({ tone: 'error', text: err.message }),
  });

  const syncMutation = useMutation({
    mutationFn: (id: string) => syncPaymentLink(id),
    onSuccess: (updated) => {
      setFeedback({ tone: 'success', text: `Synced ${updated.providerLinkId} -> ${updated.status}.` });
      void queryClient.invalidateQueries({ queryKey: [endpoints.payments.links.id, orgId] });
    },
    onError: (err: Error) => setFeedback({ tone: 'error', text: err.message }),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => cancelPaymentLink(id),
    onSuccess: (updated) => {
      setFeedback({ tone: 'success', text: `Cancelled ${updated.providerLinkId}.` });
      void queryClient.invalidateQueries({ queryKey: [endpoints.payments.links.id, orgId] });
    },
    onError: (err: Error) => setFeedback({ tone: 'error', text: err.message }),
  });

  const pendingOrders = ordersQuery.data?.items ?? [];
  const links = linksQuery.data?.items ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Payment Links"
        description="Razorpay test-mode hosted payment links linked to orders; completion is confirmed only via verified webhook or gateway capture."
      />

      {feedback && (
        <div
          role={feedback.tone === 'error' ? 'alert' : 'status'}
          className={`rounded border px-3 py-2 text-xs ${
            feedback.tone === 'error'
              ? 'border-danger/40 bg-danger/10 text-danger'
              : 'border-success/40 bg-success/10 text-success'
          }`}
        >
          {feedback.text}
        </div>
      )}

      {canOperate && (
        <Panel>
          <PanelHeader title="Generate payment link" />
          <PanelBody>
            <form
              className="grid gap-3 md:grid-cols-4"
              onSubmit={(e) => {
                e.preventDefault();
                setFeedback(null);
                createMutation.mutate();
              }}
            >
              <FormField label="Pending Order">
                {(p) => (
                  <Select {...p} value={orderId} onChange={(e) => setOrderId(e.target.value)}>
                    <option value="">Select order...</option>
                    {pendingOrders.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.reference} • {formatMoney(o.total, o.currency)}
                      </option>
                    ))}
                  </Select>
                )}
              </FormField>
              <FormField label="Description">
                {(p) => (
                  <Input
                    {...p}
                    placeholder="Order invoice payment"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                )}
              </FormField>
              <FormField label="Expiry (hours)">
                {(p) => (
                  <Input
                    {...p}
                    type="number"
                    min="1"
                    max="720"
                    value={expiresHours}
                    onChange={(e) => setExpiresHours(e.target.value)}
                  />
                )}
              </FormField>
              <div className="flex items-end">
                <Button type="submit" variant="primary" icon={<Link2 className="h-4 w-4" />} loading={createMutation.isPending} className="w-full">
                  Create Payment Link
                </Button>
              </div>
            </form>
          </PanelBody>
        </Panel>
      )}

      <Panel>
        <PanelHeader
          title="Merchant payment links"
          actions={
            <div className="w-48">
              <Select aria-label="Filter link status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="">All link statuses</option>
                <option value="ACTIVE">Active</option>
                <option value="PAID">Paid</option>
                <option value="EXPIRED">Expired</option>
                <option value="CANCELLED">Cancelled</option>
              </Select>
            </div>
          }
        />
        <PanelBody>
          {linksQuery.isLoading ? (
            <p className="text-sm text-ink-muted">Loading payment links...</p>
          ) : links.length === 0 ? (
            <p className="py-6 text-center text-sm text-ink-muted">No payment links created yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase text-ink-muted">
                    <th className="py-2 pr-4">Link ID / Ref</th>
                    <th className="py-2 pr-4">Order</th>
                    <th className="py-2 pr-4">Amount</th>
                    <th className="py-2 pr-4">Paid</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Expires</th>
                    <th className="py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {links.map((l) => (
                    <tr key={l.id}>
                      <td className="py-2.5 pr-4">
                        <div className="font-mono text-xs text-ink">{l.providerLinkId}</div>
                        <a
                          href={l.shortUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
                        >
                          {l.shortUrl} <ExternalLink className="h-3 w-3" aria-hidden />
                        </a>
                      </td>
                      <td className="py-2.5 pr-4 font-mono text-xs">#{l.orderId}</td>
                      <td className="py-2.5 pr-4 font-mono">{formatMoney(l.amount, l.currency)}</td>
                      <td className="py-2.5 pr-4 font-mono text-ink-muted">{formatMoney(l.amountPaid, l.currency)}</td>
                      <td className="py-2.5 pr-4">
                        <StatusBadge status={l.status} />
                      </td>
                      <td className="py-2.5 pr-4 text-xs text-ink-muted">{formatDateTime(l.expiresAt)}</td>
                      <td className="py-2.5 text-right space-x-2">
                        {canOperate && (
                          <>
                            <Button
                              size="sm"
                              variant="secondary"
                              icon={<RefreshCw className="h-3.5 w-3.5" />}
                              onClick={() => syncMutation.mutate(l.id)}
                            >
                              Sync
                            </Button>
                            {l.status !== 'PAID' && l.status !== 'CANCELLED' && l.status !== 'EXPIRED' && (
                              <Button size="sm" variant="danger" onClick={() => cancelMutation.mutate(l.id)}>
                                Cancel
                              </Button>
                            )}
                          </>
                        )}
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
