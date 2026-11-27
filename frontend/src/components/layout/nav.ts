import {
  Activity,
  BarChart3,
  Boxes,
  Building2,
  ClipboardList,
  CreditCard,
  FileClock,
  FileSpreadsheet,
  FlaskConical,
  HeartPulse,
  Landmark,
  LayoutDashboard,
  Link2,
  Mic,
  Package,
  Receipt,
  RotateCcw,
  Scale,
  Settings,
  ShoppingBag,
  ShoppingCart,
  Store,
  Truck,
  Upload,
  Users,
  Warehouse,
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
        label: 'POS & Billing',
        path: '/pos',
        icon: Store,
        keywords: ['pos', 'cashier', 'gst', 'upi', 'shift'],
        roles: ['owner', 'admin', 'operator'],
      },
      {
        label: 'Voice Intelligence',
        path: '/voice',
        icon: Mic,
        keywords: ['ai', 'groq', 'hindi', 'hinglish', 'assistant'],
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
      {
        label: 'Catalog',
        path: '/catalog',
        icon: ShoppingBag,
        keywords: ['commerce', 'sku', 'barcode', 'hsn'],
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
      {
        label: 'Retail Inventory',
        path: '/retail-inventory',
        icon: Warehouse,
        keywords: ['stock', 'locations', 'reservations'],
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
      {
        label: 'Warehouses',
        path: '/warehouses',
        icon: Building2,
        keywords: ['transfers', 'stores', 'branches'],
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
      {
        label: 'Procurement',
        path: '/procurement',
        icon: Truck,
        keywords: ['suppliers', 'purchase orders', 'grn', 'requisitions'],
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
      {
        label: 'Orders',
        path: '/orders',
        icon: ShoppingCart,
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
      {
        label: 'Sales & Invoices',
        path: '/sales',
        icon: Receipt,
        keywords: ['pnl', 'gst', 'tax invoice', 'credit note'],
        roles: ['owner', 'admin', 'analyst'],
      },
      {
        label: 'Surge & Promotions',
        path: '/surge-control',
        icon: ClipboardList,
        keywords: ['flash sale', 'coupons', 'campaigns'],
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
      {
        label: 'Returns',
        path: '/returns',
        icon: RotateCcw,
        keywords: ['exchange', 'restock'],
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
    label: 'Finance & Simulation',
    items: [
      {
        label: 'Payments',
        path: '/payments',
        icon: CreditCard,
        keywords: ['razorpay', 'transactions', 'checkout'],
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
      {
        label: 'Refunds',
        path: '/refunds',
        icon: RotateCcw,
        keywords: ['refund', 'approval'],
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
      {
        label: 'Payment Links',
        path: '/payment-links',
        icon: Link2,
        keywords: ['link', 'invoice', 'razorpay'],
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
      {
        label: 'Settlements',
        path: '/settlements',
        icon: Landmark,
        keywords: ['payout', 'fees', 'utr'],
        roles: ['owner', 'admin', 'analyst', 'operator'],
      },
      {
        label: 'Reconciliation',
        path: '/reconciliation',
        icon: Scale,
        keywords: ['exceptions', 'audit', 'mismatch'],
        roles: ['owner', 'admin', 'analyst', 'operator'],
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
    ],
  },
  {
    label: 'Observe',
    items: [
      {
        label: 'Reports Hub',
        path: '/reports',
        icon: FileSpreadsheet,
        keywords: ['csv', 'automation', 'forecast', 'ondc'],
        roles: ['owner', 'admin', 'analyst'],
      },
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
