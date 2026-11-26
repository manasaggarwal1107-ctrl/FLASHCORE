import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { FormField, Input } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { DetailList } from '@/features/shared/DetailList';
import { useAuthToken } from '@/hooks/useAuthToken';
import { config } from '@/lib/config';
import { setAuthToken } from '@/services/api/auth';
import { tokenSchema } from './tokenSchema';
import type { TokenFormValues } from './tokenSchema';

export function SettingsPage() {
  const token = useAuthToken();
  const [saved, setSaved] = useState(false);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<TokenFormValues>({ resolver: zodResolver(tokenSchema) });

  return (
    <div>
      <PageHeader title="Settings" description="Connection credentials and read-only application configuration." />
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
                { label: 'Theme', value: 'Dark (light theme not implemented)' },
              ]}
            />
          </PanelBody>
        </Panel>
      </div>
    </div>
  );
}
