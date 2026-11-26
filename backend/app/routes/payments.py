from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext, require_org_roles
from app.core.database import get_db
from app.schemas.payments import (
    GatewayAccountOut,
    GatewayAccountUpsert,
    PaymentOrderCreateRequest,
    PaymentOrderOut,
    PaymentTransactionListResponse,
    PaymentTransactionOut,
    PaymentVerificationOut,
    PaymentVerifyRequest,
)
from app.services import payment_service

router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


@router.put("/accounts/razorpay", response_model=GatewayAccountOut)
def upsert_razorpay_account(
    payload: GatewayAccountUpsert,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return payment_service.upsert_razorpay_account(db, org_ctx, payload)


@router.get("/accounts", response_model=list[GatewayAccountOut])
def list_gateway_accounts(
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return payment_service.list_gateway_accounts(db, org_ctx.organisation.id)


@router.post("/orders", response_model=PaymentOrderOut, status_code=201)
def create_payment_order(
    payload: PaymentOrderCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return payment_service.create_payment_order_for_checkout(
        db, org_ctx, payload.order_id, idempotency_key=idempotency_key
    )


@router.get("/orders/{payment_order_id}", response_model=PaymentOrderOut)
def get_payment_order(
    payment_order_id: int,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return payment_service.get_payment_order(
        db, org_ctx.organisation.id, payment_order_id
    )


@router.post("/orders/{payment_order_id}/verify", response_model=PaymentVerificationOut)
def verify_payment_order(
    payment_order_id: int,
    payload: PaymentVerifyRequest,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return payment_service.verify_checkout_payment(
        db, org_ctx, payment_order_id, payload
    )


@router.get("/transactions", response_model=PaymentTransactionListResponse)
def list_payment_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    status: str | None = Query(None),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return payment_service.list_payment_transactions(
        db, org_ctx.organisation.id, page=page, page_size=page_size, status=status
    )


@router.get("/transactions/{transaction_id}", response_model=PaymentTransactionOut)
def get_payment_transaction(
    transaction_id: int,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return payment_service.get_payment_transaction(
        db, org_ctx.organisation.id, transaction_id
    )
