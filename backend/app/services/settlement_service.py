import csv
from datetime import datetime, timezone
import hashlib
import io

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext
from app.models.finance import (
    PaymentLink,
    PaymentReconciliationItem,
    PaymentRefund,
    PaymentSettlement,
    PaymentSettlementItem,
    PaymentStatementImport,
)
from app.models.payments import PaymentProviderAccount, PaymentTransaction
from app.models.rossmann import AuditLog
from app.schemas.finance import (
    FinanceOverviewOut,
    SettlementCsvImportRequest,
    SettlementImportResponse,
    SettlementItemOut,
    SettlementOut,
    SettlementSyncResponse,
)
from app.schemas.retail import format_minor_to_decimal_str
from app.services import payment_service
from app.services.payments import (
    GatewayCapabilityUnavailableError,
    GatewayTimeoutError,
    PaymentGatewayError,
)

MAX_CSV_BYTES = 2 * 1024 * 1024
REQUIRED_SETTLEMENT_COLUMNS = {
    "provider_settlement_id",
    "status",
    "gross_amount_minor",
    "refund_amount_minor",
    "fee_minor",
    "tax_minor",
    "adjustment_minor",
    "net_amount_minor",
    "currency",
}
VALID_SETTLEMENT_STATUSES = {"INITIATED", "PROCESSED", "FAILED", "REVERSED"}
FORMULA_PREFIXES = ("=", "+", "@", "\t", "\r")


def _safe_text(val: str | None, field: str, *, allow_leading_minus: bool = False) -> str:
    cleaned = (val or "").strip()
    if not cleaned:
        raise ValueError(f"Missing required field '{field}'.")
    if cleaned[0] in FORMULA_PREFIXES or (not allow_leading_minus and cleaned.startswith("-")):
        raise ValueError(f"Unsafe formula-like prefix rejected in '{field}'.")
    return cleaned


def _csv_escape(value: object) -> str:
    text = "" if value is None else str(value)
    if text and (text[0] in FORMULA_PREFIXES or text.startswith("-")):
        text = f"'{text}"
    return text


def _parse_int(val: str | None, field: str, *, allow_negative: bool = False) -> int:
    cleaned = (val or "").strip()
    if not cleaned:
        raise ValueError(f"Missing integer field '{field}'.")
    try:
        parsed = int(cleaned)
    except ValueError as exc:
        raise ValueError(f"Field '{field}' must be an integer in minor units.") from exc
    if not allow_negative and parsed < 0:
        raise ValueError(f"Field '{field}' cannot be negative.")
    return parsed


def _parse_optional_dt(val: str | None) -> datetime | None:
    cleaned = (val or "").strip()
    if not cleaned:
        return None
    normalized = cleaned.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _to_settlement_out(
    db: Session, s: PaymentSettlement, *, include_items: bool = False
) -> SettlementOut:
    items_out: list[SettlementItemOut] | None = None
    if include_items:
        rows = list(
            db.scalars(
                select(PaymentSettlementItem)
                .where(PaymentSettlementItem.settlement_id == s.id)
                .order_by(PaymentSettlementItem.id.asc())
            ).all()
        )
        items_out = [
            SettlementItemOut(
                id=str(i.id),
                entity_type=i.entity_type,
                provider_entity_id=i.provider_entity_id,
                payment_transaction_id=(
                    str(i.payment_transaction_id) if i.payment_transaction_id else None
                ),
                refund_id=str(i.refund_id) if i.refund_id else None,
                order_id=str(i.order_id) if i.order_id else None,
                gross_amount_minor=i.gross_amount_minor,
                gross_amount=format_minor_to_decimal_str(i.gross_amount_minor),
                fee_minor=i.fee_minor,
                fee=format_minor_to_decimal_str(i.fee_minor),
                tax_minor=i.tax_minor,
                tax=format_minor_to_decimal_str(i.tax_minor),
                net_amount_minor=i.net_amount_minor,
                net_amount=format_minor_to_decimal_str(i.net_amount_minor),
                currency=i.currency,
            )
            for i in rows
        ]

    return SettlementOut(
        id=str(s.id),
        organisation_id=s.organisation_id,
        provider=s.provider,
        provider_settlement_id=s.provider_settlement_id,
        status=s.status,
        gross_amount_minor=s.gross_amount_minor,
        gross_amount=format_minor_to_decimal_str(s.gross_amount_minor),
        refund_amount_minor=s.refund_amount_minor,
        refund_amount=format_minor_to_decimal_str(s.refund_amount_minor),
        fee_minor=s.fee_minor,
        fee=format_minor_to_decimal_str(s.fee_minor),
        tax_minor=s.tax_minor,
        tax=format_minor_to_decimal_str(s.tax_minor),
        adjustment_minor=s.adjustment_minor,
        adjustment=format_minor_to_decimal_str(s.adjustment_minor),
        net_amount_minor=s.net_amount_minor,
        net_amount=format_minor_to_decimal_str(s.net_amount_minor),
        currency=s.currency,
        settlement_utr=s.settlement_utr,
        period_start=s.period_start,
        period_end=s.period_end,
        settled_at=s.settled_at,
        source=s.source,
        items=items_out,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def sync_provider_settlements(
    db: Session,
    org_ctx: OrgContext,
    *,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    adapter_factory: payment_service.AdapterFactory | None = None,
) -> SettlementSyncResponse:
    org_id = org_ctx.organisation.id
    account = db.scalar(
        select(PaymentProviderAccount).where(
            PaymentProviderAccount.organisation_id == org_id,
            PaymentProviderAccount.provider == "razorpay",
            PaymentProviderAccount.mode == "test",
            PaymentProviderAccount.status == "active",
        )
    )
    if account is None:
        return SettlementSyncResponse(
            status="capability_unavailable",
            synced_count=0,
            message="No active test-mode Razorpay gateway account is configured for this organisation.",
        )

    creds = payment_service._decrypt_credentials(account)
    adapter = (adapter_factory or payment_service.default_adapter_factory)("razorpay")
    from_ts = int(from_dt.timestamp()) if from_dt else None
    to_ts = int(to_dt.timestamp()) if to_dt else None

    try:
        gw_settlements = adapter.fetch_settlements(from_ts, to_ts, creds)
    except GatewayCapabilityUnavailableError as exc:
        db.add(
            AuditLog(
                organisation_id=org_id,
                actor_type=org_ctx.membership.role,
                actor_ref=org_ctx.user.email,
                action="settlement_sync_unavailable",
                entity_name="payment_settlements",
                entity_id=str(org_id),
                details={"reason": str(exc)},
            )
        )
        db.commit()
        return SettlementSyncResponse(
            status="capability_unavailable",
            synced_count=0,
            message=str(exc),
        )
    except GatewayTimeoutError as exc:
        raise HTTPException(
            status_code=504, detail="Gateway timed out fetching settlements."
        ) from exc
    except PaymentGatewayError as exc:
        raise HTTPException(
            status_code=502, detail="Gateway error fetching settlements."
        ) from exc

    synced = 0
    now = datetime.now(timezone.utc)
    for gs in gw_settlements:
        existing = db.scalar(
            select(PaymentSettlement)
            .where(
                PaymentSettlement.organisation_id == org_id,
                PaymentSettlement.provider == "razorpay",
                PaymentSettlement.provider_settlement_id == gs.provider_settlement_id,
            )
            .with_for_update()
        )
        if existing is None:
            db.add(
                PaymentSettlement(
                    organisation_id=org_id,
                    provider_account_id=account.id,
                    provider="razorpay",
                    provider_settlement_id=gs.provider_settlement_id,
                    status=gs.status,
                    gross_amount_minor=gs.gross_amount_minor,
                    refund_amount_minor=gs.refund_amount_minor,
                    fee_minor=gs.fee_minor,
                    tax_minor=gs.tax_minor,
                    adjustment_minor=gs.adjustment_minor,
                    net_amount_minor=gs.net_amount_minor,
                    currency=gs.currency,
                    settlement_utr=gs.utr,
                    settled_at=gs.settled_at,
                    source="provider_sync",
                    raw_metadata={"provider": "razorpay"},
                )
            )
            synced += 1
        else:
            existing.status = gs.status
            existing.gross_amount_minor = gs.gross_amount_minor
            existing.refund_amount_minor = gs.refund_amount_minor
            existing.fee_minor = gs.fee_minor
            existing.tax_minor = gs.tax_minor
            existing.adjustment_minor = gs.adjustment_minor
            existing.net_amount_minor = gs.net_amount_minor
            existing.settlement_utr = gs.utr
            existing.settled_at = gs.settled_at
            existing.updated_at = now

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="settlements_synced",
            entity_name="payment_settlements",
            entity_id=str(org_id),
            details={"synced_count": synced},
        )
    )
    db.commit()
    return SettlementSyncResponse(
        status="synced",
        synced_count=synced,
        message=f"Synchronised {synced} settlement record(s) from provider.",
    )


def import_settlement_statement_csv(
    db: Session, org_ctx: OrgContext, payload: SettlementCsvImportRequest
) -> SettlementImportResponse:
    org_id = org_ctx.organisation.id
    raw_bytes = payload.csv_content.encode("utf-8")
    if len(raw_bytes) > MAX_CSV_BYTES:
        raise HTTPException(
            status_code=413, detail="Statement CSV exceeds 2 MB limit."
        )

    file_hash = hashlib.sha256(raw_bytes).hexdigest()
    existing_imp = db.scalar(
        select(PaymentStatementImport).where(
            PaymentStatementImport.organisation_id == org_id,
            PaymentStatementImport.file_hash == file_hash,
        )
    )
    if existing_imp is not None and existing_imp.status == "IMPORTED":
        return SettlementImportResponse(
            import_id=str(existing_imp.id),
            idempotent_replay=True,
            filename=existing_imp.filename,
            file_hash=existing_imp.file_hash,
            row_count=existing_imp.row_count,
            settlements_created=0,
        )

    reader = csv.DictReader(io.StringIO(payload.csv_content))
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="CSV statement header is missing.")
    headers = {h.strip() for h in reader.fieldnames if h}
    missing = REQUIRED_SETTLEMENT_COLUMNS - headers
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required CSV column(s): {', '.join(sorted(missing))}",
        )

    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=422, detail="CSV statement contains no rows.")

    parsed_rows: list[dict] = []
    seen_sids: set[str] = set()
    try:
        for idx, raw_row in enumerate(rows, start=1):
            sid = _safe_text(raw_row.get("provider_settlement_id"), "provider_settlement_id")
            if sid in seen_sids:
                raise ValueError(
                    f"Duplicate provider_settlement_id '{sid}' inside statement."
                )
            seen_sids.add(sid)

            status = _safe_text(raw_row.get("status"), "status").upper()
            if status not in VALID_SETTLEMENT_STATUSES:
                raise ValueError(f"Unsupported settlement status '{status}' on row {idx}.")

            gross = _parse_int(raw_row.get("gross_amount_minor"), "gross_amount_minor")
            refund_amt = _parse_int(raw_row.get("refund_amount_minor"), "refund_amount_minor")
            fee = _parse_int(raw_row.get("fee_minor"), "fee_minor")
            tax = _parse_int(raw_row.get("tax_minor"), "tax_minor")
            adjustment = _parse_int(
                raw_row.get("adjustment_minor"), "adjustment_minor", allow_negative=True
            )
            net = _parse_int(
                raw_row.get("net_amount_minor"), "net_amount_minor", allow_negative=True
            )
            if gross - refund_amt - fee - tax + adjustment != net:
                raise ValueError(
                    f"Row {idx} ({sid}) net_amount_minor does not equal gross - refund - fee - tax + adjustment."
                )

            currency = _safe_text(raw_row.get("currency"), "currency").upper()
            if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
                raise ValueError(f"Invalid currency '{currency}' on row {idx}.")

            utr = (raw_row.get("settlement_utr") or "").strip() or None
            if utr is not None:
                utr = _safe_text(utr, "settlement_utr")

            settled_at = _parse_optional_dt(raw_row.get("settled_at"))
            entity_id = (raw_row.get("provider_entity_id") or "").strip() or None
            entity_type = (raw_row.get("entity_type") or "PAYMENT").strip().upper()
            if entity_id and entity_type not in ("PAYMENT", "REFUND", "FEE", "ADJUSTMENT"):
                raise ValueError(f"Invalid entity_type '{entity_type}' on row {idx}.")

            dup_db = db.scalar(
                select(PaymentSettlement).where(
                    PaymentSettlement.organisation_id == org_id,
                    PaymentSettlement.provider == payload.provider,
                    PaymentSettlement.provider_settlement_id == sid,
                )
            )
            if dup_db is not None:
                raise ValueError(
                    f"Settlement '{sid}' already exists for this organisation."
                )

            linked_txn = None
            linked_refund = None
            linked_order_id = None
            if entity_id:
                if entity_type == "PAYMENT":
                    linked_txn = db.scalar(
                        select(PaymentTransaction).where(
                            PaymentTransaction.organisation_id == org_id,
                            PaymentTransaction.provider == payload.provider,
                            PaymentTransaction.provider_payment_id == entity_id,
                            PaymentTransaction.event_type == "CAPTURED",
                        )
                    )
                    if linked_txn is not None:
                        if linked_txn.currency != currency:
                            raise ValueError(
                                f"Currency mismatch for payment {entity_id} (statement {currency} vs ledger {linked_txn.currency})."
                            )
                        linked_order_id = linked_txn.order_id
                elif entity_type == "REFUND":
                    linked_refund = db.scalar(
                        select(PaymentRefund).where(
                            PaymentRefund.organisation_id == org_id,
                            PaymentRefund.provider == payload.provider,
                            PaymentRefund.provider_refund_id == entity_id,
                        )
                    )
                    if linked_refund is not None:
                        if linked_refund.currency != currency:
                            raise ValueError(
                                f"Currency mismatch for refund {entity_id}."
                            )
                        linked_order_id = linked_refund.order_id

            parsed_rows.append(
                {
                    "sid": sid,
                    "status": status,
                    "gross": gross,
                    "refund": refund_amt,
                    "fee": fee,
                    "tax": tax,
                    "adjustment": adjustment,
                    "net": net,
                    "currency": currency,
                    "utr": utr,
                    "settled_at": settled_at,
                    "entity_id": entity_id,
                    "entity_type": entity_type,
                    "linked_txn": linked_txn,
                    "linked_refund": linked_refund,
                    "linked_order_id": linked_order_id,
                }
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    stmt_import = PaymentStatementImport(
        organisation_id=org_id,
        provider=payload.provider,
        filename=payload.filename,
        file_hash=file_hash,
        file_size_bytes=len(raw_bytes),
        row_count=len(parsed_rows),
        status="IMPORTED",
        raw_summary={"settlement_ids": [r["sid"] for r in parsed_rows[:50]]},
        imported_by_user_id=org_ctx.user.id,
    )
    db.add(stmt_import)
    db.flush()

    created_count = 0
    for r in parsed_rows:
        settlement = PaymentSettlement(
            organisation_id=org_id,
            statement_import_id=stmt_import.id,
            provider=payload.provider,
            provider_settlement_id=r["sid"],
            status=r["status"],
            gross_amount_minor=r["gross"],
            refund_amount_minor=r["refund"],
            fee_minor=r["fee"],
            tax_minor=r["tax"],
            adjustment_minor=r["adjustment"],
            net_amount_minor=r["net"],
            currency=r["currency"],
            settlement_utr=r["utr"],
            settled_at=r["settled_at"],
            source="statement_import",
            raw_metadata={"import_id": stmt_import.id},
        )
        db.add(settlement)
        db.flush()
        created_count += 1

        if r["entity_id"] or r["linked_txn"] or r["linked_refund"]:
            db.add(
                PaymentSettlementItem(
                    organisation_id=org_id,
                    settlement_id=settlement.id,
                    payment_transaction_id=r["linked_txn"].id if r["linked_txn"] else None,
                    refund_id=r["linked_refund"].id if r["linked_refund"] else None,
                    order_id=r["linked_order_id"],
                    entity_type=r["entity_type"],
                    provider_entity_id=r["entity_id"],
                    gross_amount_minor=r["gross"],
                    fee_minor=r["fee"],
                    tax_minor=r["tax"],
                    net_amount_minor=r["net"],
                    currency=r["currency"],
                )
            )

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="settlement_statement_imported",
            entity_name="payment_statement_imports",
            entity_id=str(stmt_import.id),
            details={
                "filename": payload.filename,
                "row_count": len(parsed_rows),
                "settlements_created": created_count,
            },
        )
    )
    db.commit()
    return SettlementImportResponse(
        import_id=str(stmt_import.id),
        idempotent_replay=False,
        filename=stmt_import.filename,
        file_hash=file_hash,
        row_count=len(parsed_rows),
        settlements_created=created_count,
    )


def list_settlements(
    db: Session,
    org_id: int,
    *,
    page: int = 1,
    page_size: int = 25,
    status: str | None = None,
) -> dict:
    query = select(PaymentSettlement).where(PaymentSettlement.organisation_id == org_id)
    count_q = select(func.count(PaymentSettlement.id)).where(
        PaymentSettlement.organisation_id == org_id
    )
    if status:
        norm = status.strip().upper()
        query = query.where(PaymentSettlement.status == norm)
        count_q = count_q.where(PaymentSettlement.status == norm)

    total = db.scalar(count_q) or 0
    offset = (page - 1) * page_size
    rows = list(
        db.scalars(
            query.order_by(PaymentSettlement.id.desc()).offset(offset).limit(page_size)
        ).all()
    )
    return {
        "items": [_to_settlement_out(db, r, include_items=False) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_settlement(db: Session, org_id: int, settlement_id: int) -> SettlementOut:
    row = db.scalar(
        select(PaymentSettlement).where(
            PaymentSettlement.id == settlement_id,
            PaymentSettlement.organisation_id == org_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Settlement record not found.")
    return _to_settlement_out(db, row, include_items=True)


def get_financial_overview(
    db: Session,
    org_id: int,
    *,
    currency: str = "INR",
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
) -> FinanceOverviewOut:
    norm_currency = currency.strip().upper()

    if from_dt and to_dt and from_dt > to_dt:
        raise HTTPException(
            status_code=422, detail="Start date cannot be after end date."
        )

    def _date_bounds(col):
        clauses = []
        if from_dt:
            clauses.append(col >= from_dt)
        if to_dt:
            clauses.append(col <= to_dt)
        return clauses

    cap_filters = [
        PaymentTransaction.organisation_id == org_id,
        PaymentTransaction.currency == norm_currency,
        PaymentTransaction.event_type == "CAPTURED",
        PaymentTransaction.status == "CAPTURED",
        *_date_bounds(PaymentTransaction.created_at),
    ]
    gross_captured_minor = int(
        db.scalar(select(func.coalesce(func.sum(PaymentTransaction.amount_minor), 0)).where(*cap_filters))
        or 0
    )
    successful_payment_count = int(
        db.scalar(select(func.count(PaymentTransaction.id)).where(*cap_filters)) or 0
    )

    fail_filters = [
        PaymentTransaction.organisation_id == org_id,
        PaymentTransaction.currency == norm_currency,
        PaymentTransaction.event_type == "FAILED",
        *_date_bounds(PaymentTransaction.created_at),
    ]
    failed_payment_count = int(
        db.scalar(select(func.count(PaymentTransaction.id)).where(*fail_filters)) or 0
    )

    refund_base = [
        PaymentRefund.organisation_id == org_id,
        PaymentRefund.currency == norm_currency,
        *_date_bounds(PaymentRefund.created_at),
    ]
    full_refund_count = int(
        db.scalar(
            select(func.count(PaymentRefund.id)).where(
                *refund_base,
                PaymentRefund.status == "PROCESSED",
                PaymentRefund.refund_type == "FULL",
            )
        )
        or 0
    )
    partial_refund_count = int(
        db.scalar(
            select(func.count(PaymentRefund.id)).where(
                *refund_base,
                PaymentRefund.status == "PROCESSED",
                PaymentRefund.refund_type == "PARTIAL",
            )
        )
        or 0
    )
    total_refunded_minor = int(
        db.scalar(
            select(func.coalesce(func.sum(PaymentRefund.amount_minor), 0)).where(
                *refund_base,
                PaymentRefund.status == "PROCESSED",
            )
        )
        or 0
    )

    pending_statuses = ("REQUESTED", "APPROVAL_PENDING", "SUBMITTED", "PENDING")
    pending_refund_minor = int(
        db.scalar(
            select(func.coalesce(func.sum(PaymentRefund.amount_minor), 0)).where(
                *refund_base,
                PaymentRefund.status.in_(pending_statuses),
            )
        )
        or 0
    )
    pending_refund_count = int(
        db.scalar(
            select(func.count(PaymentRefund.id)).where(
                *refund_base,
                PaymentRefund.status.in_(pending_statuses),
            )
        )
        or 0
    )

    settlement_filters = [
        PaymentSettlement.organisation_id == org_id,
        PaymentSettlement.currency == norm_currency,
        PaymentSettlement.status == "PROCESSED",
        *_date_bounds(PaymentSettlement.created_at),
    ]
    gateway_fees_minor = int(
        db.scalar(
            select(func.coalesce(func.sum(PaymentSettlement.fee_minor), 0)).where(
                *settlement_filters
            )
        )
        or 0
    )
    gateway_tax_minor = int(
        db.scalar(
            select(func.coalesce(func.sum(PaymentSettlement.tax_minor), 0)).where(
                *settlement_filters
            )
        )
        or 0
    )
    gross_settlements_minor = int(
        db.scalar(
            select(
                func.coalesce(func.sum(PaymentSettlement.gross_amount_minor), 0)
            ).where(*settlement_filters)
        )
        or 0
    )
    net_settlements_minor = int(
        db.scalar(
            select(
                func.coalesce(func.sum(PaymentSettlement.net_amount_minor), 0)
            ).where(*settlement_filters)
        )
        or 0
    )

    settled_txn_ids_subq = (
        select(PaymentSettlementItem.payment_transaction_id)
        .join(
            PaymentSettlement,
            PaymentSettlement.id == PaymentSettlementItem.settlement_id,
        )
        .where(
            PaymentSettlement.organisation_id == org_id,
            PaymentSettlement.status == "PROCESSED",
            PaymentSettlementItem.payment_transaction_id.is_not(None),
        )
    )
    unsettled_captured_minor = int(
        db.scalar(
            select(func.coalesce(func.sum(PaymentTransaction.amount_minor), 0)).where(
                *cap_filters,
                ~PaymentTransaction.id.in_(settled_txn_ids_subq),
            )
        )
        or 0
    )

    recon_exceptions_count = int(
        db.scalar(
            select(func.count(PaymentReconciliationItem.id)).where(
                PaymentReconciliationItem.organisation_id == org_id,
                PaymentReconciliationItem.outcome != "MATCHED",
                PaymentReconciliationItem.resolution_status == "UNRESOLVED",
            )
        )
        or 0
    )

    active_payment_links_count = int(
        db.scalar(
            select(func.count(PaymentLink.id)).where(
                PaymentLink.organisation_id == org_id,
                PaymentLink.currency == norm_currency,
                PaymentLink.status.in_(("CREATED", "ACTIVE", "PARTIALLY_PAID")),
            )
        )
        or 0
    )
    paid_payment_links_count = int(
        db.scalar(
            select(func.count(PaymentLink.id)).where(
                PaymentLink.organisation_id == org_id,
                PaymentLink.currency == norm_currency,
                PaymentLink.status == "PAID",
            )
        )
        or 0
    )

    return FinanceOverviewOut(
        organisation_id=org_id,
        currency=norm_currency,
        period_start=from_dt,
        period_end=to_dt,
        gross_captured_minor=gross_captured_minor,
        gross_captured=format_minor_to_decimal_str(gross_captured_minor),
        successful_payment_count=successful_payment_count,
        failed_payment_count=failed_payment_count,
        full_refund_count=full_refund_count,
        partial_refund_count=partial_refund_count,
        total_refunded_minor=total_refunded_minor,
        total_refunded=format_minor_to_decimal_str(total_refunded_minor),
        pending_refund_minor=pending_refund_minor,
        pending_refund=format_minor_to_decimal_str(pending_refund_minor),
        pending_refund_count=pending_refund_count,
        gateway_fees_minor=gateway_fees_minor,
        gateway_fees=format_minor_to_decimal_str(gateway_fees_minor),
        gateway_tax_minor=gateway_tax_minor,
        gateway_tax=format_minor_to_decimal_str(gateway_tax_minor),
        gross_settlements_minor=gross_settlements_minor,
        gross_settlements=format_minor_to_decimal_str(gross_settlements_minor),
        net_settlements_minor=net_settlements_minor,
        net_settlements=format_minor_to_decimal_str(net_settlements_minor),
        unsettled_captured_minor=unsettled_captured_minor,
        unsettled_captured=format_minor_to_decimal_str(unsettled_captured_minor),
        reconciliation_exceptions_count=recon_exceptions_count,
        active_payment_links_count=active_payment_links_count,
        paid_payment_links_count=paid_payment_links_count,
        calculation_notes={
            "gross_captured": "Sum of CAPTURED payment_transactions.amount_minor; never treated as bank-settled cash.",
            "total_refunded": "Sum of PROCESSED payment_refunds.amount_minor.",
            "net_settlements": "Sum of PROCESSED payment_settlements.net_amount_minor from provider sync or verified statement imports.",
            "unsettled_captured": "Sum of CAPTURED transactions with no linked PROCESSED settlement item.",
        },
    )


def export_financial_report_csv(
    db: Session,
    org_ctx: OrgContext,
    *,
    currency: str = "INR",
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
) -> str:
    org_id = org_ctx.organisation.id
    overview = get_financial_overview(
        db, org_id, currency=currency, from_dt=from_dt, to_dt=to_dt
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["section", "record_id", "status", "currency", "amount_minor", "amount", "fee_minor", "tax_minor", "net_minor", "timestamp"])
    writer.writerow(["SUMMARY_CAPTURED", "GROSS_CAPTURED", "CAPTURED", overview.currency, overview.gross_captured_minor, overview.gross_captured, 0, 0, overview.gross_captured_minor, ""])
    writer.writerow(["SUMMARY_REFUNDED", "TOTAL_REFUNDED", "PROCESSED", overview.currency, overview.total_refunded_minor, overview.total_refunded, 0, 0, -overview.total_refunded_minor, ""])
    writer.writerow(["SUMMARY_SETTLED", "NET_SETTLEMENTS", "PROCESSED", overview.currency, overview.gross_settlements_minor, overview.gross_settlements, overview.gateway_fees_minor, overview.gateway_tax_minor, overview.net_settlements_minor, ""])
    writer.writerow(["SUMMARY_UNSETTLED", "UNSETTLED_CAPTURED", "CAPTURED", overview.currency, overview.unsettled_captured_minor, overview.unsettled_captured, 0, 0, overview.unsettled_captured_minor, ""])

    txns = list(
        db.scalars(
            select(PaymentTransaction)
            .where(
                PaymentTransaction.organisation_id == org_id,
                PaymentTransaction.currency == overview.currency,
            )
            .order_by(PaymentTransaction.id.desc())
            .limit(500)
        ).all()
    )
    for t in txns:
        writer.writerow([
            "PAYMENT_TXN",
            _csv_escape(t.provider_payment_id),
            _csv_escape(t.status),
            t.currency,
            t.amount_minor,
            format_minor_to_decimal_str(t.amount_minor),
            0,
            0,
            t.amount_minor,
            t.created_at.isoformat(),
        ])

    refunds = list(
        db.scalars(
            select(PaymentRefund)
            .where(
                PaymentRefund.organisation_id == org_id,
                PaymentRefund.currency == overview.currency,
            )
            .order_by(PaymentRefund.id.desc())
            .limit(500)
        ).all()
    )
    for r in refunds:
        writer.writerow([
            "REFUND",
            _csv_escape(r.provider_refund_id or f"LOCAL-RFND-{r.id}"),
            _csv_escape(r.status),
            r.currency,
            r.amount_minor,
            format_minor_to_decimal_str(r.amount_minor),
            0,
            0,
            -r.amount_minor,
            r.created_at.isoformat(),
        ])

    settlements = list(
        db.scalars(
            select(PaymentSettlement)
            .where(
                PaymentSettlement.organisation_id == org_id,
                PaymentSettlement.currency == overview.currency,
            )
            .order_by(PaymentSettlement.id.desc())
            .limit(200)
        ).all()
    )
    for s in settlements:
        writer.writerow([
            "SETTLEMENT",
            _csv_escape(s.provider_settlement_id),
            _csv_escape(s.status),
            s.currency,
            s.gross_amount_minor,
            format_minor_to_decimal_str(s.gross_amount_minor),
            s.fee_minor,
            s.tax_minor,
            s.net_amount_minor,
            (s.settled_at or s.created_at).isoformat(),
        ])

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="financial_report_exported",
            entity_name="payment_transactions",
            entity_id=str(org_id),
            details={"currency": overview.currency},
        )
    )
    db.commit()
    return buf.getvalue()
