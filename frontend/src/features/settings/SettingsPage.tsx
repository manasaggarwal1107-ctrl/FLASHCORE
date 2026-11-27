import { useContext, useEffect, useState } from 'react';
import { Monitor, Moon, Sun } from 'lucide-react';
import { QueryClientContext, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useOptionalTheme } from '@/components/layout/ThemeProvider';
import type { ThemePreference } from '@/components/layout/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { FormField, Input, Select } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { GatewaySettingsPanel } from '@/features/payments/GatewaySettingsPanel';
import { DetailList } from '@/features/shared/DetailList';
import { useOptionalAuth } from '@/hooks/useAuth';
import { useAuthToken } from '@/hooks/useAuthToken';
import { cn } from '@/lib/cn';
import { config } from '@/lib/config';
import { setAuthToken } from '@/services/api/auth';
import { expansionApi } from '@/services/api/expansionApi';
import { tokenSchema } from './tokenSchema';
import type { TokenFormValues } from './tokenSchema';

const THEME_MODES: Array<{
  value: ThemePreference;
  label: string;
  description: string;
  icon: typeof Sun;
}> = [
  { value: 'light', label: 'Light', description: 'Crisp bright workspace', icon: Sun },
  { value: 'dark', label: 'Dark', description: 'Low-glare dark workspace', icon: Moon },
  { value: 'system', label: 'System default', description: 'Follow OS appearance', icon: Monitor },
];

export function SettingsPage() {
  const token = useAuthToken();
  const [saved, setSaved] = useState(false);
  const themeCtx = useOptionalTheme();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<TokenFormValues>({ resolver: zodResolver(tokenSchema) });

  const preference = themeCtx?.preference ?? 'dark';
  const activeTheme = themeCtx?.theme ?? 'dark';
  const systemTheme = themeCtx?.systemTheme ?? 'dark';
  const themeSummary =
    preference === 'system'
      ? `System default (${activeTheme})`
      : preference === 'light'
        ? 'Light'
        : 'Dark';

  return (
    <div>
      <PageHeader title="Settings" description="Connection credentials, appearance, and application configuration." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="API credentials" badge={<Badge tone={token ? 'success' : 'neutral'}>{token ? 'Token set' : 'No token'}</Badge>} />
          <PanelBody>
            <p className="mb-4 text-xs text-ink-muted">
              The token is kept in this browser tab’s session storage only and is sent as a Bearer token. The authentication scheme is pending confirmation in the API contract.
            </p>
            <form
              noValidate
              className="space-y-3"
              onSubmit={handleSubmit((v) => {
                setAuthToken(v.token);
                reset({ token: '' });
                setSaved(true);
              })}
            >
              <FormField label="Bearer token" error={errors.token?.message}>
                {(p) => <Input {...p} type="password" autoComplete="off" spellCheck={false} {...register('token')} />}
              </FormField>
              <div className="flex items-center gap-2">
                <Button type="submit" variant="primary">
                  Save token
                </Button>
                <Button
                  variant="danger"
                  disabled={!token}
                  onClick={() => {
                    setAuthToken(null);
                    setSaved(false);
                  }}
                >
                  Clear token
                </Button>
                {saved && token && (
                  <span role="status" className="text-xs text-success">
                    Saved for this session
                  </span>
                )}
              </div>
            </form>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="Application" description="Set at build time via environment variables" />
          <PanelBody>
            <DetailList
              columns={2}
              items={[
                { label: 'Environment', value: config.environment },
                { label: 'Version', value: config.appVersion },
                { label: 'API base URL', value: config.apiBaseUrl, mono: true },
                { label: 'Request timeout', value: `${config.apiTimeoutMs} ms` },
                { label: 'Theme', value: themeSummary },
              ]}
            />
          </PanelBody>
        </Panel>
      </div>

      <div className="mt-4">
        <Panel>
          <PanelHeader
            title="Appearance"
            description="Choose Light, Dark, or follow your operating system preference."
            badge={<Badge tone="accent">Active: {activeTheme}</Badge>}
          />
          <PanelBody>
            <div
              role="radiogroup"
              aria-label="Theme preference"
              className="grid gap-3 sm:grid-cols-3"
            >
              {THEME_MODES.map((mode) => {
                const Icon = mode.icon;
                const selected = preference === mode.value;
                return (
                  <button
                    key={mode.value}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    disabled={!themeCtx}
                    onClick={() => themeCtx?.setTheme(mode.value)}
                    className={cn(
                      'flex items-start gap-3 rounded-md border p-3 text-left transition-colors',
                      selected
                        ? 'border-accent bg-accent/10 text-ink'
                        : 'border-line bg-surface-raised/60 text-ink-muted hover:border-line-strong hover:text-ink',
                    )}
                  >
                    <span
                      className={cn(
                        'mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded border',
                        selected
                          ? 'border-accent/40 bg-accent/15 text-accent'
                          : 'border-line bg-surface text-ink-faint',
                      )}
                    >
                      <Icon className="h-4 w-4" aria-hidden />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-medium text-ink">
                        {mode.label}
                      </span>
                      <span className="mt-0.5 block text-xs text-ink-muted">
                        {mode.value === 'system'
                          ? `${mode.description} (${systemTheme})`
                          : mode.description}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
            <p className="mt-3 text-xs text-ink-faint">
              Preference is saved locally in this browser. The navigation sidebar remains dark across all themes for visual hierarchy.
            </p>
          </PanelBody>
        </Panel>
      </div>

      <div className="mt-4">
        <GatewaySettingsPanel />
      </div>

      <IndiaTaxProfileSection />
    </div>
  );
}

function IndiaTaxProfileSection() {
  const hasQueryClient = Boolean(useContext(QueryClientContext));
  const auth = useOptionalAuth();
  if (!hasQueryClient) return null;
  return <IndiaTaxProfileForm enabled={Boolean(auth?.user)} />;
}

function IndiaTaxProfileForm({ enabled }: { enabled: boolean }) {
  const qc = useQueryClient();
  const [legalName, setLegalName] = useState('');
  const [gstin, setGstin] = useState('');
  const [stateCode, setStateCode] = useState('27');
  const [regType, setRegType] = useState<'regular' | 'composition' | 'unregistered'>('regular');
  const [invPrefix, setInvPrefix] = useState('INV');
  const [fyCode, setFyCode] = useState('2627');
  const [allowNeg, setAllowNeg] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const profQ = useQuery({
    queryKey: ['tax.profile'],
    queryFn: expansionApi.getTaxProfile,
    enabled,
  });

  useEffect(() => {
    if (!profQ.data) return;
    setLegalName(profQ.data.legalName);
    setGstin(profQ.data.gstin ?? '');
    setStateCode(profQ.data.stateCode);
    setRegType(profQ.data.registrationType);
    setInvPrefix(profQ.data.invoicePrefix);
    setFyCode(profQ.data.financialYearCode);
    setAllowNeg(profQ.data.allowNegativeStock);
  }, [profQ.data]);

  const saveMut = useMutation({
    mutationFn: () =>
      expansionApi.updateTaxProfile({
        legal_name: legalName || 'FLASHCORE Retail',
        gstin: gstin || null,
        registration_type: regType,
        state_name: stateCode === '07' ? 'Delhi' : 'Maharashtra',
        state_code: stateCode,
        invoice_prefix: invPrefix,
        financial_year_code: fyCode,
        allow_negative_stock: allowNeg,
      }),
    onSuccess: () => {
      setMsg('India GST & compliance profile saved.');
      void qc.invalidateQueries({ queryKey: ['tax.profile'] });
    },
    onError: (e: Error) => setMsg(e.message),
  });

  if (!enabled) return null;

  return (
    <div className="mt-4">
      <Panel>
        <PanelHeader title="India GST & DPDP Compliance Profile" description="Configurable GSTIN, place-of-supply state code, FY invoice numbering, and negative-stock policy." />
        <PanelBody className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <FormField label="Legal Business Name">{(p) => <Input {...p} value={legalName} onChange={(e) => setLegalName(e.target.value)} />}</FormField>
          <FormField label="GSTIN (15-char)">{(p) => <Input {...p} value={gstin} onChange={(e) => setGstin(e.target.value.toUpperCase())} placeholder="27AABCU9603R1ZM" />}</FormField>
          <FormField label="Registration Type">{(p) => (
            <Select {...p} value={regType} onChange={(e) => setRegType(e.target.value as typeof regType)}>
              <option value="regular">Regular (Tax Invoice)</option>
              <option value="composition">Composition (Bill of Supply)</option>
              <option value="unregistered">Unregistered</option>
            </Select>
          )}</FormField>
          <FormField label="Origin State Code">{(p) => <Input {...p} value={stateCode} onChange={(e) => setStateCode(e.target.value)} placeholder="27" />}</FormField>
          <FormField label="Invoice Prefix">{(p) => <Input {...p} value={invPrefix} onChange={(e) => setInvPrefix(e.target.value.toUpperCase())} />}</FormField>
          <FormField label="Financial Year">{(p) => <Input {...p} value={fyCode} onChange={(e) => setFyCode(e.target.value)} />}</FormField>
          <label className="flex items-center gap-2 text-xs text-ink-muted sm:col-span-2">
            <input type="checkbox" checked={allowNeg} onChange={(e) => setAllowNeg(e.target.checked)} />
            Allow admin-authorized negative stock override during POS checkout
          </label>
          <div className="flex items-center gap-3 sm:col-span-3">
            <Button variant="primary" loading={saveMut.isPending} onClick={() => saveMut.mutate()}>Save Tax Profile</Button>
            {msg && <span className="text-xs text-ink-muted">{msg}</span>}
          </div>
        </PanelBody>
      </Panel>
    </div>
  );
}
