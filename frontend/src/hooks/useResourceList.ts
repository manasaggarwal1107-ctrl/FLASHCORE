import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { apiRequest } from '@/services/api/client';
import { isEndpointLive, resolvePath } from '@/services/api/endpoints';
import type { EndpointSpec } from '@/services/api/endpoints';
import { adaptPage, toQuery } from '@/services/api/pagination';
import type { ListParams, Page } from '@/services/api/pagination';

/**
 * Generic paginated GET. When the endpoint is still `pending-contract` the query is disabled and
 * `live` is false, so the UI shows an "awaiting contract" state and no request is ever sent.
 */
export function useResourceList<T>(spec: EndpointSpec, params: ListParams, pathParams?: Record<string, string | number>) {
  const live = isEndpointLive(spec);
  const query = useQuery<Page<T>>({
    queryKey: [spec.id, pathParams ?? null, params],
    enabled: live,
    placeholderData: keepPreviousData,
    queryFn: async ({ signal }) => {
      if (!isEndpointLive(spec)) throw new Error(`Endpoint ${spec.id} is not confirmed`);
      const raw = await apiRequest<unknown>(resolvePath(spec.path, pathParams), { query: toQuery(params), signal });
      return adaptPage<T>(raw);
    },
  });
  return { live, ...query };
}

/** Generic single-resource GET with the same pending-contract behaviour. */
export function useResource<T>(spec: EndpointSpec, pathParams: Record<string, string | number> = {}, queryParams?: Record<string, string>) {
  const live = isEndpointLive(spec);
  const query = useQuery<T>({
    queryKey: [spec.id, pathParams, queryParams ?? null],
    enabled: live,
    queryFn: ({ signal }) => {
      if (!isEndpointLive(spec)) throw new Error(`Endpoint ${spec.id} is not confirmed`);
      return apiRequest<T>(resolvePath(spec.path, pathParams), { signal, query: queryParams });
    },
  });
  return { live, ...query };
}
