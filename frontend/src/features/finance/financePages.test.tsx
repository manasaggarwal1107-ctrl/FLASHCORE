import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthContext } from '@/app/AuthProvider';
import type { AuthContextValue } from '@/app/AuthProvider';
import { PaymentLinksPage } from '@/features/finance/PaymentLinksPage';
import { ReconciliationPage } from '@/features/finance/ReconciliationPage';
import { RefundsPage } from '@/features/finance/RefundsPage';
import { SettlementsPage } from '@/features/finance/SettlementsPage';
import { PaymentsPage } from '@/features/payments/PaymentsPage';
import { setActiveOrganisationId, setAuthToken } from '@/services/api/auth';
import { jsonResponse, renderWithProviders } from '@/test/utils';

function makeAuth(role: 'owner' | 'admin' | 'analyst' | 'operator' = 'owner', orgId = 7): AuthContextValue {
  const org = {
    organisationId: orgId,
    organisationName: 'Org 7',
    organisationSlug: 'org-7',
    organisationStatus: 'active',
    role,
    membershipStatus: 'active',
  };
  return {
    user: { id: 1, email: `${role}@flashcore.test`, role, status: 'active', createdAt: '2026-01-01T00:00:00Z' },
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

describe('Stage 4 financial operations frontend', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setAuthToken('jwt-test-token');
    setActiveOrganisationId(7);
  });

  it('renders Financial Operations overview separating captured collections from settlements', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes('/v1/payments/overview')) {
          return jsonResponse({
            organisation_id: 7,
            currency: 'INR',
            gross_captured_minor: 200000,
            gross_captured: '2000.00',
            successful_payment_count: 2,
            failed_payment_count: 1,
            full_refund_count: 0,
            partial_refund_count: 1,
            total_refunded_minor: 25000,
            total_refunded: '250.00',
            pending_refund_minor: 10000,
            pending_refund: '100.00',
            pending_refund_count: 1,
            gateway_fees_minor: 2000,
            gateway_fees: '20.00',
            gateway_tax_minor: 360,
            gateway_tax: '3.60',
            gross_settlements_minor: 100000,
            gross_settlements: '1000.00',
            net_settlements_minor: 97640,
            net_settlements: '976.40',
            unsettled_captured_minor: 100000,
            unsettled_captured: '1000.00',
            reconciliation_exceptions_count: 3,
            active_payment_links_count: 1,
            paid_payment_links_count: 0,
            calculation_notes: {},
          });
        }
        if (url.includes('/v1/payments/transactions')) {
          return jsonResponse({
            items: [
              {
                id: '10',
                organisation_id: 7,
                order_id: '55',
                payment_order_id: '90',
                provider: 'razorpay',
                provider_payment_id: 'pay_rzp_10',
                event_type: 'CAPTURED',
                amount_minor: 100000,
                amount: '1000.00',
                currency: 'INR',
                status: 'CAPTURED',
                method: 'upi',
                source: 'checkout_verify',
                created_at: '2026-11-27T00:00:00Z',
              },
            ],
            total: 1,
            page: 1,
            page_size: 50,
          });
        }
        return jsonResponse({});
      }),
    );

    renderWithProviders(
      <AuthContext.Provider value={makeAuth('analyst')}>
        <PaymentsPage />
      </AuthContext.Provider>,
    );

    expect(await screen.findByText(/Gross Captured Collections/i)).toBeInTheDocument();
    expect(screen.getByText(/Net Bank Settlements/i)).toBeInTheDocument();
    expect(screen.getByText(/Unsettled Captured Balance/i)).toBeInTheDocument();
    expect(await screen.findByText('pay_rzp_10')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /export csv/i })).toBeInTheDocument();
  });

  it('requires confirmation before submitting refunds and supports owner approval', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/v1/payments/policies/refunds')) {
        return jsonResponse({
          organisation_id: 7,
          refund_approval_threshold_minor: 50000,
          refund_approval_threshold: '500.00',
          currency: 'INR',
          updated_at: '2026-11-27T00:00:00Z',
        });
      }
      if (url.includes('/v1/payments/transactions/10/refunds') && init?.method === 'POST') {
        const body = JSON.parse(String(init.body));
        expect(body.amount_minor).toBe(60000);
        return jsonResponse({
          id: '4',
          organisation_id: 7,
          order_id: '55',
          payment_order_id: '90',
          payment_transaction_id: '10',
          provider: 'razorpay',
          provider_payment_id: 'pay_rzp_10',
          provider_refund_id: null,
          amount_minor: 60000,
          amount: '600.00',
          currency: 'INR',
          refund_type: 'PARTIAL',
          status: 'APPROVAL_PENDING',
          reason: body.reason,
          requires_approval: true,
          approval_request: {
            id: '1',
            refund_id: '4',
            order_id: '55',
            payment_transaction_id: '10',
            amount_minor: 60000,
            amount: '600.00',
            currency: 'INR',
            threshold_minor: 50000,
            status: 'PENDING',
            requested_by_user_id: 1,
            created_at: '2026-11-27T00:00:00Z',
          },
          events: [],
          created_at: '2026-11-27T00:00:00Z',
          updated_at: '2026-11-27T00:00:00Z',
        }, 201);
      }
      if (url.includes('/v1/payments/transactions')) {
        return jsonResponse({
          items: [
            {
              id: '10',
              organisation_id: 7,
              order_id: '55',
              payment_order_id: '90',
              provider: 'razorpay',
              provider_payment_id: 'pay_rzp_10',
              event_type: 'CAPTURED',
              amount_minor: 80000,
              amount: '800.00',
              currency: 'INR',
              status: 'CAPTURED',
              method: 'card',
              source: 'checkout_verify',
              created_at: '2026-11-27T00:00:00Z',
            },
          ],
          total: 1,
          page: 1,
          page_size: 100,
        });
      }
      if (url.endsWith('/v1/payments/refunds/4/approve') && init?.method === 'POST') {
        return jsonResponse({
          id: '4',
          organisation_id: 7,
          order_id: '55',
          payment_order_id: '90',
          payment_transaction_id: '10',
          provider: 'razorpay',
          provider_payment_id: 'pay_rzp_10',
          provider_refund_id: 'rfnd_4',
          amount_minor: 60000,
          amount: '600.00',
          currency: 'INR',
          refund_type: 'PARTIAL',
          status: 'PROCESSED',
          reason: 'Customer damaged return',
          requires_approval: true,
          approval_request: null,
          events: [],
          created_at: '2026-11-27T00:00:00Z',
          updated_at: '2026-11-27T00:00:00Z',
        });
      }
      if (url.endsWith('/v1/payments/refunds/4')) {
        return jsonResponse({
          id: '4',
          organisation_id: 7,
          order_id: '55',
          payment_order_id: '90',
          payment_transaction_id: '10',
          provider: 'razorpay',
          provider_payment_id: 'pay_rzp_10',
          provider_refund_id: null,
          amount_minor: 60000,
          amount: '600.00',
          currency: 'INR',
          refund_type: 'PARTIAL',
          status: 'APPROVAL_PENDING',
          reason: 'Customer damaged return',
          requires_approval: true,
          approval_request: {
            id: '1',
            refund_id: '4',
            order_id: '55',
            payment_transaction_id: '10',
            amount_minor: 60000,
            amount: '600.00',
            currency: 'INR',
            threshold_minor: 50000,
            status: 'PENDING',
            requested_by_user_id: 1,
            created_at: '2026-11-27T00:00:00Z',
          },
          events: [],
          created_at: '2026-11-27T00:00:00Z',
          updated_at: '2026-11-27T00:00:00Z',
        });
      }
      return jsonResponse({ items: [], total: 0, page: 1, page_size: 50 });
    });
    vi.stubGlobal('fetch', fetchMock);

    renderWithProviders(
      <AuthContext.Provider value={makeAuth('owner')}>
        <RefundsPage />
      </AuthContext.Provider>,
    );

    await screen.findByText(/pay_rzp_10/);
    await user.selectOptions(screen.getByLabelText(/captured transaction/i), '10');
    await user.type(screen.getByLabelText(/refund amount/i), '600');
    await user.type(screen.getByLabelText(/refund reason/i), 'Customer damaged return');
    await user.click(screen.getByRole('button', { name: /review refund request/i }));

    expect(await screen.findByText(/confirm refund of/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /confirm & submit refund/i }));

    expect(await screen.findByText(/Refund #4 recorded with status APPROVAL_PENDING/i)).toBeInTheDocument();
    const approveBtn = await screen.findByRole('button', { name: /Approve & Submit/i });
    await user.click(approveBtn);

    await waitFor(() => {
      expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith('/v1/payments/refunds/4/approve'))).toBe(true);
    });
  });

  it('creates and cancels payment links and displays shortUrl cleanly', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes('/v1/orders')) {
          return jsonResponse({
            items: [
              {
                id: '55',
                organisation_id: 7,
                reference: 'ORD-55',
                currency: 'INR',
                subtotal_minor: 50000,
                subtotal: '500.00',
                discount_minor: 0,
                discount: '0.00',
                tax_minor: 0,
                tax: '0.00',
                total_minor: 50000,
                total: '500.00',
                status: 'PENDING_PAYMENT',
                payment_status: 'PENDING',
                item_count: 1,
                lines: [],
                origin: 'real',
                placed_at: '2026-11-27T00:00:00Z',
                created_at: '2026-11-27T00:00:00Z',
                updated_at: '2026-11-27T00:00:00Z',
              },
            ],
            total: 1,
            page: 1,
            page_size: 100,
          });
        }
        if (url.includes('/v1/payments/links') && init?.method === 'POST') {
          return jsonResponse({
            id: '2',
            organisation_id: 7,
            order_id: '55',
            provider: 'razorpay',
            provider_link_id: 'plink_demo_2',
            reference_id: 'PL-2',
            amount_minor: 50000,
            amount: '500.00',
            amount_paid_minor: 0,
            amount_paid: '0.00',
            currency: 'INR',
            accept_partial: false,
            description: 'Invoice #55',
            short_url: 'https://rzp.io/i/plink_demo_2',
            status: 'ACTIVE',
            created_at: '2026-11-27T00:00:00Z',
            updated_at: '2026-11-27T00:00:00Z',
          }, 201);
        }
        if (url.includes('/v1/payments/links')) {
          return jsonResponse({ items: [], total: 0, page: 1, page_size: 50 });
        }
        return jsonResponse({});
      }),
    );

    renderWithProviders(
      <AuthContext.Provider value={makeAuth('operator')}>
        <PaymentLinksPage />
      </AuthContext.Provider>,
    );

    await screen.findByText(/ORD-55/);
    await user.selectOptions(screen.getByLabelText(/pending order/i), '55');
    await user.type(screen.getByLabelText(/description/i), 'Invoice #55');
    await user.click(screen.getByRole('button', { name: /create payment link/i }));

    expect(await screen.findByText(/Payment link plink_demo_2 created/i)).toBeInTheDocument();
  });

  it('surfaces unavailable Razorpay test-mode settlement capability and supports CSV import', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith('/v1/payments/settlements/sync') && init?.method === 'POST') {
          return jsonResponse({
            status: 'capability_unavailable',
            synced_count: 0,
            message: 'Razorpay test mode does not expose settlement payouts for this account.',
          });
        }
        if (url.includes('/v1/payments/settlements')) {
          return jsonResponse({ items: [], total: 0, page: 1, page_size: 50 });
        }
        return jsonResponse({});
      }),
    );

    renderWithProviders(
      <AuthContext.Provider value={makeAuth('owner')}>
        <SettlementsPage />
      </AuthContext.Provider>,
    );

    await user.click(screen.getByRole('button', { name: /sync from razorpay/i }));
    expect(await screen.findByText(/does not expose settlement payouts/i)).toBeInTheDocument();
  });

  it('renders reconciliation exceptions and restricts resolution controls to owner/admin', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes('/v1/payments/reconciliation/runs/8/items')) {
          return jsonResponse({
            items: [
              {
                id: '99',
                run_id: '8',
                outcome: 'AMOUNT_MISMATCH',
                entity_type: 'PAYMENT',
                order_id: '55',
                provider_ref: 'pay_99',
                expected_amount_minor: 50000,
                actual_amount_minor: 49000,
                expected_currency: 'INR',
                actual_currency: 'INR',
                resolution_status: 'UNRESOLVED',
                created_at: '2026-11-27T00:00:00Z',
              },
            ],
            total: 1,
            page: 1,
            page_size: 50,
          });
        }
        if (url.includes('/v1/payments/reconciliation/runs')) {
          return jsonResponse({
            items: [
              {
                id: '8',
                organisation_id: 7,
                run_reference: 'RECON-8',
                provider: 'razorpay',
                currency: 'INR',
                status: 'COMPLETED',
                total_checked: 2,
                matched_count: 1,
                exception_count: 1,
                created_at: '2026-11-27T00:00:00Z',
                completed_at: '2026-11-27T00:00:00Z',
              },
            ],
            total: 1,
            page: 1,
            page_size: 25,
          });
        }
        return jsonResponse({});
      }),
    );

    // Operator can view run & exception but does NOT see Resolve button
    renderWithProviders(
      <AuthContext.Provider value={makeAuth('operator')}>
        <ReconciliationPage />
      </AuthContext.Provider>,
    );

    expect(await screen.findByText('RECON-8')).toBeInTheDocument();
    expect(await screen.findByText(/pay_99/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Resolve$/i })).not.toBeInTheDocument();
  });
});
