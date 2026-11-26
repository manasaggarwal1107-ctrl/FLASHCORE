import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { ApiError } from '@/services/api/errors';
import { OriginBadge } from './Badge';
import { Pagination } from './Pagination';
import { ProgressBar } from './ProgressBar';
import { StatTile } from './StatTile';
import { AwaitingContractState, EmptyState, ErrorState, UnavailableState } from './States';

describe('state components', () => {
  it('EmptyState explains an empty result', () => {
    render(<EmptyState title="No products" description="Nothing here yet" />);
    expect(screen.getByRole('status')).toHaveTextContent('No products');
  });

  it('ErrorState shows the real error and a working retry', async () => {
    const onRetry = vi.fn();
    render(<ErrorState error={new ApiError('network', 'x')} onRetry={onRetry} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Cannot reach the API');
    await userEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('AwaitingContractState names the capability and does not show data', () => {
    render(<AwaitingContractState capability="List products" />);
    expect(screen.getByRole('status')).toHaveTextContent('Awaiting API contract');
    expect(screen.getByRole('status')).toHaveTextContent('List products');
  });

  it('UnavailableState renders', () => {
    render(<UnavailableState title="Not available" />);
    expect(screen.getByText('Not available')).toBeInTheDocument();
  });
});

describe('StatTile', () => {
  it('shows a loading status', () => {
    render(<StatTile label="Orders" state={{ kind: 'loading' }} />);
    expect(screen.getByRole('status', { name: /loading orders/i })).toBeInTheDocument();
  });
  it('shows an em dash (never zero) when unavailable', () => {
    render(<StatTile label="Orders" state={{ kind: 'unavailable', reason: 'Awaiting API contract' }} />);
    expect(screen.getByLabelText('Not available')).toHaveTextContent('—');
    expect(screen.queryByText('0')).not.toBeInTheDocument();
  });
  it('shows an error message', () => {
    render(<StatTile label="Orders" state={{ kind: 'error', message: 'Server error' }} />);
    expect(screen.getByText('Server error')).toBeInTheDocument();
  });
  it('shows a supplied value', () => {
    render(<StatTile label="Orders" state={{ kind: 'value', value: '1,204' }} />);
    expect(screen.getByText('1,204')).toBeInTheDocument();
  });
});

describe('OriginBadge', () => {
  it.each([
    ['real', 'Real'],
    ['imported', 'Imported'],
    ['manual', 'Manual'],
    ['simulation', 'Simulation'],
  ] as const)('labels %s data', (origin, label) => {
    render(<OriginBadge origin={origin} />);
    expect(screen.getByLabelText(`Data origin: ${label}`)).toBeInTheDocument();
  });
  it('flags a missing origin instead of assuming "real"', () => {
    render(<OriginBadge origin={null} />);
    expect(screen.getByText('Origin unknown')).toBeInTheDocument();
  });
});

describe('ProgressBar', () => {
  it('renders an explicit unavailable bar for null', () => {
    render(<ProgressBar ratio={null} label="Utilisation" />);
    expect(screen.getByLabelText('Utilisation: not available')).toBeInTheDocument();
  });
  it('clamps and exposes progress semantics', () => {
    render(<ProgressBar ratio={1.4} label="Utilisation" />);
    expect(screen.getByRole('progressbar', { name: 'Utilisation' })).toHaveAttribute('aria-valuenow', '100');
  });
});

describe('Pagination', () => {
  it('disables previous on first page and navigates', async () => {
    const onPageChange = vi.fn();
    render(<Pagination page={1} pageSize={25} total={60} onPageChange={onPageChange} />);
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Next page' }));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });
  it('disables next on the last page', () => {
    render(<Pagination page={3} pageSize={25} total={60} onPageChange={() => {}} />);
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled();
  });
});
