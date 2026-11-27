from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext
from app.models.finance import (
    PaymentApprovalPolicy,
    PaymentApprovalRequest,
    PaymentRefund,
    PaymentRefundEvent,
)
from app.models.payments import (
    PaymentOrder,
    PaymentProviderAccount,
    PaymentTransaction,
)
from app.models.rossmann import AuditLog
from app.schemas.finance import (
    RefundApprovalOut,
    RefundCreateRequest,
    RefundEventOut,
    RefundOut,
    RefundPolicyOut,
    RefundPolicyUpdate,
)
from app.schemas.retail import format_minor_to_decimal_str
from app.services import payment_service
from app.services.payments import (
    GatewayRefundRequest,
    GatewayTimeoutError,
    PaymentGatewayError,
)

DEFAULT_REFUND_THRESHOLD_MINOR = 100000  # INR 1000.00
ACTIVE_OR_SETTLED_REFUND_STATUSES = (
    "REQUESTED",
    "APPROVAL_PENDING",
    "SUBMITTED",
    "PENDING",
    "PROCESSED",
)


def _sanitize_gateway_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    blocked = {"key_secret", "webhook_secret", "authorization", "token", "secret"}
    return {
        k: v
        for k, v in payload.items()
        if str(k).lower() not in blocked
    }


def _to_approval_out(req: PaymentApprovalRequest) -> RefundApprovalOut:
    return RefundApprovalOut(
        id=str(req.id),
        refund_id=str(req.refund_id),
        order_id=str(req.order_id),
        payment_transaction_id=str(req.payment_transaction_id),
        amount_minor=req.amount_minor,
        amount=format_minor_to_decimal_str(req.amount_minor),
        currency=req.currency,
        threshold_minor=req.threshold_minor,
        status=req.status,
        requested_by_user_id=req.requested_by_user_id,
        decided_by_user_id=req.decided_by_user_id,
        decision_note=req.decision_note,
        decided_at=req.decided_at,
        created_at=req.created_at,
    )


def _to_refund_out(
    db: Session,
    refund: PaymentRefund,
    *,
    include_events: bool = True,
) -> RefundOut:
    approval = db.scalar(
        select(PaymentApprovalRequest).where(
            PaymentApprovalRequest.refund_id == refund.id
        )
    )
    events_out: list[RefundEventOut] | None = None
    if include_events:
        events = list(
            db.scalars(
                select(PaymentRefundEvent)
                .where(PaymentRefundEvent.refund_id == refund.id)
                .order_by(PaymentRefundEvent.id.asc())
            ).all()
        )
        events_out = [
            RefundEventOut(
                id=e.id,
                from_status=e.from_status,
                to_status=e.to_status,
                event_type=e.event_type,
                source=e.source,
                actor_ref=e.actor_ref,
                details=e.details,
                created_at=e.created_at,
            )
            for e in events
        ]

    return RefundOut(
        id=str(refund.id),
        organisation_id=refund.organisation_id,
        order_id=str(refund.order_id),
        payment_order_id=str(refund.payment_order_id),
        payment_transaction_id=str(refund.payment_transaction_id),
        provider=refund.provider,
        provider_payment_id=refund.provider_payment_id,
        provider_refund_id=refund.provider_refund_id,
        amount_minor=refund.amount_minor,
        amount=format_minor_to_decimal_str(refund.amount_minor),
        currency=refund.currency,
        refund_type=refund.refund_type,
        status=refund.status,
        reason=refund.reason,
        provider_status=refund.provider_status,
        failure_code=refund.failure_code,
        failure_reason=refund.failure_reason,
        requires_approval=approval is not None,
        approval_request=_to_approval_out(approval) if approval is not None else None,
        events=events_out,
        submitted_at=refund.submitted_at,
        processed_at=refund.processed_at,
        created_at=refund.created_at,
        updated_at=refund.updated_at,
    )


def get_or_create_refund_policy(db: Session, org_id: int) -> PaymentApprovalPolicy:
    policy = db.scalar(
        select(PaymentApprovalPolicy).where(
            PaymentApprovalPolicy.organisation_id == org_id
        )
    )
    if policy is None:
        policy = PaymentApprovalPolicy(
            organisation_id=org_id,
            refund_approval_threshold_minor=DEFAULT_REFUND_THRESHOLD_MINOR,
            currency="INR",
        )
        db.add(policy)
        db.flush()
    return policy


def get_refund_policy_out(db: Session, org_id: int) -> RefundPolicyOut:
    policy = get_or_create_refund_policy(db, org_id)
    db.commit()
    return RefundPolicyOut(
        organisation_id=policy.organisation_id,
        refund_approval_threshold_minor=policy.refund_approval_threshold_minor,
        refund_approval_threshold=format_minor_to_decimal_str(
            policy.refund_approval_threshold_minor
        ),
        currency=policy.currency,
        updated_at=policy.updated_at,
    )


def update_refund_policy(
    db: Session, org_ctx: OrgContext, payload: RefundPolicyUpdate
) -> RefundPolicyOut:
    org_id = org_ctx.organisation.id
    policy = get_or_create_refund_policy(db, org_id)
    policy.refund_approval_threshold_minor = payload.refund_approval_threshold_minor
    policy.currency = payload.currency
    policy.updated_by_user_id = org_ctx.user.id
    policy.updated_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="refund_policy_updated",
            entity_name="payment_approval_policies",
            entity_id=str(policy.id),
            details={
                "refund_approval_threshold_minor": payload.refund_approval_threshold_minor,
                "currency": payload.currency,
            },
        )
    )
    db.commit()
    db.refresh(policy)
    return RefundPolicyOut(
        organisation_id=policy.organisation_id,
        refund_approval_threshold_minor=policy.refund_approval_threshold_minor,
        refund_approval_threshold=format_minor_to_decimal_str(
            policy.refund_approval_threshold_minor
        ),
        currency=policy.currency,
        updated_at=policy.updated_at,
    )


def _submit_refund_to_gateway(
    db: Session,
    *,
    refund: PaymentRefund,
    actor_role: str,
    actor_ref: str,
    idempotency_key: str | None,
    adapter_factory: payment_service.AdapterFactory | None,
) -> None:
    po = db.get(PaymentOrder, refund.payment_order_id)
    if po is None or po.organisation_id != refund.organisation_id:
        raise HTTPException(status_code=404, detail="Linked payment order not found.")
    account = db.get(PaymentProviderAccount, po.provider_account_id)
    if (
        account is None
        or account.organisation_id != refund.organisation_id
        or account.status != "active"
        or account.mode != "test"
    ):
        raise HTTPException(
            status_code=409,
            detail="Active test-mode payment gateway account is required for refunds.",
        )

    now = datetime.now(timezone.utc)
    prev_status = refund.status
    refund.status = "SUBMITTED"
    refund.submitted_at = now
    refund.updated_at = now
    db.add(
        PaymentRefundEvent(
            organisation_id=refund.organisation_id,
            refund_id=refund.id,
            from_status=prev_status,
            to_status="SUBMITTED",
            event_type="refund_submitted",
            source="api",
            actor_ref=actor_ref,
        )
    )
    db.commit()

    creds = payment_service._decrypt_credentials(account)
    adapter = (adapter_factory or payment_service.default_adapter_factory)(
        refund.provider
    )
    try:
        gw_res = adapter.create_refund(
            GatewayRefundRequest(
                provider_payment_id=refund.provider_payment_id,
                amount_minor=refund.amount_minor,
                currency=refund.currency,
                receipt=f"RFND-{refund.id}",
                notes={
                    "organisation_id": str(refund.organisation_id),
                    "order_id": str(refund.order_id),
                    "refund_id": str(refund.id),
                },
                idempotency_key=idempotency_key or f"rfnd-{refund.id}",
            ),
            creds,
        )
    except GatewayTimeoutError as exc:
        err_now = datetime.now(timezone.utc)
        refund_row = db.get(PaymentRefund, refund.id)
        if refund_row is not None:
            refund_row.status = "PENDING"
            refund_row.failure_code = "GATEWAY_TIMEOUT"
            refund_row.failure_reason = str(exc)
            refund_row.updated_at = err_now
            db.add(
                PaymentRefundEvent(
                    organisation_id=refund_row.organisation_id,
                    refund_id=refund_row.id,
                    from_status="SUBMITTED",
                    to_status="PENDING",
                    event_type="refund_gateway_timeout",
                    source="api",
                    actor_ref=actor_ref,
                    details={"error": str(exc)},
                )
            )
            db.add(
                AuditLog(
                    organisation_id=refund_row.organisation_id,
                    actor_type=actor_role,
                    actor_ref=actor_ref,
                    action="refund_gateway_timeout",
                    entity_name="payment_refunds",
                    entity_id=str(refund_row.id),
                    details={"status": "PENDING", "reason": "gateway_timeout"},
                )
            )
            db.commit()
        raise HTTPException(
            status_code=504,
            detail="Payment gateway timed out while processing refund; status marked PENDING for verification.",
        ) from exc
    except PaymentGatewayError as exc:
        err_now = datetime.now(timezone.utc)
        refund_row = db.get(PaymentRefund, refund.id)
        if refund_row is not None:
            refund_row.status = "FAILED"
            refund_row.failure_code = f"HTTP_{exc.status_code}" if exc.status_code else "GATEWAY_ERROR"
            refund_row.failure_reason = str(exc)
            refund_row.updated_at = err_now
            db.add(
                PaymentRefundEvent(
                    organisation_id=refund_row.organisation_id,
                    refund_id=refund_row.id,
                    from_status="SUBMITTED",
                    to_status="FAILED",
                    event_type="refund_gateway_failed",
                    source="api",
                    actor_ref=actor_ref,
                    details={"error": str(exc)},
                )
            )
            db.add(
                AuditLog(
                    organisation_id=refund_row.organisation_id,
                    actor_type=actor_role,
                    actor_ref=actor_ref,
                    action="refund_gateway_failed",
                    entity_name="payment_refunds",
                    entity_id=str(refund_row.id),
                    details={"status": "FAILED", "error": str(exc)},
                )
            )
            db.commit()
        raise HTTPException(
            status_code=502,
            detail="Gateway rejected refund submission.",
        ) from exc

    if (
        gw_res.amount_minor != refund.amount_minor
        or gw_res.currency.upper() != refund.currency.upper()
    ):
        err_now = datetime.now(timezone.utc)
        refund.status = "FAILED"
        refund.failure_code = "RESPONSE_MISMATCH"
        refund.failure_reason = "Gateway refund amount or currency mismatched local refund."
        refund.updated_at = err_now
        db.add(
            PaymentRefundEvent(
                organisation_id=refund.organisation_id,
                refund_id=refund.id,
                from_status="SUBMITTED",
                to_status="FAILED",
                event_type="refund_response_mismatch",
                source="api",
                actor_ref=actor_ref,
            )
        )
        db.commit()
        raise HTTPException(
            status_code=502,
            detail="Gateway refund amount or currency mismatch.",
        )

    done_now = datetime.now(timezone.utc)
    refund.provider_refund_id = gw_res.provider_refund_id
    refund.provider_status = gw_res.provider_status
    refund.provider_payload = _sanitize_gateway_payload(gw_res.raw_payload)
    refund.status = gw_res.status
    if gw_res.status == "PROCESSED":
        refund.processed_at = done_now
    refund.updated_at = done_now

    db.add(
        PaymentRefundEvent(
            organisation_id=refund.organisation_id,
            refund_id=refund.id,
            from_status="SUBMITTED",
            to_status=gw_res.status,
            event_type="refund_gateway_response",
            source="api",
            actor_ref=actor_ref,
            details={
                "provider_refund_id": gw_res.provider_refund_id,
                "provider_status": gw_res.provider_status,
            },
        )
    )
    db.add(
        AuditLog(
            organisation_id=refund.organisation_id,
            actor_type=actor_role,
            actor_ref=actor_ref,
            action=f"refund_{gw_res.status.lower()}",
            entity_name="payment_refunds",
            entity_id=str(refund.id),
            details={
                "order_id": refund.order_id,
                "amount_minor": refund.amount_minor,
                "currency": refund.currency,
                "provider_refund_id": gw_res.provider_refund_id,
                "status": gw_res.status,
            },
        )
    )
    db.commit()


def request_refund(
    db: Session,
    org_ctx: OrgContext,
    transaction_id: int,
    payload: RefundCreateRequest,
    *,
    idempotency_key: str | None = None,
    adapter_factory: payment_service.AdapterFactory | None = None,
) -> RefundOut:
    org_id = org_ctx.organisation.id
    cleaned_key = idempotency_key.strip() if idempotency_key and idempotency_key.strip() else None

    if cleaned_key:
        existing_refund = db.scalar(
            select(PaymentRefund).where(
                PaymentRefund.organisation_id == org_id,
                PaymentRefund.idempotency_key == cleaned_key,
            )
        )
        if existing_refund is not None:
            if existing_refund.payment_transaction_id != transaction_id or (
                payload.amount_minor is not None
                and payload.amount_minor != existing_refund.amount_minor
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency-Key was already used for a different refund request.",
                )
            return _to_refund_out(db, existing_refund)

    txn = db.scalar(
        select(PaymentTransaction)
        .where(
            PaymentTransaction.id == transaction_id,
            PaymentTransaction.organisation_id == org_id,
        )
        .with_for_update()
    )
    if txn is None:
        raise HTTPException(status_code=404, detail="Payment transaction not found.")
    if txn.status != "CAPTURED" or txn.event_type != "CAPTURED":
        raise HTTPException(
            status_code=409,
            detail="Only CAPTURED payment transactions are eligible for refunds.",
        )

    existing_refunds = list(
        db.scalars(
            select(PaymentRefund)
            .where(
                PaymentRefund.organisation_id == org_id,
                PaymentRefund.payment_transaction_id == txn.id,
                PaymentRefund.status.in_(ACTIVE_OR_SETTLED_REFUND_STATUSES),
            )
            .with_for_update()
        ).all()
    )
    committed_minor = sum(r.amount_minor for r in existing_refunds)
    remaining_minor = txn.amount_minor - committed_minor
    if remaining_minor <= 0:
        raise HTTPException(
            status_code=409,
            detail="Captured transaction has no remaining refundable balance.",
        )

    amount_minor = payload.amount_minor if payload.amount_minor is not None else remaining_minor
    if amount_minor > remaining_minor:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Refund amount ({amount_minor}) exceeds remaining refundable balance ({remaining_minor})."
            ),
        )

    refund_type = (
        "FULL" if committed_minor == 0 and amount_minor == txn.amount_minor else "PARTIAL"
    )
    policy = get_or_create_refund_policy(db, org_id)
    needs_approval = amount_minor > policy.refund_approval_threshold_minor
    initial_status = "APPROVAL_PENDING" if needs_approval else "REQUESTED"

    refund = PaymentRefund(
        organisation_id=org_id,
        order_id=txn.order_id,
        payment_order_id=txn.payment_order_id,
        payment_transaction_id=txn.id,
        payment_attempt_id=txn.payment_attempt_id,
        provider=txn.provider,
        provider_payment_id=txn.provider_payment_id,
        idempotency_key=cleaned_key,
        amount_minor=amount_minor,
        currency=txn.currency,
        refund_type=refund_type,
        status=initial_status,
        reason=payload.reason.strip(),
        notes_json=payload.notes,
        requested_by_user_id=org_ctx.user.id,
    )
    db.add(refund)
    db.flush()

    db.add(
        PaymentRefundEvent(
            organisation_id=org_id,
            refund_id=refund.id,
            from_status=None,
            to_status=initial_status,
            event_type="refund_requested",
            source="api",
            actor_ref=org_ctx.user.email,
            details={
                "amount_minor": amount_minor,
                "currency": txn.currency,
                "refund_type": refund_type,
                "requires_approval": needs_approval,
            },
        )
    )

    if needs_approval:
        approval = PaymentApprovalRequest(
            organisation_id=org_id,
            refund_id=refund.id,
            order_id=txn.order_id,
            payment_transaction_id=txn.id,
            request_type="HIGH_VALUE_REFUND",
            amount_minor=amount_minor,
            currency=txn.currency,
            threshold_minor=policy.refund_approval_threshold_minor,
            status="PENDING",
            requested_by_user_id=org_ctx.user.id,
        )
        db.add(approval)
        db.add(
            AuditLog(
                organisation_id=org_id,
                actor_type=org_ctx.membership.role,
                actor_ref=org_ctx.user.email,
                action="refund_approval_requested",
                entity_name="payment_refunds",
                entity_id=str(refund.id),
                details={
                    "order_id": txn.order_id,
                    "amount_minor": amount_minor,
                    "currency": txn.currency,
                    "threshold_minor": policy.refund_approval_threshold_minor,
                },
            )
        )
        db.commit()
        db.refresh(refund)
        return _to_refund_out(db, refund)

    _submit_refund_to_gateway(
        db,
        refund=refund,
        actor_role=org_ctx.membership.role,
        actor_ref=org_ctx.user.email,
        idempotency_key=cleaned_key,
        adapter_factory=adapter_factory,
    )
    db.refresh(refund)
    return _to_refund_out(db, refund)


def approve_refund(
    db: Session,
    org_ctx: OrgContext,
    refund_id: int,
    decision_note: str | None = None,
    *,
    adapter_factory: payment_service.AdapterFactory | None = None,
) -> RefundOut:
    org_id = org_ctx.organisation.id
    refund = db.scalar(
        select(PaymentRefund)
        .where(
            PaymentRefund.id == refund_id,
            PaymentRefund.organisation_id == org_id,
        )
        .with_for_update()
    )
    if refund is None:
        raise HTTPException(status_code=404, detail="Refund request not found.")
    if refund.status != "APPROVAL_PENDING":
        raise HTTPException(
            status_code=409,
            detail=f"Refund in status {refund.status} cannot be approved.",
        )

    approval = db.scalar(
        select(PaymentApprovalRequest)
        .where(
            PaymentApprovalRequest.refund_id == refund.id,
            PaymentApprovalRequest.organisation_id == org_id,
        )
        .with_for_update()
    )
    if approval is None or approval.status != "PENDING":
        raise HTTPException(
            status_code=409,
            detail="No pending single-use approval request exists for this refund.",
        )

    # Strict binding invariant check
    if (
        approval.amount_minor != refund.amount_minor
        or approval.currency != refund.currency
        or approval.payment_transaction_id != refund.payment_transaction_id
        or approval.order_id != refund.order_id
    ):
        raise HTTPException(
            status_code=409,
            detail="Approval binding mismatch against refund financial parameters.",
        )

    txn = db.scalar(
        select(PaymentTransaction)
        .where(
            PaymentTransaction.id == refund.payment_transaction_id,
            PaymentTransaction.organisation_id == org_id,
        )
        .with_for_update()
    )
    if txn is None or txn.status != "CAPTURED":
        raise HTTPException(status_code=409, detail="Captured transaction not found.")

    other_committed = sum(
        r.amount_minor
        for r in db.scalars(
            select(PaymentRefund)
            .where(
                PaymentRefund.organisation_id == org_id,
                PaymentRefund.payment_transaction_id == txn.id,
                PaymentRefund.id != refund.id,
                PaymentRefund.status.in_(ACTIVE_OR_SETTLED_REFUND_STATUSES),
            )
            .with_for_update()
        ).all()
    )
    if other_committed + refund.amount_minor > txn.amount_minor:
        raise HTTPException(
            status_code=409,
            detail="Remaining refundable balance is insufficient for approval.",
        )

    now = datetime.now(timezone.utc)
    approval.status = "CONSUMED"
    approval.decided_by_user_id = org_ctx.user.id
    approval.decision_note = decision_note.strip() if decision_note else None
    approval.decided_at = now
    approval.updated_at = now

    refund.approved_by_user_id = org_ctx.user.id
    refund.updated_at = now
    db.add(
        PaymentRefundEvent(
            organisation_id=org_id,
            refund_id=refund.id,
            from_status="APPROVAL_PENDING",
            to_status="APPROVAL_PENDING",
            event_type="refund_approved",
            source="approval",
            actor_ref=org_ctx.user.email,
            details={"approval_id": approval.id, "decision_note": approval.decision_note},
        )
    )
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="refund_approved",
            entity_name="payment_refunds",
            entity_id=str(refund.id),
            details={
                "approval_id": approval.id,
                "amount_minor": refund.amount_minor,
                "currency": refund.currency,
            },
        )
    )

    _submit_refund_to_gateway(
        db,
        refund=refund,
        actor_role=org_ctx.membership.role,
        actor_ref=org_ctx.user.email,
        idempotency_key=refund.idempotency_key,
        adapter_factory=adapter_factory,
    )
    db.refresh(refund)
    return _to_refund_out(db, refund)


def reject_refund(
    db: Session,
    org_ctx: OrgContext,
    refund_id: int,
    decision_note: str | None = None,
) -> RefundOut:
    org_id = org_ctx.organisation.id
    refund = db.scalar(
        select(PaymentRefund)
        .where(
            PaymentRefund.id == refund_id,
            PaymentRefund.organisation_id == org_id,
        )
        .with_for_update()
    )
    if refund is None:
        raise HTTPException(status_code=404, detail="Refund request not found.")
    if refund.status != "APPROVAL_PENDING":
        raise HTTPException(
            status_code=409,
            detail=f"Refund in status {refund.status} cannot be rejected.",
        )

    approval = db.scalar(
        select(PaymentApprovalRequest)
        .where(
            PaymentApprovalRequest.refund_id == refund.id,
            PaymentApprovalRequest.organisation_id == org_id,
        )
        .with_for_update()
    )
    now = datetime.now(timezone.utc)
    if approval is not None and approval.status == "PENDING":
        approval.status = "REJECTED"
        approval.decided_by_user_id = org_ctx.user.id
        approval.decision_note = decision_note.strip() if decision_note else None
        approval.decided_at = now
        approval.updated_at = now

    refund.status = "REJECTED"
    refund.rejected_by_user_id = org_ctx.user.id
    refund.updated_at = now
    db.add(
        PaymentRefundEvent(
            organisation_id=org_id,
            refund_id=refund.id,
            from_status="APPROVAL_PENDING",
            to_status="REJECTED",
            event_type="refund_rejected",
            source="approval",
            actor_ref=org_ctx.user.email,
            details={"decision_note": decision_note},
        )
    )
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="refund_rejected",
            entity_name="payment_refunds",
            entity_id=str(refund.id),
            details={"amount_minor": refund.amount_minor, "currency": refund.currency},
        )
    )
    db.commit()
    db.refresh(refund)
    return _to_refund_out(db, refund)


def sync_refund(
    db: Session,
    org_ctx: OrgContext,
    refund_id: int,
    *,
    adapter_factory: payment_service.AdapterFactory | None = None,
) -> RefundOut:
    org_id = org_ctx.organisation.id
    refund = db.scalar(
        select(PaymentRefund)
        .where(
            PaymentRefund.id == refund_id,
            PaymentRefund.organisation_id == org_id,
        )
        .with_for_update()
    )
    if refund is None:
        raise HTTPException(status_code=404, detail="Refund not found.")
    if not refund.provider_refund_id:
        raise HTTPException(
            status_code=409,
            detail="Refund does not have a provider refund ID to synchronise yet.",
        )

    po = db.get(PaymentOrder, refund.payment_order_id)
    if po is None:
        raise HTTPException(status_code=404, detail="Linked payment order not found.")
    account = db.get(PaymentProviderAccount, po.provider_account_id)
    if account is None:
        raise HTTPException(status_code=409, detail="Gateway account not found.")

    creds = payment_service._decrypt_credentials(account)
    adapter = (adapter_factory or payment_service.default_adapter_factory)(
        refund.provider
    )
    try:
        gw_res = adapter.fetch_refund(refund.provider_refund_id, creds)
    except GatewayTimeoutError as exc:
        raise HTTPException(
            status_code=504, detail="Gateway timed out while verifying refund status."
        ) from exc
    except PaymentGatewayError as exc:
        raise HTTPException(
            status_code=502, detail="Unable to fetch refund status from gateway."
        ) from exc

    if gw_res.amount_minor != refund.amount_minor or gw_res.currency != refund.currency:
        raise HTTPException(
            status_code=409,
            detail="Gateway refund amount or currency mismatch during sync.",
        )

    prev = refund.status
    now = datetime.now(timezone.utc)
    if prev != "PROCESSED" or gw_res.status == "PROCESSED":
        refund.status = gw_res.status
    refund.provider_status = gw_res.provider_status
    refund.provider_payload = _sanitize_gateway_payload(gw_res.raw_payload)
    if refund.status == "PROCESSED" and refund.processed_at is None:
        refund.processed_at = now
    refund.updated_at = now

    db.add(
        PaymentRefundEvent(
            organisation_id=org_id,
            refund_id=refund.id,
            from_status=prev,
            to_status=refund.status,
            event_type="refund_synced",
            source="provider_sync",
            actor_ref=org_ctx.user.email,
            details={"provider_status": gw_res.provider_status},
        )
    )
    db.commit()
    db.refresh(refund)
    return _to_refund_out(db, refund)


def list_refunds(
    db: Session,
    org_id: int,
    *,
    page: int = 1,
    page_size: int = 25,
    status: str | None = None,
) -> dict:
    query = select(PaymentRefund).where(PaymentRefund.organisation_id == org_id)
    count_q = select(func.count(PaymentRefund.id)).where(
        PaymentRefund.organisation_id == org_id
    )
    if status:
        norm = status.strip().upper()
        query = query.where(PaymentRefund.status == norm)
        count_q = count_q.where(PaymentRefund.status == norm)

    total = db.scalar(count_q) or 0
    offset = (page - 1) * page_size
    rows = list(
        db.scalars(
            query.order_by(PaymentRefund.id.desc()).offset(offset).limit(page_size)
        ).all()
    )
    items = [_to_refund_out(db, r, include_events=False) for r in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_refund(db: Session, org_id: int, refund_id: int) -> RefundOut:
    refund = db.scalar(
        select(PaymentRefund).where(
            PaymentRefund.id == refund_id,
            PaymentRefund.organisation_id == org_id,
        )
    )
    if refund is None:
        raise HTTPException(status_code=404, detail="Refund not found.")
    return _to_refund_out(db, refund, include_events=True)
