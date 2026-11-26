import { Suspense, lazy } from 'react';
import type { ComponentType } from 'react';
import { Navigate, createBrowserRouter } from 'react-router-dom';

import { AppShell } from '@/components/layout/AppShell';
import { LoadingRegion, Skeleton } from '@/components/ui/Skeleton';
import { RequireAuth, GuestOnly, RequireRole } from '@/app/AuthGuards';
import { LoginPage } from '@/features/auth/LoginPage';
import { SignupPage } from '@/features/auth/SignupPage';

/** Route-level code splitting: pages export a named component. */
function page<K extends string>(
  loader: () => Promise<Record<K, ComponentType>>,
  name: K,
) {
  const Lazy = lazy<ComponentType>(async () => ({
    default: (await loader())[name],
  }));

  return (
    <Suspense
      fallback={
        <LoadingRegion label="Loading page" className="space-y-4">
          <Skeleton className="h-7 w-56" />
          <Skeleton className="h-64 w-full" />
        </LoadingRegion>
      }
    >
      <Lazy />
    </Suspense>
  );
}

export const router = createBrowserRouter([
  {
    path: '/login',
    element: (
      <GuestOnly>
        <LoginPage />
      </GuestOnly>
    ),
  },
  {
    path: '/signup',
    element: (
      <GuestOnly>
        <SignupPage />
      </GuestOnly>
    ),
  },
  {
    path: '/token-access',
    element: page(
      () => import('@/features/settings/SettingsPage'),
      'SettingsPage',
    ),
  },
  {
    path: '/',
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Navigate to="/overview" replace /> },

      {
        path: 'overview',
        element: (
          <RequireRole allowedRoles={['admin', 'analyst']}>
            {page(
              () => import('@/features/overview/OverviewPage'),
              'OverviewPage',
            )}
          </RequireRole>
        ),
      },

      {
        path: 'products',
        element: page(
          () => import('@/features/products/ProductsPage'),
          'ProductsPage',
        ),
      },
      {
        path: 'products/new',
        element: page(
          () => import('@/features/products/ProductFormPage'),
          'ProductFormPage',
        ),
      },
      {
        path: 'products/:id',
        element: page(
          () => import('@/features/products/ProductDetailPage'),
          'ProductDetailPage',
        ),
      },
      {
        path: 'products/:id/edit',
        element: page(
          () => import('@/features/products/ProductFormPage'),
          'ProductFormPage',
        ),
      },

      {
        path: 'inventory',
        element: page(
          () => import('@/features/inventory/InventoryPage'),
          'InventoryPage',
        ),
      },

      {
        path: 'flash-sales',
        element: page(
          () => import('@/features/flash-sales/FlashSalesPage'),
          'FlashSalesPage',
        ),
      },
      {
        path: 'flash-sales/new',
        element: page(
          () => import('@/features/flash-sales/FlashSaleFormPage'),
          'FlashSaleFormPage',
        ),
      },
      {
        path: 'flash-sales/:id',
        element: page(
          () => import('@/features/flash-sales/FlashSaleDetailPage'),
          'FlashSaleDetailPage',
        ),
      },
      {
        path: 'flash-sales/:id/edit',
        element: page(
          () => import('@/features/flash-sales/FlashSaleFormPage'),
          'FlashSaleFormPage',
        ),
      },

      {
        path: 'orders',
        element: page(
          () => import('@/features/orders/OrdersPage'),
          'OrdersPage',
        ),
      },
      {
        path: 'orders/:id',
        element: page(
          () => import('@/features/orders/OrderDetailPage'),
          'OrderDetailPage',
        ),
      },

      {
        path: 'customers',
        element: page(
          () => import('@/features/customers/CustomersPage'),
          'CustomersPage',
        ),
      },
      {
        path: 'customers/:id',
        element: page(
          () => import('@/features/customers/CustomerDetailPage'),
          'CustomerDetailPage',
        ),
      },

      {
        path: 'analytics',
        element: (
          <RequireRole allowedRoles={['admin', 'analyst']}>
            {page(
              () => import('@/features/analytics/AnalyticsPage'),
              'AnalyticsPage',
            )}
          </RequireRole>
        ),
      },

      {
        path: 'transactions',
        element: page(
          () => import('@/features/transactions/TransactionsPage'),
          'TransactionsPage',
        ),
      },
      {
        path: 'transactions/:id',
        element: page(
          () => import('@/features/transactions/TransactionDetailPage'),
          'TransactionDetailPage',
        ),
      },

      {
        path: 'concurrency',
        element: page(
          () => import('@/features/concurrency/ConcurrencyPage'),
          'ConcurrencyPage',
        ),
      },

      {
        path: 'imports',
        element: page(
          () => import('@/features/imports/ImportsPage'),
          'ImportsPage',
        ),
      },
      {
        path: 'imports/:id',
        element: page(
          () => import('@/features/imports/ImportDetailPage'),
          'ImportDetailPage',
        ),
      },

      {
        path: 'audit',
        element: page(
          () => import('@/features/audit/AuditPage'),
          'AuditPage',
        ),
      },
      {
        path: 'system',
        element: page(
          () => import('@/features/system/SystemHealthPage'),
          'SystemHealthPage',
        ),
      },
      {
        path: 'settings',
        element: page(
          () => import('@/features/settings/SettingsPage'),
          'SettingsPage',
        ),
      },

      {
        path: '*',
        element: page(
          () => import('@/routes/NotFoundPage'),
          'NotFoundPage',
        ),
      },
    ],
  },
]);

