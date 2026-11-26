import type { HttpMethod } from './client';

/**
 * ENDPOINT REGISTRY â€” the only place paths are declared.
 *
 * API_CONTRACT.md has not been supplied yet, so NO endpoint path is invented here. Every entry is
 * `pending-contract` with `path: null`. Pages bound to a pending endpoint render an honest
 * "unavailable" state and make no network calls.
 *
 * To integrate an endpoint: set `path` (relative to VITE_API_BASE_URL, e.g. '/products/:id') and
 * `status: 'confirmed'`, then reconcile the matching types in `src/types/api.ts`.
 */
export type EndpointStatus = 'pending-contract' | 'confirmed';

export interface EndpointSpec {
  id: string;
  label: string;
  method: HttpMethod;
  path: string | null;
  status: EndpointStatus;
}

const pending = (id: string, method: HttpMethod, label: string): EndpointSpec => ({
  id,
  label,
  method,
  path: null,
  status: 'pending-contract',
});

export function isEndpointLive(spec: EndpointSpec): spec is EndpointSpec & { path: string } {
  return spec.status === 'confirmed' && spec.path !== null;
}

/** Replaces `:param` segments; throws if one is missing so a bad URL is never requested. */
export function resolvePath(path: string, params: Record<string, string | number> = {}): string {
  return path.replace(/:([A-Za-z0-9_]+)/g, (_, name: string) => {
    const v = params[name];
    if (v === undefined) throw new Error(`Missing path parameter "${name}" for ${path}`);
    return encodeURIComponent(String(v));
  });
}

export const endpoints = {
  auth: {
    signup: {
      id: 'auth.signup',
      label: 'Create account',
      method: 'POST',
      path: '/auth/signup',
      status: 'confirmed',
    },
    login: {
      id: 'auth.login',
      label: 'Login',
      method: 'POST',
      path: '/auth/login',
      status: 'confirmed',
    },
    me: {
      id: 'auth.me',
      label: 'Get current user',
      method: 'GET',
      path: '/auth/me',
      status: 'confirmed',
    },
    logout: {
      id: 'auth.logout',
      label: 'Logout',
      method: 'POST',
      path: '/auth/logout',
      status: 'confirmed',
    },
  },
  overview: {
    summary: {
      id: 'overview.summary',
      label: 'Rossmann historical sales summary',
      method: 'GET',
      path: '/rossmann/sales/summary',
      status: 'confirmed',
    },
    salesSeries: {
      id: 'overview.salesSeries',
      label: 'Sales over time',
      method: 'GET',
      path: '/rossmann/sales/trend',
      status: 'confirmed',
    },
    purchaseOutcomes: {
      id: 'overview.purchaseOutcomes',
      label: 'Purchase success / failure distribution',
      method: 'GET',
      path: '/simulations/analytics/purchase-outcomes',
      status: 'confirmed',
    },
    inventoryAllocation: {
      id: 'overview.inventoryAllocation',
      label: 'Inventory allocation',
      method: 'GET',
      path: '/simulations/analytics/inventory-allocation',
      status: 'confirmed',
    },
    flashSalePerformance: {
      id: 'overview.flashSalePerformance',
      label: 'Flash sale performance',
      method: 'GET',
      path: '/simulations/analytics/flash-sales-overview',
      status: 'confirmed',
    },
    activity: {
      id: 'overview.activity',
      label: 'Recent activity / transaction timeline',
      method: 'GET',
      path: '/simulations/analytics/activity',
      status: 'confirmed',
    },
  },
    products: {
    list: {
      id: 'products.list',
      label: 'List simulation products',
      method: 'GET',
      path: '/simulations/products',
      status: 'confirmed',
    },
    get: pending('products.get', 'GET', 'Get product'),
    create: {
      id: 'products.create',
      label: 'Create simulation product',
      method: 'POST',
      path: '/simulations/products',
      status: 'confirmed',
    },
    update: pending('products.update', 'PATCH', 'Update product'),
  },
    inventory: {
    list: {
      id: 'inventory.list',
      label: 'List inventory',
      method: 'GET',
      path: '/simulations/inventory',
      status: 'confirmed',
    },
    movements: pending(
      'inventory.movements',
      'GET',
      'Inventory movement history',
    ),
    adjust: {
      id: 'inventory.adjust',
      label: 'Adjust stock',
      method: 'POST',
      path: '/simulations/inventory/:inventory_id/adjust',
      status: 'confirmed',
    },
  },
    flashSales: {
    list: pending('flashSales.list', 'GET', 'List flash sales'),
    get: pending('flashSales.get', 'GET', 'Get flash sale'),
    create: {
      id: 'flashSales.create',
      label: 'Create flash sale',
      method: 'POST',
      path: '/simulations/runs/:run_id/flash-sales',
      status: 'confirmed',
    },
    update: pending('flashSales.update', 'PATCH', 'Update flash sale'),
    activate: {
      id: 'flashSales.activate',
      label: 'Activate flash sale',
      method: 'POST',
      path: '/simulations/flash-sales/:sale_id/activate',
      status: 'confirmed',
    },
    allocate: {
      id: 'flashSales.allocate',
      label: 'Allocate flash-sale stock',
      method: 'POST',
      path: '/simulations/flash-sales/:sale_id/products',
      status: 'confirmed',
    },
  },
  orders: {
    list: pending('orders.list', 'GET', 'List orders'),
    get: pending('orders.get', 'GET', 'Get order'),
  },
  customers: {
    list: pending('customers.list', 'GET', 'List customers'),
    get: pending('customers.get', 'GET', 'Get customer'),
    orders: pending('customers.orders', 'GET', 'Customer order history'),
  },
  analytics: {
    salesTrend: {
      id: 'analytics.salesTrend',
      label: 'Rossmann historical sales trend',
      method: 'GET',
      path: '/rossmann/sales/trend',
      status: 'confirmed',
    },
    orderVolume: {
      id: 'analytics.orderVolume',
      label: 'Rossmann historical customers trend',
      method: 'GET',
      path: '/rossmann/sales/customers-trend',
      status: 'confirmed',
    },    promotionAnalysis: {
      id: 'analytics.promotionAnalysis',
      label: 'Rossmann promotion analysis',
      method: 'GET',
      path: '/rossmann/sales/promotion-analysis',
      status: 'confirmed',
    },
    conversion: {
      id: 'analytics.conversion',
      label: 'Simulation purchase conversion',
      method: 'GET',
      path: '/simulations/analytics/conversion',
      status: 'confirmed',
    },
    inventoryUtilisation: {
      id: 'analytics.inventoryUtilisation',
      label: 'Current inventory utilisation',
      method: 'GET',
      path: '/simulations/analytics/inventory-utilisation',
      status: 'confirmed',
    },
    flashSalePerformance: {
      id: 'analytics.flashSalePerformance',
      label: 'Daily flash-sale units sold',
      method: 'GET',
      path: '/simulations/analytics/flash-sale-performance',
      status: 'confirmed',
    },
    failureRates: {
      id: 'analytics.failureRates',
      label: 'Simulation failure rates',
      method: 'GET',
      path: '/simulations/analytics/failure-rates',
      status: 'confirmed',
    },
    export: pending('analytics.export', 'GET', 'Export report'),
  },
  transactions: {
    list: {
      id: 'transactions.list',
      label: 'List purchase attempts',
      method: 'GET',
      path: '/simulations/transactions',
      status: 'confirmed',
    },
    get: {
      id: 'transactions.get',
      label: 'Get purchase attempt',
      method: 'GET',
      path: '/simulations/transactions/:id',
      status: 'confirmed',
    },
  },
    concurrency: {
    runs: {
      id: 'concurrency.runs',
      label: 'List simulation runs',
      method: 'GET',
      path: '/simulations/runs',
      status: 'confirmed',
    },
    run: {
      id: 'concurrency.run',
      label: 'Get simulation run summary',
      method: 'GET',
      path: '/simulations/runs/:run_id/summary',
      status: 'confirmed',
    },
    start: {
      id: 'concurrency.start',
      label: 'Create simulation run',
      method: 'POST',
      path: '/simulations/runs',
      status: 'confirmed',
    },
    strategies: {
      id: 'concurrency.strategies',
      label: 'List concurrency strategies',
      method: 'GET',
      path: '/simulations/strategies',
      status: 'confirmed',
    },
  },
  imports: {
    list: {
      id: 'imports.list',
      label: 'List imports',
      method: 'GET',
      path: '/imports',
      status: 'confirmed',
    },
    get: {
      id: 'imports.get',
      label: 'Get import (with error report)',
      method: 'GET',
      path: '/imports/:id',
      status: 'confirmed',
    },
    upload: pending('imports.upload', 'POST', 'Upload CSV'),
  },
  audit: {
    list: {
      id: 'audit.list',
      label: 'List audit log entries',
      method: 'GET',
      path: '/admin/audit-logs',
      status: 'confirmed',
    },
  },
  system: {
    health: {
      id: 'system.health',
      label: 'System health',
      method: 'GET',
      path: '/health',
      status: 'confirmed',
    },
  },
} satisfies Record<string, Record<string, EndpointSpec>>;

export function allEndpoints(): EndpointSpec[] {
  return Object.values(endpoints).flatMap((group) => Object.values(group));
}



