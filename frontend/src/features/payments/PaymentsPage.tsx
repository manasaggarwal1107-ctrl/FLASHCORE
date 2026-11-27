import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Download, Search, Settings } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input, Select } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { useOptionalAuth } from '@/hooks/useAuth';
import { formatDateTime, formatInteger } from '@/lib/format';
import { formatMoney } from '@/lib/money';
import { getActiveOrganisationId } from '@/services/api/auth';
import { listPaymentTransactions } from '@/services/api/commerceApi';
import { endpoints } from '@/services/api/endpoints';
import { exportFinanceCsv, getFinanceOverview } from '@/services/api/financeApi';

export function PaymentsPage() {
  const auth = useOptionalAuth();
  const orgId = auth?.activeOrganisation?.organisationId ?? getActiveOrganisationId() ?? null;
  const role = auth?.activeRole ?? 'owner';
  const canExport = role === 'owner' || role === 'admin' || role === 'analyst';
  const canRefund = role === 'owner' || role === 'admin' || role === 'operator';

  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [exportError, setExportError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const overviewQuery = useQuery({
    queryKey: [endpoints.payments.overview.id, orgId, fromDate, toDate],
    queryFn: () =>
      getFinanceOverview({
        currency: 'INR',
        fromDate: fromDate ? new Date(`${fromDate}T00:00:00Z`).toISOString() : undefined,
        toDate: toDate ? new Date(`${toDate}T23:59:59Z`).toISOString() : undefined,
      }),
  });

  const txnsQuery = useQuery({
    queryKey: [endpoints.payments.transactions.id, orgId, statusFilter],
    queryFn: () => listPaymentTransactions({ status: statusFilter || undefined }),
  });

  const items = useMemo(() => {
    const rows = txnsQuery.data?.items ?? [];
    const term = search.trim().toLowerCase();
    if (!term) return rows;
    return rows.filter((t) =>
      [t.providerPaymentId, t.orderId, t.method ?? '', t.status].some((v) =>
        v.toLowerCase().includes(term),
      ),
    );
  }, [txnsQuery.data?.items, search]);

  async function handleExport() {
    setExportError(null);
    setExporting(true);
    try {
      const csv = await exportFinanceCsv({
        currency: 'INR',
        fromDate: fromDate ? new Date(`${fromDate}T00:00:00Z`).toISOString() : undefined,
        toDate: toDate ? new Date(`${toDate}T23:59:59Z`).toISOString() : undefined,
      });
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'flashcore-financial-report.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError((err as Error)?.message || 'Failed to export report.');
    } finally {
      setExporting(false);
    }
  }

  const ov = overviewQuery.data;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Financial Operations"
        description="Real tenant-scoped ledger separating captured collections, refunds, settlements, and reconciliation exceptions."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {canExport && (
              <Button
                variant="secondary"
                icon={<Download className="h-4 w-4" />}
                loading={exporting}
                onClick={() => void handleExport()}
              >
                Export CSV
              </Button>
            )}
            <Link
              to="/settings"
              className="inline-flex h-9 items-center gap-2 rounded border border-line-strong bg-surface-raised px-3 text-sm font-medium text-ink hover:bg-surface-overlay"
            >
              <Settings className="h-4 w-4" aria-hidden />
              Gateway Config
            </Link>
          </div>
        }
      />

      {exportError && (
        <div role="alert" className="rounded border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
          {exportError}
        </div>
      )}

      <Panel>
        <PanelHeader
          title="Financial position summary (INR)"
          description="Captured gateway collections and settled bank payouts are tracked independently."
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Input
                type="date"
                aria-label="Overview from date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="w-36"
              />
              <Input
                type="date"
                aria-label="Overview to date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="w-36"
              />
            </div>
          }
        />
        <PanelBody>
          {overviewQuery.isLoading ? (
            <p className="text-sm text-ink-muted">Loading financial metrics...</p>
          ) : overviewQuery.isError ? (
            <div role="alert" className="rounded border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
              {(overviewQuery.error as Error)?.message || 'Failed to load financial overview.'}
            </div>
          ) : ov ? (
            <div className="grid gap-3 md:grid-cols-4">
              <div className="rounded border border-line bg-canvas p-3">
                <div className="text-xs uppercase text-ink-muted">Gross Captured Collections</div>
                <div className="mt-1 font-mono text-lg font-semibold text-ink">
                  {formatMoney(ov.grossCaptured, ov.currency)}
                </div>
                <div className="mt-1 text-xs text-ink-muted">
                  {formatInteger(ov.successfulPaymentCount)} captured • {formatInteger(ov.failedPaymentCount)} failed
                </div>
              </div>
              <div className="rounded border border-line bg-canvas p-3">
                <div className="text-xs uppercase text-ink-muted">Processed Refunds</div>
                <div className="mt-1 font-mono text-lg font-semibold text-warning">
                  {formatMoney(ov.totalRefunded, ov.currency)}
                </div>
                <div className="mt-1 text-xs text-ink-muted">
                  {formatInteger(ov.fullRefundCount)} full • {formatInteger(ov.partialRefundCount)} partial • Pending:{' '}
                  {formatMoney(ov.pendingRefund, ov.currency)} ({formatInteger(ov.pendingRefundCount)})
                </div>
              </div>
              <div className="rounded border border-line bg-canvas p-3">
                <div className="text-xs uppercase text-ink-muted">Net Bank Settlements</div>
                <div className="mt-1 font-mono text-lg font-semibold text-success">
                  {formatMoney(ov.netSettlements, ov.currency)}
                </div>
                <div className="mt-1 text-xs text-ink-muted">
                  Gross: {formatMoney(ov.grossSettlements, ov.currency)} • Fees: {formatMoney(ov.gatewayFees, ov.currency)} • Tax:{' '}
                  {formatMoney(ov.gatewayTax, ov.currency)}
                </div>
              </div>
              <div className="rounded border border-line bg-canvas p-3">
                <div className="text-xs uppercase text-ink-muted">Unsettled Captured Balance</div>
                <div className="mt-1 font-mono text-lg font-semibold text-accent">
                  {formatMoney(ov.unsettledCaptured, ov.currency)}
                </div>
                <div className="mt-1 text-xs text-ink-muted">
                  Recon exceptions: {formatInteger(ov.reconciliationExceptionsCount)} • Links: {formatInteger(ov.activePaymentLinksCount)} active /{' '}
                  {formatInteger(ov.paidPaymentLinksCount)} paid
                </div>
              </div>
            </div>
          ) : null}

          <div className="mt-4 flex flex-wrap gap-2">
            <Link to="/refunds" className="inline-flex items-center gap-1 rounded border border-line px-3 py-1.5 text-xs font-medium text-ink hover:bg-surface-raised">
              Manage Refunds <ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link to="/payment-links" className="inline-flex items-center gap-1 rounded border border-line px-3 py-1.5 text-xs font-medium text-ink hover:bg-surface-raised">
              Payment Links <ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link to="/settlements" className="inline-flex items-center gap-1 rounded border border-line px-3 py-1.5 text-xs font-medium text-ink hover:bg-surface-raised">
              Settlements <ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link to="/reconciliation" className="inline-flex items-center gap-1 rounded border border-line px-3 py-1.5 text-xs font-medium text-ink hover:bg-surface-raised">
              Reconciliation <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader
          title="Payment transactions ledger"
          description="Verified payment events from Razorpay test checkout and webhooks."
        />
        <PanelBody>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-1 min-w-[220px] items-center gap-2 rounded border border-line-strong bg-canvas px-3 h-9">
              <Search className="h-4 w-4 text-ink-muted" aria-hidden />
              <input
                type="search"
                aria-label="Search payment transactions"
                placeholder="Search payment ID, order ID, or method..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-transparent text-sm text-ink placeholder:text-ink-faint focus:outline-none"
              />
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
              No payment transactions recorded yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase text-ink-muted">
                    <th className="py-2 pr-4">Payment ID</th>
                    <th className="py-2 pr-4">Order</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Method</th>
                    <th className="py-2 pr-4">Source</th>
                    <th className="py-2 pr-4">Amount</th>
                    <th className="py-2 pr-4">Recorded</th>
                    {canRefund && <th className="py-2 text-right">Action</th>}
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
                      {canRefund && (
                        <td className="py-3 text-right">
                          {txn.status === 'CAPTURED' && (
                            <Link
                              to={`/refunds?transactionId=${txn.id}`}
                              className="inline-flex h-7 items-center rounded border border-line-strong px-2.5 text-xs font-medium text-ink hover:bg-surface-raised"
                            >
                              Issue refund
                            </Link>
                          )}
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
