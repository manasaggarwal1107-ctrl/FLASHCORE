import type { ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel } from '@/components/ui/Panel';
import { AwaitingContractState, EmptyState, ErrorState } from '@/components/ui/States';
import { LoadingRegion, Skeleton } from '@/components/ui/Skeleton';
import { useResource } from '@/hooks/useResource';
import type { EndpointSpec } from '@/services/api/endpoints';
import { isApiError } from '@/services/api/errors';

/**
 * Standard detail-view wrapper: resolves the `:id` route param, loads the resource and
 * renders awaiting-contract / loading / not-found / error states. `children` only ever sees real data.
 */
export function DetailPage<T>({
  endpoint,
  backTo,
  backLabel,
  title,
  actions,
  children,
}: {
  endpoint: EndpointSpec;
  backTo: string;
  backLabel: string;
  title: (data: T | undefined, id: string) => string;
  actions?: ReactNode;
  children: (data: T) => ReactNode;
}) {
  const { id = '' } = useParams<{ id: string }>();
  const query = useResource<T>(endpoint, { id });

  let body: ReactNode;
  if (!query.live) body = <Panel><AwaitingContractState capability={endpoint.label} /></Panel>;
  else if (query.isPending)
    body = (
      <LoadingRegion label="Loading details" className="space-y-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-48 w-full" />
      </LoadingRegion>
    );
  else if (query.isError && isApiError(query.error) && query.error.kind === 'not-found')
    body = <Panel><EmptyState title="Record not found" description={`No record with reference “${id}”.`} /></Panel>;
  else if (query.isError) body = <Panel><ErrorState error={query.error} onRetry={() => void query.refetch()} /></Panel>;
  else body = children(query.data);

  return (
    <div>
      <Link to={backTo} className="mb-3 inline-flex items-center gap-1.5 text-xs text-ink-muted hover:text-ink">
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> {backLabel}
      </Link>
      <PageHeader title={title(query.data, id)} actions={actions} />
      {body}
    </div>
  );
}
