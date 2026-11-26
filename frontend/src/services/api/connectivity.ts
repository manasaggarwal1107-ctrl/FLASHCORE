/**
 * API connectivity is derived ONLY from real request outcomes — no health endpoint is assumed
 * and nothing is simulated. Before any request is made the state is "unknown".
 */
export type ConnectivityStatus = 'unknown' | 'reachable' | 'unreachable';

export interface ConnectivitySnapshot {
  status: ConnectivityStatus;
  lastChangedAt: number | null;
  lastError: string | null;
}

let snapshot: ConnectivitySnapshot = { status: 'unknown', lastChangedAt: null, lastError: null };
const listeners = new Set<() => void>();

function set(next: ConnectivitySnapshot) {
  if (next.status === snapshot.status && next.lastError === snapshot.lastError) return;
  snapshot = next;
  listeners.forEach((l) => l());
}

/** The server answered (any HTTP status): the API is reachable. */
export function reportResponseReceived(): void {
  set({ status: 'reachable', lastChangedAt: Date.now(), lastError: null });
}

/** No response (network failure or timeout). */
export function reportUnreachable(reason: string): void {
  set({ status: 'unreachable', lastChangedAt: Date.now(), lastError: reason });
}

export function getConnectivitySnapshot(): ConnectivitySnapshot {
  return snapshot;
}

export function subscribeConnectivity(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Test helper. */
export function resetConnectivity(): void {
  snapshot = { status: 'unknown', lastChangedAt: null, lastError: null };
  listeners.forEach((l) => l());
}
