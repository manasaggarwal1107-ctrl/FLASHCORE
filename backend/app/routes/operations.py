from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext, require_org_roles
from app.core.database import get_db
from app.schemas.expansion import (
    NotificationOut,
    ReturnCreate,
    ReturnOut,
    ReturnReviewRequest,
    SalesDashboardOut,
)
from app.services import (
    notifications_service,
    reports_service,
    returns_service,
    sales_service,
)

router = APIRouter(prefix="/api/v1", tags=["Sales, Returns, Reports & Alerts"])


@router.get("/sales/records")
def list_sales_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None),
    refund_status: str | None = Query(None),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return sales_service.list_sales_records(
        db,
        org_ctx.organisation.id,
        page=page,
        page_size=page_size,
        search=search,
        refund_status=refund_status,
    )


@router.get("/sales/dashboard", response_model=SalesDashboardOut)
def get_sales_dashboard(
    days: int = Query(30, ge=1, le=365),
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "analyst")),
    db: Session = Depends(get_db),
):
    return sales_service.get_sales_dashboard(db, org_ctx.organisation.id, days=days)


@router.get("/reports/{report_type}")
def get_report(
    report_type: str,
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "analyst")),
    db: Session = Depends(get_db),
):
    try:
        headers, _, records = reports_service.generate_report(
            db, org_ctx.organisation.id, report_type, start_at=start_at, end_at=end_at
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"report_type": report_type, "headers": headers, "rows": records, "count": len(records)}


@router.get("/reports/{report_type}/export.csv")
def export_report_csv(
    report_type: str,
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "analyst")),
    db: Session = Depends(get_db),
):
    try:
        csv_body = reports_service.export_report_csv(
            db, org_ctx.organisation.id, report_type, start_at=start_at, end_at=end_at
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=csv_body,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="flashcore_{report_type}_report.csv"'
        },
    )


@router.get("/returns", response_model=list[ReturnOut])
def list_returns(
    status: str | None = Query(None),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return returns_service.list_returns(db, org_ctx.organisation.id, status=status)


@router.post("/returns", response_model=ReturnOut, status_code=201)
def create_return(
    payload: ReturnCreate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return returns_service.create_return_request(db, org_ctx, payload)


@router.post("/returns/{return_id}/review", response_model=ReturnOut)
def review_return(
    return_id: int,
    payload: ReturnReviewRequest,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return returns_service.review_return(db, org_ctx, return_id, payload)


@router.get("/notifications")
def list_notifications(
    unread_only: bool = Query(False),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return notifications_service.list_notifications(
        db, org_ctx.organisation.id, unread_only=unread_only
    )


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: int,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    out = notifications_service.mark_notification_read(
        db, org_ctx.organisation.id, notification_id
    )
    if out is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return out
