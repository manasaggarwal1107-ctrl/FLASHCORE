const SNAKE_SEGMENT = /_+([a-z0-9])/g;

export function snakeToCamel(key: string): string {
  return key.replace(SNAKE_SEGMENT, (_, c: string) => c.toUpperCase());
}

/**
 * Recursively converts snake_case object keys to camelCase.
 * A no-op for payloads that are already camelCase, so it is safe whichever convention
 * the backend contract ends up using. Values are never modified.
 */
export function camelizeKeys<T = unknown>(input: unknown): T {
  if (Array.isArray(input)) return input.map((v) => camelizeKeys(v)) as T;
  if (input !== null && typeof input === 'object' && Object.getPrototypeOf(input) === Object.prototype) {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(input as Record<string, unknown>)) {
      out[snakeToCamel(k)] = camelizeKeys(v);
    }
    return out as T;
  }
  return input as T;
}
