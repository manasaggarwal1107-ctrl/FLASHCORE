import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '@/services/api/client';
import { isEndpointLive, resolvePath } from '@/services/api/endpoints';
import type { EndpointSpec } from '@/services/api/endpoints';

/**
 * Mutation bound to one endpoint. Never retried (see queryClient). While the endpoint is
 * `pending-contract`, `live` is false and `mutate` rejects without sending a request, so forms
 * can validate locally but cannot pretend to save.
 *
 * `invalidatePrefixes` are endpoint ids (e.g. 'products.list') whose cached queries are refreshed on success.
 */
export function useEndpointMutation<TBody, TResult = unknown>(
  spec: EndpointSpec,
  options: { invalidatePrefixes?: string[]; pathParams?: Record<string, string | number>; idempotencyKey?: () => string } = {},
) {
  const queryClient = useQueryClient();
  const live = isEndpointLive(spec);
  const mutation = useMutation<TResult, Error, TBody>({
    mutationFn: async (body) => {
      if (!isEndpointLive(spec)) throw new Error(`${spec.label} is not connected: awaiting API contract.`);
      return apiRequest<TResult>(resolvePath(spec.path, options.pathParams), {
        method: spec.method,
        body,
        idempotencyKey: options.idempotencyKey?.(),
      });
    },
    onSuccess: async () => {
      await Promise.all((options.invalidatePrefixes ?? []).map((id) => queryClient.invalidateQueries({ queryKey: [id] })));
    },
  });
  return { live, ...mutation };
}
