import hashlib
import hmac

import httpx

from app.services.payments.adapter import (
    CheckoutSignatureInput,
    GatewayCredentials,
    GatewayOrderRequest,
    GatewayOrderResult,
    GatewayPaymentDetails,
    PaymentGatewayAdapter,
)


class RazorpayGatewayError(RuntimeError):
    pass


class RazorpayAdapter(PaymentGatewayAdapter):
    provider_name = "razorpay"
    BASE_URL = "https://api.razorpay.com/v1"

    def __init__(self, transport: httpx.BaseTransport | None = None):
        self._transport = transport

    def _client(self, credentials: GatewayCredentials) -> httpx.Client:
        if credentials.mode != "test":
            raise RazorpayGatewayError(
                "Live Razorpay operations are disabled in Stage 3; test mode only."
            )
        return httpx.Client(
            base_url=self.BASE_URL,
            auth=(credentials.key_id, credentials.key_secret),
            timeout=15.0,
            transport=self._transport,
        )

    def create_order(
        self, request: GatewayOrderRequest, credentials: GatewayCredentials
    ) -> GatewayOrderResult:
        with self._client(credentials) as client:
            resp = client.post(
                "/orders",
                json={
                    "amount": request.amount_minor,
                    "currency": request.currency,
                    "receipt": request.receipt,
                    "notes": request.notes,
                },
            )
        if resp.status_code >= 400:
            raise RazorpayGatewayError(
                f"Razorpay order creation failed with status {resp.status_code}."
            )
        data = resp.json()
        return GatewayOrderResult(
            provider_order_id=str(data["id"]),
            amount_minor=int(data["amount"]),
            currency=str(data["currency"]),
            receipt=str(data.get("receipt") or request.receipt),
            status=str(data.get("status") or "created"),
            raw_payload=data,
        )

    def verify_checkout_signature(
        self, payload: CheckoutSignatureInput, credentials: GatewayCredentials
    ) -> bool:
        message = f"{payload.provider_order_id}|{payload.provider_payment_id}".encode(
            "utf-8"
        )
        expected = hmac.new(
            credentials.key_secret.encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, payload.signature.strip().lower())

    def fetch_payment(
        self, provider_payment_id: str, credentials: GatewayCredentials
    ) -> GatewayPaymentDetails:
        with self._client(credentials) as client:
            resp = client.get(f"/payments/{provider_payment_id}")
        if resp.status_code >= 400:
            raise RazorpayGatewayError(
                f"Razorpay payment lookup failed with status {resp.status_code}."
            )
        data = resp.json()
        return GatewayPaymentDetails(
            provider_payment_id=str(data["id"]),
            provider_order_id=data.get("order_id"),
            amount_minor=int(data["amount"]),
            currency=str(data["currency"]),
            status=str(data["status"]),
            method=data.get("method"),
            error_code=data.get("error_code"),
            error_description=data.get("error_description"),
            raw_payload=data,
        )

    def verify_webhook(
        self, raw_body: bytes, signature: str, webhook_secret: str
    ) -> bool:
        if not signature or not webhook_secret:
            return False
        expected = hmac.new(
            webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature.strip().lower())
