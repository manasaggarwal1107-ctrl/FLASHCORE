function parsePositiveInt(raw: string | undefined, fallback: number): number {
  const n = Number(raw);
  return Number.isInteger(n) && n > 0 ? n : fallback;
}

export type AppEnvironment = 'development' | 'production';

function parseEnvironment(raw: string | undefined): AppEnvironment {
  return raw === 'production' ? 'production' : 'development';
}

/** Single source of truth for build-time configuration. */
export const config = {
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/+$/, ''),
  apiTimeoutMs: parsePositiveInt(import.meta.env.VITE_API_TIMEOUT_MS, 15_000),
  environment: parseEnvironment(import.meta.env.VITE_APP_ENV),
  /** ASSUMPTION until API_CONTRACT.md confirms it. */
  idempotencyHeader: import.meta.env.VITE_IDEMPOTENCY_HEADER ?? 'Idempotency-Key',
  appVersion: '0.1.0',
} as const;
