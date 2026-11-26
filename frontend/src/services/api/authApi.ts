import { apiRequest } from './client';
import { endpoints, isEndpointLive, resolvePath } from './endpoints';

export type UserRole = 'admin' | 'analyst' | 'operator';
export type UserStatus = 'active' | 'disabled';

export interface AuthUser {
  id: number;
  email: string;
  role: UserRole;
  status: UserStatus;
  createdAt: string;
}

export interface AuthResponse {
  accessToken: string;
  tokenType: 'bearer';
  expiresAt: string;
  user: AuthUser;
}

export interface AuthCredentials {
  email: string;
  password: string;
}

function getAuthPath(
  endpoint: keyof typeof endpoints.auth,
): string {
  const spec = endpoints.auth[endpoint];

  if (!isEndpointLive(spec)) {
    throw new Error(`Authentication endpoint "${endpoint}" is not available.`);
  }

  return resolvePath(spec.path);
}

export const authApi = {
  signup(credentials: AuthCredentials): Promise<AuthResponse> {
    return apiRequest<AuthResponse>(getAuthPath('signup'), {
      method: 'POST',
      body: credentials,
    });
  },

  login(credentials: AuthCredentials): Promise<AuthResponse> {
    return apiRequest<AuthResponse>(getAuthPath('login'), {
      method: 'POST',
      body: credentials,
    });
  },

  me(): Promise<AuthUser> {
    return apiRequest<AuthUser>(getAuthPath('me'), {
      method: 'GET',
    });
  },

  logout(): Promise<void> {
    return apiRequest<void>(getAuthPath('logout'), {
      method: 'POST',
    });
  },
};
