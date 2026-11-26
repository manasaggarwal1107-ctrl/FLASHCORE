import { NavLink } from 'react-router-dom';
import { ChevronsLeft, ChevronsRight } from 'lucide-react';

import { cn } from '@/lib/cn';
import { useOptionalAuth } from '@/hooks/useAuth';
import { Logo } from './Logo';
import { getNavGroupsForRole, navGroups } from './nav';

export function SidebarNav({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const auth = useOptionalAuth();

  const visibleGroups = auth?.user
    ? getNavGroupsForRole(auth.user.role)
    : navGroups;

  return (
    <nav aria-label="Primary" className="flex-1 overflow-y-auto px-2 py-3">
      {visibleGroups.map((group) => (
        <div key={group.label} className="mb-4">
          {!collapsed && (
            <div className="eyebrow mb-1.5 px-2">{group.label}</div>
          )}

          {collapsed && (
            <div
              className="mx-2 mb-1.5 border-t border-line first:hidden"
              aria-hidden
            />
          )}

          <ul className="space-y-0.5">
            {group.items.map((item) => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  onClick={onNavigate}
                  title={collapsed ? item.label : undefined}
                  className={({ isActive }) =>
                    cn(
                      'group relative flex h-8 items-center gap-2.5 rounded px-2 text-sm transition-colors',
                      collapsed && 'justify-center',
                      isActive
                        ? 'bg-accent/10 font-medium text-accent'
                        : 'text-ink-muted hover:bg-surface-raised hover:text-ink',
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <span
                          className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-accent"
                          aria-hidden
                        />
                      )}

                      <item.icon className="h-4 w-4 shrink-0" aria-hidden />

                      {collapsed ? (
                        <span className="sr-only">{item.label}</span>
                      ) : (
                        <span className="truncate">{item.label}</span>
                      )}
                    </>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

/** Desktop (lg+) collapsible sidebar. */
export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <aside
      className={cn(
        'hidden shrink-0 flex-col border-r border-line bg-sidebar transition-[width] duration-200 lg:flex',
        collapsed ? 'w-[60px]' : 'w-60',
      )}
    >
      <div
        className={cn(
          'flex h-14 items-center border-b border-line',
          collapsed ? 'justify-center' : 'px-4',
        )}
      >
        <Logo collapsed={collapsed} />
      </div>

      <SidebarNav collapsed={collapsed} />

      <div className="border-t border-line p-2">
        <button
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
          aria-expanded={!collapsed}
          className={cn(
            'flex h-8 w-full items-center gap-2 rounded px-2 text-xs text-ink-faint transition-colors hover:bg-surface-raised hover:text-ink',
            collapsed && 'justify-center',
          )}
        >
          {collapsed ? (
            <ChevronsRight className="h-4 w-4" aria-hidden />
          ) : (
            <>
              <ChevronsLeft className="h-4 w-4" aria-hidden />
              Collapse
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
