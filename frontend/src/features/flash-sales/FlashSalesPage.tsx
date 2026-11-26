import { useState } from 'react';
import type { FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { Button } from '@/components/ui/Button';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody } from '@/components/ui/Panel';
import { apiRequest } from '@/services/api/client';
import { endpoints, resolvePath } from '@/services/api/endpoints';

interface SimulationRun {
  id: number;
  runName: string;
  description?: string | null;
  status?: string;
  createdAt?: string;
}

interface InventoryRecord {
  id: number;
  storeId: number;
  productId: number;
  productName: string | null;
  sku: string | null;
  quantity: number;
  reservedQuantity: number;
}

interface FlashSaleSummary {
  flashSaleId: number;
  title: string;
  status: string;
  unitsSold: number;
  allocatedStock: number;
}

interface RunSummary {
  run: SimulationRun;
  purchases: {
    totalAttempts: number;
    successful: number;
    rejected: number;
    failed: number;
    unitsSold: number;
  };
  flashSales: FlashSaleSummary[];
}

interface CreatedRecord {
  id: number;
}

export function FlashSalesPage() {
  const queryClient = useQueryClient();

  const [selectedRunId, setSelectedRunId] = useState('');
  const [selectedSaleId, setSelectedSaleId] = useState('');

  const [runName, setRunName] = useState('');
  const [runDescription, setRunDescription] = useState('');

  const [saleTitle, setSaleTitle] = useState('');
  const [startsAt, setStartsAt] = useState('');
  const [endsAt, setEndsAt] = useState('');

  const [inventoryId, setInventoryId] = useState('');
  const [salePrice, setSalePrice] = useState('');
  const [stockLimit, setStockLimit] = useState('');

  const runsQuery = useQuery({
    queryKey: [endpoints.concurrency.runs.id],
    queryFn: () => apiRequest<SimulationRun[]>('/simulations/runs'),
  });

  const inventoryQuery = useQuery({
    queryKey: [endpoints.inventory.list.id],
    queryFn: () => apiRequest<InventoryRecord[]>('/simulations/inventory'),
  });

  const summaryQuery = useQuery({
    queryKey: [endpoints.concurrency.run.id, selectedRunId],
    enabled: Boolean(selectedRunId),
    queryFn: () =>
      apiRequest<RunSummary>(
        resolvePath(endpoints.concurrency.run.path!, {
          run_id: selectedRunId,
        }),
      ),
  });

  const selectedInventory = (inventoryQuery.data ?? []).find(
    (item) => String(item.id) === inventoryId,
  );

  const selectedSale = summaryQuery.data?.flashSales.find(
    (sale) => String(sale.flashSaleId) === selectedSaleId,
  );

  const createRunMutation = useMutation({
    mutationFn: (payload: {
      run_name: string;
      description: string | null;
      configuration: Record<string, never>;
    }) =>
      apiRequest<CreatedRecord>('/simulations/runs', {
        method: 'POST',
        body: payload,
      }),
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({
        queryKey: [endpoints.concurrency.runs.id],
      });
      setSelectedRunId(String(created.id));
      setSelectedSaleId('');
      setRunName('');
      setRunDescription('');
    },
  });

  const createSaleMutation = useMutation({
    mutationFn: (payload: {
      title: string;
      starts_at: string;
      ends_at: string;
    }) =>
      apiRequest<CreatedRecord>(
        resolvePath(endpoints.flashSales.create.path!, {
          run_id: selectedRunId,
        }),
        {
          method: 'POST',
          body: payload,
        },
      ),
    onSuccess: async (created) => {
      setSelectedSaleId(String(created.id));
      await queryClient.invalidateQueries({
        queryKey: [endpoints.concurrency.run.id, selectedRunId],
      });
      setSaleTitle('');
      setStartsAt('');
      setEndsAt('');
    },
  });

  const allocateMutation = useMutation({
    mutationFn: (payload: {
      inventory_id: number;
      sale_price: string;
      stock_limit: number;
    }) =>
      apiRequest<unknown>(
        resolvePath(endpoints.flashSales.allocate.path!, {
          sale_id: selectedSaleId,
        }),
        {
          method: 'POST',
          body: payload,
        },
      ),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: [endpoints.concurrency.run.id, selectedRunId],
        }),
        queryClient.invalidateQueries({
          queryKey: [endpoints.inventory.list.id],
        }),
      ]);
      setInventoryId('');
      setSalePrice('');
      setStockLimit('');
    },
  });

  const activateMutation = useMutation({
    mutationFn: () =>
      apiRequest<unknown>(
        resolvePath(endpoints.flashSales.activate.path!, {
          sale_id: selectedSaleId,
        }),
        { method: 'POST' },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: [endpoints.concurrency.run.id, selectedRunId],
      });
    },
  });

  function submitRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    createRunMutation.mutate({
      run_name: runName.trim(),
      description: runDescription.trim() || null,
      configuration: {},
    });
  }

  function submitSale(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedRunId) return;

    const start = new Date(startsAt);
    const end = new Date(endsAt);

    if (
      Number.isNaN(start.getTime()) ||
      Number.isNaN(end.getTime()) ||
      end.getTime() <= start.getTime()
    ) {
      return;
    }

    createSaleMutation.mutate({
      title: saleTitle.trim(),
      starts_at: start.toISOString(),
      ends_at: end.toISOString(),
    });
  }

  function submitAllocation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedSaleId || !selectedInventory) return;

    const price = salePrice.trim();
    const quantity = Number(stockLimit);
    const available =
      selectedInventory.quantity - selectedInventory.reservedQuantity;

    if (
      !/^\d+(\.\d+)?$/.test(price) ||
      !Number.isInteger(quantity) ||
      quantity <= 0 ||
      quantity > available
    ) {
      return;
    }

    allocateMutation.mutate({
      inventory_id: selectedInventory.id,
      sale_price: price,
      stock_limit: quantity,
    });
  }

  const busy =
    createRunMutation.isPending ||
    createSaleMutation.isPending ||
    allocateMutation.isPending ||
    activateMutation.isPending;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Flash Sales"
        description="Create simulation runs, configure time-boxed sales, reserve stock and activate sales."
      />

      <Panel>
        <PanelBody>
          <h2 className="mb-3 text-base font-semibold">1. Simulation run</h2>

          <div className="mb-4">
            <label htmlFor="run-select" className="mb-1 block text-sm font-medium">
              Select an existing run
            </label>
            <select
              id="run-select"
              value={selectedRunId}
              onChange={(event) => {
                setSelectedRunId(event.target.value);
                setSelectedSaleId('');
              }}
              className="min-h-10 w-full rounded-md border border-line bg-surface px-3 text-sm"
            >
              <option value="">Choose a simulation run</option>
              {(runsQuery.data ?? []).map((run) => (
                <option key={run.id} value={run.id}>
                  #{run.id} — {run.runName} ({run.status ?? 'created'})
                </option>
              ))}
            </select>
            {runsQuery.isError && (
              <p className="mt-2 text-sm text-danger" role="alert">
                Could not load runs: {runsQuery.error.message}
              </p>
            )}
          </div>

          <details className="rounded-md border border-line p-3">
            <summary className="cursor-pointer text-sm font-medium">
              Create a new simulation run
            </summary>

            <form onSubmit={submitRun} className="mt-3 space-y-3">
              <div>
                <label htmlFor="run-name" className="mb-1 block text-sm">
                  Run name
                </label>
                <input
                  id="run-name"
                  required
                  maxLength={200}
                  value={runName}
                  onChange={(event) => setRunName(event.target.value)}
                  className="min-h-10 w-full rounded-md border border-line bg-surface px-3 text-sm"
                />
              </div>

              <div>
                <label htmlFor="run-description" className="mb-1 block text-sm">
                  Description
                </label>
                <textarea
                  id="run-description"
                  rows={2}
                  value={runDescription}
                  onChange={(event) => setRunDescription(event.target.value)}
                  className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm"
                />
              </div>

              <Button type="submit" disabled={createRunMutation.isPending}>
                {createRunMutation.isPending ? 'Creating…' : 'Create run'}
              </Button>

              {createRunMutation.isError && (
                <p className="text-sm text-danger" role="alert">
                  {createRunMutation.error.message}
                </p>
              )}
            </form>
          </details>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelBody>
          <h2 className="mb-3 text-base font-semibold">2. Create flash sale</h2>

          <form onSubmit={submitSale} className="grid gap-3 md:grid-cols-2">
            <div className="md:col-span-2">
              <label htmlFor="sale-title" className="mb-1 block text-sm">
                Sale title
              </label>
              <input
                id="sale-title"
                required
                maxLength={200}
                value={saleTitle}
                onChange={(event) => setSaleTitle(event.target.value)}
                className="min-h-10 w-full rounded-md border border-line bg-surface px-3 text-sm"
              />
            </div>

            <div>
              <label htmlFor="sale-start" className="mb-1 block text-sm">
                Starts at
              </label>
              <input
                id="sale-start"
                type="datetime-local"
                required
                value={startsAt}
                onChange={(event) => setStartsAt(event.target.value)}
                className="min-h-10 w-full rounded-md border border-line bg-surface px-3 text-sm"
              />
            </div>

            <div>
              <label htmlFor="sale-end" className="mb-1 block text-sm">
                Ends at
              </label>
              <input
                id="sale-end"
                type="datetime-local"
                required
                value={endsAt}
                onChange={(event) => setEndsAt(event.target.value)}
                className="min-h-10 w-full rounded-md border border-line bg-surface px-3 text-sm"
              />
            </div>

            <div className="md:col-span-2">
              <Button
                type="submit"
                variant="primary"
                disabled={!selectedRunId || createSaleMutation.isPending}
              >
                {createSaleMutation.isPending ? 'Creating…' : 'Create flash sale'}
              </Button>
            </div>

            {createSaleMutation.isError && (
              <p className="text-sm text-danger md:col-span-2" role="alert">
                Sale creation failed: {createSaleMutation.error.message}
              </p>
            )}
          </form>
          {!selectedRunId && (
            <p className="mt-2 text-xs text-ink-muted">
              Select or create a simulation run before creating a sale.
            </p>
          )}
        </PanelBody>
      </Panel>

      <Panel>
        <PanelBody>
          <h2 className="mb-3 text-base font-semibold">3. Allocate inventory</h2>

          <form onSubmit={submitAllocation} className="grid gap-3 md:grid-cols-2">
            <div className="md:col-span-2">
              <label htmlFor="sale-select" className="mb-1 block text-sm">
                Flash sale
              </label>
              <select
                id="sale-select"
                value={selectedSaleId}
                onChange={(event) => setSelectedSaleId(event.target.value)}
                disabled={!selectedRunId}
                className="min-h-10 w-full rounded-md border border-line bg-surface px-3 text-sm"
              >
                <option value="">Choose a sale</option>
                {(summaryQuery.data?.flashSales ?? []).map((sale) => (
                  <option key={sale.flashSaleId} value={sale.flashSaleId}>
                    #{sale.flashSaleId} — {sale.title} ({sale.status})
                  </option>
                ))}
                {createSaleMutation.isSuccess && selectedSaleId && (
                  <option value={selectedSaleId}>
                    Newly created sale #{selectedSaleId}
                  </option>
                )}
              </select>
            </div>

            <div className="md:col-span-2">
              <label htmlFor="inventory-select" className="mb-1 block text-sm">
                Inventory record
              </label>
              <select
                id="inventory-select"
                required
                value={inventoryId}
                onChange={(event) => {
                  setInventoryId(event.target.value);
                  setStockLimit('');
                }}
                className="min-h-10 w-full rounded-md border border-line bg-surface px-3 text-sm"
              >
                <option value="">Choose inventory</option>
                {(inventoryQuery.data ?? []).map((item) => {
                  const available = item.quantity - item.reservedQuantity;
                  return (
                    <option
                      key={item.id}
                      value={item.id}
                      disabled={available <= 0}
                    >
                      #{item.id} — {item.productName ?? `Product ${item.productId}`}
                      {' · '}SKU {item.sku ?? '—'}
                      {' · '}Store {item.storeId}
                      {' · '}Available {available}
                    </option>
                  );
                })}
              </select>
              {inventoryQuery.isError && (
                <p className="mt-1 text-sm text-danger" role="alert">
                  Could not load inventory: {inventoryQuery.error.message}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="sale-price" className="mb-1 block text-sm">
                Sale price
              </label>
              <input
                id="sale-price"
                type="number"
                min="0"
                step="0.01"
                required
                value={salePrice}
                onChange={(event) => setSalePrice(event.target.value)}
                className="min-h-10 w-full rounded-md border border-line bg-surface px-3 text-sm"
              />
            </div>

            <div>
              <label htmlFor="stock-limit" className="mb-1 block text-sm">
                Stock limit
              </label>
              <input
                id="stock-limit"
                type="number"
                min="1"
                max={selectedInventory
                  ? selectedInventory.quantity - selectedInventory.reservedQuantity
                  : undefined}
                step="1"
                required
                value={stockLimit}
                onChange={(event) => setStockLimit(event.target.value)}
                className="min-h-10 w-full rounded-md border border-line bg-surface px-3 text-sm"
              />
              {selectedInventory && (
                <p className="mt-1 text-xs text-ink-muted">
                  Available to allocate: {selectedInventory.quantity - selectedInventory.reservedQuantity}
                </p>
              )}
            </div>

            <div className="md:col-span-2">
              <Button
                type="submit"
                disabled={
                  !selectedSaleId ||
                  !selectedInventory ||
                  allocateMutation.isPending
                }
              >
                {allocateMutation.isPending ? 'Allocating…' : 'Allocate stock'}
              </Button>
            </div>

            {allocateMutation.isError && (
              <p className="text-sm text-danger md:col-span-2" role="alert">
                Allocation failed: {allocateMutation.error.message}
              </p>
            )}
            {allocateMutation.isSuccess && (
              <p className="text-sm text-success md:col-span-2">
                Stock allocation completed successfully.
              </p>
            )}
          </form>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelBody>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold">4. Run summary and activation</h2>
            {selectedRunId && (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => void summaryQuery.refetch()}
              >
                Refresh summary
              </Button>
            )}
          </div>

          {!selectedRunId && (
            <p className="py-4 text-sm text-ink-muted">
              Select a run to view its flash sales and purchase results.
            </p>
          )}

          {summaryQuery.isPending && selectedRunId && (
            <p className="py-4 text-sm text-ink-muted">Loading run summary…</p>
          )}

          {summaryQuery.isError && (
            <p className="py-4 text-sm text-danger" role="alert">
              Could not load run summary: {summaryQuery.error.message}
            </p>
          )}

          {summaryQuery.data && (
            <>
              <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
                <div className="rounded-md border border-line p-3">
                  <p className="text-xs text-ink-muted">Purchase attempts</p>
                  <p className="mt-1 text-xl font-semibold tabular-nums">
                    {summaryQuery.data.purchases.totalAttempts}
                  </p>
                </div>
                <div className="rounded-md border border-line p-3">
                  <p className="text-xs text-ink-muted">Successful</p>
                  <p className="mt-1 text-xl font-semibold tabular-nums">
                    {summaryQuery.data.purchases.successful}
                  </p>
                </div>
                <div className="rounded-md border border-line p-3">
                  <p className="text-xs text-ink-muted">Rejected</p>
                  <p className="mt-1 text-xl font-semibold tabular-nums">
                    {summaryQuery.data.purchases.rejected}
                  </p>
                </div>
                <div className="rounded-md border border-line p-3">
                  <p className="text-xs text-ink-muted">Units sold</p>
                  <p className="mt-1 text-xl font-semibold tabular-nums">
                    {summaryQuery.data.purchases.unitsSold}
                  </p>
                </div>
              </div>

              {summaryQuery.data.flashSales.length === 0 ? (
                <p className="py-4 text-sm text-ink-muted">
                  This run does not have any flash sales yet.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[560px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-line text-xs text-ink-muted">
                        <th className="px-3 py-3 font-medium">Sale</th>
                        <th className="px-3 py-3 font-medium">Status</th>
                        <th className="px-3 py-3 text-right font-medium">Allocated</th>
                        <th className="px-3 py-3 text-right font-medium">Sold</th>
                        <th className="px-3 py-3 text-right font-medium">Remaining</th>
                      </tr>
                    </thead>
                    <tbody>
                      {summaryQuery.data.flashSales.map((sale) => (
                        <tr
                          key={sale.flashSaleId}
                          onClick={() => setSelectedSaleId(String(sale.flashSaleId))}
                          className={`cursor-pointer border-b border-line last:border-0 ${
                            selectedSaleId === String(sale.flashSaleId)
                              ? 'bg-surface-overlay'
                              : ''
                          }`}
                        >
                          <td className="px-3 py-3 font-medium">
                            #{sale.flashSaleId} — {sale.title}
                          </td>
                          <td className="px-3 py-3 capitalize">{sale.status}</td>
                          <td className="px-3 py-3 text-right tabular-nums">
                            {sale.allocatedStock}
                          </td>
                          <td className="px-3 py-3 text-right tabular-nums">
                            {sale.unitsSold}
                          </td>
                          <td className="px-3 py-3 text-right tabular-nums">
                            {sale.allocatedStock - sale.unitsSold}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="mt-4 flex flex-wrap items-center gap-3">
                <span className="text-sm text-ink-muted">
                  Selected sale: {selectedSale?.title ?? 'None'}
                </span>
                <Button
                  variant="primary"
                  disabled={
                    !selectedSale ||
                    selectedSale.status === 'active' ||
                    selectedSale.status === 'completed' ||
                    selectedSale.status === 'cancelled' ||
                    busy
                  }
                  onClick={() => activateMutation.mutate()}
                >
                  {activateMutation.isPending ? 'Activating…' : 'Activate selected sale'}
                </Button>
              </div>

              {activateMutation.isError && (
                <p className="mt-2 text-sm text-danger" role="alert">
                  Activation failed: {activateMutation.error.message}
                </p>
              )}
              {activateMutation.isSuccess && (
                <p className="mt-2 text-sm text-success">
                  Activation request completed. The current sale status is shown in the refreshed summary.
                </p>
              )}
            </>
          )}
        </PanelBody>
      </Panel>
    </div>
  );
}