import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { RefreshCw, Upload } from 'lucide-react';

import { StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { FormField, Input } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { useOptionalAuth } from '@/hooks/useAuth';
import { formatDateTime } from '@/lib/format';
import { formatMoney } from '@/lib/money';
import { getActiveOrganisationId } from '@/services/api/auth';
import { endpoints } from '@/services/api/endpoints';
import {
  getSettlement,
  importSettlementStatement,
  listSettlements,
  syncSettlements,
} from '@/services/api/financeApi';

export function SettlementsPage() {
  const queryClient = useQueryClient();
  const auth = useOptionalAuth();
  const orgId = auth?.activeOrganisation?.organisationId ?? getActiveOrganisationId() ?? null;
  const role = auth?.activeRole ?? 'owner';
  const isAdminOrOwner = role === 'owner' || role === 'admin';

  const [filename, setFilename] = useState('statement.csv');
  const [csvContent, setCsvContent] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: 'info' | 'error' | 'success'; text: string } | null>(null);

  const settlementsQuery = useQuery({
    queryKey: [endpoints.payments.settlements.id, orgId],
    queryFn: () => listSettlements(),
  });

  const detailQuery = useQuery({
    queryKey: [endpoints.payments.settlement.id, orgId, selectedId],
    queryFn: () => getSettlement(selectedId!),
    enabled: Boolean(selectedId),
  });

  const syncMutation = useMutation({
    mutationFn: syncSettlements,
    onSuccess: (res) => {
      setNotice({
        tone: res.status === 'capability_unavailable' ? 'info' : 'success',
        text: res.message,
      });
      void queryClient.invalidateQueries({ queryKey: [endpoints.payments.settlements.id, orgId] });
      void queryClient.invalidateQueries({ queryKey: [endpoints.payments.overview.id, orgId] });
    },
    onError: (err: Error) => setNotice({ tone: 'error', text: err.message }),
  });

  const importMutation = useMutation({
    mutationFn: () => {
      if (!csvContent.trim()) throw new Error('Select a CSV file or paste settlement CSV rows.');
      return importSettlementStatement({ filename: filename.trim() || 'statement.csv', csv_content: csvContent });
    },
    onSuccess: (res) => {
      setCsvContent('');
      setNotice({
        tone: 'success',
        text: res.idempotentReplay
          ? `Statement '${res.filename}' was already imported (hash ${res.fileHash.slice(0, 12)}).`
          : `Imported ${res.settlementsCreated} settlement(s) from '${res.filename}'.`,
      });
      void queryClient.invalidateQueries({ queryKey: [endpoints.payments.settlements.id, orgId] });
      void queryClient.invalidateQueries({ queryKey: [endpoints.payments.overview.id, orgId] });
    },
    onError: (err: Error) => setNotice({ tone: 'error', text: err.message }),
  });

  const settlements = settlementsQuery.data?.items ?? [];
  const detail = detailQuery.data;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Settlements"
        description="Bank payouts, gateway fees, taxes, and validated settlement CSV imports—tracked strictly separately from captured checkout amounts."
        actions={
          isAdminOrOwner && (
            <Button
              variant="secondary"
              icon={<RefreshCw className="h-4 w-4" />}
              loading={syncMutation.isPending}
              onClick={() => syncMutation.mutate()}
            >
              Sync from Razorpay
            </Button>
          )
        }
      />

      {notice && (
        <div
          role={notice.tone === 'error' ? 'alert' : 'status'}
          className={`rounded border px-3 py-2 text-xs ${
            notice.tone === 'error'
              ? 'border-danger/40 bg-danger/10 text-danger'
              : notice.tone === 'success'
                ? 'border-success/40 bg-success/10 text-success'
                : 'border-accent/30 bg-accent/10 text-ink'
          }`}
        >
          {notice.text}
        </div>
      )}

      {isAdminOrOwner && (
        <Panel>
          <PanelHeader
            title="Import validated settlement statement (CSV)"
            description="Requires exact columns: provider_settlement_id, status, gross_amount_minor, refund_amount_minor, fee_minor, tax_minor, adjustment_minor, net_amount_minor, currency."
          />
          <PanelBody>
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                setNotice(null);
                importMutation.mutate();
              }}
            >
              <div className="grid gap-3 md:grid-cols-2">
                <FormField label="Filename (.csv)">
                  {(p) => <Input {...p} value={filename} onChange={(e) => setFilename(e.target.value)} />}
                </FormField>
                <FormField label="Upload CSV file (optional)">
                  {(p) => (
                    <Input
                      {...p}
                      type="file"
                      accept=".csv,text/csv"
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        setFilename(file.name);
                        setCsvContent(await file.text());
                      }}
                    />
                  )}
                </FormField>
              </div>
              <textarea
                aria-label="Settlement CSV content"
                rows={4}
                placeholder="Paste settlement CSV rows here..."
                value={csvContent}
                onChange={(e) => setCsvContent(e.target.value)}
                className="w-full rounded border border-line-strong bg-canvas p-2 font-mono text-xs text-ink placeholder:text-ink-faint"
              />
              <Button type="submit" variant="primary" icon={<Upload className="h-4 w-4" />} loading={importMutation.isPending}>
                Validate & Import Statement
              </Button>
            </form>
          </PanelBody>
        </Panel>
      )}

      <Panel>
        <PanelHeader title="Recorded settlements" />
        <PanelBody>
          {settlementsQuery.isLoading ? (
            <p className="text-sm text-ink-muted">Loading settlements...</p>
          ) : settlements.length === 0 ? (
            <p className="py-6 text-center text-sm text-ink-muted">
              No bank settlement records recorded yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase text-ink-muted">
                    <th className="py-2 pr-4">Settlement ID</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Gross</th>
                    <th className="py-2 pr-4">Fees & Tax</th>
                    <th className="py-2 pr-4">Net Payout</th>
                    <th className="py-2 pr-4">Source</th>
                    <th className="py-2 pr-4">UTR</th>
                    <th className="py-2 text-right">Items</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {settlements.map((s) => (
                    <tr key={s.id}>
                      <td className="py-2.5 pr-4 font-mono text-xs">{s.providerSettlementId}</td>
                      <td className="py-2.5 pr-4">
                        <StatusBadge status={s.status} />
                      </td>
                      <td className="py-2.5 pr-4 font-mono">{formatMoney(s.grossAmount, s.currency)}</td>
                      <td className="py-2.5 pr-4 font-mono text-xs text-ink-muted">
                        {formatMoney(s.fee, s.currency)} + {formatMoney(s.tax, s.currency)}
                      </td>
                      <td className="py-2.5 pr-4 font-mono font-semibold text-success">
                        {formatMoney(s.netAmount, s.currency)}
                      </td>
                      <td className="py-2.5 pr-4 text-xs">{s.source}</td>
                      <td className="py-2.5 pr-4 font-mono text-xs text-ink-muted">{s.settlementUtr ?? '—'}</td>
                      <td className="py-2.5 text-right">
                        <Button size="sm" variant="secondary" onClick={() => setSelectedId(s.id)}>
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

      {detail && (
        <Panel>
          <PanelHeader title={`Settlement ${detail.providerSettlementId} items`} description={`Settled at: ${formatDateTime(detail.settledAt)}`} />
          <PanelBody>
            {!detail.items || detail.items.length === 0 ? (
              <p className="text-xs text-ink-muted">No line-level transaction items attached to this settlement.</p>
            ) : (
              <div className="space-y-2">
                {detail.items.map((it) => (
                  <div key={it.id} className="flex flex-wrap items-center justify-between gap-2 rounded border border-line bg-canvas px-3 py-2 text-xs">
                    <span className="font-mono">{it.entityType} • {it.providerEntityId ?? '—'}</span>
                    <span className="font-mono">Net: {formatMoney(it.netAmount, it.currency)}</span>
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
