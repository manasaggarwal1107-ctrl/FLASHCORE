import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Bell,
  Building2,
  KeyRound,
  LogOut,
  Menu,
  Search,
  UserCircle2,
  Sun,
  Moon,
} from 'lucide-react';

import { Popover } from '@/components/ui/Popover';
import { useAuthToken } from '@/hooks/useAuthToken';
import { useOptionalAuth } from '@/hooks/useAuth';
import { Breadcrumbs } from './Breadcrumbs';
import { ConnectivityIndicator, EnvironmentBadge } from './StatusIndicators';
import { useTheme } from './ThemeProvider';

const iconButton =
  'inline-flex h-8 w-8 items-center justify-center rounded text-ink-muted transition-colors hover:bg-surface-raised hover:text-ink';

export function Header({
  onOpenMobileNav,
  onOpenSearch,
}: {
  onOpenMobileNav: () => void;
  onOpenSearch: () => void;
}) {
  const token = useAuthToken();
  const auth = useOptionalAuth();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const [switchingOrg, setSwitchingOrg] = useState(false);

  const user = auth?.user;
  const organisations = auth?.organisations ?? [];
  const activeOrg = auth?.activeOrganisation;
  const activeRole = auth?.activeRole ?? user?.role;

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-canvas px-3 sm:px-5">
      <button
        type="button"
        className={`${iconButton} lg:hidden`}
        onClick={onOpenMobileNav}
        aria-label="Open navigation"
      >
        <Menu className="h-4 w-4" aria-hidden />
      </button>

      <Breadcrumbs />

      <div className="ml-auto flex items-center gap-2">
        {activeOrg && (
          <div className="hidden items-center gap-1.5 rounded border border-line-strong bg-surface px-2 py-1 text-xs text-ink sm:flex">
            <Building2 className="h-3.5 w-3.5 text-ink-muted" aria-hidden />
            {organisations.length > 1 && auth ? (
              <select
                aria-label="Active organisation"
                disabled={switchingOrg}
                value={activeOrg.organisationId}
                onChange={(event) => {
                  const nextId = Number(event.target.value);
                  if (!Number.isInteger(nextId) || nextId === activeOrg.organisationId) return;
                  setSwitchingOrg(true);
                  void auth.switchOrganisation(nextId).finally(() => {
                    setSwitchingOrg(false);
                  });
                }}
                className="bg-transparent text-xs font-medium text-ink focus:outline-none"
              >
                {organisations.map((org) => (
                  <option key={org.organisationId} value={org.organisationId}>
                    {org.organisationName} ({org.role})
                  </option>
                ))}
              </select>
            ) : (
              <span className="max-w-[160px] truncate font-medium">
                {activeOrg.organisationName}
              </span>
            )}
          </div>
        )}

        <button
          type="button"
          onClick={onOpenSearch}
          className="hidden h-8 w-56 items-center gap-2 rounded border border-line-strong bg-surface px-2.5 text-xs text-ink-faint transition-colors hover:border-ink-faint md:flex"
          aria-label="Open command search"
        >
          <Search className="h-3.5 w-3.5" aria-hidden />
          <span className="flex-1 text-left">Jump to...</span>
          <kbd className="rounded border border-line-strong px-1 font-mono text-2xs">
            Ctrl K
          </kbd>
        </button>

        <button
          type="button"
          onClick={onOpenSearch}
          className={`${iconButton} md:hidden`}
          aria-label="Open command search"
        >
          <Search className="h-4 w-4" aria-hidden />
        </button>

        <button
          type="button"
          onClick={toggleTheme}
          className={iconButton}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {theme === 'dark'
            ? <Sun className="h-4 w-4" aria-hidden />
            : <Moon className="h-4 w-4" aria-hidden />}
        </button>

        <ConnectivityIndicator />
        <EnvironmentBadge />

        <Popover
          trigger={({ toggle, ...aria }) => (
            <button
              type="button"
              onClick={toggle}
              className={iconButton}
              aria-label="Notifications"
              {...aria}
            >
              <Bell className="h-4 w-4" aria-hidden />
            </button>
          )}
        >
          {() => (
            <div className="w-72 p-4">
              <h2 className="text-sm font-semibold">Notifications</h2>
              <p className="mt-2 text-xs text-ink-muted">
                No notification source is connected. Alerts will appear here
                once the API contract defines a notifications endpoint.
              </p>
            </div>
          )}
        </Popover>

        <Popover
          trigger={({ toggle, ...aria }) => (
            <button
              type="button"
              onClick={toggle}
              className={iconButton}
              aria-label="Account menu"
              {...aria}
            >
              <UserCircle2 className="h-5 w-5" aria-hidden />
            </button>
          )}
        >
          {(close) => (
            <div className="w-64 p-1.5">
              <div className="border-b border-line px-2.5 py-2">
                {user ? (
                  <>
                    <div className="truncate text-sm font-medium text-ink">
                      {user.email}
                    </div>
                    <div className="mt-1 text-xs capitalize text-ink-muted">
                      {activeRole} role{activeOrg ? ` · ${activeOrg.organisationName}` : ''}
                    </div>
                    <div className="mt-1 text-2xs text-ink-faint">
                      Account status: {user.status}
                    </div>
                  </>
                ) : (
                  <>
                    <div className="text-sm font-medium">
                      {token ? 'API token set' : 'No API token'}
                    </div>
                    <div className="text-xs text-ink-muted">
                      User identity is unavailable.
                    </div>
                  </>
                )}
              </div>

              <Link
                to="/settings"
                onClick={close}
                className="mt-1 flex h-8 items-center gap-2 rounded px-2.5 text-sm text-ink-muted hover:bg-surface-raised hover:text-ink"
              >
                <KeyRound className="h-4 w-4" aria-hidden />
                Credentials & settings
              </Link>

              {user && auth && (
                <button
                  type="button"
                  onClick={() => {
                    void (async () => {
                      try {
                        await auth.logout();
                      } catch {
                        // Local credentials are cleared by AuthProvider even
                        // if the server cannot confirm session revocation.
                      }

                      close();
                      navigate('/login', { replace: true });
                    })();
                  }}
                  className="mt-1 flex h-8 w-full items-center gap-2 rounded px-2.5 text-sm text-red-400 hover:bg-red-500/10"
                >
                  <LogOut className="h-4 w-4" aria-hidden />
                  Sign out
                </button>
              )}
            </div>
          )}
        </Popover>
      </div>
    </header>
  );
}
