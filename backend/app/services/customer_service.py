from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext
from app.models.retail import Customer, Order
from app.models.rossmann import AuditLog
from app.schemas.retail import CustomerCreate, CustomerOut


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _customer_reference(customer: Customer) -> str:
    return f"CUST-{customer.id:05d}"


def to_customer_out(customer: Customer, order_count: int = 0) -> CustomerOut:
    return CustomerOut(
        id=str(customer.id),
        organisation_id=customer.organisation_id,
        reference=_customer_reference(customer),
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        billing_address=customer.billing_address,
        shipping_address=customer.shipping_address,
        status=customer.status,
        order_count=order_count,
        origin="real",
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


def create_customer(
    db: Session, org_ctx: OrgContext, payload: CustomerCreate
) -> CustomerOut:
    org_id = org_ctx.organisation.id
    customer = Customer(
        organisation_id=org_id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        billing_address=payload.billing_address,
        shipping_address=payload.shipping_address,
        status="active",
    )
    try:
        db.add(customer)
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A customer with this email already exists in this organisation.",
        ) from exc

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="commerce_customer_created",
            entity_name="customers",
            entity_id=str(customer.id),
            details={"name": customer.name, "status": "success"},
        )
    )
    db.commit()
    db.refresh(customer)
    return to_customer_out(customer, order_count=0)


def list_customers(
    db: Session,
    org_id: int,
    *,
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    status: str | None = None,
) -> dict:
    query = select(Customer).where(Customer.organisation_id == org_id)
    count_q = select(func.count(Customer.id)).where(
        Customer.organisation_id == org_id
    )

    if status:
        query = query.where(Customer.status == status)
        count_q = count_q.where(Customer.status == status)
    if search:
        pattern = f"%{_escape_like(search.strip())}%"
        filt = (
            Customer.name.ilike(pattern, escape="\\")
            | Customer.email.ilike(pattern, escape="\\")
            | Customer.phone.ilike(pattern, escape="\\")
        )
        query = query.where(filt)
        count_q = count_q.where(filt)

    total = db.scalar(count_q) or 0
    offset = (page - 1) * page_size
    customers = list(
        db.scalars(
            query.order_by(Customer.id.desc()).offset(offset).limit(page_size)
        ).all()
    )

    counts_map: dict[int, int] = {}
    if customers:
        cids = [c.id for c in customers]
        rows = db.execute(
            select(Order.customer_id, func.count(Order.id))
            .where(Order.organisation_id == org_id, Order.customer_id.in_(cids))
            .group_by(Order.customer_id)
        ).all()
        counts_map = {cid: int(cnt) for cid, cnt in rows if cid is not None}

    items = [to_customer_out(c, counts_map.get(c.id, 0)) for c in customers]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_customer(db: Session, org_id: int, customer_id: int) -> CustomerOut:
    customer = db.scalar(
        select(Customer).where(
            Customer.id == customer_id, Customer.organisation_id == org_id
        )
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    order_count = (
        db.scalar(
            select(func.count(Order.id)).where(
                Order.organisation_id == org_id, Order.customer_id == customer.id
            )
        )
        or 0
    )
    return to_customer_out(customer, int(order_count))
