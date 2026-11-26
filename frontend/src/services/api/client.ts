import { camelizeKeys } from '@/lib/case';
import { config } from '@/lib/config';
import { getAuthHeaders } from './auth';
import { reportResponseReceived, reportUnreachable } from './connectivity';
import { ApiError, kindFromStatus, messageFromBody } from './errors';

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
export type QueryValue = string | number | boolean | null | undefined;

export interface RequestOptions {
  method?: HttpMethod;
  query?: Record<string, QueryValue>;
  /** JSON-serialisable object, or FormData for uploads. */
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  timeoutMs?: number;
  /**
   * Key sent in the configured idempotency header. Required by the caller for any request that
   * must be safe to repeat. NOTE: this client NEVER retries non-GET requests automatically,
   * regardless of whether a key is present.
   */
  idempotencyKey?: string;
  /** Skip snake_case → camelCase conversion of the response. */
  rawKeys?: boolean;
}

export function buildUrl(path: string, query?: Record<string, QueryValue>, base: string = config.apiBaseUrl): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  let url = `${base}${normalizedPath}`;
  if (query) {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v === null || v === undefined || v === '') continue;
      sp.append(k, String(v));
    }
    const qs = sp.toString();
    if (qs) url += `${url.includes('?') ? '&' : '?'}${qs}`;
  }
  return url;
}

async function readBody(res: Response): Promise<unknown> {
  if (res.status === 204) return undefined;
  const type = res.headers.get('content-type') ?? '';
  const text = await res.text();
  if (!text) return undefined;
  if (type.includes('json')) {
    try {
      return JSON.parse(text);
    } catch {
      throw new ApiError('contract', 'The server returned malformed JSON.', { status: res.status });
    }
  }
  return text;
}

/**
 * Typed request helper. Throws `ApiError` for every failure mode; never returns fallback data.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', query, body, headers = {}, signal, timeoutMs = config.apiTimeoutMs, idempotencyKey, rawKeys } = options;

  const finalHeaders: Record<string, string> = { Accept: 'application/json', ...getAuthHeaders(), ...headers };
  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body; // browser sets the multipart boundary
  } else if (body !== undefined) {
    payload = JSON.stringify(body);
    finalHeaders['Content-Type'] = 'application/json';
  }
  if (idempotencyKey) finalHeaders[config.idempotencyHeader] = idempotencyKey;

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const onCallerAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener('abort', onCallerAbort, { once: true });
  }

  let res: Response;
  try {
    res = await fetch(buildUrl(path, query), { method, headers: finalHeaders, body: payload, signal: controller.signal });
  } catch (cause) {
    if (timedOut) {
      reportUnreachable('timeout');
      throw new ApiError('timeout', `No response within ${Math.round(timeoutMs / 1000)}s.`, { cause });
    }
    if (controller.signal.aborted) {
      throw new ApiError('aborted', 'The request was cancelled.', { cause });
    }
    reportUnreachable('network');
    throw new ApiError('network', 'Network request failed.', { cause });
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', onCallerAbort);
  }

  reportResponseReceived();
  const parsed = await readBody(res);

  if (!res.ok) {
    throw new ApiError(kindFromStatus(res.status), messageFromBody(parsed, `Request failed with status ${res.status}.`), {
      status: res.status,
      body: parsed,
    });
  }
  return (rawKeys ? parsed : camelizeKeys(parsed)) as T;
}
