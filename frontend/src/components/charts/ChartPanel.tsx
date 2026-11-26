import type { ReactNode } from 'react';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { AwaitingContractState } from '@/components/ui/States';
import { Skeleton } from '@/components/ui/Skeleton';
import type { EndpointSpec } from '@/services/api/endpoints';
import { isEndpointLive } from '@/services/api/endpoints';

/**
 * Panel wrapper for any chart whose data comes from one endpoint. It owns the
 * awaiting-contract / loading / error / empty decision so chart bodies only render real data.
 */
export function ChartPanel({
  title,
  description,
  endpoint,
  isLoading,
  error,
  isEmpty,
  actions,
  badge,
  children,
  renderError,
  renderEmpty,
}: {
  title: string;
  description?: string;
  endpoint: EndpointSpec;
  isLoading?: boolean;
  error?: unknown;
  isEmpty?: boolean;
  actions?: ReactNode;
  badge?: ReactNode;
  children: ReactNode;
  renderError: (error: unknown) => ReactNode;
  renderEmpty: () => ReactNode;
}) {
  let body: ReactNode;
  if (!isEndpointLive(endpoint)) body = <AwaitingContractState capability={endpoint.label} />;
  else if (isLoading) body = <Skeleton className="h-[220px] w-full" />;
  else if (error) body = renderError(error);
  else if (isEmpty) body = renderEmpty();
  else body = children;

  return (
    <Panel>
      <PanelHeader title={title} description={description} actions={actions} badge={badge} />
      <PanelBody>{body}</PanelBody>
    </Panel>
  );
}
