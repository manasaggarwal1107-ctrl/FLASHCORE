import type { ReactNode } from 'react';
import { Link, Navigate } from 'react-router-dom';

import { Button } from '@/components/ui/Button';
import { useAuth } from '@/hooks/useAuth';
import type { UserRole } from '@/services/api/authApi';

function AuthLoading() {
  return (
    <main className="flex min-h-full items-center justify-center bg-canvas px-4">
      <div className="text-center">
        <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-line border-t-accent" />
        <p className="text-sm text-ink-muted">
          Verifying your FLASHCORE session...
        </p>
      </div>
    </main>
  );
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status, error, retrySession } = useAuth();

  if (status === 'loading') return <AuthLoading />;

  if (status === 'anonymous') {
    return <Navigate to="/login" replace />;
  }

  if (status === 'error') {
    return (
      <main className="flex min-h-full items-center justify-center bg-canvas px-4">
        <section className="panel w-full max-w-md p-6">
          <h1 className="text-lg font-semibold text-ink">
            Unable to verify your session
          </h1>
          <p className="mt-2 text-sm text-ink-muted">
            {error || 'The authentication service could not be reached.'}
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Button variant="primary" onClick={retrySession}>
              Retry verification
            </Button>
            <Link
              to="/login"
              className="inline-flex h-9 items-center rounded border border-line-strong px-3 text-sm text-ink-muted hover:bg-surface-raised"
            >
              Return to sign in
            </Link>
          </div>
        </section>
      </main>
    );
  }

  return children;
}

export function GuestOnly({ children }: { children: ReactNode }) {
  const { status } = useAuth();

  if (status === 'loading') return <AuthLoading />;

  if (status === 'authenticated') {
    return <Navigate to="/overview" replace />;
  }

  return children;
}

export function RequireRole({
  allowedRoles,
  children,
}: {
  allowedRoles: UserRole[];
  children: ReactNode;
}) {
  const { status, user } = useAuth();

  if (status === 'loading') return <AuthLoading />;

  if (status !== 'authenticated' || !user) {
    return <Navigate to="/login" replace />;
  }

  if (!allowedRoles.includes(user.role)) {
    return (
      <main className="flex min-h-full items-center justify-center bg-canvas px-4">
        <section className="panel w-full max-w-md p-6">
          <p className="eyebrow mb-2">Access restricted</p>
          <h1 className="text-lg font-semibold text-ink">
            You don't have permission to view this page.
          </h1>
          <p className="mt-2 text-sm text-ink-muted">
            Your current role ({user.role}) does not have access to this section.
            Contact an administrator if you believe this is incorrect.
          </p>
          <div className="mt-5">
            <Link to="/settings">
              <Button variant="secondary">Return to settings</Button>
            </Link>
          </div>
        </section>
      </main>
    );
  }

  return children;
}
