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
  OrgRole,
  UserOrganisation,
} from '@/services/api/authApi';
import {
  getActiveOrganisationId,
  getAuthToken,
  setActiveOrganisationId,
  setAuthToken,
  subscribeAuth,
} from '@/services/api/auth';
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
  organisations: UserOrganisation[];
  activeOrganisation: UserOrganisation | null;
  activeRole: OrgRole | null;
  membershipError: string | null;
  login: (credentials: AuthCredentials) => Promise<void>;
  signup: (credentials: AuthCredentials) => Promise<void>;
  logout: () => Promise<void>;
  retrySession: () => void;
  switchOrganisation: (organisationId: number) => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

function resolveOrganisationSelection(
  user: AuthUser,
  onClearCache?: () => void,
): {
  organisations: UserOrganisation[];
  activeOrganisation: UserOrganisation | null;
  membershipError: string | null;
} {
  if (!Array.isArray(user.organisations)) {
    return {
      organisations: [],
      activeOrganisation: null,
      membershipError: null,
    };
  }

  const activeOrgs = user.organisations.filter(
    (org) =>
      org.membershipStatus === 'active' && org.organisationStatus === 'active',
  );

  if (activeOrgs.length === 0) {
    setActiveOrganisationId(null);
    onClearCache?.();
    return {
      organisations: [],
      activeOrganisation: null,
      membershipError: 'No active organisation membership is available for this account.',
    };
  }

  const storedOrgId = getActiveOrganisationId();
  if (storedOrgId !== null) {
    const matched = activeOrgs.find((o) => o.organisationId === storedOrgId);
    if (matched) {
      return {
        organisations: activeOrgs,
        activeOrganisation: matched,
        membershipError: null,
      };
    }
    // Stored organisation membership was revoked or expired: clear stale cache before fallback.
    onClearCache?.();
  }

  const preferred =
    (user.activeOrganisationId != null
      ? activeOrgs.find((o) => o.organisationId === user.activeOrganisationId)
      : undefined) ?? activeOrgs[0]!;

  setActiveOrganisationId(preferred.organisationId);

  return {
    organisations: activeOrgs,
    activeOrganisation: preferred,
    membershipError: null,
  };
}

export function AuthProvider({
  children,
  onClearCache,
}: {
  children: ReactNode;
  onClearCache?: () => void;
}) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [error, setError] = useState<string | null>(null);
  const [organisations, setOrganisations] = useState<UserOrganisation[]>([]);
  const [activeOrganisation, setActiveOrganisation] =
    useState<UserOrganisation | null>(null);
  const [membershipError, setMembershipError] = useState<string | null>(null);

  const requestId = useRef(0);
  const observedToken = useRef<string | null | undefined>(undefined);

  const applyAuthenticatedUser = useCallback(
    (currentUser: AuthUser) => {
      const resolved = resolveOrganisationSelection(currentUser, onClearCache);
      setUser(currentUser);
      setOrganisations(resolved.organisations);
      setActiveOrganisation(resolved.activeOrganisation);
      setMembershipError(resolved.membershipError);
      setError(null);
      setStatus('authenticated');
    },
    [onClearCache],
  );

  const validateSession = useCallback(
    async (token: string) => {
      const currentRequest = ++requestId.current;

      setStatus('loading');
      setError(null);
      setMembershipError(null);
      setUser(null);

      try {
        const currentUser = await authApi.me();

        if (
          currentRequest !== requestId.current ||
          getAuthToken() !== token
        ) {
          return;
        }

        applyAuthenticatedUser(currentUser);
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
          if (cause.kind === 'forbidden' && getActiveOrganisationId() !== null) {
            // Active organisation membership may have been revoked; clear org selection and retry /me once.
            setActiveOrganisationId(null);
            onClearCache?.();
            try {
              const fallbackUser = await authApi.me();
              if (
                currentRequest === requestId.current &&
                getAuthToken() === token
              ) {
                applyAuthenticatedUser(fallbackUser);
                return;
              }
            } catch {
              /* Fall through to clearing session if re-check fails */
            }
          }

          observedToken.current = null;
          setAuthToken(null);
          onClearCache?.();
          setUser(null);
          setOrganisations([]);
          setActiveOrganisation(null);
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
    },
    [applyAuthenticatedUser, onClearCache],
  );

  const syncToken = useCallback(
    (token: string | null) => {
      if (observedToken.current === token) return;

      observedToken.current = token;

      if (!token) {
        requestId.current += 1;
        setUser(null);
        setOrganisations([]);
        setActiveOrganisation(null);
        setMembershipError(null);
        setError(null);
        setStatus('anonymous');
        return;
      }

      void validateSession(token);
    },
    [validateSession],
  );

  useEffect(() => {
    const unsubscribe = subscribeAuth(() => {
      syncToken(getAuthToken());
    });

    syncToken(getAuthToken());

    return unsubscribe;
  }, [syncToken]);

  const authenticate = useCallback(
    async (
      operation: (credentials: AuthCredentials) => ReturnType<typeof authApi.login>,
      credentials: AuthCredentials,
    ) => {
      const response = await operation(credentials);

      requestId.current += 1;
      observedToken.current = response.accessToken;
      setAuthToken(response.accessToken);
      onClearCache?.();
      applyAuthenticatedUser(response.user);
    },
    [applyAuthenticatedUser, onClearCache],
  );

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
      onClearCache?.();
      setUser(null);
      setOrganisations([]);
      setActiveOrganisation(null);
      setMembershipError(null);
      setError(null);
      setStatus('anonymous');
    }
  }, [onClearCache]);

  const retrySession = useCallback(() => {
    observedToken.current = undefined;
    syncToken(getAuthToken());
  }, [syncToken]);

  const switchOrganisation = useCallback(
    async (organisationId: number) => {
      const target = organisations.find(
        (org) => org.organisationId === organisationId,
      );
      if (!target) {
        throw new Error('Selected organisation is not available.');
      }

      setActiveOrganisationId(organisationId);
      setActiveOrganisation(target);
      onClearCache?.();

      const refreshed = await authApi.me();
      applyAuthenticatedUser(refreshed);
    },
    [applyAuthenticatedUser, onClearCache, organisations],
  );

  const activeRole = useMemo<OrgRole | null>(() => {
    if (activeOrganisation) return activeOrganisation.role;
    if (user?.activeOrganisationRole) return user.activeOrganisationRole;
    return user?.role ?? null;
  }, [activeOrganisation, user]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      status,
      error,
      organisations,
      activeOrganisation,
      activeRole,
      membershipError,
      login,
      signup,
      logout,
      retrySession,
      switchOrganisation,
    }),
    [
      user,
      status,
      error,
      organisations,
      activeOrganisation,
      activeRole,
      membershipError,
      login,
      signup,
      logout,
      retrySession,
      switchOrganisation,
    ],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}
