import type { ReactNode } from 'react';
import { AlertTriangle, CircleSlash, Inbox, PlugZap, RefreshCw } from 'lucide-react';
import { describeError } from '@/services/api/errors';
import { Button } from './Button';
import { cn } from '@/lib/cn';

interface StateShellProps {
  icon: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  tone?: 'neutral' | 'danger' | 'warning';
  compact?: boolean;
  role?: 'status' | 'alert';
}

function StateShell({ icon, title, description, action, tone = 'neutral', compact, role }: StateShellProps) {
  return (
    <div
      role={role}
      className={cn('flex flex-col items-center justify-center text-center', compact ? 'gap-1.5 px-4 py-8' : 'gap-2 px-6 py-14')}
    >
      <div
        className={cn(
          'mb-1 flex h-9 w-9 items-center justify-center rounded-md border',
          tone === 'danger' && 'border-danger/30 bg-danger/10 text-danger',
          tone === 'warning' && 'border-warning/30 bg-warning/10 text-warning',
          tone === 'neutral' && 'border-line-strong bg-surface-raised text-ink-muted',
        )}
      >
        {icon}
      </div>
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      {description && <p className="max-w-md text-xs text-ink-muted">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

/** The request succeeded and returned nothing. */
export function EmptyState({ title = 'No records', description, action, compact }: { title?: string; description?: ReactNode; action?: ReactNode; compact?: boolean }) {
  return <StateShell icon={<Inbox className="h-4 w-4" />} title={title} description={description} action={action} compact={compact} role="status" />;
}

/** The request failed. Shows the real error; never substitutes data. */
export function ErrorState({ error, onRetry, compact }: { error: unknown; onRetry?: () => void; compact?: boolean }) {
  const { title, detail } = describeError(error);
  return (
    <StateShell
      tone="danger"
      icon={<AlertTriangle className="h-4 w-4" />}
      title={title}
      description={detail}
      compact={compact}
      role="alert"
      action={
        onRetry && (
          <Button size="sm" icon={<RefreshCw className="h-3.5 w-3.5" />} onClick={onRetry}>
            Retry
          </Button>
        )
      }
    />
  );
}

/** A single metric / panel the backend does not supply. */
export function UnavailableState({ title = 'Not available', description, compact = true }: { title?: string; description?: ReactNode; compact?: boolean }) {
  return <StateShell icon={<CircleSlash className="h-4 w-4" />} title={title} description={description} compact={compact} role="status" />;
}

/** Endpoint has no confirmed contract yet: honest, non-interactive, no network call is made. */
export function AwaitingContractState({ capability, compact }: { capability: string; compact?: boolean }) {
  return (
    <StateShell
      tone="warning"
      icon={<PlugZap className="h-4 w-4" />}
      title="Awaiting API contract"
      description={
        <>
          <span className="text-ink">{capability}</span> is not connected. No endpoint has been confirmed in <code className="font-mono">API_CONTRACT.md</code>, so
          no request is made and no placeholder data is shown.
        </>
      }
      compact={compact}
      role="status"
    />
  );
}
