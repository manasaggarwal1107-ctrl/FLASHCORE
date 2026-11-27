import { config } from '@/lib/config';
import { getActiveOrganisationId, getAuthHeaders } from './auth';
import { apiRequest } from './client';
import type { Page } from './pagination';
import { adaptPage } from './pagination';

export interface WarehouseRecord {
  id: string;
  code: string;
  name: string;
  locationType: string;
  city: string | null;
  state: string | null;
  isDefault: boolean;
  isActive: boolean;
  totalUnits: number;
  reservedUnits: number;
  damagedUnits: number;
}

export interface TransferRecord {
  id: string;
  transferNumber: string;
  productId: string;
  productName: string;
  sku: string;
  fromLocationId: number;
  fromLocationName: string;
  toLocationId: number;
  toLocationName: string;
  quantity: number;
  status: string;
  requiresApproval: boolean;
  requestedBy: string;
  approvedBy: string | null;
  createdAt: string;
}

export interface SupplierRecord {
  id: string;
  code: string;
  name: string;
  contactName: string | null;
  email: string | null;
  phone: string | null;
  gstin: string | null;
  stateCode: string | null;
  outstandingPayable: string;
  status: string;
  orderCount: number;
  totalSpend: string;
}

export interface PurchaseOrderRecord {
  id: string;
  poNumber: string;
  supplierId: string;
  supplierName: string;
  locationId: number;
  locationName: string;
  status: string;
  totalCost: string;
  items: Array<{
    id: string;
    productId: string;
    sku: string;
    productName: string;
    orderedQuantity: number;
    receivedQuantity: number;
    unitCost: string;
    lineTotal: string;
  }>;
  createdAt: string;
}

export interface SurgeCampaignRecord {
  id: string;
  name: string;
  description: string | null;
  status: string;
  startsAt: string;
  endsAt: string;
  discountType: string;
  discountValue: number;
  totalUnitsSold: number;
  revenue: string;
  ordersGenerated: number;
  products: Array<{
    id: string;
    productId: string;
    sku: string;
    productName: string;
    originalPrice: string;
    salePrice: string;
    allocatedUnits: number;
    soldUnits: number;
    remainingUnits: number;
  }>;
}

export interface PromotionRecord {
  id: string;
  code: string;
  name: string;
  discountType: string;
  discountValue: number;
  minOrder: string;
  maxDiscount: string | null;
  usageLimit: number | null;
  usedCount: number;
  isActive: boolean;
}

export interface SalesRecordItem {
  id: string;
  transactionRef: string;
  orderId: string;
  orderNumber: string;
  customerName: string | null;
  grossAmount: string;
  discount: string;
  tax: string;
  netAmount: string;
  refunded: string;
  paymentStatus: string;
  refundStatus: string;
  soldAt: string;
}

export interface InvoiceRecord {
  id: string;
  invoiceNumber: string;
  documentType: string;
  financialYear: string;
  orderId: string | null;
  customerName: string | null;
  placeOfSupplyState: string;
  isInterstate: boolean;
  taxableValue: string;
  cgst: string;
  sgst: string;
  igst: string;
  total: string;
  status: string;
  irnStatus: string;
  issuedAt: string;
}

export interface ReturnRecord {
  id: string;
  returnNumber: string;
  orderId: string;
  orderNumber: string;
  returnType: string;
  status: string;
  reason: string;
  condition: string;
  restockApproved: boolean;
  refundAmount: string;
  refundId: string | null;
  items: Array<{
    id: string;
    productName: string;
    sku: string;
    quantity: number;
    condition: string;
    restocked: boolean;
  }>;
  createdAt: string;
}

export interface PosShiftRecord {
  id: string;
  locationId: number;
  locationName: string;
  cashierEmail: string;
  status: string;
  openingCash: string;
  cashSales: string;
  upiSales: string;
  cardSales: string;
  bankSales: string;
  expectedCash: string;
  countedCash: string | null;
  variance: string | null;
  openedAt: string;
  closedAt: string | null;
}

export interface PosHeldBillRecord {
  id: string;
  locationId: number;
  label: string;
  customerId: number | null;
  couponCode: string | null;
  discountMinor: number;
  items: Array<{ product_id: number; quantity: number; unit_multiplier?: number; item_discount_minor?: number }>;
  createdAt: string;
}

export interface TaxProfileRecord {
  id: string;
  legalName: string;
  gstin: string | null;
  registrationType: 'regular' | 'composition' | 'unregistered';
  stateName: string;
  stateCode: string;
  address: string | null;
  invoicePrefix: string;
  financialYearCode: string;
  taxInclusiveDefault: boolean;
  allowNegativeStock: boolean;
  dpdpRetentionDays: number;
}

export interface NotificationItem {
  id: string;
  category: string;
  severity: string;
  title: string;
  message: string;
  isRead: boolean;
  createdAt: string;
}

export interface VoiceProposal {
  id: string;
  toolName: string;
  arguments: Record<string, unknown>;
  summary: string;
  status: string;
  approvedBy: string | null;
  result: Record<string, unknown> | null;
  errorMessage: string | null;
  createdAt: string;
}

export interface VoiceSessionRecord {
  id: string;
  languageMode: string;
  title: string;
  messages: Array<{
    id: string;
    role: string;
    content: string;
    transcriptLanguage: string | null;
    createdAt: string;
  }>;
  proposals: VoiceProposal[];
  createdAt: string;
}

export const expansionApi = {
  // Warehouses & Transfers
  listWarehouses: () => apiRequest<WarehouseRecord[]>('/v1/warehouses'),
  createWarehouse: (body: { code: string; name: string; location_type: string; city?: string; state?: string; is_default?: boolean }) =>
    apiRequest<WarehouseRecord>('/v1/warehouses', { method: 'POST', body }),
  listTransfers: () => apiRequest<TransferRecord[]>('/v1/transfers'),
  createTransfer: (body: { product_id: number; from_location_id: number; to_location_id: number; quantity: number; requires_approval: boolean; notes?: string }) =>
    apiRequest<TransferRecord>('/v1/transfers', { method: 'POST', body }),
  approveTransfer: (id: string) => apiRequest<TransferRecord>(`/v1/transfers/${id}/approve`, { method: 'POST' }),
  dispatchTransfer: (id: string) => apiRequest<TransferRecord>(`/v1/transfers/${id}/dispatch`, { method: 'POST' }),
  receiveTransfer: (id: string) => apiRequest<TransferRecord>(`/v1/transfers/${id}/receive`, { method: 'POST' }),
  getInventoryIntelligence: () => apiRequest<Record<string, unknown>>('/v1/retail-inventory/intelligence'),

  // Procurement
  listSuppliers: () => apiRequest<SupplierRecord[]>('/v1/suppliers'),
  createSupplier: (body: { code: string; name: string; contact_name?: string; email?: string; phone?: string; gstin?: string; state_code?: string; payment_terms?: string }) =>
    apiRequest<SupplierRecord>('/v1/suppliers', { method: 'POST', body }),
  listPurchaseOrders: () => apiRequest<PurchaseOrderRecord[]>('/v1/purchase-orders'),
  createPurchaseOrder: (body: { supplier_id: number; location_id: number; notes?: string; items: Array<{ product_id: number; ordered_quantity: number; unit_cost_minor: number }> }) =>
    apiRequest<PurchaseOrderRecord>('/v1/purchase-orders', { method: 'POST', body }),
  submitPurchaseOrder: (id: string) => apiRequest<PurchaseOrderRecord>(`/v1/purchase-orders/${id}/submit`, { method: 'POST' }),
  receivePurchaseOrder: (id: string, items: Array<{ item_id: number; quantity_received: number }>, note?: string) =>
    apiRequest<PurchaseOrderRecord>(`/v1/purchase-orders/${id}/receive`, { method: 'POST', body: { items, note } }),
  listRequisitions: () => apiRequest<Array<Record<string, unknown>>>('/v1/requisitions'),
  createRequisition: (body: { location_id: number; supplier_id?: number; notes?: string; items: Array<Record<string, unknown>> }) =>
    apiRequest<Record<string, unknown>>('/v1/requisitions', { method: 'POST', body }),
  convertRequisition: (id: string) => apiRequest<Record<string, unknown>>(`/v1/requisitions/${id}/convert`, { method: 'POST' }),

  // Campaigns & Promotions
  listCampaigns: () => apiRequest<SurgeCampaignRecord[]>('/v1/campaigns'),
  createCampaign: (body: Record<string, unknown>) => apiRequest<SurgeCampaignRecord>('/v1/campaigns', { method: 'POST', body }),
  transitionCampaign: (id: string, target_status: string) =>
    apiRequest<SurgeCampaignRecord>(`/v1/campaigns/${id}/transition`, { method: 'POST', body: { target_status } }),
  listPromotions: () => apiRequest<PromotionRecord[]>('/v1/promotions'),
  createPromotion: (body: Record<string, unknown>) => apiRequest<PromotionRecord>('/v1/promotions', { method: 'POST', body }),
  validateCoupon: (body: { code: string; subtotal_minor: number; customer_id?: number | null }) =>
    apiRequest<{ valid: boolean; code: string; discountMinor: number; discount: string; reason: string | null }>('/v1/promotions/validate', { method: 'POST', body }),

  // Sales, Invoices, Returns, Reports & P&L
  listSalesRecords: async (search?: string): Promise<Page<SalesRecordItem>> => {
    const raw = await apiRequest<unknown>('/v1/sales/records', { query: { page: 1, pageSize: 50, search } });
    return adaptPage<SalesRecordItem>(raw);
  },
  getSalesDashboard: () => apiRequest<Record<string, unknown>>('/v1/sales/dashboard'),
  getSalesPnl: () => apiRequest<Record<string, unknown>>('/v1/sales/pnl'),
  listInvoices: () => apiRequest<InvoiceRecord[]>('/v1/invoices'),
  listReturns: () => apiRequest<ReturnRecord[]>('/v1/returns'),
  createReturn: (body: Record<string, unknown>) => apiRequest<ReturnRecord>('/v1/returns', { method: 'POST', body }),
  reviewReturn: (id: string, body: Record<string, unknown>) =>
    apiRequest<ReturnRecord>(`/v1/returns/${id}/review`, { method: 'POST', body }),
  getReport: (reportType: string) => apiRequest<{ reportType: string; headers: string[]; rows: Array<Record<string, unknown>>; count: number }>(`/v1/reports/${reportType}`),
  downloadReportCsv: async (reportType: string) => {
    const activeOrg = getActiveOrganisationId();
    const res = await fetch(`${config.apiBaseUrl}/v1/reports/${reportType}/export.csv`, {
      headers: {
        ...getAuthHeaders(),
        ...(activeOrg !== null ? { 'X-Organisation-Id': String(activeOrg) } : {}),
      },
    });
    if (!res.ok) throw new Error(`Failed to export ${reportType} report.`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `flashcore_${reportType}_report.csv`;
    a.click();
    URL.revokeObjectURL(url);
  },

  // POS
  listShifts: () => apiRequest<PosShiftRecord[]>('/v1/pos/shifts'),
  openShift: (body: { location_id: number; opening_cash_minor: number }) =>
    apiRequest<PosShiftRecord>('/v1/pos/shifts/open', { method: 'POST', body }),
  closeShift: (id: string, counted_cash_minor: number) =>
    apiRequest<PosShiftRecord>(`/v1/pos/shifts/${id}/close`, { method: 'POST', body: { counted_cash_minor } }),
  listHeldBills: () => apiRequest<PosHeldBillRecord[]>('/v1/pos/held-bills'),
  holdBill: (body: Record<string, unknown>) => apiRequest<PosHeldBillRecord>('/v1/pos/held-bills', { method: 'POST', body }),
  posCheckout: (body: Record<string, unknown>) => apiRequest<Record<string, unknown>>('/v1/pos/checkout', { method: 'POST', body }),

  // Tax & Governance & Automation & Readiness
  getTaxProfile: () => apiRequest<TaxProfileRecord>('/v1/tax/profile'),
  updateTaxProfile: (body: Record<string, unknown>) => apiRequest<TaxProfileRecord>('/v1/tax/profile', { method: 'PUT', body }),
  listNotifications: () => apiRequest<{ unreadCount: number; items: NotificationItem[] }>('/v1/notifications'),
  markNotificationRead: (id: string) => apiRequest<NotificationItem>(`/v1/notifications/${id}/read`, { method: 'POST' }),
  listAutomationRules: () => apiRequest<Array<Record<string, unknown>>>('/v1/automation/rules'),
  createAutomationRule: (body: { name: string; trigger_type: string; threshold_value: number }) =>
    apiRequest<Record<string, unknown>>('/v1/automation/rules', { method: 'POST', body }),
  runAutomationRules: () => apiRequest<{ executedRules: number }>('/v1/automation/run', { method: 'POST' }),
  listReadinessAdapters: () => apiRequest<Array<{ channel: string; category: string; status: string; detail: string }>>('/v1/integrations/readiness'),

  // Voice Intelligence
  listVoiceSessions: () => apiRequest<VoiceSessionRecord[]>('/v1/voice/sessions'),
  queryVoice: (body: { session_id?: number; transcript: string; language: string; input_mode: 'voice' | 'text' }) =>
    apiRequest<Record<string, unknown>>('/v1/voice/query', { method: 'POST', body }),
  transcribeAudio: (body: { audio_base64: string; filename: string; language: string }) =>
    apiRequest<{ text: string; language: string; provider: string }>('/v1/voice/transcribe', { method: 'POST', body }),
  decideVoiceAction: (id: string, approve: boolean, note?: string) =>
    apiRequest<VoiceProposal>(`/v1/voice/actions/${id}/decide`, { method: 'POST', body: { approve, note } }),
};
