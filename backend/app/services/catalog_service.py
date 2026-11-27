from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext
from app.models.retail import CommerceProduct, InventoryBalance
from app.models.rossmann import AuditLog
from app.schemas.retail import (
    CommerceProductCreate,
    CommerceProductOut,
    CommerceProductUpdate,
    InventorySummaryOut,
    format_minor_to_decimal_str,
)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _inventory_map(
    db: Session, organisation_id: int, product_ids: list[int]
) -> dict[int, InventorySummaryOut]:
    if not product_ids:
        return {}
    rows = db.execute(
        select(
            InventoryBalance.product_id,
            func.coalesce(func.sum(InventoryBalance.quantity), 0).label("on_hand"),
            func.coalesce(func.sum(InventoryBalance.reserved_quantity), 0).label(
                "reserved"
            ),
            func.coalesce(func.sum(InventoryBalance.damaged_quantity), 0).label(
                "damaged"
            ),
            func.min(InventoryBalance.low_stock_threshold).label("threshold"),
        )
        .where(
            InventoryBalance.organisation_id == organisation_id,
            InventoryBalance.product_id.in_(product_ids),
        )
        .group_by(InventoryBalance.product_id)
    ).all()

    result: dict[int, InventorySummaryOut] = {}
    for row in rows:
        on_hand = int(row.on_hand or 0)
        reserved = int(row.reserved or 0)
        damaged = int(row.damaged or 0)
        result[row.product_id] = InventorySummaryOut(
            on_hand=on_hand,
            reserved=reserved,
            damaged=damaged,
            sold=0,
            available=max(0, on_hand - reserved),
            low_stock_threshold=int(row.threshold) if row.threshold is not None else 5,
        )
    return result


def to_product_out(
    product: CommerceProduct, summary: InventorySummaryOut | None = None
) -> CommerceProductOut:
    inv = summary or InventorySummaryOut(
        on_hand=0,
        reserved=0,
        damaged=0,
        sold=0,
        available=0,
        low_stock_threshold=product.reorder_threshold,
    )
    return CommerceProductOut(
        id=str(product.id),
        organisation_id=product.organisation_id,
        sku=product.sku,
        barcode=product.barcode,
        name=product.name,
        brand=product.brand,
        description=product.description,
        category=product.category,
        status=product.status,
        cost_price_minor=product.cost_price_minor,
        cost_price=(
            format_minor_to_decimal_str(product.cost_price_minor)
            if product.cost_price_minor is not None
            else None
        ),
        price_minor=product.price_minor,
        price=format_minor_to_decimal_str(product.price_minor),
        currency=product.currency,
        tax_rate_bps=product.tax_rate_bps,
        tax_name=product.tax_name,
        hsn_sac_code=product.hsn_sac_code,
        tax_inclusive=product.tax_inclusive,
        unit=product.unit,
        variants=product.variants_json,
        reorder_threshold=product.reorder_threshold,
        image_url=product.image_url,
        metadata=product.metadata_json,
        inventory=inv,
        origin="real",
        source="manual",
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def create_product(
    db: Session, org_ctx: OrgContext, payload: CommerceProductCreate
) -> CommerceProductOut:
    org_id = org_ctx.organisation.id
    product = CommerceProduct(
        organisation_id=org_id,
        sku=payload.sku,
        barcode=payload.barcode,
        name=payload.name,
        brand=payload.brand,
        description=payload.description,
        category=payload.category,
        status=payload.status,
        cost_price_minor=payload.cost_price_minor,
        price_minor=payload.price_minor,
        currency=payload.currency,
        tax_rate_bps=payload.tax_rate_bps,
        tax_name=payload.tax_name,
        hsn_sac_code=payload.hsn_sac_code,
        tax_inclusive=payload.tax_inclusive,
        unit=payload.unit,
        variants_json=payload.variants,
        reorder_threshold=payload.reorder_threshold,
        image_url=payload.image_url,
        metadata_json=payload.metadata,
    )
    try:
        db.add(product)
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A product with this SKU already exists in this organisation.",
        ) from exc

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="commerce_product_created",
            entity_name="commerce_products",
            entity_id=str(product.id),
            details={
                "sku": product.sku,
                "name": product.name,
                "price_minor": product.price_minor,
                "currency": product.currency,
                "status": "success",
            },
        )
    )
    db.commit()
    db.refresh(product)
    return to_product_out(product)


def list_products(
    db: Session,
    org_id: int,
    *,
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    status: str | None = None,
    category: str | None = None,
) -> dict:
    query = select(CommerceProduct).where(CommerceProduct.organisation_id == org_id)
    count_query = select(func.count(CommerceProduct.id)).where(
        CommerceProduct.organisation_id == org_id
    )

    if status:
        query = query.where(CommerceProduct.status == status)
        count_query = count_query.where(CommerceProduct.status == status)
    if category:
        query = query.where(CommerceProduct.category == category)
        count_query = count_query.where(CommerceProduct.category == category)
    if search:
        pattern = f"%{_escape_like(search.strip())}%"
        filt = (
            CommerceProduct.sku.ilike(pattern, escape="\\")
            | CommerceProduct.barcode.ilike(pattern, escape="\\")
            | CommerceProduct.name.ilike(pattern, escape="\\")
            | CommerceProduct.brand.ilike(pattern, escape="\\")
            | CommerceProduct.category.ilike(pattern, escape="\\")
        )
        query = query.where(filt)
        count_query = count_query.where(filt)

    total = db.scalar(count_query) or 0
    offset = (page - 1) * page_size
    rows = db.scalars(
        query.order_by(CommerceProduct.id.desc()).offset(offset).limit(page_size)
    ).all()

    inv_map = _inventory_map(db, org_id, [p.id for p in rows])
    items = [to_product_out(p, inv_map.get(p.id)) for p in rows]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_product(db: Session, org_id: int, product_id: int) -> CommerceProductOut:
    product = db.scalar(
        select(CommerceProduct).where(
            CommerceProduct.id == product_id,
            CommerceProduct.organisation_id == org_id,
        )
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    inv_map = _inventory_map(db, org_id, [product.id])
    return to_product_out(product, inv_map.get(product.id))


def update_product(
    db: Session,
    org_ctx: OrgContext,
    product_id: int,
    payload: CommerceProductUpdate,
) -> CommerceProductOut:
    org_id = org_ctx.organisation.id
    product = db.scalar(
        select(CommerceProduct)
        .where(
            CommerceProduct.id == product_id,
            CommerceProduct.organisation_id == org_id,
        )
        .with_for_update()
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")

    changes: dict = {}
    for field in (
        "sku",
        "barcode",
        "name",
        "brand",
        "description",
        "category",
        "status",
        "cost_price_minor",
        "price_minor",
        "currency",
        "tax_rate_bps",
        "tax_name",
        "reorder_threshold",
        "image_url",
    ):
        val = getattr(payload, field)
        if val is not None and getattr(product, field) != val:
            changes[field] = {"from": getattr(product, field), "to": val}
            setattr(product, field, val)

    if payload.metadata is not None:
        product.metadata_json = payload.metadata
        changes["metadata"] = "updated"

    product.updated_at = datetime.now(timezone.utc)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A product with this SKU already exists in this organisation.",
        ) from exc

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="commerce_product_updated",
            entity_name="commerce_products",
            entity_id=str(product.id),
            details={"changes": changes, "status": "success"},
        )
    )
    db.commit()
    db.refresh(product)
    inv_map = _inventory_map(db, org_id, [product.id])
    return to_product_out(product, inv_map.get(product.id))
