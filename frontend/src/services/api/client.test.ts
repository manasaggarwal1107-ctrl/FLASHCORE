import { afterEach, beforeEach, vi } from 'vitest';
import { setAuthToken } from './auth';
import { apiRequest, buildUrl } from './client';
import { getConnectivitySnapshot, resetConnectivity } from './connectivity';
import { ApiError, describeError } from './errors';
import { createQueryClient } from './queryClient';
import { jsonResponse } from '@/test/utils';

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
  fetchMock.mockReset();
  resetConnectivity();
  setAuthToken(null);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('buildUrl', () => {
  it('joins base, path and drops empty query values', () => {
    expect(buildUrl('/products', { page: 2, search: '', sort: undefined, q: 'a b' }, '/api/v1')).toBe('/api/v1/products?page=2&q=a+b');
    expect(buildUrl('products', undefined, '/api/v1')).toBe('/api/v1/products');
  });
});

describe('apiRequest', () => {
  it('returns parsed JSON with camelCased keys and marks the API reachable', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ product_name: 'Lamp', nested_value: { unit_price: '9.99' } }));
    const data = await apiRequest<{ productName: string; nestedValue: { unitPrice: string } }>('/x');
    expect(data).toEqual({ productName: 'Lamp', nestedValue: { unitPrice: '9.99' } });
    expect(getConnectivitySnapshot().status).toBe('reachable');
  });

  it('attaches the bearer token and idempotency key when supplied', async () => {
    setAuthToken('tok_123');
    fetchMock.mockResolvedValue(jsonResponse({}));
    await apiRequest('/purchases', { method: 'POST', body: { a: 1 }, idempotencyKey: 'key-1' });
    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer tok_123');
    expect(headers['Idempotency-Key']).toBe('key-1');
    expect(headers['Content-Type']).toBe('application/json');
    expect(init.body).toBe(JSON.stringify({ a: 1 }));
  });

  it('maps HTTP errors to typed ApiErrors using the response message', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ message: 'SKU already exists' }, 409));
    await expect(apiRequest('/x', { method: 'POST', body: {} })).rejects.toMatchObject({ kind: 'validation', status: 409, message: 'SKU already exists' });
  });

  it.each([
    [401, 'unauthorized'],
    [403, 'forbidden'],
    [404, 'not-found'],
    [500, 'server'],
  ])('maps status %i to kind %s', async (status, kind) => {
    fetchMock.mockResolvedValue(jsonResponse({}, status));
    await expect(apiRequest('/x')).rejects.toMatchObject({ kind, status });
  });

  it('reports network failures and flips connectivity to unreachable', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(apiRequest('/x')).rejects.toMatchObject({ kind: 'network' });
    expect(getConnectivitySnapshot().status).toBe('unreachable');
  });

  it('times out when no response arrives', async () => {
    vi.useFakeTimers();
    fetchMock.mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_, reject) => {
          init.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
        }),
    );
    const assertion = expect(apiRequest('/slow', { timeoutMs: 50 })).rejects.toMatchObject({ kind: 'timeout' });
    await vi.advanceTimersByTimeAsync(60);
    await assertion;
    expect(getConnectivitySnapshot().status).toBe('unreachable');
  });

  it('flags malformed JSON as a contract error', async () => {
    fetchMock.mockResolvedValue(new Response('{oops', { status: 200, headers: { 'content-type': 'application/json' } }));
    await expect(apiRequest('/x')).rejects.toMatchObject({ kind: 'contract' });
  });

  it('handles 204 No Content', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(apiRequest('/x', { method: 'DELETE' })).resolves.toBeUndefined();
  });
});

describe('error presentation', () => {
  it('produces user-facing titles', () => {
    expect(describeError(new ApiError('network', 'x')).title).toBe('Cannot reach the API');
    expect(describeError(new ApiError('unauthorized', 'x', { status: 401 })).title).toBe('Authentication required');
    expect(describeError(new Error('boom'))).toEqual({ title: 'Unexpected error', detail: 'boom' });
  });
});

describe('retry policy (protects purchase operations)', () => {
  const client = createQueryClient();

  it('never retries mutations', () => {
    expect(client.getDefaultOptions().mutations?.retry).toBe(false);
  });

  it('retries queries only for transient errors, at most twice', () => {
    const retry = client.getDefaultOptions().queries?.retry as (count: number, error: unknown) => boolean;
    expect(retry(0, new ApiError('network', 'x'))).toBe(true);
    expect(retry(0, new ApiError('server', 'x', { status: 503 }))).toBe(true);
    expect(retry(2, new ApiError('network', 'x'))).toBe(false);
    expect(retry(0, new ApiError('server', 'x', { status: 500 }))).toBe(false);
    expect(retry(0, new ApiError('validation', 'x', { status: 422 }))).toBe(false);
    expect(retry(0, new Error('plain'))).toBe(false);
  });
});
