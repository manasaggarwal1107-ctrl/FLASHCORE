import { ApiError } from './errors';
import { allEndpoints, endpoints, isEndpointLive, resolvePath } from './endpoints';
import { adaptPage, toQuery } from './pagination';

describe('endpoint registry', () => {
  it('only enables endpoints verified against the backend', () => {
    const confirmedEndpoints = [
      {
        endpoint: endpoints.overview.summary,
        path: '/rossmann/sales/summary',
      },
      {
        endpoint: endpoints.analytics.salesTrend,
        path: '/rossmann/sales/trend',
      },
      {
        endpoint: endpoints.analytics.orderVolume,
        path: '/rossmann/sales/customers-trend',
      },
      {
        endpoint: endpoints.analytics.promotionAnalysis,
        path: '/rossmann/sales/promotion-analysis',
      },
      {
        endpoint: endpoints.analytics.conversion,
        path: '/simulations/analytics/conversion',
      },
      {
        endpoint: endpoints.analytics.failureRates,
        path: '/simulations/analytics/failure-rates',
      },
      {
        endpoint: endpoints.analytics.inventoryUtilisation,
        path: '/simulations/analytics/inventory-utilisation',
      },
      {
        endpoint: endpoints.analytics.flashSalePerformance,
        path: '/simulations/analytics/flash-sale-performance',
      },
    ];

    for (const { endpoint, path } of confirmedEndpoints) {
      expect(endpoint).toMatchObject({
        status: 'confirmed',
        method: 'GET',
        path,
      });
    }

    const simulationEndpoints = [
      { endpoint: endpoints.products.list, method: 'GET', path: '/simulations/products' },
      { endpoint: endpoints.products.create, method: 'POST', path: '/simulations/products' },
      { endpoint: endpoints.concurrency.runs, method: 'GET', path: '/simulations/runs' },
      { endpoint: endpoints.concurrency.run, method: 'GET', path: '/simulations/runs/:run_id/summary' },
      { endpoint: endpoints.concurrency.start, method: 'POST', path: '/simulations/runs' },
      { endpoint: endpoints.flashSales.create, method: 'POST', path: '/simulations/runs/:run_id/flash-sales' },
      { endpoint: endpoints.flashSales.activate, method: 'POST', path: '/simulations/flash-sales/:sale_id/activate' },
      { endpoint: endpoints.flashSales.allocate, method: 'POST', path: '/simulations/flash-sales/:sale_id/products' },
    ];

    for (const { endpoint, method, path } of simulationEndpoints) {
      expect(endpoint).toMatchObject({ status: 'confirmed', method, path });
    }

    const authEndpoints = [
      {
        endpoint: endpoints.auth.signup,
        method: 'POST',
        path: '/auth/signup',
      },
      {
        endpoint: endpoints.auth.login,
        method: 'POST',
        path: '/auth/login',
      },
      {
        endpoint: endpoints.auth.me,
        method: 'GET',
        path: '/auth/me',
      },
      {
        endpoint: endpoints.auth.logout,
        method: 'POST',
        path: '/auth/logout',
      },
    ] as const;

    for (const { endpoint, method, path } of authEndpoints) {
      expect(endpoint).toMatchObject({
        status: 'confirmed',
        method,
        path,
      });
    }

    const inventoryEndpoints = [
      {
        endpoint: endpoints.inventory.list,
        method: 'GET',
        path: '/simulations/inventory',
      },
      {
        endpoint: endpoints.inventory.adjust,
        method: 'POST',
        path: '/simulations/inventory/:inventory_id/adjust',
      },
    ] as const;

    for (const { endpoint, method, path } of inventoryEndpoints) {
      expect(endpoint).toMatchObject({
        status: 'confirmed',
        method,
        path,
      });
    }

    const additionalConfirmedEndpoints = [
      { endpoint: endpoints.overview.salesSeries, method: 'GET', path: '/rossmann/sales/trend' },
      { endpoint: endpoints.overview.purchaseOutcomes, method: 'GET', path: '/simulations/analytics/purchase-outcomes' },
      { endpoint: endpoints.overview.inventoryAllocation, method: 'GET', path: '/simulations/analytics/inventory-allocation' },
      { endpoint: endpoints.overview.flashSalePerformance, method: 'GET', path: '/simulations/analytics/flash-sales-overview' },
      { endpoint: endpoints.overview.activity, method: 'GET', path: '/simulations/analytics/activity' },
      { endpoint: endpoints.organisations.list, method: 'GET', path: '/organisations' },
      { endpoint: endpoints.organisations.create, method: 'POST', path: '/organisations' },
      { endpoint: endpoints.concurrency.strategies, method: 'GET', path: '/simulations/strategies' },
      { endpoint: endpoints.imports.list, method: 'GET', path: '/imports' },
      { endpoint: endpoints.imports.get, method: 'GET', path: '/imports/:id' },
      { endpoint: endpoints.audit.list, method: 'GET', path: '/admin/audit-logs' },
      { endpoint: endpoints.system.health, method: 'GET', path: '/health' },
      { endpoint: endpoints.orders.list, method: 'GET', path: '/v1/orders' },
      { endpoint: endpoints.orders.get, method: 'GET', path: '/v1/orders/:id' },
      { endpoint: endpoints.orders.create, method: 'POST', path: '/v1/orders' },
      { endpoint: endpoints.orders.transition, method: 'POST', path: '/v1/orders/:id/transition' },
      { endpoint: endpoints.orders.checkout, method: 'POST', path: '/v1/orders/:id/checkout' },
      { endpoint: endpoints.customers.list, method: 'GET', path: '/v1/customers' },
      { endpoint: endpoints.customers.get, method: 'GET', path: '/v1/customers/:id' },
      { endpoint: endpoints.customers.create, method: 'POST', path: '/v1/customers' },
      { endpoint: endpoints.customers.orders, method: 'GET', path: '/v1/customers/:id/orders' },
      { endpoint: endpoints.catalog.list, method: 'GET', path: '/v1/products' },
      { endpoint: endpoints.catalog.get, method: 'GET', path: '/v1/products/:id' },
      { endpoint: endpoints.catalog.create, method: 'POST', path: '/v1/products' },
      { endpoint: endpoints.catalog.update, method: 'PATCH', path: '/v1/products/:id' },
      { endpoint: endpoints.retailInventory.list, method: 'GET', path: '/v1/inventory' },
      { endpoint: endpoints.retailInventory.locations, method: 'GET', path: '/v1/inventory/locations' },
      { endpoint: endpoints.retailInventory.createLocation, method: 'POST', path: '/v1/inventory/locations' },
      { endpoint: endpoints.retailInventory.adjust, method: 'POST', path: '/v1/inventory/adjustments' },
      { endpoint: endpoints.retailInventory.movements, method: 'GET', path: '/v1/inventory/movements' },
      { endpoint: endpoints.payments.accounts, method: 'GET', path: '/v1/payments/accounts' },
      { endpoint: endpoints.payments.upsertRazorpay, method: 'PUT', path: '/v1/payments/accounts/razorpay' },
      { endpoint: endpoints.payments.createOrder, method: 'POST', path: '/v1/payments/orders' },
      { endpoint: endpoints.payments.getOrder, method: 'GET', path: '/v1/payments/orders/:id' },
      { endpoint: endpoints.payments.verifyOrder, method: 'POST', path: '/v1/payments/orders/:id/verify' },
      { endpoint: endpoints.payments.transactions, method: 'GET', path: '/v1/payments/transactions' },
      { endpoint: endpoints.payments.getTransaction, method: 'GET', path: '/v1/payments/transactions/:id' },
    ] as const;

    for (const { endpoint, method, path } of additionalConfirmedEndpoints) {
      expect(endpoint).toMatchObject({
        status: 'confirmed',
        method,
        path,
      });
    }

    const confirmedIds = new Set([
      'transactions.list',
      'transactions.get',
      ...confirmedEndpoints.map(({ endpoint }) => endpoint.id),
      ...simulationEndpoints.map(({ endpoint }) => endpoint.id),
      ...authEndpoints.map(({ endpoint }) => endpoint.id),
      ...inventoryEndpoints.map(({ endpoint }) => endpoint.id),
      ...additionalConfirmedEndpoints.map(({ endpoint }) => endpoint.id),
    ]);

    for (const spec of allEndpoints()) {
      if (!confirmedIds.has(spec.id)) {
        expect(spec.status).toBe('pending-contract');
        expect(spec.path).toBeNull();
      }
    }
  });

  it('isEndpointLive requires both confirmed status and a path', () => {
    expect(isEndpointLive(endpoints.products.get)).toBe(false);
    expect(isEndpointLive({ ...endpoints.products.get, status: 'confirmed', path: null })).toBe(false);
    expect(isEndpointLive({ ...endpoints.products.get, status: 'confirmed', path: '/products' })).toBe(true);
  });

  it('has unique ids', () => {
    const ids = allEndpoints().map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe('resolvePath', () => {
  it('substitutes and encodes params', () => {
    expect(resolvePath('/products/:id', { id: 'a/b c' })).toBe('/products/a%2Fb%20c');
  });
  it('throws instead of requesting a broken URL', () => {
    expect(() => resolvePath('/products/:id')).toThrow(/Missing path parameter "id"/);
  });
});

describe('pagination adapter', () => {
  it('accepts the canonical envelope', () => {
    expect(adaptPage<{ id: string }>({ items: [{ id: '1' }], total: 1, page: 1, pageSize: 25 })).toEqual({ items: [{ id: '1' }], total: 1, page: 1, pageSize: 25 });
  });
  it('fails loudly on a mismatched shape rather than guessing', () => {
    expect(() => adaptPage({ data: [] })).toThrow(ApiError);
    try {
      adaptPage(null);
    } catch (e) {
      expect((e as ApiError).kind).toBe('contract');
    }
  });
  it('toQuery merges filters', () => {
    expect(toQuery({ page: 2, pageSize: 25, search: 'x', filters: { status: 'active' } })).toMatchObject({ page: 2, pageSize: 25, search: 'x', status: 'active' });
  });
});
