import { ApiError } from './errors';
import type { QueryValue } from './client';

/** Canonical list shape used by the UI. */
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

export interface ListParams {
  page: number;
  pageSize: number;
  search?: string;
  sort?: string;
  order?: 'asc' | 'desc';
  filters?: Record<string, string>;
}

export const DEFAULT_PAGE_SIZE = 25;

/**
 * Query-string mapping. ADAPTER POINT: parameter names (page, page_size, q, sort …) must be aligned
 * with API_CONTRACT.md. These names are placeholders and are unused while endpoints are pending.
 */
export function toQuery(params: ListParams): Record<string, QueryValue> {
  return {
    page: params.page,
    pageSize: params.pageSize,
    search: params.search,
    sort: params.sort,
    order: params.order,
    ...params.filters,
  };
}

/**
 * Response adapter. ADAPTER POINT: rewrite to the contract's pagination envelope.
 * It validates strictly and fails loudly with `ApiError('contract')` rather than guessing.
 */
export function adaptPage<T>(raw: unknown): Page<T> {
  // Support backend endpoints returning a raw array.
  if (Array.isArray(raw)) {
    return {
      items: raw as T[],
      total: raw.length,
      page: 1,
      pageSize: raw.length || DEFAULT_PAGE_SIZE,
    };
  }

  // Preserve the existing paginated response format.
  if (raw && typeof raw === 'object') {
    const r = raw as Record<string, unknown>;

    if (
      Array.isArray(r.items) &&
      typeof r.total === 'number' &&
      typeof r.page === 'number' &&
      typeof r.pageSize === 'number'
    ) {
      return {
        items: r.items as T[],
        total: r.total,
        page: r.page,
        pageSize: r.pageSize,
      };
    }
  }

  throw new ApiError(
    'contract',
    'List response did not match a raw array or the expected pagination envelope.',
  );
}