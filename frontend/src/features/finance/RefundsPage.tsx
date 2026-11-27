import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { RefreshCw, ShieldCheck } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';

import { StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { FormField, Input, Select } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { DetailList } from '@/features/shared/DetailList';
import { useOptionalAuth } from '@/hooks/useAuth';
import { formatDateTime } from '@/lib/format';
import { formatMoney } from '@/lib/money';
import { getActiveOrganisationId } from '@/services/api/auth';
import { listPaymentTransactions } from '@/services/api/commerceApi';
import { endpoints } from '@/services/api/endpoints';
import {
  approveRefund,
  getRefund,
  getRefundPolicy,
  listRefunds,
  rejectRefund,
  requestRefund,
  syncRefund,
  updateRefundPolicy,
} from '@/services/api/financeApi';

export function RefundsPage() {
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const auth = useOptionalAuth();
  const orgId = auth?.activeOrganisation?.organisationId ?? getActiveOrganisationId() ?? null;
  const role = auth?.activeRole ?? 'owner';
  const canRequest = role === 'owner' || role === 'admin' || role === 'operator';
  const canApprove = role === 'owner' || role === 'admin';

  const [statusFilter, setStatusFilter] = useState('');
  const [selectedRefundId, setSelectedRefundId] = useState<string | null>(null);
  const [txnId, setTxnId] = useState(searchParams.get('transactionId') ?? '');
  const [amountInr, setAmountInr] = useState('');
  const [reason, setReason] = useState('');
  const [confirmPending, setConfirmPending] = useState(false);
  const [idempKey, setIdempKey] = useState(() => `rf-${Date.now()}`);
  const [feedback, setFeedback] = useState<{ tone: 'error' | 'success'; text: string } | null>(null);
  const [thresholdInr, setThresholdInr] = useState('');
  const [decisionNote, setDecisionNote] = useState('');

  const policyQuery = useQuery({
    queryKey: [endpoints.payments.refundPolicy.id, orgId],
    queryFn: getRefundPolicy,
  });

  const refundsQuery = useQuery({
    queryKey: [endpoints.payments.refunds.id, orgId, statusFilter],
    queryFn: () => listRefunds({ status: statusFilter || undefined }),
  });

  const txnsQuery = useQuery({
    queryKey: [endpoints.payments.transactions.id, orgId, 'refund-picker'],
    queryFn: () => listPaymentTransactions({ status: 'CAPTURED', pageSize: 100 }),
    enabled: canRequest,
  });

  const detailQuery = useQuery({
    queryKey: [endpoints.payments.refund.id, orgId, selectedRefundId],
    queryFn: () => getRefund(selectedRefundId!),
    enabled: Boolean(selectedRefundId),
  });

  const invalidateAll = () => {
    void queryClient.invalidateQueries({ queryKey: [endpoints.payments.refunds.id, orgId] });
    void queryClient.invalidateQueries({ queryKey: [endpoints.payments.overview.id, orgId] });
    if (selectedRefundId) {
      void queryClient.invalidateQueries({ queryKey: [endpoints.payments.refund.id, orgId, selectedRefundId] });
    }
  };

  const requestMutation = useMutation({
    mutationFn: () => {
      if (!txnId) throw new Error('Select a captured payment transaction.');
      if (reason.trim().length < 3) throw new Error('Provide a refund reason (min 3 characters).');
      const amtMinor = amountInr.trim() ? Math.round(Number(amountInr) * 100) : undefined;
      if (amtMinor !== undefined && (!Number.isInteger(amtMinor) || amtMinor <= 0)) {
        throw new Error('Enter a valid positive INR refund amount or leave blank for full balance.');
      }
      return requestRefund(txnId, { amount_minor: amtMinor, reason: reason.trim() }, idempKey);
    },
    onSuccess: (created) => {
      setConfirmPending(false);
      setAmountInr('');
      setReason('');
      setIdempKey(`rf-${Date.now()}`);
      setSelectedRefundId(created.id);
      setFeedback({
        tone: 'success',
        text: `Refund #${created.id} recorded with status ${created.status}.`,
      });
      invalidateAll();
    },
    onError: (err: Error) => {
      setConfirmPending(false);
      setFeedback({ tone: 'error', text: err.message || 'Refund request failed.' });
    },
  });

  const policyMutation = useMutation({
    mutationFn: () => {
      const val = Number(thresholdInr);
      if (!Number.isFinite(val) || val < 0) throw new Error('Threshold must be a non-negative INR amount.');
      return updateRefundPolicy({ refund_approval_threshold_minor: Math.round(val * 100), currency: 'INR' });
    },
    onSuccess: () => {
      setThresholdInr('');
      setFeedback({ tone: 'success', text: 'Refund approval threshold updated.' });
      void queryClient.invalidateQueries({ queryKey: [endpoints.payments.refundPolicy.id, orgId] });
    },
    onError: (err: Error) => setFeedback({ tone: 'error', text: err.message }),
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => approveRefund(id, decisionNote.trim() || undefined),
    onSuccess: (res) => {
      setDecisionNote('');
      setFeedback({ tone: 'success', text: `Refund #${res.id} approved -> ${res.status}.` });
      invalidateAll();
    },
    onError: (err: Error) => setFeedback({ tone: 'error', text: err.message }),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) => rejectRefund(id, decisionNote.trim() || undefined),
    onSuccess: (res) => {
      setDecisionNote('');
      setFeedback({ tone: 'success', text: `Refund #${res.id} rejected.` });
      invalidateAll();
    },
    onError: (err: Error) => setFeedback({ tone: 'error', text: err.message }),
  });

  const syncMutation = useMutation({
    mutationFn: (id: string) => syncRefund(id),
    onSuccess: (res) => {
      setFeedback({ tone: 'success', text: `Refund #${res.id} synced -> ${res.status}.` });
      invalidateAll();
    },
    onError: (err: Error) => setFeedback({ tone: 'error', text: err.message }),
  });

  const capturedTxns = txnsQuery.data?.items ?? [];
  const selectedTxn = capturedTxns.find((t) => t.id === txnId);
  const refunds = refundsQuery.data?.items ?? [];
  const detail = detailQuery.data;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Refunds & Approvals"
        description="Full and partial Razorpay refunds with balance checks, approval thresholds, and gateway sync."
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

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel className="lg:col-span-2">
          <PanelHeader title="Initiate refund" description="Confirmed backend balance validation protects against over-refunds." />
          <PanelBody className="space-y-3">
            {!canRequest ? (
              <p className="text-xs text-ink-muted">Your role is read-only for refund requests.</p>
            ) : (
              <>
                <div className="grid gap-3 md:grid-cols-3">
                  <FormField label="Captured Transaction">
                    {(p) => (
                      <Select {...p} value={txnId} onChange={(e) => { setConfirmPending(false); setTxnId(e.target.value); }}>
                        <option value="">Select captured payment...</option>
                        {capturedTxns.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.providerPaymentId} • {formatMoney(t.amount, t.currency)} (Order #{t.orderId})
                          </option>
                        ))}
                      </Select>
                    )}
                  </FormField>
                  <FormField label="Refund Amount (INR, optional = full)">
                    {(p) => (
                      <Input
                        {...p}
                        type="number"
                        step="0.01"
                        min="0.01"
                        placeholder={selectedTxn ? selectedTxn.amount : 'Full remaining'}
                        value={amountInr}
                        onChange={(e) => { setConfirmPending(false); setAmountInr(e.target.value); }}
                      />
                    )}
                  </FormField>
                  <FormField label="Refund Reason">
                    {(p) => (
                      <Input
                        {...p}
                        placeholder="Customer return / item issue"
                        value={reason}
                        onChange={(e) => { setConfirmPending(false); setReason(e.target.value); }}
                      />
                    )}
                  </FormField>
                </div>

                {!confirmPending ? (
                  <Button
                    variant="primary"
                    onClick={() => {
                      setFeedback(null);
                      if (!txnId || reason.trim().length < 3) {
                        setFeedback({ tone: 'error', text: 'Select a captured transaction and enter a reason.' });
                        return;
                      }
                      setConfirmPending(true);
                    }}
                  >
                    Review Refund Request
                  </Button>
                ) : (
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded border border-warning/40 bg-warning/10 p-3 text-xs">
                    <div>
                      Confirm refund of{' '}
                      <strong className="font-mono">
                        {amountInr.trim() ? `${amountInr} INR` : selectedTxn ? `${selectedTxn.amount} ${selectedTxn.currency}` : 'full remaining'}
                      </strong>{' '}
                      against transaction #{txnId}?
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="secondary" onClick={() => setConfirmPending(false)}>
                        Back
                      </Button>
                      <Button
                        size="sm"
                        variant="primary"
                        loading={requestMutation.isPending}
                        onClick={() => requestMutation.mutate()}
                      >
                        Confirm & Submit Refund
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader
            title="Approval threshold"
            badge={<ShieldCheck className="h-4 w-4 text-accent" aria-hidden />}
          />
          <PanelBody className="space-y-3">
            <div className="text-xs text-ink-muted">
              Current threshold requiring owner/admin approval:{' '}
              <strong className="font-mono text-ink">
                {policyQuery.data
                  ? formatMoney(policyQuery.data.refundApprovalThreshold, policyQuery.data.currency)
                  : 'Loading...'}
              </strong>
            </div>
            {canApprove && (
              <form
                className="flex items-end gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  policyMutation.mutate();
                }}
              >
                <div className="flex-1">
                  <FormField label="New threshold (INR)">
                    {(p) => (
                      <Input
                        {...p}
                        type="number"
                        step="0.01"
                        min="0"
                        placeholder="500.00"
                        value={thresholdInr}
                        onChange={(e) => setThresholdInr(e.target.value)}
                      />
                    )}
                  </FormField>
                </div>
                <Button type="submit" size="sm" variant="secondary" loading={policyMutation.isPending}>
                  Update
                </Button>
              </form>
            )}
          </PanelBody>
        </Panel>
      </div>

      <Panel>
        <PanelHeader
          title="Refund requests & lifecycle"
          actions={
            <div className="w-48">
              <Select aria-label="Filter refund status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="">All statuses</option>
                <option value="APPROVAL_PENDING">Approval Pending</option>
                <option value="PENDING">Pending</option>
                <option value="PROCESSED">Processed</option>
                <option value="FAILED">Failed</option>
                <option value="REJECTED">Rejected</option>
              </Select>
            </div>
          }
        />
        <PanelBody>
          {refundsQuery.isLoading ? (
            <p className="text-sm text-ink-muted">Loading refunds...</p>
          ) : refunds.length === 0 ? (
            <p className="py-6 text-center text-sm text-ink-muted">No refunds recorded yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase text-ink-muted">
                    <th className="py-2 pr-4">Refund #</th>
                    <th className="py-2 pr-4">Provider ID</th>
                    <th className="py-2 pr-4">Type</th>
                    <th className="py-2 pr-4">Amount</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Created</th>
                    <th className="py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {refunds.map((r) => (
                    <tr key={r.id}>
                      <td className="py-2.5 pr-4 font-mono text-xs">#{r.id} (Order #{r.orderId})</td>
                      <td className="py-2.5 pr-4 font-mono text-xs text-ink-muted">{r.providerRefundId ?? 'Awaiting approval'}</td>
                      <td className="py-2.5 pr-4 text-xs">{r.refundType}</td>
                      <td className="py-2.5 pr-4 font-mono">{formatMoney(r.amount, r.currency)}</td>
                      <td className="py-2.5 pr-4">
                        <StatusBadge status={r.status} />
                      </td>
                      <td className="py-2.5 pr-4 text-xs text-ink-muted">{formatDateTime(r.createdAt)}</td>
                      <td className="py-2.5 text-right">
                        <Button size="sm" variant="secondary" onClick={() => setSelectedRefundId(r.id)}>
                          Inspect
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </PanelBody>
      </Panel>

      {detail && (
        <Panel>
          <PanelHeader
            title={`Refund #${detail.id} details`}
            badge={<StatusBadge status={detail.status} />}
            actions={
              detail.providerRefundId && canRequest ? (
                <Button
                  size="sm"
                  variant="secondary"
                  icon={<RefreshCw className="h-3.5 w-3.5" />}
                  loading={syncMutation.isPending}
                  onClick={() => syncMutation.mutate(detail.id)}
                >
                  Sync Status
                </Button>
              ) : null
            }
          />
          <PanelBody className="space-y-4">
            <DetailList
              columns={3}
              items={[
                { label: 'Amount', value: formatMoney(detail.amount, detail.currency), mono: true },
                { label: 'Payment ID', value: detail.providerPaymentId, mono: true },
                { label: 'Provider Refund ID', value: detail.providerRefundId ?? '—', mono: true },
                { label: 'Order ID', value: `#${detail.orderId}`, mono: true },
                { label: 'Reason', value: detail.reason ?? '—' },
                { label: 'Failure Reason', value: detail.failureReason ?? '—' },
              ]}
            />

            {detail.status === 'APPROVAL_PENDING' && canApprove && detail.approvalRequest && (
              <div className="space-y-2 rounded border border-warning/40 bg-warning/10 p-3 text-xs">
                <div className="font-semibold text-ink">
                  High-value approval bound to {formatMoney(detail.approvalRequest.amount, detail.approvalRequest.currency)} (Order #{detail.approvalRequest.orderId})
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Input
                    aria-label="Approval decision note"
                    placeholder="Optional approval or rejection note..."
                    value={decisionNote}
                    onChange={(e) => setDecisionNote(e.target.value)}
                    className="max-w-sm"
                  />
                  <Button
                    size="sm"
                    variant="primary"
                    loading={approveMutation.isPending}
                    onClick={() => approveMutation.mutate(detail.id)}
                  >
                    Approve & Submit {formatMoney(detail.amount, detail.currency)}
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    loading={rejectMutation.isPending}
                    onClick={() => rejectMutation.mutate(detail.id)}
                  >
                    Reject
                  </Button>
                </div>
              </div>
            )}
          </PanelBody>
        </Panel>
      )}
    </div>
  );
}
