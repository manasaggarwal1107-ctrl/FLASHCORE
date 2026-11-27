import { apiRequest } from './client';
import { endpoints, resolvePath } from './endpoints';
import type { Page } from './pagination';
import type {
  CommerceCustomer,
  CommerceOrder,
  CommerceProduct,
  GatewayAccount,
  InventoryLocation,
  PaymentOrder,
  PaymentTransaction,
  PaymentVerificationResult,
  RetailInventoryBalance,
  RetailInventoryMovement,
} from '@/types/api';

export interface CatalogCreatePayload {
  sku: string;
  name: string;
  description?: string | null;
  category?: string | null;
  status?: 'draft' | 'active' | 'archived';
  price_minor: number;
  currency?: string;
  tax_rate_bps?: number;
}

export interface CustomerCreatePayload {
  name: string;
  email?: string | null;
  phone?: string | null;
}

export interface OrderCreatePayload {
  customer_id?: number | null;
  discount_minor?: number;
  submit_for_payment?: boolean;
  items: Array<{
    product_id: number;
    location_id?: number | null;
    quantity: number;
  }>;
}

export interface StockAdjustmentPayload {
  product_id: number;
  location_id?: number | null;
  quantity_delta: number;
  low_stock_threshold?: number | null;
  reason: string;
}

export interface RazorpayGatewayConfigPayload {
  mode: 'test';
  key_id: string;
  key_secret: string;
  webhook_secret: string;
  status?: 'active' | 'disabled';
}

export function listCatalogProducts(params?: { page?: number; pageSize?: number; search?: string; status?: string }) {
  return apiRequest<Page<CommerceProduct>>(endpoints.catalog.list.path!, {
    query: { page: params?.page ?? 1, pageSize: params?.pageSize ?? 50, search: params?.search, status: params?.status },
  });
}

export function getCatalogProduct(id: string | number) {
  return apiRequest<CommerceProduct>(resolvePath(endpoints.catalog.get.path!, { id }));
}

export function createCatalogProduct(payload: CatalogCreatePayload) {
  return apiRequest<CommerceProduct>(endpoints.catalog.create.path!, {
    method: 'POST',
    body: payload,
  });
}

export function updateCatalogProduct(id: string | number, payload: Partial<CatalogCreatePayload>) {
  return apiRequest<CommerceProduct>(resolvePath(endpoints.catalog.update.path!, { id }), {
    method: 'PATCH',
    body: payload,
  });
}

export function listInventoryLocations() {
  return apiRequest<InventoryLocation[]>(endpoints.retailInventory.locations.path!);
}

export function createInventoryLocation(payload: { code: string; name: string; location_type?: 'warehouse' | 'store' | 'fulfilment_centre' }) {
  return apiRequest<InventoryLocation>(endpoints.retailInventory.createLocation.path!, {
    method: 'POST',
    body: payload,
  });
}

export function listRetailInventory(params?: { page?: number; pageSize?: number; search?: string; locationId?: number }) {
  return apiRequest<Page<RetailInventoryBalance>>(endpoints.retailInventory.list.path!, {
    query: {
      page: params?.page ?? 1,
      pageSize: params?.pageSize ?? 50,
      search: params?.search,
      locationId: params?.locationId,
    },
  });
}

export function adjustRetailStock(payload: StockAdjustmentPayload) {
  return apiRequest<RetailInventoryBalance>(endpoints.retailInventory.adjust.path!, {
    method: 'POST',
    body: payload,
  });
}

export function listRetailMovements(params?: { page?: number; pageSize?: number; search?: string }) {
  return apiRequest<Page<RetailInventoryMovement>>(endpoints.retailInventory.movements.path!, {
    query: { page: params?.page ?? 1, pageSize: params?.pageSize ?? 50, search: params?.search },
  });
}

export function listCustomers(params?: { page?: number; pageSize?: number; search?: string }) {
  return apiRequest<Page<CommerceCustomer>>(endpoints.customers.list.path!, {
    query: { page: params?.page ?? 1, pageSize: params?.pageSize ?? 50, search: params?.search },
  });
}

export function getCustomer(id: string | number) {
  return apiRequest<CommerceCustomer>(resolvePath(endpoints.customers.get.path!, { id }));
}

export function createCustomer(payload: CustomerCreatePayload) {
  return apiRequest<CommerceCustomer>(endpoints.customers.create.path!, {
    method: 'POST',
    body: payload,
  });
}

export function listCustomerOrders(id: string | number, params?: { page?: number; pageSize?: number }) {
  return apiRequest<Page<CommerceOrder>>(resolvePath(endpoints.customers.orders.path!, { id }), {
    query: { page: params?.page ?? 1, pageSize: params?.pageSize ?? 25 },
  });
}

export function listOrders(params?: { page?: number; pageSize?: number; search?: string; status?: string }) {
  return apiRequest<Page<CommerceOrder>>(endpoints.orders.list.path!, {
    query: { page: params?.page ?? 1, pageSize: params?.pageSize ?? 50, search: params?.search, status: params?.status },
  });
}

export function getOrder(id: string | number) {
  return apiRequest<CommerceOrder>(resolvePath(endpoints.orders.get.path!, { id }));
}

export function createOrder(payload: OrderCreatePayload, idempotencyKey?: string) {
  return apiRequest<CommerceOrder>(endpoints.orders.create.path!, {
    method: 'POST',
    body: payload,
    idempotencyKey,
  });
}

export function transitionOrder(
  id: string | number,
  target_status: 'PENDING_PAYMENT' | 'PROCESSING' | 'FULFILLED' | 'CANCELLED',
  reason?: string,
) {
  return apiRequest<CommerceOrder>(resolvePath(endpoints.orders.transition.path!, { id }), {
    method: 'POST',
    body: { target_status, reason },
  });
}

export function initiateOrderCheckout(id: string | number, idempotencyKey?: string) {
  return apiRequest<PaymentOrder>(resolvePath(endpoints.orders.checkout.path!, { id }), {
    method: 'POST',
    idempotencyKey,
  });
}

export function listGatewayAccounts() {
  return apiRequest<GatewayAccount[]>(endpoints.payments.accounts.path!);
}

export function upsertRazorpayGateway(payload: RazorpayGatewayConfigPayload) {
  return apiRequest<GatewayAccount>(endpoints.payments.upsertRazorpay.path!, {
    method: 'PUT',
    body: payload,
  });
}

export function verifyRazorpayPayment(
  paymentOrderId: string | number,
  payload: {
    razorpay_order_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
  },
) {
  return apiRequest<PaymentVerificationResult>(
    resolvePath(endpoints.payments.verifyOrder.path!, { id: paymentOrderId }),
    {
      method: 'POST',
      body: payload,
    },
  );
}

export function listPaymentTransactions(params?: { page?: number; pageSize?: number; status?: string }) {
  return apiRequest<Page<PaymentTransaction>>(endpoints.payments.transactions.path!, {
    query: { page: params?.page ?? 1, pageSize: params?.pageSize ?? 50, status: params?.status },
  });
}
