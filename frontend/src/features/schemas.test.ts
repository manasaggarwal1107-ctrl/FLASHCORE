import { flashSaleSchema } from './flash-sales/flashSaleSchema';
import { importSchema, MAX_IMPORT_BYTES } from './imports/importSchema';
import { stockAdjustmentSchema } from './inventory/StockAdjustmentForm';
import { productSchema } from './products/productSchema';
import { SIMULATION_LIMITS, simulationSchema } from './concurrency/simulationSchema';
import { tokenSchema } from './settings/tokenSchema';

const messages = (r: { success: boolean; error?: { issues: { message: string; path: (string | number)[] }[] } }) => (r.success ? [] : r.error!.issues.map((i) => i.message));

describe('productSchema', () => {
  const valid = { name: 'Desk Lamp', sku: 'LAMP-01', category: 'Lighting', status: 'active', price: '19.99', currency: 'usd' };
  it('accepts valid input and normalises currency', () => {
    const r = productSchema.safeParse(valid);
    expect(r.success).toBe(true);
    if (r.success) expect(r.data.currency).toBe('USD');
  });
  it('rejects float-looking or malformed prices', () => {
    expect(messages(productSchema.safeParse({ ...valid, price: '19.999' }))).toContain('Enter a positive amount with up to 2 decimals');
    expect(productSchema.safeParse({ ...valid, price: '-5' }).success).toBe(false);
    expect(productSchema.safeParse({ ...valid, price: '1e3' }).success).toBe(false);
  });
  it('requires a name and a 3-letter currency', () => {
    expect(messages(productSchema.safeParse({ ...valid, name: '  ' }))).toContain('Name is required');
    expect(messages(productSchema.safeParse({ ...valid, currency: 'US' }))).toContain('Use a 3-letter ISO currency code');
  });
  it('rejects unsafe SKUs', () => {
    expect(productSchema.safeParse({ ...valid, sku: 'a b!' }).success).toBe(false);
  });
});

describe('flashSaleSchema', () => {
  const valid = { name: 'Black Friday', productId: 'p1', salePrice: '49.90', currency: 'USD', allocated: '100', startsAt: '2026-11-27T09:00', endsAt: '2026-11-27T21:00' };
  it('accepts valid input and coerces allocation', () => {
    const r = flashSaleSchema.safeParse(valid);
    expect(r.success).toBe(true);
    if (r.success) expect(r.data.allocated).toBe(100);
  });
  it('requires end after start', () => {
    const r = flashSaleSchema.safeParse({ ...valid, endsAt: '2026-11-27T08:00' });
    expect(r.success).toBe(false);
    expect(messages(r)).toContain('End must be after start');
  });
  it('requires a positive whole allocation', () => {
    expect(flashSaleSchema.safeParse({ ...valid, allocated: '0' }).success).toBe(false);
    expect(flashSaleSchema.safeParse({ ...valid, allocated: '2.5' }).success).toBe(false);
    expect(flashSaleSchema.safeParse({ ...valid, allocated: 'abc' }).success).toBe(false);
  });
});

describe('stockAdjustmentSchema', () => {
  it('allows negative whole adjustments with a reason', () => {
    expect(
      stockAdjustmentSchema.safeParse({
        inventoryId: 'inv-1',
        quantityDelta: '-5',
        reason: 'Damaged goods',
      }).success,
    ).toBe(true);
  });

  it('allows positive whole adjustments with a reason', () => {
    expect(
      stockAdjustmentSchema.safeParse({
        inventoryId: 'inv-1',
        quantityDelta: '10',
        reason: 'New stock received',
      }).success,
    ).toBe(true);
  });

  it('rejects zero, fractions and missing reason', () => {
    expect(
      messages(
        stockAdjustmentSchema.safeParse({
          inventoryId: 'inv-1',
          quantityDelta: '0',
          reason: 'Recount',
        }),
      ),
    ).toContain('Adjustment cannot be zero');

    expect(
      stockAdjustmentSchema.safeParse({
        inventoryId: 'inv-1',
        quantityDelta: '1.5',
        reason: 'Recount',
      }).success,
    ).toBe(false);

    expect(
      stockAdjustmentSchema.safeParse({
        inventoryId: 'inv-1',
        quantityDelta: '3',
        reason: '',
      }).success,
    ).toBe(false);
  });

  it('requires an inventory record reference', () => {
    expect(
      stockAdjustmentSchema.safeParse({
        inventoryId: '',
        quantityDelta: '5',
        reason: 'Stock received',
      }).success,
    ).toBe(false);
  });
});
describe('simulationSchema', () => {
  const valid = { strategy: 'optimistic-lock', workers: '50', requestedPurchases: '1000', targetInventory: '200' };
  it('accepts and coerces numeric strings', () => {
    const r = simulationSchema.safeParse(valid);
    expect(r.success).toBe(true);
    if (r.success) expect(r.data).toMatchObject({ workers: 50, requestedPurchases: 1000, targetInventory: 200 });
  });
  it('requires a strategy', () => {
    expect(messages(simulationSchema.safeParse({ ...valid, strategy: '' }))).toContain('Select a concurrency strategy');
  });
  it('enforces bounds', () => {
    expect(simulationSchema.safeParse({ ...valid, workers: '0' }).success).toBe(false);
    expect(simulationSchema.safeParse({ ...valid, workers: String(SIMULATION_LIMITS.maxWorkers + 1), requestedPurchases: '2000' }).success).toBe(false);
  });
  it('rejects more workers than requested purchases', () => {
    expect(messages(simulationSchema.safeParse({ ...valid, workers: '500', requestedPurchases: '100' }))).toContain('Workers cannot exceed requested purchases');
  });
});

describe('importSchema', () => {
  const csv = new File(['a,b\n1,2'], 'data.csv', { type: 'text/csv' });
  it('accepts a CSV with a source', () => {
    expect(importSchema.safeParse({ file: csv, datasetSource: 'Warehouse export' }).success).toBe(true);
  });
  it('rejects non-CSV, empty and oversized files', () => {
    expect(messages(importSchema.safeParse({ file: new File(['x'], 'data.xlsx'), datasetSource: 'Source' }))).toContain('File must have a .csv extension');
    expect(messages(importSchema.safeParse({ file: new File([], 'empty.csv'), datasetSource: 'Source' }))).toContain('File is empty');
    const big = new File([new Uint8Array(MAX_IMPORT_BYTES + 1)], 'big.csv');
    expect(importSchema.safeParse({ file: big, datasetSource: 'Source' }).success).toBe(false);
  });
  it('requires a file and a stated source', () => {
    expect(importSchema.safeParse({ datasetSource: 'Source' }).success).toBe(false);
    expect(importSchema.safeParse({ file: csv, datasetSource: ' ' }).success).toBe(false);
  });
});

describe('tokenSchema', () => {
  it('trims and requires a single token with no spaces', () => {
    expect(tokenSchema.safeParse({ token: '  abc123  ' }).success).toBe(true);
    expect(tokenSchema.safeParse({ token: '' }).success).toBe(false);
    expect(tokenSchema.safeParse({ token: 'two words' }).success).toBe(false);
  });
});
