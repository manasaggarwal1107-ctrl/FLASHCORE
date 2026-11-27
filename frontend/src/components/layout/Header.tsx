import { useContext, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { QueryClientContext, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Bell,
  Building2,
  Check,
  KeyRound,
  LogOut,
  Menu,
  Mic,
  Monitor,
  Moon,
  Search,
  Sun,
  UserCircle2,
} from 'lucide-react';

import { Popover } from '@/components/ui/Popover';
import { useAuthToken } from '@/hooks/useAuthToken';
import { useOptionalAuth } from '@/hooks/useAuth';
import { expansionApi } from '@/services/api/expansionApi';
import { Breadcrumbs } from './Breadcrumbs';
import { ConnectivityIndicator, EnvironmentBadge } from './StatusIndicators';
import { useTheme } from './ThemeProvider';
import type { ThemePreference } from './ThemeProvider';

const iconButton =
  'inline-flex h-8 w-8 items-center justify-center rounded text-ink-muted transition-colors hover:bg-surface-raised hover:text-ink';

const THEME_OPTIONS: Array<{
  value: ThemePreference;
  label: string;
  icon: typeof Sun;
}> = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System default', icon: Monitor },
];

function NotificationsBellControl({ orgId, enabled }: { orgId?: number; enabled: boolean }) {
  const qc = useQueryClient();
  const notificationsQ = useQuery({
    queryKey: ['header.notifications', orgId],
    queryFn: expansionApi.listNotifications,
    enabled,
  });
  const markReadMut = useMutation({
    mutationFn: (id: string) => expansionApi.markNotificationRead(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['header.notifications'] }),
  });

  return (
    <Popover
      trigger={({ toggle, ...aria }) => (
        <button
          type="button"
          onClick={toggle}
          className={`${iconButton} relative`}
          aria-label="Notifications"
          {...aria}
        >
          <Bell className="h-4 w-4" aria-hidden />
          {(notificationsQ.data?.unreadCount ?? 0) > 0 && (
            <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-warning" aria-hidden />
          )}
        </button>
      )}
    >
      {() => (
        <div className="w-80 p-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Alerts & Notifications</h2>
            <span className="text-2xs text-ink-faint">{notificationsQ.data?.unreadCount ?? 0} unread</span>
          </div>
          <div className="mt-2 max-h-64 space-y-2 overflow-y-auto">
            {(notificationsQ.data?.items ?? []).length === 0 ? (
              <p className="text-xs text-ink-muted">No active operational alerts.</p>
            ) : (
              notificationsQ.data?.items.slice(0, 8).map((n) => (
                <div key={n.id} className="rounded border border-line bg-surface-raised p-2 text-xs">
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium text-ink">{n.title}</span>
                    {!n.isRead && (
                      <button type="button" onClick={() => markReadMut.mutate(n.id)} className="text-2xs text-accent underline">
                        Mark read
                      </button>
                    )}
                  </div>
                  <p className="mt-0.5 text-ink-muted">{n.message}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </Popover>
  );
}

export function Header({
  onOpenMobileNav,
  onOpenSearch,
}: {
  onOpenMobileNav: () => void;
  onOpenSearch: () => void;
}) {
  const token = useAuthToken();
  const auth = useOptionalAuth();
  const hasQueryClient = Boolean(useContext(QueryClientContext));
  const navigate = useNavigate();
  const { theme, preference, systemTheme, setTheme } = useTheme();
  const [switchingOrg, setSwitchingOrg] = useState(false);

  const ActiveThemeIcon = preference === 'system' ? Monitor : theme === 'dark' ? Moon : Sun;

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

        <Popover
          trigger={({ toggle, ...aria }) => (
            <button
              type="button"
              onClick={toggle}
              className={iconButton}
              aria-label={`Theme mode: ${preference}`}
              title={`Theme: ${preference === 'system' ? `System (${theme})` : preference}`}
              {...aria}
            >
              <ActiveThemeIcon className="h-4 w-4" aria-hidden />
            </button>
          )}
        >
          {(close) => (
            <div className="w-52 p-1.5" role="radiogroup" aria-label="Theme mode">
              <div className="px-2.5 py-1.5 text-2xs font-medium uppercase text-ink-faint">
                Appearance
              </div>
              {THEME_OPTIONS.map((option) => {
                const Icon = option.icon;
                const selected = preference === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => {
                      setTheme(option.value);
                      close();
                    }}
                    className="flex w-full items-center justify-between rounded px-2.5 py-1.5 text-left text-sm text-ink transition-colors hover:bg-surface-raised"
                  >
                    <span className="flex items-center gap-2">
                      <Icon className="h-3.5 w-3.5 text-ink-muted" aria-hidden />
                      <span>
                        <span className="block">{option.label}</span>
                        {option.value === 'system' && (
                          <span className="block text-2xs text-ink-faint">
                            Active: {systemTheme}
                          </span>
                        )}
                      </span>
                    </span>
                    {selected && <Check className="h-3.5 w-3.5 text-accent" aria-hidden />}
                  </button>
                );
              })}
            </div>
          )}
        </Popover>

        <ConnectivityIndicator />
        <EnvironmentBadge />

        <Link to="/voice" className={iconButton} aria-label="Voice Intelligence" title="FLASHCORE Voice Intelligence">
          <Mic className="h-4 w-4" aria-hidden />
        </Link>

        {hasQueryClient ? (
          <NotificationsBellControl orgId={activeOrg?.organisationId} enabled={Boolean(user && activeOrg)} />
        ) : (
          <button type="button" className={iconButton} aria-label="Notifications">
            <Bell className="h-4 w-4" aria-hidden />
          </button>
        )}

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
                        // Local credentials cleared by AuthProvider even if unreachable.
                      }
                      close();
                      navigate('/login', { replace: true });
                    })();
                  }}
                  className="mt-1 flex h-8 w-full items-center gap-2 rounded px-2.5 text-sm text-danger hover:bg-danger/10"
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
