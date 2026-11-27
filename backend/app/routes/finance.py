from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext, require_org_roles
from app.core.database import get_db
from app.schemas.finance import (
    FinanceOverviewOut,
    PaymentLinkCreateRequest,
    PaymentLinkListResponse,
    PaymentLinkOut,
    ReconciliationItemListResponse,
    ReconciliationItemOut,
    ReconciliationResolveRequest,
    ReconciliationRunCreateRequest,
    ReconciliationRunListResponse,
    ReconciliationRunOut,
    RefundCreateRequest,
    RefundDecisionRequest,
    RefundListResponse,
    RefundOut,
    RefundPolicyOut,
    RefundPolicyUpdate,
    SettlementCsvImportRequest,
    SettlementImportResponse,
    SettlementListResponse,
    SettlementOut,
    SettlementSyncResponse,
)
from app.services import (
    payment_link_service,
    reconciliation_service,
    refund_service,
    settlement_service,
)

router = APIRouter(prefix="/api/v1/payments", tags=["Financial Operations"])


@router.get("/policies/refunds", response_model=RefundPolicyOut)
def get_refund_policy(
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return refund_service.get_refund_policy_out(db, org_ctx.organisation.id)


@router.put("/policies/refunds", response_model=RefundPolicyOut)
def update_refund_policy(
    payload: RefundPolicyUpdate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return refund_service.update_refund_policy(db, org_ctx, payload)


@router.post(
    "/transactions/{transaction_id}/refunds",
    response_model=RefundOut,
    status_code=201,
)
def create_refund(
    transaction_id: int,
    payload: RefundCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return refund_service.request_refund(
        db,
        org_ctx,
        transaction_id,
        payload,
        idempotency_key=idempotency_key,
    )


@router.get("/refunds", response_model=RefundListResponse)
def list_refunds(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    status: str | None = Query(None),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return refund_service.list_refunds(
        db, org_ctx.organisation.id, page=page, page_size=page_size, status=status
    )


@router.get("/refunds/{refund_id}", response_model=RefundOut)
def get_refund(
    refund_id: int,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return refund_service.get_refund(db, org_ctx.organisation.id, refund_id)


@router.post("/refunds/{refund_id}/approve", response_model=RefundOut)
def approve_refund(
    refund_id: int,
    payload: RefundDecisionRequest | None = None,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return refund_service.approve_refund(
        db, org_ctx, refund_id, payload.decision_note if payload else None
    )


@router.post("/refunds/{refund_id}/reject", response_model=RefundOut)
def reject_refund(
    refund_id: int,
    payload: RefundDecisionRequest | None = None,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return refund_service.reject_refund(
        db, org_ctx, refund_id, payload.decision_note if payload else None
    )


@router.post("/refunds/{refund_id}/sync", response_model=RefundOut)
def sync_refund(
    refund_id: int,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return refund_service.sync_refund(db, org_ctx, refund_id)


@router.post("/links", response_model=PaymentLinkOut, status_code=201)
def create_payment_link(
    payload: PaymentLinkCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return payment_link_service.create_payment_link(
        db, org_ctx, payload, idempotency_key=idempotency_key
    )


@router.get("/links", response_model=PaymentLinkListResponse)
def list_payment_links(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    status: str | None = Query(None),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return payment_link_service.list_payment_links(
        db, org_ctx.organisation.id, page=page, page_size=page_size, status=status
    )


@router.get("/links/{link_id}", response_model=PaymentLinkOut)
def get_payment_link(
    link_id: int,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return payment_link_service.get_payment_link(db, org_ctx.organisation.id, link_id)


@router.post("/links/{link_id}/cancel", response_model=PaymentLinkOut)
def cancel_payment_link(
    link_id: int,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return payment_link_service.cancel_payment_link(db, org_ctx, link_id)


@router.post("/links/{link_id}/sync", response_model=PaymentLinkOut)
def sync_payment_link(
    link_id: int,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return payment_link_service.sync_payment_link(db, org_ctx, link_id)


@router.post("/settlements/sync", response_model=SettlementSyncResponse)
def sync_settlements(
    from_date: datetime | None = Query(None, alias="fromDate"),
    to_date: datetime | None = Query(None, alias="toDate"),
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return settlement_service.sync_provider_settlements(
        db, org_ctx, from_dt=from_date, to_dt=to_date
    )


@router.post("/settlements/import", response_model=SettlementImportResponse, status_code=201)
def import_settlement_statement(
    payload: SettlementCsvImportRequest,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return settlement_service.import_settlement_statement_csv(db, org_ctx, payload)


@router.get("/settlements", response_model=SettlementListResponse)
def list_settlements(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    status: str | None = Query(None),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return settlement_service.list_settlements(
        db, org_ctx.organisation.id, page=page, page_size=page_size, status=status
    )


@router.get("/settlements/{settlement_id}", response_model=SettlementOut)
def get_settlement(
    settlement_id: int,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return settlement_service.get_settlement(db, org_ctx.organisation.id, settlement_id)


@router.get("/overview", response_model=FinanceOverviewOut)
def get_finance_overview(
    currency: str = Query("INR", min_length=3, max_length=3),
    from_date: datetime | None = Query(None, alias="fromDate"),
    to_date: datetime | None = Query(None, alias="toDate"),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return settlement_service.get_financial_overview(
        db,
        org_ctx.organisation.id,
        currency=currency,
        from_dt=from_date,
        to_dt=to_date,
    )


@router.get("/reports/export")
def export_finance_report(
    currency: str = Query("INR", min_length=3, max_length=3),
    from_date: datetime | None = Query(None, alias="fromDate"),
    to_date: datetime | None = Query(None, alias="toDate"),
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "analyst")),
    db: Session = Depends(get_db),
):
    csv_text = settlement_service.export_financial_report_csv(
        db, org_ctx, currency=currency, from_dt=from_date, to_dt=to_date
    )
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="flashcore-financial-report.csv"'
        },
    )


@router.post(
    "/reconciliation/runs", response_model=ReconciliationRunOut, status_code=201
)
def create_reconciliation_run(
    payload: ReconciliationRunCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return reconciliation_service.run_reconciliation(
        db,
        org_ctx,
        provider=payload.provider,
        currency=payload.currency,
        period_start=payload.period_start,
        period_end=payload.period_end,
        include_provider_fetch=payload.include_provider_fetch,
        idempotency_key=idempotency_key,
    )


@router.get("/reconciliation/runs", response_model=ReconciliationRunListResponse)
def list_reconciliation_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return reconciliation_service.list_reconciliation_runs(
        db, org_ctx.organisation.id, page=page, page_size=page_size
    )


@router.get("/reconciliation/runs/{run_id}", response_model=ReconciliationRunOut)
def get_reconciliation_run(
    run_id: int,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return reconciliation_service.get_reconciliation_run(
        db, org_ctx.organisation.id, run_id
    )


@router.get(
    "/reconciliation/runs/{run_id}/items",
    response_model=ReconciliationItemListResponse,
)
def list_reconciliation_items(
    run_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100, alias="pageSize"),
    outcome: str | None = Query(None),
    resolution_status: str | None = Query(None, alias="resolutionStatus"),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return reconciliation_service.list_reconciliation_items(
        db,
        org_ctx.organisation.id,
        run_id,
        page=page,
        page_size=page_size,
        outcome=outcome,
        resolution_status=resolution_status,
    )


@router.post(
    "/reconciliation/items/{item_id}/resolve",
    response_model=ReconciliationItemOut,
)
def resolve_reconciliation_item(
    item_id: int,
    payload: ReconciliationResolveRequest,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return reconciliation_service.resolve_reconciliation_item(
        db,
        org_ctx,
        item_id,
        resolution_status=payload.resolution_status,
        resolution_note=payload.resolution_note,
    )
