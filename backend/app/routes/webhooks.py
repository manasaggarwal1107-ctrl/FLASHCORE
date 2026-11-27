from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import webhook_service

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/razorpay")
async def receive_razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(
        default=None, alias="X-Razorpay-Signature"
    ),
    x_razorpay_event_id: str | None = Header(
        default=None, alias="X-Razorpay-Event-Id"
    ),
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    return webhook_service.process_razorpay_webhook(
        db,
        raw_body=raw_body,
        signature=x_razorpay_signature,
        header_event_id=x_razorpay_event_id,
    )
