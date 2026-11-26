import { useAuth } from '@/hooks/useAuth';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthProvider } from './AuthProvider';
import { authApi } from '@/services/api/authApi';
import type { AuthUser } from '@/services/api/authApi';
import { getAuthToken, setAuthToken } from '@/services/api/auth';
import { ApiError } from '@/services/api/errors';

vi.mock('@/services/api/authApi', () => ({
  authApi: {
    signup: vi.fn(),
    login: vi.fn(),
    me: vi.fn(),
    logout: vi.fn(),
  },
}));

const testUser: AuthUser = {
  id: 1,
  email: 'analyst@flashcore.test',
  role: 'analyst',
  status: 'active',
  createdAt: '2026-11-22T10:00:00Z',
};

const credentials = {
  email: 'analyst@flashcore.test',
  password: 'correct-password-123',
};

function AuthProbe() {
  const auth = useAuth();

  return (
    <div>
      <output data-testid="auth-status">{auth.status}</output>
      <output data-testid="auth-email">{auth.user?.email ?? ''}</output>
      <output data-testid="auth-error">{auth.error ?? ''}</output>

      <button
        type="button"
        onClick={() => {
          void auth.login(credentials).catch(() => undefined);
        }}
      >
        Test login
      </button>

      <button
        type="button"
        onClick={() => {
          void auth.signup(credentials).catch(() => undefined);
        }}
      >
        Test signup
      </button>

      <button type="button" onClick={auth.retrySession}>
        Retry session
      </button>

      <button
        type="button"
        onClick={() => {
          void auth.logout().catch(() => undefined);
        }}
      >
        Test logout
      </button>
    </div>
  );
}

function renderAuth() {
  return render(
    <AuthProvider>
      <AuthProbe />
    </AuthProvider>,
  );
}

describe('AuthProvider', () => {
  beforeEach(() => {
    setAuthToken(null);

    vi.mocked(authApi.signup).mockReset();
    vi.mocked(authApi.login).mockReset();
    vi.mocked(authApi.me).mockReset();
    vi.mocked(authApi.logout).mockReset();
  });

  it('starts anonymous when no token exists', async () => {
    renderAuth();

    expect(screen.getByTestId('auth-status')).toHaveTextContent('anonymous');
    expect(screen.getByTestId('auth-email')).toBeEmptyDOMElement();
    expect(authApi.me).not.toHaveBeenCalled();
  });

  it('restores a valid stored session using the current-user endpoint', async () => {
    vi.mocked(authApi.me).mockResolvedValue(testUser);
    setAuthToken('stored-token');

    renderAuth();

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('authenticated');
    });

    expect(screen.getByTestId('auth-email')).toHaveTextContent(testUser.email);
    expect(authApi.me).toHaveBeenCalledOnce();
  });

  it('clears an invalid stored token after an unauthorized response', async () => {
    vi.mocked(authApi.me).mockRejectedValue(
      new ApiError('unauthorized', 'Invalid session', { status: 401 }),
    );

    setAuthToken('invalid-token');
    renderAuth();

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('anonymous');
    });

    expect(getAuthToken()).toBeNull();
    expect(screen.getByTestId('auth-email')).toBeEmptyDOMElement();
  });

  it('preserves the token and exposes an error when session verification fails temporarily', async () => {
    vi.mocked(authApi.me).mockRejectedValue(
      new ApiError('network', 'API unavailable'),
    );

    setAuthToken('temporarily-unverifiable-token');
    renderAuth();

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('error');
    });

    expect(getAuthToken()).toBe('temporarily-unverifiable-token');
    expect(screen.getByTestId('auth-error')).toHaveTextContent('API unavailable');
  });

  it('retries session verification successfully', async () => {
    const user = userEvent.setup();

    vi.mocked(authApi.me)
      .mockRejectedValueOnce(new ApiError('network', 'Temporary failure'))
      .mockResolvedValueOnce(testUser);

    setAuthToken('retry-token');
    renderAuth();

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('error');
    });

    await user.click(screen.getByRole('button', { name: 'Retry session' }));

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('authenticated');
    });

    expect(authApi.me).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId('auth-email')).toHaveTextContent(testUser.email);
  });

  it('authenticates after a successful login and stores the returned token', async () => {
    const user = userEvent.setup();

    vi.mocked(authApi.login).mockResolvedValue({
      accessToken: 'login-token',
      tokenType: 'bearer',
      expiresAt: '2026-11-23T10:00:00Z',
      user: testUser,
    });

    renderAuth();

    await user.click(screen.getByRole('button', { name: 'Test login' }));

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('authenticated');
    });

    expect(getAuthToken()).toBe('login-token');
    expect(screen.getByTestId('auth-email')).toHaveTextContent(testUser.email);
    expect(authApi.login).toHaveBeenCalledWith(credentials);
  });

  it('authenticates after successful signup', async () => {
    const user = userEvent.setup();

    vi.mocked(authApi.signup).mockResolvedValue({
      accessToken: 'signup-token',
      tokenType: 'bearer',
      expiresAt: '2026-11-23T10:00:00Z',
      user: testUser,
    });

    renderAuth();

    await user.click(screen.getByRole('button', { name: 'Test signup' }));

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('authenticated');
    });

    expect(getAuthToken()).toBe('signup-token');
    expect(authApi.signup).toHaveBeenCalledWith(credentials);
  });

  it('clears local authentication even if server logout fails', async () => {
    const user = userEvent.setup();

    vi.mocked(authApi.me).mockResolvedValue(testUser);
    vi.mocked(authApi.logout).mockRejectedValue(
      new ApiError('network', 'Server logout could not be confirmed'),
    );

    setAuthToken('logout-token');
    renderAuth();

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('authenticated');
    });

    await user.click(screen.getByRole('button', { name: 'Test logout' }));

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('anonymous');
    });

    expect(authApi.logout).toHaveBeenCalledOnce();
    expect(getAuthToken()).toBeNull();
    expect(screen.getByTestId('auth-email')).toBeEmptyDOMElement();
  });
});
