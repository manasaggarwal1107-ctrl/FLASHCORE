import { getActiveOrganisationId, getAuthHeaders } from './auth';
import { apiRequest, buildUrl } from './client';
import { endpoints, resolvePath } from './endpoints';
import type { Page } from './pagination';
import type {
  FinanceOverview,
  PaymentLink,
  PaymentRefund,
  PaymentSettlement,
  ReconciliationItem,
  ReconciliationRun,
  RefundPolicy,
  SettlementImportResult,
  SettlementSyncResult,
} from '@/types/api';

export function getFinanceOverview(params?: { currency?: string; fromDate?: string; toDate?: string }) {
  return apiRequest<FinanceOverview>(endpoints.payments.overview.path!, {
    query: { currency: params?.currency ?? 'INR', fromDate: params?.fromDate, toDate: params?.toDate },
  });
}

export async function exportFinanceCsv(params?: { currency?: string; fromDate?: string; toDate?: string }): Promise<string> {
  const activeOrgId = getActiveOrganisationId();
  const res = await fetch(
    buildUrl(endpoints.payments.exportReport.path!, {
      currency: params?.currency ?? 'INR',
      fromDate: params?.fromDate,
      toDate: params?.toDate,
    }),
    {
      method: 'GET',
      headers: {
        ...getAuthHeaders(),
        ...(activeOrgId !== null ? { 'X-Organisation-Id': String(activeOrgId) } : {}),
      },
    },
  );
  if (!res.ok) {
    throw new Error(`Export failed (${res.status})`);
  }
  return res.text();
}

export function getRefundPolicy() {
  return apiRequest<RefundPolicy>(endpoints.payments.refundPolicy.path!);
}

export function updateRefundPolicy(payload: { refund_approval_threshold_minor: number; currency?: string }) {
  return apiRequest<RefundPolicy>(endpoints.payments.updateRefundPolicy.path!, {
    method: 'PUT',
    body: payload,
  });
}

export function listRefunds(params?: { page?: number; pageSize?: number; status?: string }) {
  return apiRequest<Page<PaymentRefund>>(endpoints.payments.refunds.path!, {
    query: { page: params?.page ?? 1, pageSize: params?.pageSize ?? 50, status: params?.status },
  });
}

export function getRefund(id: string | number) {
  return apiRequest<PaymentRefund>(resolvePath(endpoints.payments.refund.path!, { id }));
}

export function requestRefund(
  transactionId: string | number,
  payload: { amount_minor?: number; reason: string },
  idempotencyKey?: string,
) {
  return apiRequest<PaymentRefund>(
    resolvePath(endpoints.payments.createRefund.path!, { id: transactionId }),
    { method: 'POST', body: payload, idempotencyKey },
  );
}

export function approveRefund(refundId: string | number, decision_note?: string) {
  return apiRequest<PaymentRefund>(resolvePath(endpoints.payments.approveRefund.path!, { id: refundId }), {
    method: 'POST',
    body: decision_note ? { decision_note } : {},
  });
}

export function rejectRefund(refundId: string | number, decision_note?: string) {
  return apiRequest<PaymentRefund>(resolvePath(endpoints.payments.rejectRefund.path!, { id: refundId }), {
    method: 'POST',
    body: decision_note ? { decision_note } : {},
  });
}

export function syncRefund(refundId: string | number) {
  return apiRequest<PaymentRefund>(resolvePath(endpoints.payments.syncRefund.path!, { id: refundId }), {
    method: 'POST',
  });
}

export function listPaymentLinks(params?: { page?: number; pageSize?: number; status?: string }) {
  return apiRequest<Page<PaymentLink>>(endpoints.payments.links.path!, {
    query: { page: params?.page ?? 1, pageSize: params?.pageSize ?? 50, status: params?.status },
  });
}

export function createPaymentLink(
  payload: {
    order_id: number;
    amount_minor?: number;
    description: string;
    accept_partial?: boolean;
    expires_in_hours?: number;
    customer_name?: string;
    customer_email?: string;
    customer_phone?: string;
  },
  idempotencyKey?: string,
) {
  return apiRequest<PaymentLink>(endpoints.payments.createLink.path!, {
    method: 'POST',
    body: payload,
    idempotencyKey,
  });
}

export function cancelPaymentLink(linkId: string | number) {
  return apiRequest<PaymentLink>(resolvePath(endpoints.payments.cancelLink.path!, { id: linkId }), {
    method: 'POST',
  });
}

export function syncPaymentLink(linkId: string | number) {
  return apiRequest<PaymentLink>(resolvePath(endpoints.payments.syncLink.path!, { id: linkId }), {
    method: 'POST',
  });
}

export function listSettlements(params?: { page?: number; pageSize?: number; status?: string }) {
  return apiRequest<Page<PaymentSettlement>>(endpoints.payments.settlements.path!, {
    query: { page: params?.page ?? 1, pageSize: params?.pageSize ?? 50, status: params?.status },
  });
}

export function getSettlement(id: string | number) {
  return apiRequest<PaymentSettlement>(resolvePath(endpoints.payments.settlement.path!, { id }));
}

export function syncSettlements() {
  return apiRequest<SettlementSyncResult>(endpoints.payments.syncSettlements.path!, {
    method: 'POST',
  });
}

export function importSettlementStatement(payload: { filename: string; csv_content: string; provider?: 'razorpay' }) {
  return apiRequest<SettlementImportResult>(endpoints.payments.importSettlements.path!, {
    method: 'POST',
    body: payload,
  });
}

export function listReconciliationRuns(params?: { page?: number; pageSize?: number }) {
  return apiRequest<Page<ReconciliationRun>>(endpoints.payments.reconRuns.path!, {
    query: { page: params?.page ?? 1, pageSize: params?.pageSize ?? 25 },
  });
}

export function createReconciliationRun(
  payload: { provider?: 'razorpay'; currency?: string; include_provider_fetch?: boolean },
  idempotencyKey?: string,
) {
  return apiRequest<ReconciliationRun>(endpoints.payments.createReconRun.path!, {
    method: 'POST',
    body: payload,
    idempotencyKey,
  });
}

export function listReconciliationItems(
  runId: string | number,
  params?: { page?: number; pageSize?: number; outcome?: string; resolutionStatus?: string },
) {
  return apiRequest<Page<ReconciliationItem>>(resolvePath(endpoints.payments.reconItems.path!, { id: runId }), {
    query: {
      page: params?.page ?? 1,
      pageSize: params?.pageSize ?? 50,
      outcome: params?.outcome,
      resolutionStatus: params?.resolutionStatus,
    },
  });
}

export function resolveReconciliationItem(
  itemId: string | number,
  payload: { resolution_status: 'ACKNOWLEDGED' | 'RESOLVED'; resolution_note: string },
) {
  return apiRequest<ReconciliationItem>(resolvePath(endpoints.payments.resolveReconItem.path!, { id: itemId }), {
    method: 'POST',
    body: payload,
  });
}
