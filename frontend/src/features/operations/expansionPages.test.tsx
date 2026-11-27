import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/utils';
import { PosPage } from '@/features/pos/PosPage';
import { VoiceIntelligencePage } from '@/features/voice/VoiceIntelligencePage';
import { WarehousesPage } from '@/features/operations/WarehousesPage';
import { ProcurementPage } from '@/features/operations/ProcurementPage';
import { CampaignsPromotionsPage } from '@/features/operations/CampaignsPromotionsPage';
import { SalesInvoicesPage } from '@/features/operations/SalesInvoicesPage';
import { ReturnsPage } from '@/features/operations/ReturnsPage';
import { ReportsHubPage } from '@/features/operations/ReportsHubPage';

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    const body = url.includes('/v1/products') || url.includes('/v1/customers') || url.includes('/v1/orders') || url.includes('/v1/sales/records')
      ? { items: [], total: 0, page: 1, pageSize: 25 }
      : url.includes('/v1/reports/')
        ? { reportType: 'sales', headers: ['Order'], rows: [], count: 0 }
        : url.includes('/v1/sales/pnl')
          ? { grossSales: '0.00', discounts: '0.00', returnsRefunded: '0.00', taxCollected: '0.00', netSalesExTax: '0.00', grossProfit: null }
          : url.includes('/v1/retail-inventory/intelligence')
            ? { totalStockValue: '0.00', lowStockCount: 0, outOfStockCount: 0 }
            : [];
    return Promise.resolve(
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
  });
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('Stage 5-8 & India-first frontend modules', () => {
  it('renders Retail POS & Voice Intelligence with text fallback and approval workflow', async () => {
    renderWithProviders(<PosPage />);
    expect(screen.getByText('Retail POS & Billing')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Open Cashier Shift/i })).toBeInTheDocument();

    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify([]), { status: 200, headers: { 'content-type': 'application/json' } }),
    );
    renderWithProviders(<VoiceIntelligencePage />);
    expect(screen.getByText('FLASHCORE Voice Intelligence')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Push to Talk/i })).toBeInTheDocument();

    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          sessionId: '1',
          reply: 'Prepared inventory adjustment awaiting approval.',
          language: 'hinglish',
          provider: 'groq',
          model: 'llama-3.3-70b-versatile',
          toolExecutions: [],
          pendingProposal: {
            id: '77',
            toolName: 'propose_adjust_inventory',
            arguments: { product_id: 1, quantity_delta: 5, reason: 'Check' },
            summary: 'Adjust SKU stock by +5',
            status: 'PENDING_APPROVAL',
            approvedBy: null,
            result: null,
            errorMessage: null,
            createdAt: new Date().toISOString(),
          },
          ttsHint: { voiceLang: 'hi-IN' },
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    );
    await user.type(screen.getByLabelText('Ask FLASHCORE assistant'), 'Add 5 units');
    await user.click(screen.getByRole('button', { name: 'Send' }));
    expect(await screen.findByText(/Approval Required: propose_adjust_inventory/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Approve & Execute/i })).toBeInTheDocument();
  });

  it('renders Warehouses, Procurement, Surge Control, Sales & Invoices, Returns, and Reports Hub', () => {
    renderWithProviders(<WarehousesPage />);
    expect(screen.getByText('Warehouses & Stock Transfers')).toBeInTheDocument();

    renderWithProviders(<ProcurementPage />);
    expect(screen.getByText('Suppliers & Procurement')).toBeInTheDocument();

    renderWithProviders(<CampaignsPromotionsPage />);
    expect(screen.getByText('Surge Control & Promotions')).toBeInTheDocument();

    renderWithProviders(<SalesInvoicesPage />);
    expect(screen.getByText('Sales Records, Invoices & P&L')).toBeInTheDocument();

    renderWithProviders(<ReturnsPage />);
    expect(screen.getByText('Returns & Exchanges')).toBeInTheDocument();

    renderWithProviders(<ReportsHubPage />);
    expect(screen.getByText('Reports, Intelligence & Automation')).toBeInTheDocument();
  });
});
