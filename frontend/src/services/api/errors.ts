export type ApiErrorKind =
  | 'network' // no response received
  | 'timeout' // request exceeded timeout
  | 'aborted' // caller cancelled
  | 'unauthorized' // 401
  | 'forbidden' // 403
  | 'not-found' // 404
  | 'validation' // 400 / 409 / 422 — request was rejected
  | 'server' // 5xx
  | 'http' // any other non-2xx
  | 'contract'; // 2xx response that does not match the expected shape

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  /** Raw decoded error body, if any. Shape is defined by API_CONTRACT.md. */
  readonly body: unknown;

  constructor(kind: ApiErrorKind, message: string, options: { status?: number | null; body?: unknown; cause?: unknown } = {}) {
    super(message, options.cause !== undefined ? { cause: options.cause } : undefined);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = options.status ?? null;
    this.body = options.body;
  }

  /** Safe to retry automatically for idempotent reads only. */
  get isTransient(): boolean {
    return this.kind === 'network' || this.kind === 'timeout' || (this.status !== null && [502, 503, 504].includes(this.status));
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}

export function kindFromStatus(status: number): ApiErrorKind {
  if (status === 401) return 'unauthorized';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'not-found';
  if (status === 400 || status === 409 || status === 422) return 'validation';
  if (status >= 500) return 'server';
  return 'http';
}

/**
 * Extracts a human-readable message from an error response body.
 * ADAPTER POINT: align with the error format in API_CONTRACT.md.
 */
export function messageFromBody(body: unknown, fallback: string): string {
  if (body && typeof body === 'object') {
    const b = body as Record<string, unknown>;
    if (typeof b.message === 'string') return b.message;
    if (typeof b.detail === 'string') return b.detail;
    if (b.error && typeof b.error === 'object') {
      const m = (b.error as Record<string, unknown>).message;
      if (typeof m === 'string') return m;
    }
    if (typeof b.error === 'string') return b.error;
  }
  return fallback;
}

/** Short, user-safe description for UI. */
export function describeError(error: unknown): { title: string; detail: string } {
  if (!isApiError(error)) {
    return { title: 'Unexpected error', detail: error instanceof Error ? error.message : 'Something went wrong.' };
  }
  switch (error.kind) {
    case 'network':
      return { title: 'Cannot reach the API', detail: 'The server did not respond. Check the API base URL and that the backend is running.' };
    case 'timeout':
      return { title: 'Request timed out', detail: error.message };
    case 'unauthorized':
      return { title: 'Authentication required', detail: 'The API rejected the credentials. Provide a valid token in Settings.' };
    case 'forbidden':
      return { title: 'Not permitted', detail: error.message };
    case 'not-found':
      return { title: 'Not found', detail: error.message };
    case 'validation':
      return { title: 'Request rejected', detail: error.message };
    case 'server':
      return { title: 'Server error', detail: error.message };
    case 'contract':
      return { title: 'Unexpected response shape', detail: error.message };
    case 'aborted':
      return { title: 'Request cancelled', detail: error.message };
    default:
      return { title: 'Request failed', detail: error.message };
  }
}
