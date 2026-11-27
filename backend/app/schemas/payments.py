from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class GatewayAccountUpsert(BaseModel):
    mode: Literal["test", "live"] = "test"
    key_id: str = Field(min_length=8, max_length=120)
    key_secret: str = Field(min_length=8, max_length=256)
    webhook_secret: str = Field(min_length=8, max_length=256)
    status: Literal["active", "disabled"] = "active"

    @field_validator("key_id", "key_secret", "webhook_secret")
    @classmethod
    def strip_secret(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Credential field cannot be blank.")
        return cleaned


class GatewayAccountOut(BaseModel):
    id: int
    organisation_id: int
    provider: str
    mode: str
    key_id: str
    status: str
    has_key_secret: bool = True
    has_webhook_secret: bool = True
    created_at: datetime
    updated_at: datetime


class PaymentOrderCreateRequest(BaseModel):
    order_id: int = Field(gt=0)


class PaymentOrderOut(BaseModel):
    id: str
    organisation_id: int
    order_id: str
    provider: str
    mode: str
    provider_order_id: str
    key_id: str
    amount_minor: int
    amount: str
    currency: str
    receipt: str
    status: str
    prefill: dict | None = None
    created_at: datetime
    updated_at: datetime


class PaymentVerifyRequest(BaseModel):
    razorpay_order_id: str = Field(min_length=4, max_length=120)
    razorpay_payment_id: str = Field(min_length=4, max_length=120)
    razorpay_signature: str = Field(min_length=16, max_length=256)


class PaymentVerificationOut(BaseModel):
    verified: bool
    payment_order_id: str
    order_id: str
    order_status: str
    payment_status: str
    provider_order_id: str
    provider_payment_id: str
    amount_minor: int
    amount: str
    currency: str
    idempotent_replay: bool = False


class PaymentTransactionOut(BaseModel):
    id: str
    organisation_id: int
    order_id: str
    payment_order_id: str
    provider: str
    provider_payment_id: str
    event_type: str
    amount_minor: int
    amount: str
    currency: str
    status: str
    method: str | None = None
    source: str
    created_at: datetime


class PaymentTransactionListResponse(BaseModel):
    items: list[PaymentTransactionOut]
    total: int
    page: int
    page_size: int
