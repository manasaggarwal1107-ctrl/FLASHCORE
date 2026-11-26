from datetime import datetime, timezone
from decimal import Decimal
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_roles
from app.core.database import get_db

router = APIRouter(
    prefix="/api/simulations",
    tags=["Retail Simulation Engine"],
)


# ---------------- REQUEST SCHEMAS ----------------

class RunCreate(BaseModel):
    run_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    configuration: dict = Field(default_factory=dict)


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class InventoryCreate(BaseModel):
    store_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    quantity: int = Field(ge=0)


class InventoryAdjustment(BaseModel):
    quantity_delta: int
    reason: str = Field(min_length=3, max_length=500)

class FlashSaleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    ends_at: datetime


class SaleProductCreate(BaseModel):
    inventory_id: int = Field(gt=0)
    sale_price: Decimal = Field(ge=0)
    stock_limit: int = Field(gt=0)


class PurchaseCreate(BaseModel):
    customer_ref: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=255)
    quantity: int = Field(gt=0)


# ---------------- HELPERS ----------------

def commit_or_conflict(db: Session):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Database constraint conflict. Check duplicate IDs, SKU, stock or references.",
        ) from exc


def fetch_one(db: Session, query: str, params: dict):
    return db.execute(text(query), params).mappings().first()


def write_audit(
    db: Session,
    action: str,
    entity_name: str,
    entity_id,
    details: dict,
    actor_type: str = "system",
    actor_ref: str | None = None,
):
    db.execute(
        text("""
            INSERT INTO audit_logs
                (actor_type, actor_ref, action, entity_name, entity_id, details)
            VALUES
                (:actor_type, :actor_ref, :action, :entity_name,
                 :entity_id, CAST(:details AS JSONB))
        """),
        {
            "actor_type": actor_type,
            "actor_ref": actor_ref,
            "action": action,
            "entity_name": entity_name,
            "entity_id": str(entity_id),
            "details": json.dumps(details),
        },
    )


def write_transaction(
    db: Session,
    run_id: int,
    action: str,
    outcome: dict,
    attempt_id: int | None = None,
):
    db.execute(
        text("""
            INSERT INTO transactions_log
                (simulation_run_id, purchase_attempt_id, action, outcome)
            VALUES
                (:run_id, :attempt_id, :action, CAST(:outcome AS JSONB))
        """),
        {
            "run_id": run_id,
            "attempt_id": attempt_id,
            "action": action,
            "outcome": json.dumps(outcome),
        },
    )


def require_aware(dt: datetime):
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise HTTPException(
            status_code=422,
            detail="Datetime values must include a timezone.",
        )


# ---------------- SIMULATION RUNS ----------------

@router.post("/runs", status_code=201, dependencies=[Depends(require_roles('admin', 'operator'))])
def create_run(payload: RunCreate, db: Session = Depends(get_db)):
    row = fetch_one(
        db,
        """
        INSERT INTO simulation_runs
            (run_name, description, configuration, status)
        VALUES
            (:name, :description, CAST(:configuration AS JSONB), 'created')
        RETURNING *
        """,
        {
            "name": payload.run_name,
            "description": payload.description,
            "configuration": json.dumps(payload.configuration),
        },
    )

    write_audit(
        db, "simulation_created", "simulation_runs",
        row["id"], {"run_name": payload.run_name},
    )
    commit_or_conflict(db)
    return dict(row)


@router.get("/runs", dependencies=[Depends(require_roles('admin', 'analyst', 'operator'))])
def list_runs(db: Session = Depends(get_db)):
    rows = db.execute(
        text("SELECT * FROM simulation_runs ORDER BY created_at DESC")
    ).mappings().all()

    return [dict(row) for row in rows]


@router.get("/runs/{run_id}/summary", dependencies=[Depends(require_roles('admin', 'analyst', 'operator'))])
def run_summary(run_id: int, db: Session = Depends(get_db)):
    run = fetch_one(
        db,
        "SELECT * FROM simulation_runs WHERE id=:id",
        {"id": run_id},
    )

    if not run:
        raise HTTPException(404, "Simulation run not found")

    purchases = fetch_one(
        db,
        """
        SELECT
            COUNT(*) AS total_attempts,
            COUNT(*) FILTER (WHERE status='success') AS successful,
            COUNT(*) FILTER (WHERE status='rejected') AS rejected,
            COUNT(*) FILTER (WHERE status='failed') AS failed,
            COALESCE(SUM(quantity) FILTER (WHERE status='success'), 0)
                AS units_sold
        FROM purchase_attempts
        WHERE simulation_run_id=:id
        """,
        {"id": run_id},
    )

    sales = db.execute(
        text("""
            SELECT
                fs.id AS flash_sale_id,
                fs.title,
                fs.status,
                COALESCE(SUM(fsp.sold_quantity), 0) AS units_sold,
                COALESCE(SUM(fsp.stock_limit), 0) AS allocated_stock
            FROM flash_sales fs
            LEFT JOIN flash_sale_products fsp
                ON fsp.flash_sale_id = fs.id
            WHERE fs.simulation_run_id = :id
            GROUP BY fs.id, fs.title, fs.status
            ORDER BY fs.id
        """),
        {"id": run_id},
    ).mappings().all()

    return {
        "run": dict(run),
        "purchases": dict(purchases),
        "flash_sales": [dict(row) for row in sales],
    }


# ---------------- PRODUCTS ----------------

@router.post("/products", status_code=201, dependencies=[Depends(require_roles('admin', 'operator'))])
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    try:
        row = fetch_one(
            db,
            """
            INSERT INTO simulation_products (sku, name, description)
            VALUES (:sku, :name, :description)
            RETURNING *
            """,
            {
                "sku": payload.sku,
                "name": payload.name,
                "description": payload.description,
            },
        )
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Database constraint conflict. SKU may already exist.",
        ) from exc

    write_audit(
        db, "product_created", "simulation_products",
        row["id"], {"sku": payload.sku, "name": payload.name},
    )
    commit_or_conflict(db)
    return dict(row)

@router.get("/products", dependencies=[Depends(require_roles('admin', 'analyst', 'operator'))])
def list_products(db: Session = Depends(get_db)):
    rows = db.execute(
        text("SELECT * FROM simulation_products ORDER BY id")
    ).mappings().all()

    return [dict(row) for row in rows]


# ---------------- INVENTORY ----------------

@router.post("/inventory", status_code=201, dependencies=[Depends(require_roles('admin', 'operator'))])
def create_inventory(
    payload: InventoryCreate,
    db: Session = Depends(get_db),
):
    try:
        row = fetch_one(
            db,
            """
            INSERT INTO simulation_inventory
                (store_id, product_id, quantity, reserved_quantity)
            VALUES
                (:store_id, :product_id, :quantity, 0)
            RETURNING *
            """,
            {
                "store_id": payload.store_id,
                "product_id": payload.product_id,
                "quantity": payload.quantity,
            },
        )
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Database constraint conflict. Check that the store and "
                "product exist and inventory is not already registered."
            ),
        ) from exc

    write_audit(
        db, "inventory_created", "simulation_inventory",
        row["id"], {"quantity": payload.quantity},
    )
    commit_or_conflict(db)
    return dict(row)


@router.get("/inventory", dependencies=[Depends(require_roles('admin', 'analyst', 'operator'))])
def list_inventory(db: Session = Depends(get_db)):
    rows = db.execute(
        text("""
            SELECT
                i.*,
                p.sku,
                p.name AS product_name
            FROM simulation_inventory i
            JOIN simulation_products p ON p.id = i.product_id
            ORDER BY i.id
        """)
    ).mappings().all()

    return [dict(row) for row in rows]


@router.post(
    "/inventory/{inventory_id}/adjust",
    dependencies=[Depends(require_roles('admin', 'operator'))],
)
def adjust_inventory(
    inventory_id: int,
    payload: InventoryAdjustment,
    db: Session = Depends(get_db),
):
    if payload.quantity_delta == 0:
        raise HTTPException(422, "Quantity adjustment cannot be zero")

    inventory = fetch_one(
        db,
        """
        SELECT *
        FROM simulation_inventory
        WHERE id = :id
        FOR UPDATE
        """,
        {"id": inventory_id},
    )

    if not inventory:
        raise HTTPException(404, "Inventory record not found")

    old_quantity = inventory["quantity"]
    reserved_quantity = inventory["reserved_quantity"]
    new_quantity = old_quantity + payload.quantity_delta

    if new_quantity < reserved_quantity:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Adjustment would reduce physical stock below reserved stock",
                "current_quantity": old_quantity,
                "reserved_quantity": reserved_quantity,
                "requested_quantity": new_quantity,
            },
        )

    updated = fetch_one(
        db,
        """
        UPDATE simulation_inventory
        SET quantity = :quantity,
            updated_at = NOW()
        WHERE id = :id
        RETURNING *
        """,
        {
            "quantity": new_quantity,
            "id": inventory_id,
        },
    )

    write_audit(
        db,
        "inventory_adjusted",
        "simulation_inventory",
        inventory_id,
        {
            "quantity_before": old_quantity,
            "quantity_delta": payload.quantity_delta,
            "quantity_after": new_quantity,
            "reserved_quantity": reserved_quantity,
            "reason": payload.reason,
        },
    )

    commit_or_conflict(db)

    return {
        "inventory_id": inventory_id,
        "quantity_before": old_quantity,
        "quantity_delta": payload.quantity_delta,
        "quantity_after": updated["quantity"],
        "reserved_quantity": updated["reserved_quantity"],
        "available_quantity": (
            updated["quantity"] - updated["reserved_quantity"]
        ),
        "updated_at": updated["updated_at"],
    }

# ---------------- FLASH SALES ----------------

@router.post("/runs/{run_id}/flash-sales", status_code=201, dependencies=[Depends(require_roles('admin', 'operator'))])
def create_flash_sale(
    run_id: int,
    payload: FlashSaleCreate,
    db: Session = Depends(get_db),
):
    require_aware(payload.starts_at)
    require_aware(payload.ends_at)

    if payload.ends_at <= payload.starts_at:
        raise HTTPException(422, "ends_at must be after starts_at")

    if not fetch_one(
        db,
        "SELECT id FROM simulation_runs WHERE id=:id",
        {"id": run_id},
    ):
        raise HTTPException(404, "Simulation run not found")

    row = fetch_one(
        db,
        """
        INSERT INTO flash_sales
            (simulation_run_id, title, starts_at, ends_at, status)
        VALUES
            (:run_id, :title, :starts_at, :ends_at, 'draft')
        RETURNING *
        """,
        {
            "run_id": run_id,
            "title": payload.title,
            "starts_at": payload.starts_at,
            "ends_at": payload.ends_at,
        },
    )

    write_audit(
        db, "flash_sale_created", "flash_sales",
        row["id"], {"title": payload.title},
    )
    commit_or_conflict(db)
    return dict(row)


@router.post("/flash-sales/{sale_id}/activate", dependencies=[Depends(require_roles('admin', 'operator'))])
def activate_flash_sale(
    sale_id: int,
    db: Session = Depends(get_db),
):
    sale = fetch_one(
        db,
        "SELECT * FROM flash_sales WHERE id=:id FOR UPDATE",
        {"id": sale_id},
    )

    if not sale:
        raise HTTPException(404, "Flash sale not found")

    if sale["status"] not in ("draft", "scheduled", "active"):
        raise HTTPException(409, "Flash sale cannot be activated")

    now = datetime.now(timezone.utc)

    if now >= sale["ends_at"]:
        raise HTTPException(409, "Flash sale has already expired")

    new_status = (
        "scheduled" if now < sale["starts_at"] else "active"
    )

    row = fetch_one(
        db,
        """
        UPDATE flash_sales
        SET status=:status
        WHERE id=:id
        RETURNING *
        """,
        {"id": sale_id, "status": new_status},
    )

    write_audit(
        db, "flash_sale_activated", "flash_sales",
        sale_id, {"status": new_status},
    )
    commit_or_conflict(db)
    return dict(row)


# ---------------- STOCK ALLOCATION ----------------

@router.post("/flash-sales/{sale_id}/products", status_code=201, dependencies=[Depends(require_roles('admin', 'operator'))])
def allocate_sale_stock(
    sale_id: int,
    payload: SaleProductCreate,
    db: Session = Depends(get_db),
):
    sale = fetch_one(
        db,
        "SELECT * FROM flash_sales WHERE id=:id FOR UPDATE",
        {"id": sale_id},
    )

    if not sale:
        raise HTTPException(404, "Flash sale not found")

    if sale["status"] not in ("draft", "scheduled", "active"):
        raise HTTPException(409, "Flash sale is not accepting allocations")

    inventory = fetch_one(
        db,
        "SELECT * FROM simulation_inventory WHERE id=:id FOR UPDATE",
        {"id": payload.inventory_id},
    )

    if not inventory:
        raise HTTPException(404, "Inventory record not found")

    available = inventory["quantity"] - inventory["reserved_quantity"]

    if payload.stock_limit > available:
        raise HTTPException(
            409,
            detail={
                "message": "Insufficient available inventory",
                "available": available,
                "requested": payload.stock_limit,
            },
        )

    db.execute(
        text("""
            UPDATE simulation_inventory
            SET reserved_quantity = reserved_quantity + :stock,
                updated_at = NOW()
            WHERE id = :id
        """),
        {"stock": payload.stock_limit, "id": payload.inventory_id},
    )

    row = fetch_one(
        db,
        """
        INSERT INTO flash_sale_products
            (flash_sale_id, inventory_id, sale_price, stock_limit)
        VALUES
            (:sale_id, :inventory_id, :price, :stock)
        RETURNING *
        """,
        {
            "sale_id": sale_id,
            "inventory_id": payload.inventory_id,
            "price": payload.sale_price,
            "stock": payload.stock_limit,
        },
    )

    write_audit(
        db, "stock_allocated", "flash_sale_products",
        row["id"],
        {
            "inventory_id": payload.inventory_id,
            "stock_limit": payload.stock_limit,
        },
    )

    commit_or_conflict(db)
    return dict(row)


# ---------------- TRANSACTIONAL PURCHASE ENGINE ----------------

@router.post("/flash-sale-products/{sale_product_id}/purchase", dependencies=[Depends(require_roles('admin', 'operator'))])
def purchase(
    sale_product_id: int,
    payload: PurchaseCreate,
    db: Session = Depends(get_db),
):
    # Fast idempotency check.
    existing = fetch_one(
        db,
        """
        SELECT * FROM purchase_attempts
        WHERE idempotency_key=:key
        """,
        {"key": payload.idempotency_key},
    )

    if existing:
        if (
            existing["customer_ref"] != payload.customer_ref
            or existing["flash_sale_product_id"] != sale_product_id
            or existing["quantity"] != payload.quantity
        ):
            raise HTTPException(
                409,
                "Idempotency key was already used with different purchase data",
            )

        return {"duplicate": True, "attempt": dict(existing)}

    # Lock the sale product: concurrent purchases for this product
    # must be processed one at a time.
    sale_product = fetch_one(
        db,
        """
        SELECT * FROM flash_sale_products
        WHERE id=:id
        FOR UPDATE
        """,
        {"id": sale_product_id},
    )

    if not sale_product:
        raise HTTPException(404, "Flash sale product not found")

    sale = fetch_one(
        db,
        "SELECT * FROM flash_sales WHERE id=:id",
        {"id": sale_product["flash_sale_id"]},
    )

    inventory = fetch_one(
        db,
        "SELECT * FROM simulation_inventory WHERE id=:id FOR UPDATE",
        {"id": sale_product["inventory_id"]},
    )

    if not inventory:
        raise HTTPException(409, "Associated inventory record is missing")

    now = datetime.now(timezone.utc)

    # A scheduled sale becomes active automatically once its
    # scheduled start time is reached.
    sale_status = sale["status"]

    if sale_status == "scheduled" and sale["starts_at"] <= now < sale["ends_at"]:
        db.execute(
            text("UPDATE flash_sales SET status='active' WHERE id=:id"),
            {"id": sale["id"]},
        )
        sale_status = "active"

    failure = None

    if sale_status != "active":
        failure = "Flash sale is not active"
    elif now < sale["starts_at"] or now >= sale["ends_at"]:
        failure = "Flash sale is outside its active time window"
    elif sale_product["sold_quantity"] + payload.quantity > sale_product["stock_limit"]:
        failure = "Flash sale stock limit exceeded"
    elif inventory["quantity"] < payload.quantity:
        failure = "Insufficient physical inventory"
    elif inventory["reserved_quantity"] < payload.quantity:
        failure = "Insufficient reserved inventory"
    else:
        successful = fetch_one(
            db,
            """
            SELECT id FROM purchase_attempts
            WHERE customer_ref=:customer
              AND flash_sale_product_id=:product
              AND status='success'
            """,
            {
                "customer": payload.customer_ref,
                "product": sale_product_id,
            },
        )

        if successful:
            failure = "Customer has already purchased this flash-sale product"

    attempt_status = "rejected" if failure else "success"

    try:
        attempt = fetch_one(
            db,
            """
            INSERT INTO purchase_attempts
                (simulation_run_id, flash_sale_product_id, customer_ref,
                 idempotency_key, quantity, status, failure_reason)
            VALUES
                (:run_id, :product_id, :customer, :key, :quantity,
                 :status, :reason)
            RETURNING *
            """,
            {
                "run_id": sale["simulation_run_id"],
                "product_id": sale_product_id,
                "customer": payload.customer_ref,
                "key": payload.idempotency_key,
                "quantity": payload.quantity,
                "status": attempt_status,
                "reason": failure,
            },
        )
    except IntegrityError as exc:
        db.rollback()
        existing = fetch_one(
            db,
            "SELECT * FROM purchase_attempts WHERE idempotency_key=:key",
            {"key": payload.idempotency_key},
        )
        if existing:
            if (
                existing["customer_ref"] == payload.customer_ref
                and existing["flash_sale_product_id"] == sale_product_id
                and existing["quantity"] == payload.quantity
            ):
                return {"duplicate": True, "attempt": dict(existing)}
            raise HTTPException(
                409, "Idempotency key was used by another request"
            ) from exc
        raise HTTPException(
            409, "Purchase conflicts with a database constraint"
        ) from exc

    if not failure:
        # All stock changes occur within the same database transaction.
        db.execute(
            text("""
                UPDATE simulation_inventory
                SET quantity = quantity - :quantity,
                    reserved_quantity = reserved_quantity - :quantity,
                    updated_at = NOW()
                WHERE id = :id
            """),
            {"quantity": payload.quantity, "id": inventory["id"]},
        )

        db.execute(
            text("""
                UPDATE flash_sale_products
                SET sold_quantity = sold_quantity + :quantity
                WHERE id = :id
            """),
            {"quantity": payload.quantity, "id": sale_product_id},
        )

    outcome = {
        "attempt_id": attempt["id"],
        "customer_ref": payload.customer_ref,
        "quantity": payload.quantity,
        "status": attempt_status,
        "reason": failure,
    }

    write_transaction(
        db,
        sale["simulation_run_id"],
        "purchase_" + attempt_status,
        outcome,
        attempt["id"],
    )

    write_audit(
        db,
        "purchase_" + attempt_status,
        "purchase_attempts",
        attempt["id"],
        outcome,
        actor_type="customer",
        actor_ref=payload.customer_ref,
    )

    # Commit rejected attempts too, so they remain auditable.
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        # Another request may have committed the same idempotency key
        # while this request was waiting for the row lock.
        existing = fetch_one(
            db,
            "SELECT * FROM purchase_attempts WHERE idempotency_key=:key",
            {"key": payload.idempotency_key},
        )

        if existing:
            if (
                existing["customer_ref"] == payload.customer_ref
                and existing["flash_sale_product_id"] == sale_product_id
                and existing["quantity"] == payload.quantity
            ):
                return {"duplicate": True, "attempt": dict(existing)}

            raise HTTPException(
                409, "Idempotency key was used by another request"
            ) from exc

        raise HTTPException(
            409, "Purchase conflicts with a database constraint"
        ) from exc

    return {
        "success": not bool(failure),
        "attempt": dict(attempt),
        "message": failure or "Purchase completed successfully",
    }


# ---------------- SIMULATION ANALYTICS ----------------

def analytics_period(from_date, to_date):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(400, "from cannot be after to")
    return from_date, to_date


def purchase_analytics_series(db: Session, from_date, to_date, metric: str):
    numerator = {
        "conversion": "successful",
        "failure": "failed",
    }.get(metric)

    if numerator is None:
        raise ValueError("Unsupported analytics metric")

    rows = db.execute(
        text(f"""
            WITH daily AS (
                SELECT
                    created_at::date AS period,
                    COUNT(*) FILTER (
                        WHERE status IN ('success', 'rejected', 'failed')
                    ) AS completed,
                    COUNT(*) FILTER (
                        WHERE status = 'success'
                    ) AS successful,
                    COUNT(*) FILTER (
                        WHERE status = 'failed'
                    ) AS failed
                FROM purchase_attempts
                WHERE (CAST(:start AS TIMESTAMPTZ) IS NULL OR created_at >= CAST(:start AS TIMESTAMPTZ))
                  AND (CAST(:end AS TIMESTAMPTZ) IS NULL OR created_at <= CAST(:end AS TIMESTAMPTZ))
                GROUP BY created_at::date
            )
            SELECT
                period,
                CASE
                    WHEN completed = 0 THEN 0
                    ELSE {numerator}::double precision / completed
                END AS value
            FROM daily
            ORDER BY period
        """),
        {"start": from_date, "end": to_date},
    ).mappings().all()

    return {
        "points": [
            {"t": row["period"].isoformat(), "value": row["value"]}
            for row in rows
        ],
        "period_start": rows[0]["period"].isoformat() if rows else None,
        "period_end": rows[-1]["period"].isoformat() if rows else None,
        "origin": "simulation",
    }


@router.get("/analytics/conversion", dependencies=[Depends(require_roles('admin', 'analyst'))])
def analytics_conversion(
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    start, end = analytics_period(from_date, to_date)
    return purchase_analytics_series(db, start, end, "conversion")


@router.get("/analytics/failure-rates", dependencies=[Depends(require_roles('admin', 'analyst'))])
def analytics_failure_rates(
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    start, end = analytics_period(from_date, to_date)
    return purchase_analytics_series(db, start, end, "failure")



@router.get("/analytics/inventory-utilisation", dependencies=[Depends(require_roles('admin', 'analyst'))])
def analytics_inventory_utilisation(
    db: Session = Depends(get_db),
):
    row = db.execute(
        text("""
            WITH initial_stock AS (
                SELECT DISTINCT ON (entity_id)
                    entity_id::bigint AS inventory_id,
                    (details->>'quantity')::integer AS initial_quantity
                FROM audit_logs
                WHERE entity_name = 'simulation_inventory'
                  AND action = 'inventory_created'
                ORDER BY entity_id, created_at ASC
            ),
            totals AS (
                SELECT
                    COUNT(i.id) AS total_rows,
                    COUNT(s.inventory_id) AS audited_rows,
                    COALESCE(SUM(s.initial_quantity), 0) AS initial_stock,
                    COALESCE(SUM(i.quantity), 0) AS current_stock,
                    COALESCE(SUM(i.reserved_quantity), 0) AS reserved_stock
                FROM simulation_inventory i
                LEFT JOIN initial_stock s
                    ON s.inventory_id = i.id
            )
            SELECT
                *,
                CURRENT_TIMESTAMP AS snapshot_at
            FROM totals
        """)
    ).mappings().one()

    if row["total_rows"] == 0:
        return {
            "points": [],
            "period_start": None,
            "period_end": None,
            "origin": "simulation",
        }

    if row["total_rows"] != row["audited_rows"]:
        raise HTTPException(
            status_code=409,
            detail="Inventory utilisation unavailable: some inventory rows have no initial-stock audit record.",
        )

    initial = row["initial_stock"]
    current = row["current_stock"]
    reserved = row["reserved_stock"]

    if initial <= 0:
        raise HTTPException(
            status_code=409,
            detail="Inventory utilisation unavailable: initial stock must be greater than zero.",
        )

    if current < 0 or reserved < 0 or reserved > current:
        raise HTTPException(
            status_code=409,
            detail="Inventory utilisation unavailable: inconsistent inventory quantities.",
        )

    sold = initial - current

    if sold < 0:
        raise HTTPException(
            status_code=409,
            detail="Inventory utilisation unavailable: current stock exceeds audited initial stock.",
        )

    utilisation = (sold + reserved) / initial
    snapshot = row["snapshot_at"].isoformat()

    return {
        "points": [
            {
                "t": snapshot,
                "value": utilisation,
            }
        ],
        "period_start": snapshot,
        "period_end": snapshot,
        "origin": "simulation",
    }



@router.get("/analytics/flash-sale-performance", dependencies=[Depends(require_roles('admin', 'analyst'))])
def analytics_flash_sale_performance(
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    start, end = analytics_period(from_date, to_date)

    rows = db.execute(
        text("""
            SELECT
                p.created_at::date AS period,
                COALESCE(SUM(p.quantity), 0)::bigint AS value
            FROM purchase_attempts p
            INNER JOIN flash_sale_products fsp
                ON fsp.id = p.flash_sale_product_id
            INNER JOIN flash_sales fs
                ON fs.id = fsp.flash_sale_id
            WHERE p.status = 'success'
              AND (CAST(:start AS TIMESTAMPTZ) IS NULL OR p.created_at >= CAST(:start AS TIMESTAMPTZ))
              AND (CAST(:end AS TIMESTAMPTZ) IS NULL OR p.created_at <= CAST(:end AS TIMESTAMPTZ))
            GROUP BY p.created_at::date
            ORDER BY period
        """),
        {"start": start, "end": end},
    ).mappings().all()

    return {
        "points": [
            {
                "t": row["period"].isoformat(),
                "value": int(row["value"]),
            }
            for row in rows
        ],
        "period_start": rows[0]["period"].isoformat() if rows else None,
        "period_end": rows[-1]["period"].isoformat() if rows else None,
        "origin": "simulation",
    }

# ---------------- TRANSACTION MONITOR READ API ----------------

# ---------------- TRANSACTION MONITOR READ API ----------------

def _transaction_monitor_item(row):
    status_map = {
        "success": "succeeded",
        "failed": "failed",
        "rejected": "rejected",
    }
    attempt_id = str(row["id"])
    return {
        "id": attempt_id,
        "purchase_attempt_id": attempt_id,
        "order_ref": None,
        "status": status_map.get(row["status"], row["status"]),
        "occurred_at": row["created_at"],
        "duration_ms": None,
        "failure_reason": row["failure_reason"],
        "idempotency_outcome": None,
        "origin": "simulation",
    }


@router.get(
    "/transactions",
    dependencies=[Depends(require_roles("admin", "analyst", "operator"))],
)
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, alias="pageSize", ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    sort: str | None = Query("occurredAt"),
    order: str = Query("desc"),
    status: str | None = Query(None),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    origin: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if order not in ("asc", "desc"):
        raise HTTPException(status_code=422, detail="Invalid sort order")

    sort_columns = {
        "occurredAt": "created_at",
        "status": "status",
        "id": "id",
    }
    sort_column = sort_columns.get(sort or "occurredAt")
    if sort_column is None:
        raise HTTPException(status_code=422, detail="Unsupported sort field")

    where = []
    params = {}

    if status:
        status_map = {
            "succeeded": "success",
            "failed": "failed",
            "rejected": "rejected",
            "pending": "pending",
        }
        if status not in status_map:
            raise HTTPException(status_code=422, detail="Unsupported transaction status")
        where.append("status = :status")
        params["status"] = status_map[status]

    if search:
        where.append(
            "(CAST(id AS TEXT) ILIKE :search OR COALESCE(failure_reason, '') ILIKE :search)"
        )
        params["search"] = "%" + search.strip() + "%"

    if from_date:
        where.append("created_at >= CAST(:from_date AS date)")
        params["from_date"] = from_date

    if to_date:
        where.append("created_at < (CAST(:to_date AS date) + INTERVAL '1 day')")
        params["to_date"] = to_date

    if origin and origin != "simulation":
        where.append("1 = 0")

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    total = db.execute(
        text("SELECT COUNT(*) FROM purchase_attempts" + where_sql),
        params,
    ).scalar_one()

    offset = (page - 1) * page_size
    rows = db.execute(
        text(
            "SELECT id, status, created_at, failure_reason "
            "FROM purchase_attempts"
            + where_sql
            + f" ORDER BY {sort_column} {order.upper()}, id DESC "
            "LIMIT :limit OFFSET :offset"
        ),
        {**params, "limit": page_size, "offset": offset},
    ).mappings().all()

    return {
        "items": [_transaction_monitor_item(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/transactions/{attempt_id}",
    dependencies=[Depends(require_roles("admin", "analyst", "operator"))],
)
def get_transaction(
    attempt_id: int,
    db: Session = Depends(get_db),
):
    row = fetch_one(
        db,
        """
        SELECT id, status, created_at, failure_reason
        FROM purchase_attempts
        WHERE id = :attempt_id
        """,
        {"attempt_id": attempt_id},
    )

    if row is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return _transaction_monitor_item(row)




# ---------------- CONCURRENCY STRATEGIES & OVERVIEW ANALYTICS ----------------

@router.get("/strategies")
def get_strategies():
    return {
        "items": [
            {"id": "atomic_update", "label": "Atomic Update (Optimistic)"},
            {"id": "select_for_update", "label": "Select for Update (Pessimistic)"},
        ]
    }


@router.get(
    "/analytics/purchase-outcomes",
    dependencies=[Depends(require_roles("admin", "analyst"))],
)
def analytics_purchase_outcomes(
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    start, end = analytics_period(from_date, to_date)
    row = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'success') AS successful,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed,
                COUNT(*) FILTER (WHERE status = 'rejected') AS rejected,
                COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                MIN(created_at) AS period_start,
                MAX(created_at) AS period_end
            FROM purchase_attempts
            WHERE (CAST(:start AS TIMESTAMPTZ) IS NULL OR created_at >= CAST(:start AS TIMESTAMPTZ))
              AND (CAST(:end AS TIMESTAMPTZ) IS NULL OR created_at <= CAST(:end AS TIMESTAMPTZ))
        """),
        {"start": start, "end": end},
    ).mappings().one()

    return {
        "successful": int(row["successful"] or 0),
        "failed": int(row["failed"] or 0),
        "rejected": int(row["rejected"] or 0),
        "pending": int(row["pending"] or 0),
        "period_start": row["period_start"].isoformat() if row["period_start"] else None,
        "period_end": row["period_end"].isoformat() if row["period_end"] else None,
        "origin": "simulation",
    }


@router.get(
    "/analytics/inventory-allocation",
    dependencies=[Depends(require_roles("admin", "analyst"))],
)
def analytics_inventory_allocation(db: Session = Depends(get_db)):
    phys = db.execute(
        text("""
            SELECT
                COALESCE(SUM(quantity), 0) AS on_hand,
                COALESCE(SUM(reserved_quantity), 0) AS reserved,
                COALESCE(SUM(quantity - reserved_quantity), 0) AS available
            FROM simulation_inventory
        """)
    ).mappings().one()

    flash = db.execute(
        text("""
            SELECT
                COALESCE(SUM(stock_limit), 0) AS allocated,
                COALESCE(SUM(sold_quantity), 0) AS sold,
                COALESCE(SUM(stock_limit - sold_quantity), 0) AS remaining
            FROM flash_sale_products
        """)
    ).mappings().one()

    sold_phys = db.execute(
        text("SELECT COALESCE(SUM(quantity), 0) FROM purchase_attempts WHERE status = 'success'")
    ).scalar() or 0

    return {
        "physical": {
            "on_hand": int(phys["on_hand"]),
            "reserved": int(phys["reserved"]),
            "sold": int(sold_phys),
            "available": int(phys["available"]),
        },
        "flash_sale": {
            "allocated": int(flash["allocated"]),
            "sold": int(flash["sold"]),
            "remaining": int(flash["remaining"]),
        },
        "origin": "simulation",
    }


@router.get(
    "/analytics/flash-sales-overview",
    dependencies=[Depends(require_roles("admin", "analyst"))],
)
def analytics_flash_sales_overview(db: Session = Depends(get_db)):
    rows = db.execute(
        text("""
            SELECT
                fs.id,
                fs.title AS name,
                fs.status,
                COALESCE(SUM(fsp.stock_limit), 0) AS allocated,
                COALESCE(SUM(fsp.sold_quantity), 0) AS sold,
                COALESCE(SUM(fsp.stock_limit - fsp.sold_quantity), 0) AS remaining
            FROM flash_sales fs
            LEFT JOIN flash_sale_products fsp ON fsp.flash_sale_id = fs.id
            GROUP BY fs.id, fs.title, fs.status
            ORDER BY fs.id DESC
            LIMIT 10
        """)
    ).mappings().all()

    return {
        "items": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "status": r["status"],
                "allocated": int(r["allocated"]),
                "sold": int(r["sold"]),
                "remaining": int(r["remaining"]),
                "origin": "simulation",
            }
            for r in rows
        ]
    }


@router.get(
    "/analytics/activity",
    dependencies=[Depends(require_roles("admin", "analyst"))],
)
def analytics_activity(db: Session = Depends(get_db)):
    rows = db.execute(
        text("""
            SELECT id, action, outcome, created_at
            FROM transactions_log
            ORDER BY created_at DESC
            LIMIT 20
        """)
    ).mappings().all()

    items = []
    for r in rows:
        summary = None
        if r["outcome"] and isinstance(r["outcome"], dict):
            summary = r["outcome"].get("message") or r["outcome"].get("detail")
        if not summary:
            summary = f"Transaction {r['action']}"
        items.append({
            "id": str(r["id"]),
            "occurred_at": r["created_at"].isoformat() if r["created_at"] else None,
            "kind": r["action"],
            "summary": summary,
            "origin": "simulation",
        })

    return {"items": items}
