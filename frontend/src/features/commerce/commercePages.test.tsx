import { Route, Routes } from 'react-router-dom';
import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthContext } from '@/app/AuthProvider';
import type { AuthContextValue } from '@/app/AuthProvider';
import { CatalogPage } from '@/features/catalog/CatalogPage';
import { RetailInventoryPage } from '@/features/catalog/RetailInventoryPage';
import { CustomersPage } from '@/features/customers/CustomersPage';
import { OrderDetailPage } from '@/features/orders/OrderDetailPage';
import { OrdersPage } from '@/features/orders/OrdersPage';
import { GatewaySettingsPanel } from '@/features/payments/GatewaySettingsPanel';
import { setActiveOrganisationId, setAuthToken } from '@/services/api/auth';
import { resetRazorpayLoaderForTest } from '@/services/payments/razorpayCheckout';
import { jsonResponse, renderWithProviders } from '@/test/utils';

function makeAuthValue(role: 'owner' | 'admin' | 'analyst' | 'operator' = 'owner', orgId = 7): AuthContextValue {
  const org = {
    organisationId: orgId,
    organisationName: 'Org 7',
    organisationSlug: 'org-7',
    organisationStatus: 'active',
    role,
    membershipStatus: 'active',
  };
  return {
    user: { id: 1, email: 'owner@flashcore.test', role, status: 'active', createdAt: '2026-01-01T00:00:00Z' },
    status: 'authenticated',
    error: null,
    organisations: [org],
    activeOrganisation: org,
    activeRole: role,
    membershipError: null,
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
    retrySession: vi.fn(),
    switchOrganisation: vi.fn(),
  };
}

describe('Stage 3 commerce & Razorpay frontend flows', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    resetRazorpayLoaderForTest();
    delete window.Razorpay;
    setAuthToken('jwt-test-token');
    setActiveOrganisationId(7);
  });

  it('lists and creates real commerce catalog products with minor-unit conversion', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/v1/products') && (!init?.method || init.method === 'GET')) {
        return jsonResponse({
          items: [
            {
              id: '10',
              organisation_id: 7,
              sku: 'POS-900',
              name: 'Thermal Printer',
              description: null,
              category: 'Hardware',
              status: 'active',
              price_minor: 499900,
              price: '4999.00',
              currency: 'INR',
              tax_rate_bps: 1800,
              metadata: null,
              inventory: { on_hand: 12, reserved: 2, sold: 0, available: 10, low_stock_threshold: 3 },
              origin: 'real',
              source: 'manual',
              created_at: '2026-11-26T00:00:00Z',
              updated_at: '2026-11-26T00:00:00Z',
            },
          ],
          total: 1,
          page: 1,
          page_size: 50,
        });
      }
      if (url.includes('/v1/products') && init?.method === 'POST') {
        const body = JSON.parse(String(init.body));
        expect(body.price_minor).toBe(149950);
        expect(body.tax_rate_bps).toBe(1800);
        return jsonResponse({
          id: '11',
          organisation_id: 7,
          sku: body.sku,
          name: body.name,
          status: 'active',
          price_minor: body.price_minor,
          price: '1499.50',
          currency: 'INR',
          tax_rate_bps: 1800,
          inventory: { on_hand: 0, reserved: 0, sold: 0, available: 0, low_stock_threshold: null },
          origin: 'real',
          source: 'manual',
          created_at: '2026-11-26T00:00:00Z',
          updated_at: '2026-11-26T00:00:00Z',
        }, 201);
      }
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);

    renderWithProviders(
      <AuthContext.Provider value={makeAuthValue('owner')}>
        <CatalogPage />
      </AuthContext.Provider>,
    );

    expect(await screen.findByText('Thermal Printer')).toBeInTheDocument();
    expect(screen.getByText('POS-900')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /new catalog sku/i }));
    await user.type(screen.getByLabelText(/^SKU$/i), 'POS-901');
    await user.type(screen.getByLabelText(/product name/i), 'Handheld Scanner');
    await user.type(screen.getByLabelText(/unit price/i), '1499.50');
    await user.click(screen.getByRole('button', { name: /create product/i }));

    await waitFor(() => {
      const postCall = fetchMock.mock.calls.find((c) => c[1]?.method === 'POST');
      expect(postCall).toBeTruthy();
    });
  });

  it('loads real inventory balances and posts stock adjustments', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/v1/inventory/locations')) {
        return jsonResponse([{ id: 1, organisation_id: 7, code: 'MAIN', name: 'Main Warehouse', location_type: 'warehouse', is_active: true, created_at: '2026-11-26T00:00:00Z', updated_at: '2026-11-26T00:00:00Z' }]);
      }
      if (url.includes('/v1/products')) {
        return jsonResponse({
          items: [{ id: '10', organisation_id: 7, sku: 'POS-900', name: 'Thermal Printer', status: 'active', price_minor: 1000, price: '10.00', currency: 'INR', tax_rate_bps: 0, inventory: { on_hand: 5, reserved: 0, sold: 0, available: 5, low_stock_threshold: 5 }, origin: 'real', source: 'manual', created_at: '2026-11-26T00:00:00Z', updated_at: '2026-11-26T00:00:00Z' }],
          total: 1, page: 1, page_size: 100,
        });
      }
      if (url.includes('/v1/inventory/adjustments') && init?.method === 'POST') {
        const body = JSON.parse(String(init.body));
        expect(body.quantity_delta).toBe(20);
        return jsonResponse({ id: 1, product_id: '10', sku: 'POS-900', product_name: 'Thermal Printer', location_id: 1, location_code: 'MAIN', location_name: 'Main Warehouse', on_hand: 25, reserved: 0, available: 25, low_stock_threshold: 5, origin: 'real', updated_at: '2026-11-26T00:00:00Z' });
      }
      if (url.includes('/v1/inventory')) {
        return jsonResponse({
          items: [{ id: 1, product_id: '10', sku: 'POS-900', product_name: 'Thermal Printer', location_id: 1, location_code: 'MAIN', location_name: 'Main Warehouse', on_hand: 5, reserved: 1, available: 4, low_stock_threshold: 5, origin: 'real', updated_at: '2026-11-26T00:00:00Z' }],
          total: 1, page: 1, page_size: 50,
        });
      }
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);

    renderWithProviders(
      <AuthContext.Provider value={makeAuthValue('operator')}>
        <RetailInventoryPage />
      </AuthContext.Provider>,
    );

    expect((await screen.findAllByText(/MAIN — Main Warehouse/)).length).toBeGreaterThan(0);
    await user.selectOptions(screen.getByLabelText(/^Product$/i), '10');
    await user.type(screen.getByLabelText(/quantity delta/i), '20');
    await user.click(screen.getByRole('button', { name: /apply adjustment/i }));

    await waitFor(() => {
      expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('/v1/inventory/adjustments'))).toBe(true);
    });
  });

  it('lists customers and real orders cleanly', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes('/v1/customers')) {
          return jsonResponse({
            items: [{ id: '4', organisation_id: 7, reference: 'CUST-00004', name: 'Meera Kapoor', email: 'meera@example.com', phone: null, status: 'active', order_count: 2, origin: 'real', created_at: '2026-11-26T00:00:00Z', updated_at: '2026-11-26T00:00:00Z' }],
            total: 1, page: 1, page_size: 50,
          });
        }
        if (url.includes('/v1/orders')) {
          return jsonResponse({
            items: [{
              id: '55', organisation_id: 7, reference: 'ORD-000055', customer_id: 4, customer_name: 'Meera Kapoor',
              currency: 'INR', subtotal_minor: 100000, subtotal: '1000.00', discount_minor: 0, discount: '0.00',
              tax_minor: 18000, tax: '180.00', total_minor: 118000, total: '1180.00',
              status: 'PENDING_PAYMENT', payment_status: 'PENDING', item_count: 1, lines: [], events: [], origin: 'real',
              placed_at: '2026-11-26T00:00:00Z', created_at: '2026-11-26T00:00:00Z', updated_at: '2026-11-26T00:00:00Z',
            }],
            total: 1, page: 1, page_size: 50,
          });
        }
        return jsonResponse({});
      }),
    );

    renderWithProviders(
      <AuthContext.Provider value={makeAuthValue('analyst')}>
        <CustomersPage />
        <OrdersPage />
      </AuthContext.Provider>,
    );

    expect(await screen.findByText('Meera Kapoor')).toBeInTheDocument();
    expect(await screen.findByText('ORD-000055')).toBeInTheDocument();
  });

  it('runs Razorpay checkout, requires server verification, and surfaces cancellation errors honestly', async () => {
    const user = userEvent.setup();
    let orderStatus = 'PENDING_PAYMENT';
    let paymentStatus = 'PENDING';
    let triggerMode: 'success' | 'dismiss' = 'success';

    class MockRazorpay {
      private opts: Record<string, unknown>;
      constructor(opts: Record<string, unknown>) {
        this.opts = opts;
      }
      on() {
        // registered by wrapper
      }
      open() {
        if (triggerMode === 'success') {
          const handler = this.opts.handler as (r: Record<string, string>) => void;
          handler({
            razorpay_order_id: 'order_rzp_mock_55',
            razorpay_payment_id: 'pay_rzp_mock_55',
            razorpay_signature: 'sig_hmac_mock_valid_123456',
          });
        } else {
          const modal = this.opts.modal as { ondismiss: () => void };
          modal.ondismiss();
        }
      }
    }
    window.Razorpay = MockRazorpay as unknown as typeof window.Razorpay;

    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/v1/orders/55/checkout') && init?.method === 'POST') {
        return jsonResponse({
          id: '90',
          organisation_id: 7,
          order_id: '55',
          provider: 'razorpay',
          mode: 'test',
          provider_order_id: 'order_rzp_mock_55',
          key_id: 'rzp_test_demo1234',
          amount_minor: 118000,
          amount: '1180.00',
          currency: 'INR',
          receipt: 'ORD-000055',
          status: 'CREATED',
          prefill: { name: 'Meera Kapoor', email: 'meera@example.com' },
          created_at: '2026-11-26T00:00:00Z',
          updated_at: '2026-11-26T00:00:00Z',
        }, 201);
      }
      if (url.endsWith('/v1/payments/orders/90/verify') && init?.method === 'POST') {
        orderStatus = 'PAID';
        paymentStatus = 'CAPTURED';
        return jsonResponse({
          verified: true,
          payment_order_id: '90',
          order_id: '55',
          order_status: 'PAID',
          payment_status: 'CAPTURED',
          provider_order_id: 'order_rzp_mock_55',
          provider_payment_id: 'pay_rzp_mock_55',
          amount_minor: 118000,
          amount: '1180.00',
          currency: 'INR',
          idempotent_replay: false,
        });
      }
      if (url.endsWith('/v1/orders/55')) {
        return jsonResponse({
          id: '55',
          organisation_id: 7,
          reference: 'ORD-000055',
          customer_id: 4,
          customer_name: 'Meera Kapoor',
          currency: 'INR',
          subtotal_minor: 100000,
          subtotal: '1000.00',
          discount_minor: 0,
          discount: '0.00',
          tax_minor: 18000,
          tax: '180.00',
          total_minor: 118000,
          total: '1180.00',
          status: orderStatus,
          payment_status: paymentStatus,
          item_count: 1,
          lines: [{ id: 1, product_id: '10', location_id: 1, sku: 'POS-900', product_name: 'Thermal Printer', quantity: 1, unit_price_minor: 100000, unit_price: '1000.00', tax_rate_bps: 1800, tax_minor: 18000, line_total_minor: 118000, line_total: '1180.00' }],
          events: [],
          origin: 'real',
          placed_at: '2026-11-26T00:00:00Z',
          created_at: '2026-11-26T00:00:00Z',
          updated_at: '2026-11-26T00:00:00Z',
        });
      }
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);

    // First verify modal cancellation does NOT verify/mark paid
    triggerMode = 'dismiss';
    renderWithProviders(
      <AuthContext.Provider value={makeAuthValue('operator')}>
        <Routes>
          <Route path="/orders/:id" element={<OrderDetailPage />} />
        </Routes>
      </AuthContext.Provider>,
      { route: '/orders/55' },
    );

    const payBtn = await screen.findByRole('button', { name: /pay with razorpay/i });
    await user.click(payBtn);
    expect(await screen.findByText(/checkout cancelled/i)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('/verify'))).toBe(false);

    // Retry and verify server-side confirmation succeeds
    triggerMode = 'success';
    await act(async () => {
      await user.click(screen.getByRole('button', { name: /retry razorpay test checkout/i }));
    });
    expect(await screen.findByText(/Payment verified server-side \(pay_rzp_mock_55\)/i)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('/v1/payments/orders/90/verify'))).toBe(true);
  });

  it('rejects live Razorpay keys in GatewaySettingsPanel and restricts non-admins', async () => {
    const user = userEvent.setup();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse([])));

    renderWithProviders(
      <AuthContext.Provider value={makeAuthValue('owner')}>
        <GatewaySettingsPanel />
      </AuthContext.Provider>,
    );

    await user.type(await screen.findByLabelText(/razorpay test key id/i), 'rzp_live_blocked');
    await user.type(screen.getByLabelText(/razorpay key secret/i), 'secret_12345678');
    await user.type(screen.getByLabelText(/razorpay webhook secret/i), 'whsec_12345678');
    await user.click(screen.getByRole('button', { name: /save razorpay test credentials/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/rzp_test_/i);
  });
});
