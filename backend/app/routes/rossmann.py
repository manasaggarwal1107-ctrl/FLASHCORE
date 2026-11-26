
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_roles
from app.core.database import get_db
from app.models.rossmann import Store, DailyStoreSale
from app.schemas.rossmann import (
    StoreOut,
    DailyStoreSaleOut,
    SalesSummary,
)

router = APIRouter(
    prefix="/api/rossmann",
    tags=["Rossmann Historical Data"],
    dependencies=[Depends(require_roles("admin", "analyst"))],
)


@router.get("/stores", response_model=list[StoreOut])
def list_stores(
    store_type: str | None = None,
    assortment: str | None = None,
    limit: int = Query(100, ge=1, le=1115),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(Store)

    if store_type:
        query = query.where(Store.store_type == store_type)

    if assortment:
        query = query.where(Store.assortment == assortment)

    query = query.order_by(Store.store_id).offset(offset).limit(limit)

    return db.scalars(query).all()


@router.get("/stores/{store_id}", response_model=StoreOut)
def get_store(
    store_id: int,
    db: Session = Depends(get_db),
):
    store = db.get(Store, store_id)

    if store is None:
        raise HTTPException(
            status_code=404,
            detail="Store not found",
        )

    return store


@router.get("/sales", response_model=list[DailyStoreSaleOut])
def get_sales(
    store_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date cannot be after end_date",
        )

    query = select(DailyStoreSale)

    if store_id is not None:
        query = query.where(DailyStoreSale.store_id == store_id)

    if start_date:
        query = query.where(
            DailyStoreSale.sales_date >= start_date
        )

    if end_date:
        query = query.where(
            DailyStoreSale.sales_date <= end_date
        )

    query = (
        query.order_by(DailyStoreSale.sales_date.desc())
        .offset(offset)
        .limit(limit)
    )

    return db.scalars(query).all()


@router.get("/sales/summary", response_model=SalesSummary)
def sales_summary(
    store_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date cannot be after end_date",
        )

    query = select(
        func.count(DailyStoreSale.store_id),
        func.sum(DailyStoreSale.sales),
        func.avg(DailyStoreSale.sales),
        func.max(DailyStoreSale.sales),
        func.sum(DailyStoreSale.customers),
    )

    if store_id is not None:
        query = query.where(
            DailyStoreSale.store_id == store_id
        )

    if start_date:
        query = query.where(
            DailyStoreSale.sales_date >= start_date
        )

    if end_date:
        query = query.where(
            DailyStoreSale.sales_date <= end_date
        )

    result = db.execute(query).one()

    return SalesSummary(
        total_records=result[0],
        total_sales=result[1],
        average_sales=float(result[2]) if result[2] is not None else None,
        highest_sales=result[3],
        total_customers=result[4],
    )



# ---------------- HISTORICAL ANALYTICS ----------------

def analytics_period(from_date, to_date):
    start = from_date.date() if from_date else None
    end = to_date.date() if to_date else None

    if start and end and start > end:
        raise HTTPException(400, "from cannot be after to")

    return start, end


@router.get("/sales/trend")
def sales_trend(
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    start, end = analytics_period(from_date, to_date)

    rows = db.execute(
        text("""
            SELECT
                sales_date AS period,
                COALESCE(SUM(sales), 0)::double precision AS value
            FROM daily_store_sales
            WHERE (CAST(:start AS date) IS NULL OR sales_date >= CAST(:start AS date))
              AND (CAST(:end AS date) IS NULL OR sales_date <= CAST(:end AS date))
            GROUP BY sales_date
            ORDER BY sales_date
        """),
        {"start": start, "end": end},
    ).mappings().all()

    return {
        "points": [
            {"t": row["period"].isoformat(), "value": row["value"]}
            for row in rows
        ],
        "period_start": rows[0]["period"].isoformat() if rows else None,
        "period_end": rows[-1]["period"].isoformat() if rows else None,
        "origin": "imported",
    }


@router.get("/sales/customers-trend")
def customers_trend(
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    start, end = analytics_period(from_date, to_date)

    rows = db.execute(
        text("""
            SELECT
                sales_date AS period,
                COALESCE(SUM(customers), 0)::double precision AS value
            FROM daily_store_sales
            WHERE (CAST(:start AS date) IS NULL OR sales_date >= CAST(:start AS date))
              AND (CAST(:end AS date) IS NULL OR sales_date <= CAST(:end AS date))
            GROUP BY sales_date
            ORDER BY sales_date
        """),
        {"start": start, "end": end},
    ).mappings().all()

    return {
        "points": [
            {"t": row["period"].isoformat(), "value": row["value"]}
            for row in rows
        ],
        "period_start": rows[0]["period"].isoformat() if rows else None,
        "period_end": rows[-1]["period"].isoformat() if rows else None,
        "origin": "imported",
    }


@router.get("/sales/promotion-analysis")
def promotion_analysis(
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    start, end = analytics_period(from_date, to_date)

    row = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE promo IS TRUE) AS promoted_count,
                SUM(sales) FILTER (WHERE promo IS TRUE) AS promoted_sales,
                AVG(sales) FILTER (WHERE promo IS TRUE) AS promoted_average_sales,
                SUM(customers) FILTER (WHERE promo IS TRUE) AS promoted_customers,
                AVG(customers) FILTER (WHERE promo IS TRUE) AS promoted_average_customers,

                COUNT(*) FILTER (WHERE promo IS FALSE) AS non_promoted_count,
                SUM(sales) FILTER (WHERE promo IS FALSE) AS non_promoted_sales,
                AVG(sales) FILTER (WHERE promo IS FALSE) AS non_promoted_average_sales,
                SUM(customers) FILTER (WHERE promo IS FALSE) AS non_promoted_customers,
                AVG(customers) FILTER (WHERE promo IS FALSE) AS non_promoted_average_customers,

                MIN(sales_date) AS period_start,
                MAX(sales_date) AS period_end
            FROM daily_store_sales
            WHERE is_open IS TRUE
              AND (CAST(:start AS date) IS NULL OR sales_date >= CAST(:start AS date))
              AND (CAST(:end AS date) IS NULL OR sales_date <= CAST(:end AS date))
        """),
        {"start": start, "end": end},
    ).mappings().one()

    def group(count, sales, average_sales, customers, average_customers):
        return {
            "open_store_days": int(count or 0),
            "total_sales": float(sales) if sales is not None else None,
            "average_sales_per_store_day": (
                float(average_sales) if average_sales is not None else None
            ),
            "total_customers": int(customers) if customers is not None else None,
            "average_customers_per_store_day": (
                float(average_customers) if average_customers is not None else None
            ),
        }

    return {
        "promoted": group(
            row["promoted_count"],
            row["promoted_sales"],
            row["promoted_average_sales"],
            row["promoted_customers"],
            row["promoted_average_customers"],
        ),
        "non_promoted": group(
            row["non_promoted_count"],
            row["non_promoted_sales"],
            row["non_promoted_average_sales"],
            row["non_promoted_customers"],
            row["non_promoted_average_customers"],
        ),
        "period_start": row["period_start"].isoformat() if row["period_start"] else None,
        "period_end": row["period_end"].isoformat() if row["period_end"] else None,
        "origin": "imported",
        "comparison_basis": "open_store_days",
    }