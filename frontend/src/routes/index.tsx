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
          <RequireRole allowedRoles={['owner', 'admin', 'analyst']}>
            {page(
              () => import('@/features/overview/OverviewPage'),
              'OverviewPage',
            )}
          </RequireRole>
        ),
      },
      {
        path: 'pos',
        element: (
          <RequireRole allowedRoles={['owner', 'admin', 'operator']}>
            {page(() => import('@/features/pos/PosPage'), 'PosPage')}
          </RequireRole>
        ),
      },
      {
        path: 'voice',
        element: page(
          () => import('@/features/voice/VoiceIntelligencePage'),
          'VoiceIntelligencePage',
        ),
      },
      {
        path: 'warehouses',
        element: page(
          () => import('@/features/operations/WarehousesPage'),
          'WarehousesPage',
        ),
      },
      {
        path: 'procurement',
        element: page(
          () => import('@/features/operations/ProcurementPage'),
          'ProcurementPage',
        ),
      },
      {
        path: 'sales',
        element: (
          <RequireRole allowedRoles={['owner', 'admin', 'analyst']}>
            {page(
              () => import('@/features/operations/SalesInvoicesPage'),
              'SalesInvoicesPage',
            )}
          </RequireRole>
        ),
      },
      {
        path: 'surge-control',
        element: page(
          () => import('@/features/operations/CampaignsPromotionsPage'),
          'CampaignsPromotionsPage',
        ),
      },
      {
        path: 'returns',
        element: page(
          () => import('@/features/operations/ReturnsPage'),
          'ReturnsPage',
        ),
      },
      {
        path: 'reports',
        element: (
          <RequireRole allowedRoles={['owner', 'admin', 'analyst']}>
            {page(
              () => import('@/features/operations/ReportsHubPage'),
              'ReportsHubPage',
            )}
          </RequireRole>
        ),
      },

      {
        path: 'catalog',
        element: page(
          () => import('@/features/catalog/CatalogPage'),
          'CatalogPage',
        ),
      },
      {
        path: 'retail-inventory',
        element: page(
          () => import('@/features/catalog/RetailInventoryPage'),
          'RetailInventoryPage',
        ),
      },
      {
        path: 'payments',
        element: page(
          () => import('@/features/payments/PaymentsPage'),
          'PaymentsPage',
        ),
      },
      {
        path: 'refunds',
        element: page(
          () => import('@/features/finance/RefundsPage'),
          'RefundsPage',
        ),
      },
      {
        path: 'payment-links',
        element: page(
          () => import('@/features/finance/PaymentLinksPage'),
          'PaymentLinksPage',
        ),
      },
      {
        path: 'settlements',
        element: page(
          () => import('@/features/finance/SettlementsPage'),
          'SettlementsPage',
        ),
      },
      {
        path: 'reconciliation',
        element: page(
          () => import('@/features/finance/ReconciliationPage'),
          'ReconciliationPage',
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
        element: (
          <RequireRole allowedRoles={['owner', 'admin', 'operator']}>
            {page(
              () => import('@/features/products/ProductFormPage'),
              'ProductFormPage',
            )}
          </RequireRole>
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
        element: (
          <RequireRole allowedRoles={['owner', 'admin', 'operator']}>
            {page(
              () => import('@/features/products/ProductFormPage'),
              'ProductFormPage',
            )}
          </RequireRole>
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
        element: (
          <RequireRole allowedRoles={['owner', 'admin', 'operator']}>
            {page(
              () => import('@/features/flash-sales/FlashSaleFormPage'),
              'FlashSaleFormPage',
            )}
          </RequireRole>
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
        element: (
          <RequireRole allowedRoles={['owner', 'admin', 'operator']}>
            {page(
              () => import('@/features/flash-sales/FlashSaleFormPage'),
              'FlashSaleFormPage',
            )}
          </RequireRole>
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
          <RequireRole allowedRoles={['owner', 'admin', 'analyst']}>
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
        element: (
          <RequireRole allowedRoles={['owner', 'admin', 'analyst']}>
            {page(
              () => import('@/features/imports/ImportsPage'),
              'ImportsPage',
            )}
          </RequireRole>
        ),
      },
      {
        path: 'imports/:id',
        element: (
          <RequireRole allowedRoles={['owner', 'admin', 'analyst']}>
            {page(
              () => import('@/features/imports/ImportDetailPage'),
              'ImportDetailPage',
            )}
          </RequireRole>
        ),
      },

      {
        path: 'audit',
        element: (
          <RequireRole allowedRoles={['owner', 'admin']}>
            {page(
              () => import('@/features/audit/AuditPage'),
              'AuditPage',
            )}
          </RequireRole>
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
        path: 'token-access',
        element: <Navigate to="/settings" replace />,
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
