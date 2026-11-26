import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, vi } from 'vitest';
import { endpoints } from '@/services/api/endpoints';
import { jsonResponse, liveEndpoint, renderWithProviders } from '@/test/utils';
import { ResourceTable } from './ResourceTable';
import type { Column } from './DataTable';

interface Row {
  id: string;
  name: string;
}
const columns: Column<Row>[] = [{ id: 'name', header: 'Name', cell: (r) => r.name }];

const fetchMock = vi.fn();
beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe('ResourceTable', () => {
  it('shows the awaiting-contract state and makes NO request for a pending endpoint', () => {
    renderWithProviders(<ResourceTable<Row> endpoint={endpoints.products.get} columns={columns} rowKey={(r) => r.id} caption="Test" />);
    expect(screen.getByText('Awaiting API contract')).toBeInTheDocument();
    expect(screen.getByRole('searchbox')).toBeDisabled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('shows a loading skeleton, then rows', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ items: [{ id: '1', name: 'Alpha' }], total: 1, page: 1, pageSize: 25 }));
    renderWithProviders(<ResourceTable<Row> endpoint={liveEndpoint()} columns={columns} rowKey={(r) => r.id} caption="Test" />);
    expect(screen.getByText(/loading table/i)).toBeInTheDocument();
    expect(await screen.findByText('Alpha')).toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Test' })).toBeInTheDocument();
  });

  it('shows a genuine empty state when the API returns no rows', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ items: [], total: 0, page: 1, pageSize: 25 }));
    renderWithProviders(<ResourceTable<Row> endpoint={liveEndpoint()} columns={columns} rowKey={(r) => r.id} caption="Test" emptyTitle="No widgets" />);
    expect(await screen.findByText('No widgets')).toBeInTheDocument();
  });

  it('shows the API error (not fake data) and retries on demand', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ message: 'boom' }, 500));
    renderWithProviders(<ResourceTable<Row> endpoint={liveEndpoint()} columns={columns} rowKey={(r) => r.id} caption="Test" />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Server error');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();

    fetchMock.mockResolvedValueOnce(jsonResponse({ items: [{ id: '1', name: 'Recovered' }], total: 1, page: 1, pageSize: 25 }));
    await userEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(await screen.findByText('Recovered')).toBeInTheDocument();
  });

  it('reports a contract error when the response shape is wrong', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ rows: [] }));
    renderWithProviders(<ResourceTable<Row> endpoint={liveEndpoint()} columns={columns} rowKey={(r) => r.id} caption="Test" />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Unexpected response shape');
  });

  it('sends pagination parameters', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ items: [{ id: '1', name: 'Alpha' }], total: 60, page: 1, pageSize: 25 }));
    renderWithProviders(<ResourceTable<Row> endpoint={liveEndpoint()} columns={columns} rowKey={(r) => r.id} caption="Test" />);
    await screen.findByText('Alpha');
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(String(fetchMock.mock.calls[0]![0])).toContain('page=1');
    expect(String(fetchMock.mock.calls[0]![0])).toContain('pageSize=25');
  });
});
