import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach } from 'vitest';
import { renderWithProviders } from '@/test/utils';
import { reportResponseReceived, reportUnreachable, resetConnectivity } from '@/services/api/connectivity';
import { AppShell } from './AppShell';
import { buildCrumbs } from './Breadcrumbs';
import { filterNavItems } from './CommandPalette';
import { ErrorBoundary } from './ErrorBoundary';
import { ConnectivityIndicator } from './StatusIndicators';
import { allNavItems, getNavGroupsForRole } from './nav';

beforeEach(() => resetConnectivity());

describe('navigation model', () => {
  it('contains exactly the 13 required sections in order', () => {
    expect(allNavItems.map((i) => i.label)).toEqual([
      'Overview',
      'Products',
      'Inventory',
      'Flash Sales',
      'Orders',
      'Customers',
      'Analytics',
      'Transaction Monitor',
      'Concurrency Lab',
      'Data Imports',
      'Audit Logs',
      'System Health',
      'Settings',
    ]);
  });

  it('shows all unrestricted sections to analysts while retaining explicit role restrictions', () => {
    const analystItems = getNavGroupsForRole('analyst').flatMap((g) => g.items);
    const operatorItems = getNavGroupsForRole('operator').flatMap((g) => g.items);
    const adminItems = getNavGroupsForRole('admin').flatMap((g) => g.items);

    expect(analystItems.map((i) => i.label)).toEqual(allNavItems.map((i) => i.label));
    expect(adminItems).toHaveLength(13);
    expect(operatorItems).toHaveLength(11);
    expect(operatorItems.some((i) => i.label === 'Overview')).toBe(false);
    expect(operatorItems.some((i) => i.label === 'Analytics')).toBe(false);
  });
  it('filters by label and keyword', () => {
    expect(filterNavItems('flash').map((i) => i.label)).toEqual(['Flash Sales']);
    expect(filterNavItems('csv').map((i) => i.label)).toEqual(['Data Imports']);
    expect(filterNavItems('')).toHaveLength(13);
    expect(filterNavItems('zzz')).toHaveLength(0);
  });
});

describe('buildCrumbs', () => {
  it('labels the first segment and links parents', () => {
    expect(buildCrumbs('/products/abc')).toEqual([{ label: 'Products', to: '/products' }, { label: 'abc' }]);
    expect(buildCrumbs('/')).toEqual([]);
  });
});

describe('ConnectivityIndicator', () => {
  it('starts as not checked and follows real request outcomes', () => {
    render(<ConnectivityIndicator />);
    expect(screen.getByRole('status')).toHaveTextContent('API not checked');
    act(() => reportResponseReceived());
    expect(screen.getByRole('status')).toHaveTextContent('API reachable');
    act(() => reportUnreachable('network'));
    expect(screen.getByRole('status')).toHaveTextContent('API unreachable');
  });
});

describe('ErrorBoundary', () => {
  it('shows a recoverable error view instead of a blank screen', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const Bomb = () => {
      throw new Error('kaboom');
    };
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('kaboom');
    spy.mockRestore();
  });
});

describe('AppShell', () => {
  it('renders primary navigation, environment badge and opens command search with Ctrl+K', async () => {
    renderWithProviders(
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/overview" element={<div>page body</div>} />
        </Route>
      </Routes>,
      { route: '/overview' },
    );
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeInTheDocument();
    expect(screen.getByText('page body')).toBeInTheDocument();
    expect(screen.getByText(/development/i)).toBeInTheDocument();
    await userEvent.keyboard('{Control>}k{/Control}');
    expect(screen.getByRole('dialog', { name: 'Command search' })).toBeInTheDocument();
  });

  it('collapses the sidebar', async () => {
    render(
      <MemoryRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<div />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Collapse navigation' }));
    expect(screen.getByRole('button', { name: 'Expand navigation' })).toBeInTheDocument();
  });
});
