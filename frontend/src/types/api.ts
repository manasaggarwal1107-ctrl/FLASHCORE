/**
 * API resource types.
 *
 * STATUS: PROVISIONAL. API_CONTRACT.md has not been supplied; these shapes describe what the UI
 * needs to render each page, derived from the product brief â€” NOT the backend's confirmed schema.
 * Reconcile every interface with the contract before enabling its endpoint
 * (see INTEGRATION_HANDOVER.md). Fields the backend may omit are nullable on purpose so the UI
 * handles missing data safely.
 *
 * Conventions:
 *  - Money is a decimal STRING (never a float) plus an ISO-4217 currency code.
 *  - Timestamps are ISO-8601 strings.
 *  - `origin` distinguishes real / imported / manual / simulation records.
 */

export type DecimalString = string;
export type IsoTimestamp = string;

export type DataOrigin = 'real' | 'imported' | 'manual' | 'simulation';

export interface Money {
  amount: DecimalString;
  currency: string;
}

// ---- Products & inventory ---------------------------------------------------

export type ProductStatus = 'active' | 'draft' | 'archived';

export interface InventorySummary {
  /** Physical stock on hand. Never conflate with flash-sale allocation. */
  onHand: number | null;
  reserved: number | null;
  sold: number | null;
  available: number | null;
  lowStockThreshold: number | null;
}

export interface Product {
  id: string;
  sku: string | null;
  name: string;
  category: string | null;
  status: ProductStatus | null;
  price: DecimalString | null;
  currency: string | null;
  origin: DataOrigin | null;
  /** Where the record came from (import id, "manual entry", simulation run id â€¦). */
  source: string | null;
  inventory: InventorySummary | null;
  createdAt: IsoTimestamp | null;
  updatedAt: IsoTimestamp | null;
}

export interface InventoryItem {
  productId: string;
  productName: string | null;
  sku: string | null;
  onHand: number | null;
  reserved: number | null;
  sold: number | null;
  available: number | null;
  lowStockThreshold: number | null;
  origin: DataOrigin | null;
  updatedAt: IsoTimestamp | null;
}

export interface InventoryMovement {
  id: string;
  productId: string;
  productName: string | null;
  type: string | null; // e.g. adjustment, sale, reservation, release
  quantityDelta: number | null;
  balanceAfter: number | null;
  reason: string | null;
  actor: string | null;
  origin: DataOrigin | null;
  occurredAt: IsoTimestamp | null;
}

// ---- Flash sales -------------------------------------------------------------

export type FlashSaleStatus = 'scheduled' | 'active' | 'completed' | 'cancelled';

export interface FlashSale {
  id: string;
  name: string;
  status: FlashSaleStatus | null;
  startsAt: IsoTimestamp | null;
  endsAt: IsoTimestamp | null;
  productId: string | null;
  productName: string | null;
  salePrice: DecimalString | null;
  currency: string | null;
  /** Units reserved for this sale. A sale allocation is NOT physical inventory. */
  allocated: number | null;
  sold: number | null;
  remaining: number | null;
  origin: DataOrigin | null;
}

// ---- Orders & customers --------------------------------------------------------

export interface OrderLine {
  productId: string | null;
  productName: string | null;
  quantity: number | null;
  unitPrice: DecimalString | null;
  lineTotal: DecimalString | null;
}

export interface Order {
  id: string;
  reference: string | null;
  customerRef: string | null;
  status: string | null;
  total: DecimalString | null;
  currency: string | null;
  itemCount: number | null;
  lines: OrderLine[] | null;
  transactionRef: string | null;
  origin: DataOrigin | null;
  placedAt: IsoTimestamp | null;
}

export interface Customer {
  id: string;
  /** Pseudonymous reference preferred over personal data (data minimisation). */
  reference: string | null;
  status: string | null;
  orderCount: number | null;
  origin: DataOrigin | null;
  createdAt: IsoTimestamp | null;
}

// ---- Transactions ----------------------------------------------------------------

export type TransactionStatus = 'succeeded' | 'failed' | 'pending' | 'rejected';

export interface Transaction {
  id: string;
  purchaseAttemptId: string | null;
  status: TransactionStatus | null;
  occurredAt: IsoTimestamp | null;
  failureReason: string | null;
  origin: DataOrigin | null;
}

// ---- Concurrency Lab -----------------------------------------------------------------

export interface SimulationConfig {
  strategy: string;
  workers: number;
  requestedPurchases: number;
  targetInventory: number;
}

export type SimulationStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface SimulationRun {
  id: string;
  status: SimulationStatus | null;
  strategy: string | null;
  workers: number | null;
  requestedPurchases: number | null;
  targetInventory: number | null;
  successful: number | null;
  failed: number | null;
  oversold: number | null;
  throughputPerSec: number | null;
  avgLatencyMs: number | null;
  p95LatencyMs: number | null;
  p99LatencyMs: number | null;
  inventoryBefore: number | null;
  inventoryAfter: number | null;
  startedAt: IsoTimestamp | null;
  finishedAt: IsoTimestamp | null;
  /** Always 'simulation' for lab runs; kept explicit so it can be asserted. */
  origin: DataOrigin | null;
}

// ---- Data imports ------------------------------------------------------------------------

export interface DataImport {
  id: string;
  filename: string | null;
  status: string | null;
  datasetSource: string | null;
  uploadedBy: string | null;
  importedRows: number | null;
  rejectedRows: number | null;
  duplicateRows: number | null;
  createdAt: IsoTimestamp | null;
  /** Provenance as stated by the uploader â€” unverified unless the backend says otherwise. */
  provenance: string | null;
}

// ---- Audit ---------------------------------------------------------------------------------

export interface AuditEntry {
  id: string;
  occurredAt: IsoTimestamp | null;
  actor: string | null;
  action: string | null;
  entityType: string | null;
  entityRef: string | null;
  outcome: string | null;
  metadata: Record<string, unknown> | null;
}

// ---- System health ---------------------------------------------------------------------------

export interface ServiceStatus {
  name: string;
  status: string | null;
  detail: string | null;
}

export interface SystemHealth {
  status: string | null;
  version: string | null;
  database: string | null;
  services: ServiceStatus[] | null;
  checkedAt: IsoTimestamp | null;
}

// ---- Overview / analytics aggregates ----------------------------------------------------------

export interface OverviewSummary {
  totalProducts: number | null;
  availableInventory: number | null;
  activeFlashSales: number | null;
  ordersProcessed: number | null;
  successfulPurchases: number | null;
  failedPurchases: number | null;
  throughputPerSec: number | null;
  /** Ratio 0..1 */
  inventoryUtilisation: number | null;
  generatedAt: IsoTimestamp | null;
  origin: DataOrigin | null;
}

export interface TimeSeriesPoint {
  t: string;
  value: number;
}

export interface TimeSeries {
  points: TimeSeriesPoint[];
  periodStart: IsoTimestamp | null;
  periodEnd: IsoTimestamp | null;
  origin: DataOrigin | null;
}

export interface PurchaseOutcomes {
  successful: number | null;
  failed: number | null;
  rejected: number | null;
  pending: number | null;
  periodStart: IsoTimestamp | null;
  periodEnd: IsoTimestamp | null;
  origin: DataOrigin | null;
}

export interface InventoryAllocation {
  /** Physical stock */
  physical: { onHand: number | null; reserved: number | null; sold: number | null; available: number | null };
  /** Flash-sale allocations are a separate ledger from physical stock. */
  flashSale: { allocated: number | null; sold: number | null; remaining: number | null };
  origin: DataOrigin | null;
}

export interface Collection<T> {
  items: T[];
}

export interface ActivityEvent {
  id: string;
  occurredAt: IsoTimestamp | null;
  kind: string | null;
  summary: string | null;
  origin: DataOrigin | null;
}

export interface ImportRowError {
  row: number | null;
  field: string | null;
  message: string | null;
}

export interface DataImportDetail extends DataImport {
  errors: ImportRowError[] | null;
}

export interface StrategyOption {
  id: string;
  label: string | null;
}
export interface RossmannSalesSummary {
  totalRecords: number;
  totalSales: number | string | null;
  averageSales: number | null;
  highestSales: number | string | null;
  totalCustomers: number | null;
}



export interface PromotionAnalysisGroup {
  openStoreDays: number;
  totalSales: number | null;
  averageSalesPerStoreDay: number | null;
  totalCustomers: number | null;
  averageCustomersPerStoreDay: number | null;
}

export interface PromotionAnalysis {
  promoted: PromotionAnalysisGroup;
  nonPromoted: PromotionAnalysisGroup;
  periodStart: IsoTimestamp | null;
  periodEnd: IsoTimestamp | null;
  origin: DataOrigin | null;
  comparisonBasis: string;
}
