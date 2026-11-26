import { useContext } from 'react';
import { AuthContext } from '@/app/AuthProvider';

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider.');
  }

  return context;
}

/** Optional context access for reusable components and isolated tests. */
export function useOptionalAuth() {
  return useContext(AuthContext);
}
