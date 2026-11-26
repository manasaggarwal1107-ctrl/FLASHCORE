import { fireEvent, screen } from '@testing-library/react';
import { afterEach, beforeEach, vi } from 'vitest';
import { renderWithProviders } from '@/test/utils';
import { ConcurrencyPage } from './concurrency/ConcurrencyPage';
import { FlashSaleFormPage } from './flash-sales/FlashSaleFormPage';
import { ImportsPage } from './imports/ImportsPage';
import { isLowStock } from './inventory/inventoryLogic';
import { metricState, OverviewPage } from './overview/OverviewPage';
import { outcomeSegments } from './overview/PurchaseOutcomesPanel';
import { ProductFormPage } from './products/ProductFormPage';
import { ProductsPage } from './products/ProductsPage';
import { SystemHealthPage } from './system/SystemHealthPage';
import { periodRange } from './analytics/periods';

const fetchMock = vi.fn();
beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe('with no API contract (all endpoints pending)', () => {
  it('Overview requests and displays the Rossmann historical sales summary', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      text: async () =>
        JSON.stringify({
          total_records: 1017209,
          total_sales: 5873180623,
          average_sales: 5773.818972305593,
          highest_sales: 41551,
          total_customers: 644041755,
        }),
    });

    renderWithProviders(<OverviewPage />);

    expect(await screen.findByText('1M')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalled();
    expect(screen.getByText('Rossmann Retail Intelligence')).toBeInTheDocument();
  });

  it('Products loads the simulation product catalogue', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      text: async () => JSON.stringify([
        { id: 1, sku: 'FLASH-001', name: 'Test Product', description: 'Simulation catalogue item' },
      ]),
    });

    renderWithProviders(<ProductsPage />);

    expect(screen.getByRole('button', { name: /new product/i })).toBeEnabled();
    expect(await screen.findByText('Test Product')).toBeInTheDocument();
    expect(screen.getByText('FLASH-001')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalled();
  });

  it('System Health shows local config and renders verified backend status', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      text: async () =>
        JSON.stringify({
          status: 'healthy',
          version: '1.0.0',
          database: 'flashcore_rossmann',
          services: [
            { name: 'FastAPI Application', status: 'healthy', detail: 'Operational (v1.0.0)' },
            { name: 'PostgreSQL Database', status: 'healthy', detail: 'Connected to flashcore_rossmann' },
          ],
          checkedAt: '2026-11-24T12:00:00Z',
        }),
    });

    renderWithProviders(<SystemHealthPage />);
    expect(screen.getByText('This frontend')).toBeInTheDocument();
    expect(screen.getByText('Backend')).toBeInTheDocument();
    expect(await screen.findByText('FastAPI Application')).toBeInTheDocument();
    expect(screen.getByText('PostgreSQL Database')).toBeInTheDocument();
  });

  it('Concurrency Lab labels everything as simulation and enables the verified Run action', () => {
    renderWithProviders(<ConcurrencyPage />);
    expect(screen.getByRole('note')).toHaveTextContent(/simulation data/i);
    expect(screen.getByRole('button', { name: /run simulation/i })).toBeEnabled();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/simulations/runs'),
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('Imports explains that uploads are not verified and disables upload', () => {
    renderWithProviders(<ImportsPage />);
    expect(screen.getByText(/does not verify that a dataset is authentic/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /upload and import/i })).toBeDisabled();
  });
});

describe('form validation in the UI', () => {
  it('ProductFormPage validates required fields without calling the API', async () => {
    renderWithProviders(<ProductFormPage />, { route: '/products/new' });

    const form = screen.getByRole('button', { name: /create product/i }).closest('form')!;
    fireEvent.submit(form);

    expect(await screen.findByText('Name is required')).toBeInTheDocument();
    expect(screen.getByText('SKU is required')).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('FlashSaleFormPage redirects to the combined Flash Sales workflow', () => {
    renderWithProviders(<FlashSaleFormPage />, { route: '/flash-sales/new' });
    expect(screen.queryByRole('button', { name: /create flash sale/i })).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('data transformations', () => {
  it('metricState never converts a missing value into zero', () => {
    const base: {
      live: boolean;
      isPending: boolean;
      isError: boolean;
      error: unknown;
      data: { totalProducts: number } | undefined;
    } = {
      live: true,
      isPending: false,
      isError: false,
      error: null,
      data: {
        totalProducts: 0,
      },
    };
    expect(metricState<{ totalProducts: number }, 'totalProducts'>({ ...base, data: undefined }, 'totalProducts', String)).toEqual({ kind: 'unavailable' });
    expect(metricState({ ...base, data: { totalProducts: null } as never }, 'totalProducts', String)).toEqual({ kind: 'unavailable' });
    expect(metricState({ ...base, data: { totalProducts: 0 } as never }, 'totalProducts', String)).toEqual({ kind: 'value', value: '0' });
    expect(metricState<{ totalProducts: number }, 'totalProducts'>({ ...base, live: false, data: undefined }, 'totalProducts', String)).toMatchObject({ kind: 'unavailable' });
    expect(metricState<{ totalProducts: number }, 'totalProducts'>({ ...base, isPending: true, data: undefined }, 'totalProducts', String)).toEqual({ kind: 'loading' });
  });

  it('outcomeSegments omits fields the API did not return', () => {
    const segs = outcomeSegments({ successful: 90, failed: 10, rejected: null, pending: null, periodStart: null, periodEnd: null, origin: 'real' });
    expect(segs.map((s) => s.label)).toEqual(['Successful', 'Failed']);
  });

  it('isLowStock is unknown without a threshold', () => {
    expect(isLowStock({ available: 3, lowStockThreshold: 5 })).toBe(true);
    expect(isLowStock({ available: 5, lowStockThreshold: 5 })).toBe(true);
    expect(isLowStock({ available: 6, lowStockThreshold: 5 })).toBe(false);
    expect(isLowStock({ available: 3, lowStockThreshold: null })).toBeNull();
    expect(isLowStock({ available: null, lowStockThreshold: 5 })).toBeNull();
  });

  it('periodRange is relative to the supplied clock', () => {
    const now = new Date('2026-11-19T12:00:00.000Z');
    expect(periodRange('24h', now)).toEqual({ from: '2026-11-18T12:00:00.000Z', to: '2026-11-19T12:00:00.000Z' });
    expect(periodRange('7d', now).from).toBe('2026-11-12T12:00:00.000Z');
  });
});
