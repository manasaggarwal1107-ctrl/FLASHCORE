import type { ReactElement } from 'react';
import { render } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { createQueryClient } from '@/services/api/queryClient';
import type { EndpointSpec } from '@/services/api/endpoints';

export function renderWithProviders(ui: ReactElement, { route = '/' }: { route?: string } = {}) {
  const client = createQueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
}

/** A confirmed endpoint used only in tests to exercise live-data states. */
export const liveEndpoint = (path = '/test-resources'): EndpointSpec => ({
  id: 'test.list',
  label: 'Test list',
  method: 'GET',
  path,
  status: 'confirmed',
});
