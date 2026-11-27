from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


class PaymentGatewayError(RuntimeError):
    """Base error raised by payment gateway adapters."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class GatewayTimeoutError(PaymentGatewayError):
    """Raised when a gateway call times out and provider state is uncertain."""


class GatewayCapabilityUnavailableError(PaymentGatewayError):
    """Raised when a provider or test-mode account does not support an operation."""


@dataclass(frozen=True)
class GatewayCredentials:
    provider: str
    mode: str
    key_id: str
    key_secret: str
    webhook_secret: str


@dataclass(frozen=True)
class GatewayOrderRequest:
    amount_minor: int
    currency: str
    receipt: str
    notes: dict[str, str]


@dataclass(frozen=True)
class GatewayOrderResult:
    provider_order_id: str
    amount_minor: int
    currency: str
    receipt: str
    status: str
    raw_payload: dict


@dataclass(frozen=True)
class CheckoutSignatureInput:
    provider_order_id: str
    provider_payment_id: str
    signature: str


@dataclass(frozen=True)
class GatewayPaymentDetails:
    provider_payment_id: str
    provider_order_id: str | None
    amount_minor: int
    currency: str
    status: str
    method: str | None
    error_code: str | None = None
    error_description: str | None = None
    fee_minor: int | None = None
    tax_minor: int | None = None
    raw_payload: dict | None = None


@dataclass(frozen=True)
class GatewayRefundRequest:
    provider_payment_id: str
    amount_minor: int
    currency: str
    speed: str = "normal"
    receipt: str | None = None
    notes: dict[str, str] | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class GatewayRefundResult:
    provider_refund_id: str
    provider_payment_id: str
    amount_minor: int
    currency: str
    status: str
    provider_status: str
    raw_payload: dict | None = None


@dataclass(frozen=True)
class GatewayPaymentLinkRequest:
    reference_id: str
    amount_minor: int
    currency: str
    description: str
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    accept_partial: bool = False
    expire_by_epoch: int | None = None
    notes: dict[str, str] | None = None


@dataclass(frozen=True)
class GatewayPaymentLinkResult:
    provider_link_id: str
    reference_id: str
    short_url: str
    amount_minor: int
    amount_paid_minor: int
    currency: str
    status: str
    provider_status: str
    expires_at: datetime | None = None
    raw_payload: dict | None = None


@dataclass(frozen=True)
class GatewaySettlementResult:
    provider_settlement_id: str
    status: str
    gross_amount_minor: int
    refund_amount_minor: int
    fee_minor: int
    tax_minor: int
    adjustment_minor: int
    net_amount_minor: int
    currency: str
    utr: str | None = None
    settled_at: datetime | None = None
    raw_payload: dict | None = None


class PaymentGatewayAdapter(ABC):
    provider_name: str

    @abstractmethod
    def create_order(
        self, request: GatewayOrderRequest, credentials: GatewayCredentials
    ) -> GatewayOrderResult: ...

    @abstractmethod
    def verify_checkout_signature(
        self, payload: CheckoutSignatureInput, credentials: GatewayCredentials
    ) -> bool: ...

    @abstractmethod
    def fetch_payment(
        self, provider_payment_id: str, credentials: GatewayCredentials
    ) -> GatewayPaymentDetails: ...

    @abstractmethod
    def verify_webhook(
        self, raw_body: bytes, signature: str, webhook_secret: str
    ) -> bool: ...

    @abstractmethod
    def create_refund(
        self, request: GatewayRefundRequest, credentials: GatewayCredentials
    ) -> GatewayRefundResult: ...

    @abstractmethod
    def fetch_refund(
        self, provider_refund_id: str, credentials: GatewayCredentials
    ) -> GatewayRefundResult: ...

    @abstractmethod
    def create_payment_link(
        self, request: GatewayPaymentLinkRequest, credentials: GatewayCredentials
    ) -> GatewayPaymentLinkResult: ...

    @abstractmethod
    def fetch_payment_link(
        self, provider_link_id: str, credentials: GatewayCredentials
    ) -> GatewayPaymentLinkResult: ...

    @abstractmethod
    def cancel_payment_link(
        self, provider_link_id: str, credentials: GatewayCredentials
    ) -> GatewayPaymentLinkResult: ...

    @abstractmethod
    def fetch_payments(
        self,
        from_ts: int | None,
        to_ts: int | None,
        credentials: GatewayCredentials,
        *,
        count: int = 100,
    ) -> list[GatewayPaymentDetails]: ...

    @abstractmethod
    def fetch_settlements(
        self,
        from_ts: int | None,
        to_ts: int | None,
        credentials: GatewayCredentials,
        *,
        count: int = 100,
    ) -> list[GatewaySettlementResult]: ...
