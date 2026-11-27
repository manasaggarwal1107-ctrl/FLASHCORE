from datetime import datetime, timezone
import hashlib
import hmac

import httpx

from app.services.payments.adapter import (
    CheckoutSignatureInput,
    GatewayCapabilityUnavailableError,
    GatewayCredentials,
    GatewayOrderRequest,
    GatewayOrderResult,
    GatewayPaymentDetails,
    GatewayPaymentLinkRequest,
    GatewayPaymentLinkResult,
    GatewayRefundRequest,
    GatewayRefundResult,
    GatewaySettlementResult,
    GatewayTimeoutError,
    PaymentGatewayAdapter,
    PaymentGatewayError,
)


class RazorpayGatewayError(PaymentGatewayError):
    pass


def normalize_razorpay_refund_status(provider_status: str | None) -> str:
    raw = (provider_status or "").strip().lower()
    if raw == "processed":
        return "PROCESSED"
    if raw == "failed":
        return "FAILED"
    return "PENDING"


def normalize_razorpay_link_status(provider_status: str | None) -> str:
    raw = (provider_status or "").strip().lower()
    mapping = {
        "created": "ACTIVE",
        "issued": "ACTIVE",
        "partially_paid": "PARTIALLY_PAID",
        "paid": "PAID",
        "expired": "EXPIRED",
        "cancelled": "CANCELLED",
        "failed": "FAILED",
    }
    return mapping.get(raw, "ACTIVE")


def normalize_razorpay_settlement_status(provider_status: str | None) -> str:
    raw = (provider_status or "").strip().lower()
    mapping = {
        "created": "INITIATED",
        "initiated": "INITIATED",
        "processed": "PROCESSED",
        "settled": "PROCESSED",
        "failed": "FAILED",
        "reversed": "REVERSED",
    }
    return mapping.get(raw, "INITIATED")


def _epoch_to_dt(value: object) -> datetime | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    return None


class RazorpayAdapter(PaymentGatewayAdapter):
    provider_name = "razorpay"
    BASE_URL = "https://api.razorpay.com/v1"

    def __init__(self, transport: httpx.BaseTransport | None = None):
        self._transport = transport

    def _client(self, credentials: GatewayCredentials) -> httpx.Client:
        if credentials.mode != "test":
            raise RazorpayGatewayError(
                "Live Razorpay operations are disabled; test mode only."
            )
        return httpx.Client(
            base_url=self.BASE_URL,
            auth=(credentials.key_id, credentials.key_secret),
            timeout=15.0,
            transport=self._transport,
        )

    def _send(
        self,
        method: str,
        path: str,
        credentials: GatewayCredentials,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            with self._client(credentials) as client:
                resp = client.request(
                    method, path, json=json_body, params=params, headers=headers
                )
            return resp
        except httpx.TimeoutException as exc:
            raise GatewayTimeoutError(
                f"Razorpay request timed out for {method} {path}."
            ) from exc
        except httpx.HTTPError as exc:
            raise RazorpayGatewayError(
                f"Razorpay transport error for {method} {path}."
            ) from exc

    def _parse_payment_details(self, data: dict) -> GatewayPaymentDetails:
        return GatewayPaymentDetails(
            provider_payment_id=str(data["id"]),
            provider_order_id=data.get("order_id"),
            amount_minor=int(data["amount"]),
            currency=str(data["currency"]).upper(),
            status=str(data["status"]),
            method=data.get("method"),
            error_code=data.get("error_code"),
            error_description=data.get("error_description"),
            fee_minor=int(data["fee"]) if isinstance(data.get("fee"), int) else None,
            tax_minor=int(data["tax"]) if isinstance(data.get("tax"), int) else None,
            raw_payload=data,
        )

    def _parse_refund_result(self, data: dict, fallback_currency: str = "INR") -> GatewayRefundResult:
        prov_status = str(data.get("status") or "pending")
        return GatewayRefundResult(
            provider_refund_id=str(data["id"]),
            provider_payment_id=str(data["payment_id"]),
            amount_minor=int(data["amount"]),
            currency=str(data.get("currency") or fallback_currency).upper(),
            status=normalize_razorpay_refund_status(prov_status),
            provider_status=prov_status,
            raw_payload=data,
        )

    def _parse_payment_link_result(
        self, data: dict, fallback_ref: str = ""
    ) -> GatewayPaymentLinkResult:
        prov_status = str(data.get("status") or "created")
        return GatewayPaymentLinkResult(
            provider_link_id=str(data["id"]),
            reference_id=str(data.get("reference_id") or fallback_ref),
            short_url=str(data.get("short_url") or ""),
            amount_minor=int(data["amount"]),
            amount_paid_minor=int(data.get("amount_paid") or 0),
            currency=str(data.get("currency") or "INR").upper(),
            status=normalize_razorpay_link_status(prov_status),
            provider_status=prov_status,
            expires_at=_epoch_to_dt(data.get("expire_by")),
            raw_payload=data,
        )

    def create_order(
        self, request: GatewayOrderRequest, credentials: GatewayCredentials
    ) -> GatewayOrderResult:
        resp = self._send(
            "POST",
            "/orders",
            credentials,
            json_body={
                "amount": request.amount_minor,
                "currency": request.currency,
                "receipt": request.receipt,
                "notes": request.notes,
            },
        )
        if resp.status_code >= 400:
            raise RazorpayGatewayError(
                f"Razorpay order creation failed with status {resp.status_code}.",
                status_code=resp.status_code,
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
        resp = self._send("GET", f"/payments/{provider_payment_id}", credentials)
        if resp.status_code >= 400:
            raise RazorpayGatewayError(
                f"Razorpay payment lookup failed with status {resp.status_code}.",
                status_code=resp.status_code,
            )
        return self._parse_payment_details(resp.json())

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

    def create_refund(
        self, request: GatewayRefundRequest, credentials: GatewayCredentials
    ) -> GatewayRefundResult:
        body: dict = {
            "amount": request.amount_minor,
            "speed": request.speed,
        }
        if request.receipt:
            body["receipt"] = request.receipt
        if request.notes:
            body["notes"] = request.notes
        headers = (
            {"X-Razorpay-Idempotency": request.idempotency_key}
            if request.idempotency_key
            else None
        )
        resp = self._send(
            "POST",
            f"/payments/{request.provider_payment_id}/refund",
            credentials,
            json_body=body,
            headers=headers,
        )
        if resp.status_code >= 400:
            raise RazorpayGatewayError(
                f"Razorpay refund creation failed with status {resp.status_code}.",
                status_code=resp.status_code,
            )
        return self._parse_refund_result(resp.json(), fallback_currency=request.currency)

    def fetch_refund(
        self, provider_refund_id: str, credentials: GatewayCredentials
    ) -> GatewayRefundResult:
        resp = self._send("GET", f"/refunds/{provider_refund_id}", credentials)
        if resp.status_code >= 400:
            raise RazorpayGatewayError(
                f"Razorpay refund lookup failed with status {resp.status_code}.",
                status_code=resp.status_code,
            )
        return self._parse_refund_result(resp.json())

    def create_payment_link(
        self, request: GatewayPaymentLinkRequest, credentials: GatewayCredentials
    ) -> GatewayPaymentLinkResult:
        body: dict = {
            "amount": request.amount_minor,
            "currency": request.currency,
            "reference_id": request.reference_id,
            "description": request.description,
            "accept_partial": request.accept_partial,
        }
        customer: dict[str, str] = {}
        if request.customer_name:
            customer["name"] = request.customer_name
        if request.customer_email:
            customer["email"] = request.customer_email
        if request.customer_phone:
            customer["contact"] = request.customer_phone
        if customer:
            body["customer"] = customer
        if request.expire_by_epoch is not None:
            body["expire_by"] = request.expire_by_epoch
        if request.notes:
            body["notes"] = request.notes

        resp = self._send("POST", "/payment_links", credentials, json_body=body)
        if resp.status_code >= 400:
            raise RazorpayGatewayError(
                f"Razorpay payment link creation failed with status {resp.status_code}.",
                status_code=resp.status_code,
            )
        return self._parse_payment_link_result(resp.json(), fallback_ref=request.reference_id)

    def fetch_payment_link(
        self, provider_link_id: str, credentials: GatewayCredentials
    ) -> GatewayPaymentLinkResult:
        resp = self._send("GET", f"/payment_links/{provider_link_id}", credentials)
        if resp.status_code >= 400:
            raise RazorpayGatewayError(
                f"Razorpay payment link lookup failed with status {resp.status_code}.",
                status_code=resp.status_code,
            )
        return self._parse_payment_link_result(resp.json())

    def cancel_payment_link(
        self, provider_link_id: str, credentials: GatewayCredentials
    ) -> GatewayPaymentLinkResult:
        resp = self._send(
            "POST", f"/payment_links/{provider_link_id}/cancel", credentials
        )
        if resp.status_code >= 400:
            raise RazorpayGatewayError(
                f"Razorpay payment link cancellation failed with status {resp.status_code}.",
                status_code=resp.status_code,
            )
        return self._parse_payment_link_result(resp.json())

    def fetch_payments(
        self,
        from_ts: int | None,
        to_ts: int | None,
        credentials: GatewayCredentials,
        *,
        count: int = 100,
    ) -> list[GatewayPaymentDetails]:
        params: dict[str, int] = {"count": min(max(1, count), 100)}
        if from_ts is not None:
            params["from"] = from_ts
        if to_ts is not None:
            params["to"] = to_ts
        resp = self._send("GET", "/payments", credentials, params=params)
        if resp.status_code >= 400:
            raise RazorpayGatewayError(
                f"Razorpay payments list lookup failed with status {resp.status_code}.",
                status_code=resp.status_code,
            )
        items = resp.json().get("items") or []
        return [self._parse_payment_details(item) for item in items if isinstance(item, dict)]

    def fetch_settlements(
        self,
        from_ts: int | None,
        to_ts: int | None,
        credentials: GatewayCredentials,
        *,
        count: int = 100,
    ) -> list[GatewaySettlementResult]:
        params: dict[str, int] = {"count": min(max(1, count), 100)}
        if from_ts is not None:
            params["from"] = from_ts
        if to_ts is not None:
            params["to"] = to_ts
        resp = self._send("GET", "/settlements", credentials, params=params)
        if resp.status_code in (400, 403, 404, 501):
            raise GatewayCapabilityUnavailableError(
                "Razorpay test mode does not provide settlement payout records for this account.",
                status_code=resp.status_code,
            )
        if resp.status_code >= 400:
            raise RazorpayGatewayError(
                f"Razorpay settlement fetch failed with status {resp.status_code}.",
                status_code=resp.status_code,
            )
        raw_items = resp.json().get("items")
        if not isinstance(raw_items, list) or len(raw_items) == 0:
            raise GatewayCapabilityUnavailableError(
                "No provider settlement records returned by Razorpay test mode."
            )

        results: list[GatewaySettlementResult] = []
        for item in raw_items:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            net_minor = int(item.get("amount") or 0)
            fee_minor = int(item.get("fees") or 0)
            tax_minor = int(item.get("tax") or 0)
            gross_minor = net_minor + fee_minor
            results.append(
                GatewaySettlementResult(
                    provider_settlement_id=str(item["id"]),
                    status=normalize_razorpay_settlement_status(item.get("status")),
                    gross_amount_minor=max(0, gross_minor),
                    refund_amount_minor=0,
                    fee_minor=max(0, fee_minor),
                    tax_minor=max(0, tax_minor),
                    adjustment_minor=0,
                    net_amount_minor=net_minor,
                    currency=str(item.get("currency") or "INR").upper(),
                    utr=item.get("utr"),
                    settled_at=_epoch_to_dt(item.get("created_at")),
                    raw_payload=item,
                )
            )
        if not results:
            raise GatewayCapabilityUnavailableError(
                "No valid settlement entries returned by Razorpay test mode."
            )
        return results
