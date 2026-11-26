import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthProvider } from './AuthProvider';
import { GuestOnly, RequireAuth, RequireRole } from './AuthGuards';
import { authApi } from '@/services/api/authApi';
import type { UserRole } from '@/services/api/authApi';
import { setAuthToken } from '@/services/api/auth';

vi.mock('@/services/api/authApi', () => ({
  authApi: {
    signup: vi.fn(),
    login: vi.fn(),
    me: vi.fn(),
    logout: vi.fn(),
  },
}));

const makeUser = (role: UserRole) => ({
  id: 1,
  email: `${role}@flashcore.test`,
  role,
  status: 'active' as const,
  createdAt: '2026-11-22T10:00:00Z',
});

function renderGuard(
  initialPath: string,
  role: UserRole | null,
  useGuestGuard = false,
) {
  if (role) {
    setAuthToken('guard-test-token');
    vi.mocked(authApi.me).mockResolvedValue(makeUser(role));
  } else {
    setAuthToken(null);
  }

  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AuthProvider>
        <Routes>
          <Route
            path="/login"
            element={
              useGuestGuard ? (
                <GuestOnly>
                  <div>Guest-only sign-in page</div>
                </GuestOnly>
              ) : (
                <div>Login screen</div>
              )
            }
          />
          <Route
            path="/overview"
            element={
              <RequireAuth>
                <div>Protected overview</div>
              </RequireAuth>
            }
          />
          <Route
            path="/restricted"
            element={
              <RequireRole allowedRoles={['admin', 'analyst']}>
                <div>Analytics content</div>
              </RequireRole>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('Authentication route guards', () => {
  beforeEach(() => {
    setAuthToken(null);
    vi.mocked(authApi.me).mockReset();
  });

  it('redirects anonymous users from protected routes to login', async () => {
    renderGuard('/overview', null);

    expect(await screen.findByText('Login screen')).toBeInTheDocument();
  });

  it('allows an authenticated user through RequireAuth', async () => {
    renderGuard('/overview', 'analyst');

    expect(await screen.findByText('Protected overview')).toBeInTheDocument();
  });

  it('redirects authenticated users away from guest-only pages', async () => {
    renderGuard('/login', 'analyst', true);

    expect(await screen.findByText('Protected overview')).toBeInTheDocument();
    expect(screen.queryByText('Guest-only sign-in page')).not.toBeInTheDocument();
  });

  it.each(['admin', 'analyst'] as const)(
    'allows the %s role to access analytics',
    async (role) => {
      renderGuard('/restricted', role);

      expect(await screen.findByText('Analytics content')).toBeInTheDocument();
    },
  );

  it('blocks the operator role from analytics', async () => {
    renderGuard('/restricted', 'operator');

    expect(
      await screen.findByText("You don't have permission to view this page."),
    ).toBeInTheDocument();

    expect(screen.queryByText('Analytics content')).not.toBeInTheDocument();
  });
});
