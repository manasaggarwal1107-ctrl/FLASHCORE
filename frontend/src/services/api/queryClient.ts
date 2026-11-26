import { QueryClient } from '@tanstack/react-query';
import { isApiError } from './errors';

/**
 * Retry policy:
 *  - Queries (GET): up to 2 retries, only for transient failures (network, timeout, 502/503/504).
 *    4xx errors are never retried.
 *  - Mutations (POST/PATCH/…): NEVER retried automatically. This protects purchase and stock
 *    operations from being duplicated. A user may re-submit explicitly; purchase requests must
 *    then carry the same idempotency key.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => failureCount < 2 && isApiError(error) && error.isTransient,
      },
      mutations: { retry: false },
    },
  });
}
