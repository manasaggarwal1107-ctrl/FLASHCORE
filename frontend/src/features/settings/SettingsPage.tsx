import { useState } from 'react';
import { Monitor, Moon, Sun } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useOptionalTheme } from '@/components/layout/ThemeProvider';
import type { ThemePreference } from '@/components/layout/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { FormField, Input } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { GatewaySettingsPanel } from '@/features/payments/GatewaySettingsPanel';
import { DetailList } from '@/features/shared/DetailList';
import { useAuthToken } from '@/hooks/useAuthToken';
import { cn } from '@/lib/cn';
import { config } from '@/lib/config';
import { setAuthToken } from '@/services/api/auth';
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
    </div>
  );
}
