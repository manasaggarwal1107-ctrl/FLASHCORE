import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthProvider } from './AuthProvider';
import { RequireAuth, RequireRole } from './AuthGuards';
import { Header } from '@/components/layout/Header';
import { ThemeProvider } from '@/components/layout/ThemeProvider';
import { useAuth } from '@/hooks/useAuth';
import { useResource } from '@/hooks/useResource';
import {
  getActiveOrganisationId,
  getAuthToken,
  setActiveOrganisationId,
  setAuthToken,
} from '@/services/api/auth';
import { authApi } from '@/services/api/authApi';
import type { AuthUser, UserOrganisation } from '@/services/api/authApi';
import { endpoints } from '@/services/api/endpoints';
import { ApiError } from '@/services/api/errors';
import { createQueryClient } from '@/services/api/queryClient';
import { jsonResponse } from '@/test/utils';

vi.mock('@/services/api/authApi', () => ({
  authApi: {
    signup: vi.fn(),
    login: vi.fn(),
    me: vi.fn(),
    logout: vi.fn(),
  },
}));

const orgOne: UserOrganisation = {
  organisationId: 10,
  organisationName: 'Acme Retail',
  organisationSlug: 'acme-retail',
  organisationStatus: 'active',
  role: 'admin',
  membershipStatus: 'active',
};

const orgTwo: UserOrganisation = {
  organisationId: 20,
  organisationName: 'Beta Stores',
  organisationSlug: 'beta-stores',
  organisationStatus: 'active',
  role: 'analyst',
  membershipStatus: 'active',
};

const multiOrgUser: AuthUser = {
  id: 7,
  email: 'multi@flashcore.test',
  role: 'analyst',
  status: 'active',
  createdAt: '2026-11-26T10:00:00Z',
  activeOrganisationId: 10,
  activeOrganisationRole: 'admin',
  organisations: [orgOne, orgTwo],
};

function OrgWorkspaceProbe() {
  const auth = useAuth();
  const runs = useResource<Array<{ id: number; runName: string }>>(
    endpoints.concurrency.runs,
  );

  return (
    <div>
      <Header onOpenMobileNav={() => undefined} onOpenSearch={() => undefined} />
      <output data-testid="active-org-id">
        {auth.activeOrganisation?.organisationId ?? ''}
      </output>
      <output data-testid="active-org-role">{auth.activeRole ?? ''}</output>
      <output data-testid="runs-data">
        {runs.data ? runs.data.map((r) => r.runName).join(',') : 'loading-or-empty'}
      </output>
    </div>
  );
}

describe('Organisation context, cache isolation and route protection', () => {
  beforeEach(() => {
    setAuthToken(null);
    setActiveOrganisationId(null);
    vi.restoreAllMocks();
    vi.mocked(authApi.me).mockReset();
  });

  it('switches organisations, sends X-Organisation-Id, and clears previous org cache', async () => {
    const user = userEvent.setup();
    const queryClient = createQueryClient();

    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const headers = new Headers(init?.headers);
      const orgHeader = headers.get('X-Organisation-Id');
      const url = typeof input === 'string' ? input : input.toString();

      if (url.includes('/simulations/runs')) {
        if (orgHeader === '20') {
          return Promise.resolve(jsonResponse([{ id: 2, run_name: 'Beta Run' }]));
        }
        return Promise.resolve(jsonResponse([{ id: 1, run_name: 'Acme Run' }]));
      }
      return Promise.resolve(jsonResponse({}));
    });
    vi.stubGlobal('fetch', fetchMock);

    setAuthToken('multi-token');
    vi.mocked(authApi.me)
      .mockResolvedValueOnce(multiOrgUser)
      .mockResolvedValueOnce({
        ...multiOrgUser,
        activeOrganisationId: 20,
        activeOrganisationRole: 'analyst',
      });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <ThemeProvider>
            <AuthProvider
              onClearCache={() => {
                void queryClient.cancelQueries();
                queryClient.clear();
              }}
            >
              <OrgWorkspaceProbe />
            </AuthProvider>
          </ThemeProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('active-org-id')).toHaveTextContent('10');
    });
    expect(screen.getByTestId('active-org-role')).toHaveTextContent('admin');
    await waitFor(() => {
      expect(screen.getByTestId('runs-data')).toHaveTextContent('Acme Run');
    });

    const select = screen.getByRole('combobox', { name: 'Active organisation' });
    await user.selectOptions(select, '20');

    await waitFor(() => {
      expect(screen.getByTestId('active-org-id')).toHaveTextContent('20');
    });
    expect(screen.getByTestId('active-org-role')).toHaveTextContent('analyst');
    await waitFor(() => {
      expect(screen.getByTestId('runs-data')).toHaveTextContent('Beta Run');
    });
    expect(screen.getByTestId('runs-data')).not.toHaveTextContent('Acme Run');
    expect(getActiveOrganisationId()).toBe(20);
  });

  it('handles revoked membership safely when no active organisations remain', async () => {
    setAuthToken('revoked-token');
    setActiveOrganisationId(20);
    vi.mocked(authApi.me).mockResolvedValue({
      ...multiOrgUser,
      activeOrganisationId: null,
      activeOrganisationRole: null,
      organisations: [],
    });

    render(
      <MemoryRouter initialEntries={['/overview']}>
        <AuthProvider>
          <Routes>
            <Route
              path="/overview"
              element={
                <RequireAuth>
                  <div>Protected Overview</div>
                </RequireAuth>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(
      await screen.findByText('No active organisation membership'),
    ).toBeInTheDocument();
    expect(screen.queryByText('Protected Overview')).not.toBeInTheDocument();
    expect(getActiveOrganisationId()).toBeNull();
  });

  it('clears token and org on expired session (401) and blocks unauthenticated access', async () => {
    setAuthToken('expired-token');
    setActiveOrganisationId(10);
    vi.mocked(authApi.me).mockRejectedValue(
      new ApiError('unauthorized', 'Session expired', { status: 401 }),
    );

    render(
      <MemoryRouter initialEntries={['/token-access']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<div>Login Page</div>} />
            <Route
              path="/token-access"
              element={
                <RequireAuth>
                  <div>Settings Content</div>
                </RequireAuth>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Login Page')).toBeInTheDocument();
    expect(getAuthToken()).toBeNull();
    expect(getActiveOrganisationId()).toBeNull();
  });

  it('enforces permission-based route protection using active organisation role', async () => {
    setAuthToken('org-role-token');
    vi.mocked(authApi.me).mockResolvedValue({
      ...multiOrgUser,
      role: 'admin',
      activeOrganisationId: 20,
      activeOrganisationRole: 'analyst',
      organisations: [orgTwo],
    });

    render(
      <MemoryRouter initialEntries={['/audit']}>
        <AuthProvider>
          <Routes>
            <Route
              path="/audit"
              element={
                <RequireAuth>
                  <RequireRole allowedRoles={['owner', 'admin']}>
                    <div>Audit Logs Content</div>
                  </RequireRole>
                </RequireAuth>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("You don't have permission to view this page."),
    ).toBeInTheDocument();
    expect(screen.queryByText('Audit Logs Content')).not.toBeInTheDocument();
  });
});
