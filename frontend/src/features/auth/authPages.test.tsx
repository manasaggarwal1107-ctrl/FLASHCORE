import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthProvider } from '@/app/AuthProvider';
import { GuestOnly, RequireAuth } from '@/app/AuthGuards';
import { LoginPage } from './LoginPage';
import { SignupPage } from './SignupPage';
import { authApi } from '@/services/api/authApi';
import { setAuthToken } from '@/services/api/auth';
import { ApiError } from '@/services/api/errors';

vi.mock('@/services/api/authApi', () => ({
  authApi: {
    signup: vi.fn(),
    login: vi.fn(),
    me: vi.fn(),
    logout: vi.fn(),
  },
}));

const authResponse = {
  accessToken: 'ui-test-token',
  tokenType: 'bearer' as const,
  expiresAt: '2026-11-23T10:00:00Z',
  user: {
    id: 1,
    email: 'analyst@flashcore.test',
    role: 'analyst' as const,
    status: 'active' as const,
    createdAt: '2026-11-22T10:00:00Z',
  },
};

function renderAuthRoutes(initialPath: '/login' | '/signup') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AuthProvider>
        <Routes>
          <Route
            path="/login"
            element={
              <GuestOnly>
                <LoginPage />
              </GuestOnly>
            }
          />
          <Route
            path="/signup"
            element={
              <GuestOnly>
                <SignupPage />
              </GuestOnly>
            }
          />
          <Route
            path="/overview"
            element={
              <RequireAuth>
                <div>Overview dashboard</div>
              </RequireAuth>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('LoginPage', () => {
  beforeEach(() => {
    setAuthToken(null);
    vi.mocked(authApi.login).mockReset();
    vi.mocked(authApi.me).mockReset();
  });

  it('renders the sign-in form', () => {
    renderAuthRoutes('/login');

    expect(screen.getByRole('heading', { name: 'Sign in to FLASHCORE' })).toBeInTheDocument();
    expect(screen.getByLabelText('Email address')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
  });

  it('validates invalid email without calling the API', async () => {
    const user = userEvent.setup();
    renderAuthRoutes('/login');

    await user.type(screen.getByLabelText('Email address'), 'invalid-email');
    await user.type(screen.getByLabelText('Password'), 'password123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument();
    expect(authApi.login).not.toHaveBeenCalled();
  });

  it('logs in successfully and redirects to overview', async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.login).mockResolvedValue(authResponse);

    renderAuthRoutes('/login');

    await user.type(screen.getByLabelText('Email address'), 'analyst@flashcore.test');
    await user.type(screen.getByLabelText('Password'), 'correct-password-123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText('Overview dashboard')).toBeInTheDocument();
    expect(authApi.login).toHaveBeenCalledWith({
      email: 'analyst@flashcore.test',
      password: 'correct-password-123',
    });
  });

  it('shows a server authentication error', async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.login).mockRejectedValue(
      new ApiError('unauthorized', 'Invalid email or password', { status: 401 }),
    );

    renderAuthRoutes('/login');

    await user.type(screen.getByLabelText('Email address'), 'analyst@flashcore.test');
    await user.type(screen.getByLabelText('Password'), 'incorrect-password');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password');
  });
});

describe('SignupPage', () => {
  beforeEach(() => {
    setAuthToken(null);
    vi.mocked(authApi.signup).mockReset();
    vi.mocked(authApi.me).mockReset();
  });

  it('renders all registration fields', () => {
    renderAuthRoutes('/signup');

    expect(screen.getByRole('heading', { name: 'Create your account' })).toBeInTheDocument();
    expect(screen.getByLabelText('Email address')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
    expect(screen.getByLabelText('Confirm password')).toBeInTheDocument();
  });

  it('rejects passwords shorter than 12 characters', async () => {
    const user = userEvent.setup();
    renderAuthRoutes('/signup');

    await user.type(screen.getByLabelText('Email address'), 'analyst@flashcore.test');
    await user.type(screen.getByLabelText('Password'), 'short123');
    await user.type(screen.getByLabelText('Confirm password'), 'short123');
    await user.click(screen.getByRole('button', { name: /create account/i }));

    expect(await screen.findByText('Password must contain at least 12 characters.')).toBeInTheDocument();
    expect(authApi.signup).not.toHaveBeenCalled();
  });

  it('rejects mismatched password confirmation', async () => {
    const user = userEvent.setup();
    renderAuthRoutes('/signup');

    await user.type(screen.getByLabelText('Email address'), 'analyst@flashcore.test');
    await user.type(screen.getByLabelText('Password'), 'correct-password-123');
    await user.type(screen.getByLabelText('Confirm password'), 'different-password');
    await user.click(screen.getByRole('button', { name: /create account/i }));

    expect(await screen.findByText('Passwords do not match.')).toBeInTheDocument();
    expect(authApi.signup).not.toHaveBeenCalled();
  });

  it('creates an account and redirects to overview', async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.signup).mockResolvedValue(authResponse);

    renderAuthRoutes('/signup');

    await user.type(screen.getByLabelText('Email address'), 'analyst@flashcore.test');
    await user.type(screen.getByLabelText('Password'), 'correct-password-123');
    await user.type(screen.getByLabelText('Confirm password'), 'correct-password-123');
    await user.click(screen.getByRole('button', { name: /create account/i }));

    expect(await screen.findByText('Overview dashboard')).toBeInTheDocument();
    expect(authApi.signup).toHaveBeenCalledWith({
      email: 'analyst@flashcore.test',
      password: 'correct-password-123',
    });
  });

  it('shows a duplicate-account server error', async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.signup).mockRejectedValue(
      new ApiError('validation', 'An account with this email already exists', { status: 409 }),
    );

    renderAuthRoutes('/signup');

    await user.type(screen.getByLabelText('Email address'), 'analyst@flashcore.test');
    await user.type(screen.getByLabelText('Password'), 'correct-password-123');
    await user.type(screen.getByLabelText('Confirm password'), 'correct-password-123');
    await user.click(screen.getByRole('button', { name: /create account/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'An account with this email already exists',
    );
  });
});

