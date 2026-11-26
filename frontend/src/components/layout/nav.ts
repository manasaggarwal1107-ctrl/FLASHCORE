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
        roles: ['owner', 'admin', 'analyst'],
      },
      {
        label: 'Products',
        path: '/products',
        icon: Package,
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
      {
        label: 'Inventory',
        path: '/inventory',
        icon: Boxes,
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
      {
        label: 'Flash Sales',
        path: '/flash-sales',
        icon: Zap,
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
      {
        label: 'Orders',
        path: '/orders',
        icon: ShoppingCart,
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
      {
        label: 'Customers',
        path: '/customers',
        icon: Users,
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
    ],
  },
  {
    label: 'Observe',
    items: [
      {
        label: 'Analytics',
        path: '/analytics',
        icon: BarChart3,
        roles: ['owner', 'admin', 'analyst'],
      },
      {
        label: 'Transaction Monitor',
        path: '/transactions',
        icon: Activity,
        keywords: ['purchase', 'attempts'],
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
      {
        label: 'Concurrency Lab',
        path: '/concurrency',
        icon: FlaskConical,
        keywords: ['simulation', 'load'],
        roles: ['owner', 'admin', 'analyst', 'operator'],
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
        roles: ['owner', 'admin', 'analyst'],
      },
      {
        label: 'Audit Logs',
        path: '/audit',
        icon: FileClock,
        roles: ['owner', 'admin'],
      },
      {
        label: 'System Health',
        path: '/system',
        icon: HeartPulse,
        keywords: ['status'],
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
      {
        label: 'Settings',
        path: '/settings',
        icon: Settings,
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
    ],
  },
];

export const allNavItems: NavItem[] = navGroups.flatMap((g) => g.items);

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
