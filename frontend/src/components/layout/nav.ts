import {
  Activity,
  BarChart3,
  Boxes,
  FileClock,
  FlaskConical,
  HeartPulse,
  LayoutDashboard,
  Package,
  Settings,
  ShoppingCart,
  Upload,
  Users,
  Zap,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { UserRole } from '@/services/api/authApi';

export interface NavItem {
  label: string;
  path: string;
  icon: LucideIcon;
  keywords?: string[];
  roles?: UserRole[];
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const navGroups: NavGroup[] = [
  {
    label: 'Operate',
    items: [
      {
        label: 'Overview',
        path: '/overview',
        icon: LayoutDashboard,
        roles: ['admin', 'analyst'],
      },
      { label: 'Products', path: '/products', icon: Package },
      { label: 'Inventory', path: '/inventory', icon: Boxes },
      { label: 'Flash Sales', path: '/flash-sales', icon: Zap },
      { label: 'Orders', path: '/orders', icon: ShoppingCart },
      { label: 'Customers', path: '/customers', icon: Users },
    ],
  },
  {
    label: 'Observe',
    items: [
      {
        label: 'Analytics',
        path: '/analytics',
        icon: BarChart3,
        roles: ['admin', 'analyst'],
      },
      {
        label: 'Transaction Monitor',
        path: '/transactions',
        icon: Activity,
        keywords: ['purchase', 'attempts'],
      },
      {
        label: 'Concurrency Lab',
        path: '/concurrency',
        icon: FlaskConical,
        keywords: ['simulation', 'load'],
      },
    ],
  },
  {
    label: 'Govern',
    items: [
      {
        label: 'Data Imports',
        path: '/imports',
        icon: Upload,
        keywords: ['csv', 'upload'],
      },
      { label: 'Audit Logs', path: '/audit', icon: FileClock },
      {
        label: 'System Health',
        path: '/system',
        icon: HeartPulse,
        keywords: ['status'],
      },
      {
        label: 'Settings',
        path: '/settings',
        icon: Settings,
        roles: ['admin', 'analyst', 'operator'],
      },
    ],
  },
];

export const allNavItems: NavItem[] = navGroups.flatMap((g) => g.items);

/**
 * Returns only navigation entries with a confirmed role mapping.
 * Entries without role metadata remain in the full registry but are
 * excluded until their backend permissions are verified.
 */
export function getNavGroupsForRole(role: UserRole): NavGroup[] {
  return navGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => !item.roles || item.roles.includes(role)),
    }))
    .filter((group) => group.items.length > 0);
}

/** Label lookup for breadcrumbs: first path segment -> nav label. */
export function labelForSegment(segment: string): string | undefined {
  return allNavItems.find((i) => i.path === `/${segment}`)?.label;
}
