from collections import defaultdict
from datetime import datetime, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext
from app.models.finance import (
    PaymentReconciliationItem,
    PaymentReconciliationRun,
    PaymentRefund,
    PaymentSettlement,
    PaymentSettlementItem,
)
from app.models.payments import PaymentProviderAccount, PaymentTransaction
from app.models.retail import Order
from app.models.rossmann import AuditLog
from app.services import payment_service
from app.services.payments import GatewayTimeoutError, PaymentGatewayError


def _to_run_out(run: PaymentReconciliationRun) -> dict:
    return {
        "id": str(run.id),
        "organisation_id": run.organisation_id,
        "run_reference": run.run_reference,
        "provider": run.provider,
        "currency": run.currency,
        "period_start": run.period_start,
        "period_end": run.period_end,
        "status": run.status,
        "total_checked": run.total_checked,
        "matched_count": run.matched_count,
        "exception_count": run.exception_count,
        "summary_json": run.summary_json,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
    }


def _to_item_out(item: PaymentReconciliationItem) -> dict:
    return {
        "id": str(item.id),
        "run_id": str(item.run_id),
        "outcome": item.outcome,
        "entity_type": item.entity_type,
        "order_id": str(item.order_id) if item.order_id else None,
        "payment_transaction_id": (
            str(item.payment_transaction_id) if item.payment_transaction_id else None
        ),
        "refund_id": str(item.refund_id) if item.refund_id else None,
        "settlement_id": str(item.settlement_id) if item.settlement_id else None,
        "provider_ref": item.provider_ref,
        "expected_amount_minor": item.expected_amount_minor,
        "actual_amount_minor": item.actual_amount_minor,
        "expected_currency": item.expected_currency,
        "actual_currency": item.actual_currency,
        "expected_status": item.expected_status,
        "actual_status": item.actual_status,
        "discrepancy_details": item.discrepancy_details,
        "resolution_status": item.resolution_status,
        "resolution_note": item.resolution_note,
        "resolved_by_user_id": item.resolved_by_user_id,
        "resolved_at": item.resolved_at,
        "created_at": item.created_at,
    }


def run_reconciliation(
    db: Session,
    org_ctx: OrgContext,
    *,
    provider: str = "razorpay",
    currency: str = "INR",
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    include_provider_fetch: bool = False,
    idempotency_key: str | None = None,
    adapter_factory: payment_service.AdapterFactory | None = None,
) -> dict:
    org_id = org_ctx.organisation.id
    norm_currency = currency.strip().upper()
    if period_start and period_end and period_start > period_end:
        raise HTTPException(
            status_code=422, detail="period_start cannot be after period_end."
        )

    cleaned_key = idempotency_key.strip()[:80] if idempotency_key and idempotency_key.strip() else None
    if cleaned_key:
        existing_run = db.scalar(
            select(PaymentReconciliationRun).where(
                PaymentReconciliationRun.organisation_id == org_id,
                PaymentReconciliationRun.run_reference == cleaned_key,
            )
        )
        if existing_run is not None:
            return _to_run_out(existing_run)

    run_ref = (
        cleaned_key
        or f"RECON-{org_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    )
    run = PaymentReconciliationRun(
        organisation_id=org_id,
        run_reference=run_ref,
        provider=provider,
        currency=norm_currency,
        period_start=period_start,
        period_end=period_end,
        status="RUNNING",
        triggered_by_user_id=org_ctx.user.id,
    )
    db.add(run)
    db.flush()

    def _in_period(col):
        clauses = []
        if period_start:
            clauses.append(col >= period_start)
        if period_end:
            clauses.append(col <= period_end)
        return clauses

    txns = list(
        db.scalars(
            select(PaymentTransaction)
            .where(
                PaymentTransaction.organisation_id == org_id,
                PaymentTransaction.provider == provider,
                PaymentTransaction.currency == norm_currency,
                PaymentTransaction.event_type == "CAPTURED",
                *_in_period(PaymentTransaction.created_at),
            )
            .order_by(PaymentTransaction.id.asc())
        ).all()
    )

    orders = list(
        db.scalars(
            select(Order).where(
                Order.organisation_id == org_id,
                Order.currency == norm_currency,
                Order.order_status.in_(("PAID", "PROCESSING", "FULFILLED")),
                *_in_period(Order.placed_at),
            )
        ).all()
    )
    orders_by_id = {o.id: o for o in orders}

    refunds = list(
        db.scalars(
            select(PaymentRefund).where(
                PaymentRefund.organisation_id == org_id,
                PaymentRefund.provider == provider,
                PaymentRefund.currency == norm_currency,
                *_in_period(PaymentRefund.created_at),
            )
        ).all()
    )

    settlements = list(
        db.scalars(
            select(PaymentSettlement).where(
                PaymentSettlement.organisation_id == org_id,
                PaymentSettlement.provider == provider,
                PaymentSettlement.currency == norm_currency,
                *_in_period(PaymentSettlement.created_at),
            )
        ).all()
    )

    settlement_items = list(
        db.scalars(
            select(PaymentSettlementItem).where(
                PaymentSettlementItem.organisation_id == org_id,
                PaymentSettlementItem.settlement_id.in_([s.id for s in settlements])
                if settlements
                else False,
            )
        ).all()
    )

    provider_payments_by_id: dict[str, list] = defaultdict(list)
    provider_fetched = False
    account = db.scalar(
        select(PaymentProviderAccount).where(
            PaymentProviderAccount.organisation_id == org_id,
            PaymentProviderAccount.provider == provider,
            PaymentProviderAccount.mode == "test",
            PaymentProviderAccount.status == "active",
        )
    )
    if include_provider_fetch and account is not None:
        creds = payment_service._decrypt_credentials(account)
        adapter = (adapter_factory or payment_service.default_adapter_factory)(provider)
        from_ts = int(period_start.timestamp()) if period_start else None
        to_ts = int(period_end.timestamp()) if period_end else None
        try:
            gw_payments = adapter.fetch_payments(from_ts, to_ts, creds, count=100)
            provider_fetched = True
            for gp in gw_payments:
                provider_payments_by_id[gp.provider_payment_id].append(gp)
        except (GatewayTimeoutError, PaymentGatewayError) as exc:
            run.status = "FAILED"
            run.summary_json = {"error": str(exc)}
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            raise HTTPException(
                status_code=502,
                detail="Reconciliation provider fetch failed cleanly; no ledger records modified.",
            ) from exc

    recon_items: list[PaymentReconciliationItem] = []

    def _add_item(
        *,
        outcome: str,
        entity_type: str,
        order_id: int | None = None,
        txn_id: int | None = None,
        refund_id: int | None = None,
        settlement_id: int | None = None,
        provider_ref: str | None = None,
        exp_amt: int | None = None,
        act_amt: int | None = None,
        exp_curr: str | None = None,
        act_curr: str | None = None,
        exp_status: str | None = None,
        act_status: str | None = None,
        details: dict | None = None,
    ) -> None:
        recon_items.append(
            PaymentReconciliationItem(
                organisation_id=org_id,
                run_id=run.id,
                outcome=outcome,
                entity_type=entity_type,
                order_id=order_id,
                payment_transaction_id=txn_id,
                refund_id=refund_id,
                settlement_id=settlement_id,
                provider_ref=provider_ref,
                expected_amount_minor=exp_amt,
                actual_amount_minor=act_amt,
                expected_currency=exp_curr,
                actual_currency=act_curr,
                expected_status=exp_status,
                actual_status=act_status,
                discrepancy_details=details,
                resolution_status="RESOLVED" if outcome == "MATCHED" else "UNRESOLVED",
            )
        )

    # Track order -> captured transactions to detect duplicates
    txns_by_order: dict[int, list[PaymentTransaction]] = defaultdict(list)
    seen_provider_pids: set[str] = set()
    for t in txns:
        txns_by_order[t.order_id].append(t)

    # 1. Check orders & captured transactions
    for order_id, order_txns in txns_by_order.items():
        if len(order_txns) > 1:
            for t in order_txns:
                _add_item(
                    outcome="DUPLICATE",
                    entity_type="PAYMENT",
                    order_id=order_id,
                    txn_id=t.id,
                    provider_ref=t.provider_payment_id,
                    exp_amt=t.amount_minor,
                    act_amt=t.amount_minor,
                    exp_curr=t.currency,
                    act_curr=t.currency,
                    details={"reason": "Multiple CAPTURED transactions linked to single order."},
                )
            continue

        t = order_txns[0]
        seen_provider_pids.add(t.provider_payment_id)
        order = orders_by_id.get(order_id) or db.get(Order, order_id)

        matched_so_far = True
        if order is None:
            _add_item(
                outcome="NEEDS_REVIEW",
                entity_type="PAYMENT",
                txn_id=t.id,
                provider_ref=t.provider_payment_id,
                exp_amt=t.amount_minor,
                exp_curr=t.currency,
                details={"reason": "Linked order missing."},
            )
            matched_so_far = False
        elif order.currency.upper() != t.currency.upper():
            _add_item(
                outcome="CURRENCY_MISMATCH",
                entity_type="PAYMENT",
                order_id=order.id,
                txn_id=t.id,
                provider_ref=t.provider_payment_id,
                exp_amt=order.total_minor,
                act_amt=t.amount_minor,
                exp_curr=order.currency,
                act_curr=t.currency,
            )
            matched_so_far = False
        elif order.total_minor != t.amount_minor:
            _add_item(
                outcome="AMOUNT_MISMATCH",
                entity_type="PAYMENT",
                order_id=order.id,
                txn_id=t.id,
                provider_ref=t.provider_payment_id,
                exp_amt=order.total_minor,
                act_amt=t.amount_minor,
                exp_curr=order.currency,
                act_curr=t.currency,
            )
            matched_so_far = False
        elif order.order_status not in ("PAID", "PROCESSING", "FULFILLED"):
            _add_item(
                outcome="STATUS_MISMATCH",
                entity_type="ORDER",
                order_id=order.id,
                txn_id=t.id,
                provider_ref=t.provider_payment_id,
                exp_status="PAID",
                act_status=order.order_status,
            )
            matched_so_far = False

        if provider_fetched and matched_so_far:
            gp_list = provider_payments_by_id.get(t.provider_payment_id, [])
            if not gp_list:
                _add_item(
                    outcome="MISSING_IN_PROVIDER",
                    entity_type="PAYMENT",
                    order_id=t.id and order.id if order else None,
                    txn_id=t.id,
                    provider_ref=t.provider_payment_id,
                    exp_amt=t.amount_minor,
                    exp_curr=t.currency,
                    exp_status="captured",
                )
                matched_so_far = False
            elif len(gp_list) > 1:
                _add_item(
                    outcome="DUPLICATE",
                    entity_type="PAYMENT",
                    order_id=order.id if order else None,
                    txn_id=t.id,
                    provider_ref=t.provider_payment_id,
                    details={"provider_duplicates": len(gp_list)},
                )
                matched_so_far = False
            else:
                gp = gp_list[0]
                if gp.currency.upper() != t.currency.upper():
                    _add_item(
                        outcome="CURRENCY_MISMATCH",
                        entity_type="PAYMENT",
                        order_id=order.id if order else None,
                        txn_id=t.id,
                        provider_ref=t.provider_payment_id,
                        exp_amt=t.amount_minor,
                        act_amt=gp.amount_minor,
                        exp_curr=t.currency,
                        act_curr=gp.currency,
                    )
                    matched_so_far = False
                elif gp.amount_minor != t.amount_minor:
                    _add_item(
                        outcome="AMOUNT_MISMATCH",
                        entity_type="PAYMENT",
                        order_id=order.id if order else None,
                        txn_id=t.id,
                        provider_ref=t.provider_payment_id,
                        exp_amt=t.amount_minor,
                        act_amt=gp.amount_minor,
                        exp_curr=t.currency,
                        act_curr=gp.currency,
                    )
                    matched_so_far = False
                elif gp.status.lower() != "captured":
                    _add_item(
                        outcome="STATUS_MISMATCH",
                        entity_type="PAYMENT",
                        order_id=order.id if order else None,
                        txn_id=t.id,
                        provider_ref=t.provider_payment_id,
                        exp_status="captured",
                        act_status=gp.status,
                    )
                    matched_so_far = False

        if matched_so_far:
            _add_item(
                outcome="MATCHED",
                entity_type="PAYMENT",
                order_id=order.id if order else None,
                txn_id=t.id,
                provider_ref=t.provider_payment_id,
                exp_amt=t.amount_minor,
                act_amt=t.amount_minor,
                exp_curr=t.currency,
                act_curr=t.currency,
                exp_status="CAPTURED",
                act_status="CAPTURED",
            )

    # Paid orders without any CAPTURED transaction
    for order in orders:
        if order.id not in txns_by_order:
            _add_item(
                outcome="MISSING_IN_FLASHCORE",
                entity_type="ORDER",
                order_id=order.id,
                exp_amt=order.total_minor,
                exp_curr=order.currency,
                exp_status="CAPTURED",
                act_status=order.payment_status,
                details={"reason": "Order marked paid/fulfilled with no CAPTURED PaymentTransaction."},
            )

    # Provider captured payments missing locally in FLASHCORE
    if provider_fetched:
        for pid, gp_list in provider_payments_by_id.items():
            if pid not in seen_provider_pids:
                gp = gp_list[0]
                if gp.currency.upper() != norm_currency:
                    continue
                if str(gp.status).lower() == "captured":
                    _add_item(
                        outcome="MISSING_IN_FLASHCORE",
                        entity_type="PAYMENT",
                        provider_ref=pid,
                        act_amt=gp.amount_minor,
                        act_curr=gp.currency,
                        act_status=gp.status,
                    )

    # 2. Check Refunds vs captured transaction totals & pending ambiguity
    refunds_by_txn: dict[int, list[PaymentRefund]] = defaultdict(list)
    for rf in refunds:
        refunds_by_txn[rf.payment_transaction_id].append(rf)

    for txn_id, rf_list in refunds_by_txn.items():
        parent_txn = db.get(PaymentTransaction, txn_id)
        active_sum = sum(
            r.amount_minor for r in rf_list if r.status in ("PROCESSED", "PENDING", "SUBMITTED")
        )
        if parent_txn is None:
            for r in rf_list:
                _add_item(
                    outcome="REFUND_MISMATCH",
                    entity_type="REFUND",
                    refund_id=r.id,
                    provider_ref=r.provider_refund_id,
                    exp_amt=r.amount_minor,
                    exp_curr=r.currency,
                )
            continue
        if active_sum > parent_txn.amount_minor:
            for r in rf_list:
                _add_item(
                    outcome="REFUND_MISMATCH",
                    entity_type="REFUND",
                    order_id=parent_txn.order_id,
                    txn_id=parent_txn.id,
                    refund_id=r.id,
                    provider_ref=r.provider_refund_id,
                    exp_amt=parent_txn.amount_minor,
                    act_amt=active_sum,
                    exp_curr=parent_txn.currency,
                    act_curr=r.currency,
                )
            continue
        for r in rf_list:
            if r.currency != parent_txn.currency:
                _add_item(
                    outcome="CURRENCY_MISMATCH",
                    entity_type="REFUND",
                    order_id=r.order_id,
                    txn_id=parent_txn.id,
                    refund_id=r.id,
                    provider_ref=r.provider_refund_id,
                    exp_curr=parent_txn.currency,
                    act_curr=r.currency,
                )
            elif r.status in ("PENDING", "SUBMITTED"):
                _add_item(
                    outcome="NEEDS_REVIEW",
                    entity_type="REFUND",
                    order_id=r.order_id,
                    txn_id=parent_txn.id,
                    refund_id=r.id,
                    provider_ref=r.provider_refund_id,
                    exp_amt=r.amount_minor,
                    exp_curr=r.currency,
                    exp_status="PROCESSED",
                    act_status=r.status,
                )
            elif r.status == "PROCESSED":
                _add_item(
                    outcome="MATCHED",
                    entity_type="REFUND",
                    order_id=r.order_id,
                    txn_id=parent_txn.id,
                    refund_id=r.id,
                    provider_ref=r.provider_refund_id,
                    exp_amt=r.amount_minor,
                    act_amt=r.amount_minor,
                    exp_curr=r.currency,
                    act_curr=r.currency,
                    exp_status="PROCESSED",
                    act_status="PROCESSED",
                )

    # 3. Check Settlements & Settlement Items
    items_by_settlement: dict[int, list[PaymentSettlementItem]] = defaultdict(list)
    for si in settlement_items:
        items_by_settlement[si.settlement_id].append(si)

    for s in settlements:
        expected_net = (
            s.gross_amount_minor
            - s.refund_amount_minor
            - s.fee_minor
            - s.tax_minor
            + s.adjustment_minor
        )
        if expected_net != s.net_amount_minor:
            _add_item(
                outcome="SETTLEMENT_MISMATCH",
                entity_type="SETTLEMENT",
                settlement_id=s.id,
                provider_ref=s.provider_settlement_id,
                exp_amt=expected_net,
                act_amt=s.net_amount_minor,
                exp_curr=s.currency,
                act_curr=s.currency,
            )
            continue

        s_items = items_by_settlement.get(s.id, [])
        if not s_items:
            _add_item(
                outcome="MATCHED" if s.status == "PROCESSED" else "NEEDS_REVIEW",
                entity_type="SETTLEMENT",
                settlement_id=s.id,
                provider_ref=s.provider_settlement_id,
                exp_amt=s.net_amount_minor,
                act_amt=s.net_amount_minor,
                exp_curr=s.currency,
                act_curr=s.currency,
                exp_status="PROCESSED",
                act_status=s.status,
            )
            continue

        for si in s_items:
            if si.entity_type == "PAYMENT":
                if si.payment_transaction_id is None:
                    _add_item(
                        outcome="MISSING_IN_FLASHCORE",
                        entity_type="SETTLEMENT",
                        settlement_id=s.id,
                        provider_ref=si.provider_entity_id,
                        act_amt=si.gross_amount_minor,
                        act_curr=si.currency,
                    )
                else:
                    lt = db.get(PaymentTransaction, si.payment_transaction_id)
                    if lt is not None and lt.amount_minor != si.gross_amount_minor:
                        _add_item(
                            outcome="SETTLEMENT_MISMATCH",
                            entity_type="SETTLEMENT",
                            order_id=lt.order_id,
                            txn_id=lt.id,
                            settlement_id=s.id,
                            provider_ref=si.provider_entity_id,
                            exp_amt=lt.amount_minor,
                            act_amt=si.gross_amount_minor,
                            exp_curr=lt.currency,
                            act_curr=si.currency,
                        )
                    else:
                        _add_item(
                            outcome="MATCHED",
                            entity_type="SETTLEMENT",
                            order_id=lt.order_id if lt else None,
                            txn_id=si.payment_transaction_id,
                            settlement_id=s.id,
                            provider_ref=si.provider_entity_id,
                            exp_amt=si.gross_amount_minor,
                            act_amt=si.gross_amount_minor,
                            exp_curr=si.currency,
                            act_curr=si.currency,
                        )

    for ri in recon_items:
        db.add(ri)

    matched_count = sum(1 for ri in recon_items if ri.outcome == "MATCHED")
    exception_count = sum(1 for ri in recon_items if ri.outcome != "MATCHED")
    by_outcome: dict[str, int] = defaultdict(int)
    for ri in recon_items:
        by_outcome[ri.outcome] += 1

    now = datetime.now(timezone.utc)
    run.status = "COMPLETED"
    run.total_checked = len(recon_items)
    run.matched_count = matched_count
    run.exception_count = exception_count
    run.summary_json = {"by_outcome": dict(by_outcome), "provider_fetched": provider_fetched}
    run.completed_at = now

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="reconciliation_run_completed",
            entity_name="payment_reconciliation_runs",
            entity_id=str(run.id),
            details={
                "run_reference": run.run_reference,
                "total_checked": run.total_checked,
                "matched_count": matched_count,
                "exception_count": exception_count,
            },
        )
    )
    db.commit()
    db.refresh(run)
    return _to_run_out(run)


def list_reconciliation_runs(
    db: Session, org_id: int, *, page: int = 1, page_size: int = 25
) -> dict:
    total = (
        db.scalar(
            select(func.count(PaymentReconciliationRun.id)).where(
                PaymentReconciliationRun.organisation_id == org_id
            )
        )
        or 0
    )
    offset = (page - 1) * page_size
    rows = list(
        db.scalars(
            select(PaymentReconciliationRun)
            .where(PaymentReconciliationRun.organisation_id == org_id)
            .order_by(PaymentReconciliationRun.id.desc())
            .offset(offset)
            .limit(page_size)
        ).all()
    )
    return {
        "items": [_to_run_out(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_reconciliation_run(db: Session, org_id: int, run_id: int) -> dict:
    run = db.scalar(
        select(PaymentReconciliationRun).where(
            PaymentReconciliationRun.id == run_id,
            PaymentReconciliationRun.organisation_id == org_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Reconciliation run not found.")
    return _to_run_out(run)


def list_reconciliation_items(
    db: Session,
    org_id: int,
    run_id: int,
    *,
    page: int = 1,
    page_size: int = 50,
    outcome: str | None = None,
    resolution_status: str | None = None,
) -> dict:
    run = db.scalar(
        select(PaymentReconciliationRun).where(
            PaymentReconciliationRun.id == run_id,
            PaymentReconciliationRun.organisation_id == org_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Reconciliation run not found.")

    query = select(PaymentReconciliationItem).where(
        PaymentReconciliationItem.run_id == run_id,
        PaymentReconciliationItem.organisation_id == org_id,
    )
    count_q = select(func.count(PaymentReconciliationItem.id)).where(
        PaymentReconciliationItem.run_id == run_id,
        PaymentReconciliationItem.organisation_id == org_id,
    )
    if outcome:
        norm = outcome.strip().upper()
        query = query.where(PaymentReconciliationItem.outcome == norm)
        count_q = count_q.where(PaymentReconciliationItem.outcome == norm)
    if resolution_status:
        norm_res = resolution_status.strip().upper()
        query = query.where(PaymentReconciliationItem.resolution_status == norm_res)
        count_q = count_q.where(PaymentReconciliationItem.resolution_status == norm_res)

    total = db.scalar(count_q) or 0
    offset = (page - 1) * page_size
    rows = list(
        db.scalars(
            query.order_by(PaymentReconciliationItem.id.asc())
            .offset(offset)
            .limit(page_size)
        ).all()
    )
    return {
        "items": [_to_item_out(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def resolve_reconciliation_item(
    db: Session,
    org_ctx: OrgContext,
    item_id: int,
    *,
    resolution_status: str,
    resolution_note: str,
) -> dict:
    org_id = org_ctx.organisation.id
    item = db.scalar(
        select(PaymentReconciliationItem)
        .where(
            PaymentReconciliationItem.id == item_id,
            PaymentReconciliationItem.organisation_id == org_id,
        )
        .with_for_update()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Reconciliation item not found.")

    now = datetime.now(timezone.utc)
    item.resolution_status = resolution_status
    item.resolution_note = resolution_note.strip()
    item.resolved_by_user_id = org_ctx.user.id
    item.resolved_at = now
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="reconciliation_item_resolved",
            entity_name="payment_reconciliation_items",
            entity_id=str(item.id),
            details={
                "outcome": item.outcome,
                "resolution_status": resolution_status,
                "resolution_note": item.resolution_note,
            },
        )
    )
    db.commit()
    db.refresh(item)
    return _to_item_out(item)
