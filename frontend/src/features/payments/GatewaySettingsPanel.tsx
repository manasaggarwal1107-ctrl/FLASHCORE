import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { KeyRound, ShieldCheck } from 'lucide-react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { FormField, Input } from '@/components/ui/Field';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { DetailList } from '@/features/shared/DetailList';
import { useOptionalAuth } from '@/hooks/useAuth';
import { formatDateTime } from '@/lib/format';
import { getActiveOrganisationId } from '@/services/api/auth';
import { listGatewayAccounts, upsertRazorpayGateway } from '@/services/api/commerceApi';
import { endpoints } from '@/services/api/endpoints';

export function GatewaySettingsPanel() {
  const queryClient = useQueryClient();
  const auth = useOptionalAuth();
  const orgId = auth?.activeOrganisation?.organisationId ?? getActiveOrganisationId() ?? null;
  const role = auth?.activeRole ?? 'owner';
  const isAdminOrOwner = role === 'owner' || role === 'admin';

  const [keyId, setKeyId] = useState('');
  const [keySecret, setKeySecret] = useState('');
  const [webhookSecret, setWebhookSecret] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  const accountsQuery = useQuery({
    queryKey: [endpoints.payments.accounts.id, orgId],
    queryFn: listGatewayAccounts,
    enabled: isAdminOrOwner,
  });

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!keyId.trim().startsWith('rzp_test_')) {
        throw new Error('Only Razorpay test keys starting with rzp_test_ are allowed in Stage 3.');
      }
      if (keySecret.trim().length < 8 || webhookSecret.trim().length < 8) {
        throw new Error('Key secret and webhook secret must each be at least 8 characters.');
      }
      return upsertRazorpayGateway({
        mode: 'test',
        key_id: keyId.trim(),
        key_secret: keySecret.trim(),
        webhook_secret: webhookSecret.trim(),
        status: 'active',
      });
    },
    onSuccess: () => {
      setKeySecret('');
      setWebhookSecret('');
      setErrorMsg(null);
      setSavedMsg('Razorpay test-mode credentials encrypted and saved.');
      void queryClient.invalidateQueries({ queryKey: [endpoints.payments.accounts.id, orgId] });
    },
    onError: (err: Error) => {
      setSavedMsg(null);
      setErrorMsg(err.message || 'Unable to save Razorpay gateway configuration.');
    },
  });

  const razorpayAccount = (accountsQuery.data ?? []).find((a) => a.provider === 'razorpay');

  return (
    <Panel>
      <PanelHeader
        title="Payment Gateway — Razorpay (Test Mode)"
        description="Per-organisation AES-256-GCM encrypted test-mode credentials. Live keys and plaintext secret retrieval are blocked."
        badge={
          <Badge tone={razorpayAccount ? 'success' : 'warning'}>
            {razorpayAccount ? 'Test Mode Active' : 'Not Configured'}
          </Badge>
        }
      />
      <PanelBody className="space-y-4">
        {!isAdminOrOwner ? (
          <div className="rounded border border-line bg-surface-raised p-3 text-xs text-ink-muted">
            Only organisation owners and admins can view or update Razorpay gateway credentials.
          </div>
        ) : (
          <>
            {razorpayAccount && (
              <DetailList
                columns={3}
                items={[
                  { label: 'Provider', value: razorpayAccount.provider },
                  { label: 'Mode', value: razorpayAccount.mode },
                  { label: 'Key ID', value: razorpayAccount.keyId, mono: true },
                  {
                    label: 'Key Secret',
                    value: razorpayAccount.hasKeySecret ? 'Encrypted on server' : 'Missing',
                  },
                  {
                    label: 'Webhook Secret',
                    value: razorpayAccount.hasWebhookSecret ? 'Encrypted on server' : 'Missing',
                  },
                  { label: 'Updated', value: formatDateTime(razorpayAccount.updatedAt) },
                ]}
              />
            )}

            <div className="flex items-start gap-2 rounded border border-accent/25 bg-accent/5 p-3 text-xs text-ink-muted">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden />
              <div>
                Webhook endpoint URL: <code className="font-mono text-ink">/api/v1/webhooks/razorpay</code>
                <div className="mt-0.5 text-ink-faint">
                  Subscribe to <code className="font-mono">payment.authorized</code>,{' '}
                  <code className="font-mono">payment.captured</code>, and{' '}
                  <code className="font-mono">payment.failed</code> in Razorpay Test Dashboard.
                </div>
              </div>
            </div>

            <form
              className="grid gap-3 md:grid-cols-3"
              onSubmit={(e) => {
                e.preventDefault();
                setErrorMsg(null);
                setSavedMsg(null);
                saveMutation.mutate();
              }}
            >
              <FormField label="Razorpay Test Key ID">
                {(p) => (
                  <Input
                    {...p}
                    placeholder="rzp_test_..."
                    autoComplete="off"
                    value={keyId}
                    onChange={(e) => setKeyId(e.target.value)}
                  />
                )}
              </FormField>
              <FormField label="Razorpay Key Secret">
                {(p) => (
                  <Input
                    {...p}
                    type="password"
                    autoComplete="new-password"
                    placeholder="Enter secret (never echoed back)"
                    value={keySecret}
                    onChange={(e) => setKeySecret(e.target.value)}
                  />
                )}
              </FormField>
              <FormField label="Razorpay Webhook Secret">
                {(p) => (
                  <Input
                    {...p}
                    type="password"
                    autoComplete="new-password"
                    placeholder="Webhook signing secret"
                    value={webhookSecret}
                    onChange={(e) => setWebhookSecret(e.target.value)}
                  />
                )}
              </FormField>

              {errorMsg && (
                <div role="alert" className="md:col-span-3 rounded border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
                  {errorMsg}
                </div>
              )}
              {savedMsg && (
                <div role="status" className="md:col-span-3 rounded border border-success/40 bg-success/10 px-3 py-2 text-xs text-success">
                  {savedMsg}
                </div>
              )}

              <div className="md:col-span-3 flex justify-end">
                <Button
                  type="submit"
                  variant="primary"
                  icon={<KeyRound className="h-4 w-4" />}
                  loading={saveMutation.isPending}
                >
                  Save Razorpay Test Credentials
                </Button>
              </div>
            </form>
          </>
        )}
      </PanelBody>
    </Panel>
  );
}
