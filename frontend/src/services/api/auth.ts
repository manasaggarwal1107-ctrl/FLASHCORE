const STORAGE_KEY = 'flashcore.auth.token';
const ORG_STORAGE_KEY = 'flashcore.auth.orgId';

type Listener = () => void;

const listeners = new Set<Listener>();
const orgListeners = new Set<Listener>();

let memoryToken: string | null = null;
let memoryOrgId: number | null = null;

function notify(group: Set<Listener>): void {
  for (const listener of group) listener();
}

export function getAuthToken(): string | null {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY) || null;
  } catch {
    return memoryToken;
  }
}

export function setAuthToken(token: string | null): void {
  const cleaned = token?.trim() || null;
  memoryToken = cleaned;
  try {
    if (cleaned) window.sessionStorage.setItem(STORAGE_KEY, cleaned);
    else window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* sessionStorage blocked: memoryToken still works for this page lifetime */
  }
  if (!cleaned) {
    setActiveOrganisationId(null);
  }
  notify(listeners);
}

export function subscribeAuth(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getAuthHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function getActiveOrganisationId(): number | null {
  try {
    const raw = window.sessionStorage.getItem(ORG_STORAGE_KEY);
    if (!raw) return null;
    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  } catch {
    return memoryOrgId;
  }
}

export function setActiveOrganisationId(orgId: number | null): void {
  const normalized =
    orgId !== null && Number.isInteger(orgId) && orgId > 0 ? orgId : null;
  memoryOrgId = normalized;
  try {
    if (normalized !== null) {
      window.sessionStorage.setItem(ORG_STORAGE_KEY, String(normalized));
    } else {
      window.sessionStorage.removeItem(ORG_STORAGE_KEY);
    }
  } catch {
    /* sessionStorage blocked: memoryOrgId still works for this page lifetime */
  }
  notify(orgListeners);
}

export function subscribeOrganisation(listener: Listener): () => void {
  orgListeners.add(listener);
  return () => orgListeners.delete(listener);
}
