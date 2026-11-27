import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Play, Scale } from 'lucide-react';

import { StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input, Select } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { useOptionalAuth } from '@/hooks/useAuth';
import { formatDateTime, formatInteger } from '@/lib/format';
import { getActiveOrganisationId } from '@/services/api/auth';
import { endpoints } from '@/services/api/endpoints';
import {
  createReconciliationRun,
  listReconciliationItems,
  listReconciliationRuns,
  resolveReconciliationItem,
} from '@/services/api/financeApi';

export function ReconciliationPage() {
  const queryClient = useQueryClient();
  const auth = useOptionalAuth();
  const orgId = auth?.activeOrganisation?.organisationId ?? getActiveOrganisationId() ?? null;
  const role = auth?.activeRole ?? 'owner';
  const canRun = role === 'owner' || role === 'admin' || role === 'operator';
  const canResolve = role === 'owner' || role === 'admin';

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [outcomeFilter, setOutcomeFilter] = useState('');
  const [resolutionFilter, setResolutionFilter] = useState('');
  const [includeProvider, setIncludeProvider] = useState(false);
  const [noteByItem, setNoteByItem] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState<{ tone: 'error' | 'success'; text: string } | null>(null);

  const runsQuery = useQuery({
    queryKey: [endpoints.payments.reconRuns.id, orgId],
    queryFn: () => listReconciliationRuns(),
  });

  const activeRunId = selectedRunId ?? runsQuery.data?.items?.[0]?.id ?? null;

  const itemsQuery = useQuery({
    queryKey: [endpoints.payments.reconItems.id, orgId, activeRunId, outcomeFilter, resolutionFilter],
    queryFn: () =>
      listReconciliationItems(activeRunId!, {
        outcome: outcomeFilter || undefined,
        resolutionStatus: resolutionFilter || undefined,
      }),
    enabled: Boolean(activeRunId),
  });

  const runMutation = useMutation({
    mutationFn: () => createReconciliationRun({ provider: 'razorpay', currency: 'INR', include_provider_fetch: includeProvider }),
    onSuccess: (run) => {
      setSelectedRunId(run.id);
      setFeedback({
        tone: 'success',
        text: `Run ${run.runReference} completed: ${run.matchedCount} matched, ${run.exceptionCount} exception(s).`,
      });
      void queryClient.invalidateQueries({ queryKey: [endpoints.payments.reconRuns.id, orgId] });
      void queryClient.invalidateQueries({ queryKey: [endpoints.payments.overview.id, orgId] });
    },
    onError: (err: Error) => setFeedback({ tone: 'error', text: err.message }),
  });

  const resolveMutation = useMutation({
    mutationFn: ({ id, status, note }: { id: string; status: 'ACKNOWLEDGED' | 'RESOLVED'; note: string }) => {
      if (note.trim().length < 3) throw new Error('Enter a resolution note (min 3 chars).');
      return resolveReconciliationItem(id, { resolution_status: status, resolution_note: note.trim() });
    },
    onSuccess: (item) => {
      setFeedback({ tone: 'success', text: `Exception #${item.id} marked ${item.resolutionStatus}.` });
      void queryClient.invalidateQueries({ queryKey: [endpoints.payments.reconItems.id, orgId, activeRunId] });
      void queryClient.invalidateQueries({ queryKey: [endpoints.payments.overview.id, orgId] });
    },
    onError: (err: Error) => setFeedback({ tone: 'error', text: err.message }),
  });

  const runs = runsQuery.data?.items ?? [];
  const items = itemsQuery.data?.items ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Reconciliation"
        description="Deterministic verification across orders, payment transactions, Razorpay records, refunds, and settlements. Discrepancies never auto-mutate financial rows."
        actions={
          canRun && (
            <div className="flex items-center gap-3">
              <label className="inline-flex items-center gap-1.5 text-xs text-ink-muted">
                <input
                  type="checkbox"
                  checked={includeProvider}
                  onChange={(e) => setIncludeProvider(e.target.checked)}
                />
                Fetch Razorpay records
              </label>
              <Button
                variant="primary"
                icon={<Play className="h-4 w-4" />}
                loading={runMutation.isPending}
                onClick={() => runMutation.mutate()}
              >
                Run Reconciliation
              </Button>
            </div>
          )
        }
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

      <Panel>
        <PanelHeader title="Reconciliation runs" badge={<Scale className="h-4 w-4 text-accent" aria-hidden />} />
        <PanelBody>
          {runsQuery.isLoading ? (
            <p className="text-sm text-ink-muted">Loading reconciliation runs...</p>
          ) : runs.length === 0 ? (
            <p className="py-6 text-center text-sm text-ink-muted">No reconciliation runs executed yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase text-ink-muted">
                    <th className="py-2 pr-4">Run Ref</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Checked</th>
                    <th className="py-2 pr-4">Matched</th>
                    <th className="py-2 pr-4">Exceptions</th>
                    <th className="py-2 pr-4">Completed</th>
                    <th className="py-2 text-right">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {runs.map((r) => (
                    <tr key={r.id} className={activeRunId === r.id ? 'bg-surface-raised/70' : ''}>
                      <td className="py-2.5 pr-4 font-mono text-xs">{r.runReference}</td>
                      <td className="py-2.5 pr-4">
                        <StatusBadge status={r.status} />
                      </td>
                      <td className="py-2.5 pr-4 font-mono">{formatInteger(r.totalChecked)}</td>
                      <td className="py-2.5 pr-4 font-mono text-success">{formatInteger(r.matchedCount)}</td>
                      <td className="py-2.5 pr-4 font-mono text-danger">{formatInteger(r.exceptionCount)}</td>
                      <td className="py-2.5 pr-4 text-xs text-ink-muted">{formatDateTime(r.completedAt)}</td>
                      <td className="py-2.5 text-right">
                        <Button size="sm" variant="secondary" onClick={() => setSelectedRunId(r.id)}>
                          Items
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

      {activeRunId && (
        <Panel>
          <PanelHeader
            title={`Reconciliation run #${activeRunId} findings`}
            actions={
              <div className="flex flex-wrap gap-2">
                <Select aria-label="Filter outcome" value={outcomeFilter} onChange={(e) => setOutcomeFilter(e.target.value)} className="w-44">
                  <option value="">All outcomes</option>
                  <option value="MATCHED">Matched</option>
                  <option value="MISSING_IN_PROVIDER">Missing in Provider</option>
                  <option value="MISSING_IN_FLASHCORE">Missing in FLASHCORE</option>
                  <option value="AMOUNT_MISMATCH">Amount Mismatch</option>
                  <option value="CURRENCY_MISMATCH">Currency Mismatch</option>
                  <option value="STATUS_MISMATCH">Status Mismatch</option>
                  <option value="REFUND_MISMATCH">Refund Mismatch</option>
                  <option value="SETTLEMENT_MISMATCH">Settlement Mismatch</option>
                  <option value="DUPLICATE">Duplicate</option>
                  <option value="NEEDS_REVIEW">Needs Review</option>
                </Select>
                <Select aria-label="Filter resolution" value={resolutionFilter} onChange={(e) => setResolutionFilter(e.target.value)} className="w-40">
                  <option value="">All resolutions</option>
                  <option value="UNRESOLVED">Unresolved</option>
                  <option value="ACKNOWLEDGED">Acknowledged</option>
                  <option value="RESOLVED">Resolved</option>
                </Select>
              </div>
            }
          />
          <PanelBody>
            {itemsQuery.isLoading ? (
              <p className="text-sm text-ink-muted">Loading findings...</p>
            ) : items.length === 0 ? (
              <p className="py-6 text-center text-sm text-ink-muted">No reconciliation findings match filters.</p>
            ) : (
              <div className="space-y-2">
                {items.map((it) => (
                  <div key={it.id} className="rounded border border-line bg-canvas p-3 text-xs space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <StatusBadge status={it.outcome} />
                        <span className="font-mono text-ink">{it.entityType} • {it.providerRef ?? `Order #${it.orderId ?? '—'}`}</span>
                      </div>
                      <StatusBadge status={it.resolutionStatus} />
                    </div>
                    <div className="text-ink-muted">
                      Expected: {it.expectedAmountMinor ?? '—'} {it.expectedCurrency ?? ''} ({it.expectedStatus ?? '—'}) • Actual:{' '}
                      {it.actualAmountMinor ?? '—'} {it.actualCurrency ?? ''} ({it.actualStatus ?? '—'})
                    </div>
                    {it.outcome !== 'MATCHED' && it.resolutionStatus !== 'RESOLVED' && canResolve && (
                      <div className="flex flex-wrap items-center gap-2 pt-1">
                        <Input
                          aria-label={`Resolution note for item ${it.id}`}
                          placeholder="Audit resolution note..."
                          value={noteByItem[it.id] ?? ''}
                          onChange={(e) => setNoteByItem((prev) => ({ ...prev, [it.id]: e.target.value }))}
                          className="max-w-sm"
                        />
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() =>
                            resolveMutation.mutate({
                              id: it.id,
                              status: 'RESOLVED',
                              note: noteByItem[it.id] ?? '',
                            })
                          }
                        >
                          Resolve
                        </Button>
                      </div>
                    )}
                    {it.resolutionNote && (
                      <div className="text-ink-faint">Resolution note: {it.resolutionNote}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </PanelBody>
        </Panel>
      )}
    </div>
  );
}
