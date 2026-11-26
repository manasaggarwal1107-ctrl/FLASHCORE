import { useSyncExternalStore } from 'react';
import { getAuthToken, subscribeAuth } from '@/services/api/auth';

export function useAuthToken(): string | null {
  return useSyncExternalStore(subscribeAuth, getAuthToken, () => null);
}
