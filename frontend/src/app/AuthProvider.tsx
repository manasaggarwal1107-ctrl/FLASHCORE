import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { ReactNode } from 'react';
import { authApi } from '@/services/api/authApi';
import type {
  AuthCredentials,
  AuthUser,
} from '@/services/api/authApi';
import { getAuthToken, setAuthToken, subscribeAuth } from '@/services/api/auth';
import { ApiError } from '@/services/api/errors';

export type AuthStatus =
  | 'loading'
  | 'authenticated'
  | 'anonymous'
  | 'error';

export interface AuthContextValue {
  user: AuthUser | null;
  status: AuthStatus;
  error: string | null;
  login: (credentials: AuthCredentials) => Promise<void>;
  signup: (credentials: AuthCredentials) => Promise<void>;
  logout: () => Promise<void>;
  retrySession: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [error, setError] = useState<string | null>(null);

  const requestId = useRef(0);
  const observedToken = useRef<string | null | undefined>(undefined);

  const validateSession = useCallback(async (token: string) => {
    const currentRequest = ++requestId.current;

    setStatus('loading');
    setError(null);
    setUser(null);

    try {
      const currentUser = await authApi.me();

      if (
        currentRequest !== requestId.current ||
        getAuthToken() !== token
      ) {
        return;
      }

      setUser(currentUser);
      setStatus('authenticated');
    } catch (cause) {
      if (
        currentRequest !== requestId.current ||
        getAuthToken() !== token
      ) {
        return;
      }

      if (
        cause instanceof ApiError &&
        (cause.kind === 'unauthorized' || cause.kind === 'forbidden')
      ) {
        observedToken.current = null;
        setAuthToken(null);
        setUser(null);
        setError(null);
        setStatus('anonymous');
        return;
      }

      setUser(null);
      setError(
        cause instanceof Error
          ? cause.message
          : 'Unable to verify your session.',
      );
      setStatus('error');
    }
  }, []);

  const syncToken = useCallback((token: string | null) => {
    if (observedToken.current === token) return;

    observedToken.current = token;

    if (!token) {
      requestId.current += 1;
      setUser(null);
      setError(null);
      setStatus('anonymous');
      return;
    }

    void validateSession(token);
  }, [validateSession]);

  useEffect(() => {
    const unsubscribe = subscribeAuth(() => {
      syncToken(getAuthToken());
    });

    syncToken(getAuthToken());

    return unsubscribe;
  }, [syncToken]);

  const authenticate = useCallback(async (
    operation: (credentials: AuthCredentials) => ReturnType<typeof authApi.login>,
    credentials: AuthCredentials,
  ) => {
    const response = await operation(credentials);

    requestId.current += 1;
    observedToken.current = response.accessToken;
    setAuthToken(response.accessToken);
    setUser(response.user);
    setError(null);
    setStatus('authenticated');
  }, []);

  const login = useCallback(
    (credentials: AuthCredentials) =>
      authenticate(authApi.login, credentials),
    [authenticate],
  );

  const signup = useCallback(
    (credentials: AuthCredentials) =>
      authenticate(authApi.signup, credentials),
    [authenticate],
  );

  const logout = useCallback(async () => {
    try {
      if (getAuthToken()) {
        await authApi.logout();
      }
    } finally {
      requestId.current += 1;
      observedToken.current = null;
      setAuthToken(null);
      setUser(null);
      setError(null);
      setStatus('anonymous');
    }
  }, []);

  const retrySession = useCallback(() => {
    observedToken.current = undefined;
    syncToken(getAuthToken());
  }, [syncToken]);

  const value = useMemo<AuthContextValue>(() => ({
    user,
    status,
    error,
    login,
    signup,
    logout,
    retrySession,
  }), [user, status, error, login, signup, logout, retrySession]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}
