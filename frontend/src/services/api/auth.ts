/**
 * Auth token handling.
 *
 * The authentication scheme is NOT yet defined (API_CONTRACT.md pending). This module only
 * stores an opaque bearer token in sessionStorage (cleared when the tab closes) and attaches it
 * as `Authorization: Bearer <token>`. If the contract specifies cookies or another scheme,
 * change `getAuthHeaders` only.
 */
const STORAGE_KEY = 'flashcore.auth.token';

const listeners = new Set<() => void>();

function safeStorage(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function getAuthToken(): string | null {
  return safeStorage()?.getItem(STORAGE_KEY) ?? null;
}

export function setAuthToken(token: string | null): void {
  const store = safeStorage();
  if (!store) return;
  if (token) store.setItem(STORAGE_KEY, token);
  else store.removeItem(STORAGE_KEY);
  listeners.forEach((l) => l());
}

export function subscribeAuth(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getAuthHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
