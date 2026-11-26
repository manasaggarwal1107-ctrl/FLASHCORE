import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CreditCard, Settings } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Select } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody } from '@/components/ui/Panel';
import { useOptionalAuth } from '@/hooks/useAuth';
import { formatDateTime } from '@/lib/format';
import { formatMoney } from '@/lib/money';
import { getActiveOrganisationId } from '@/services/api/auth';
import { listPaymentTransactions } from '@/services/api/commerceApi';
import { endpoints } from '@/services/api/endpoints';

export function PaymentsPage() {
  const auth = useOptionalAuth();
  const orgId = auth?.activeOrganisation?.organisationId ?? getActiveOrganisationId() ?? null;
  const [statusFilter, setStatusFilter] = useState('');

  const txnsQuery = useQuery({
    queryKey: [endpoints.payments.transactions.id, orgId, statusFilter],
    queryFn: () => listPaymentTransactions({ status: statusFilter || undefined }),
  });

  const items = txnsQuery.data?.items ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Payments"
        description="Verified gateway payment transactions across Razorpay checkout verification and signed webhooks."
        actions={
          <Link
            to="/settings"
            className="inline-flex h-9 items-center gap-2 rounded border border-line-strong bg-surface-raised px-3 text-sm font-medium text-ink hover:bg-surface-overlay"
          >
            <Settings className="h-4 w-4" aria-hidden />
            Gateway Config
          </Link>
        }
      />

      <Panel>
        <PanelBody>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs text-ink-muted">
              <CreditCard className="h-4 w-4 text-accent" aria-hidden />
              <span>Test-mode Razorpay ledger ({txnsQuery.data?.total ?? 0} records)</span>
            </div>
            <div className="w-48">
              <Select
                aria-label="Filter payment status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="">All payment states</option>
                <option value="CAPTURED">Captured</option>
                <option value="AUTHORIZED">Authorized</option>
                <option value="FAILED">Failed</option>
              </Select>
            </div>
          </div>

          {txnsQuery.isLoading ? (
            <p className="text-sm text-ink-muted">Loading payment transactions...</p>
          ) : txnsQuery.isError ? (
            <div role="alert" className="rounded border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
              {(txnsQuery.error as Error)?.message || 'Failed to load payment transactions.'}
            </div>
          ) : items.length === 0 ? (
            <p className="py-8 text-center text-sm text-ink-muted">
              No payment transactions recorded yet. Initiate checkout on a pending order to test Razorpay verification.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase text-ink-muted">
                    <th className="py-2 pr-4">Payment ID</th>
                    <th className="py-2 pr-4">Order</th>
                    <th className="py-2 pr-4">Event / Status</th>
                    <th className="py-2 pr-4">Method</th>
                    <th className="py-2 pr-4">Source</th>
                    <th className="py-2 pr-4">Amount</th>
                    <th className="py-2 pr-4">Recorded</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {items.map((txn) => (
                    <tr key={txn.id} className="hover:bg-surface-raised/60">
                      <td className="py-3 pr-4 font-mono text-xs text-ink">{txn.providerPaymentId}</td>
                      <td className="py-3 pr-4 font-mono text-xs">
                        <Link to={`/orders/${txn.orderId}`} className="text-accent hover:underline">
                          Order #{txn.orderId}
                        </Link>
                      </td>
                      <td className="py-3 pr-4">
                        <StatusBadge status={txn.status} />
                      </td>
                      <td className="py-3 pr-4 text-xs text-ink-muted">{txn.method ?? '—'}</td>
                      <td className="py-3 pr-4">
                        <Badge tone="neutral">{txn.source}</Badge>
                      </td>
                      <td className="py-3 pr-4 font-mono text-ink">
                        {formatMoney(txn.amount, txn.currency)}
                      </td>
                      <td className="py-3 pr-4 text-xs text-ink-muted">
                        {formatDateTime(txn.createdAt)}
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
