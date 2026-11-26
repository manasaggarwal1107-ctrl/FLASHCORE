import { useSyncExternalStore } from 'react';
import { getConnectivitySnapshot, subscribeConnectivity } from '@/services/api/connectivity';

export function useApiConnectivity() {
  return useSyncExternalStore(subscribeConnectivity, getConnectivitySnapshot, getConnectivitySnapshot);
}
