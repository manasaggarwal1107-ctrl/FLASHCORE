from abc import ABC, abstractmethod
from dataclasses import dataclass


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
