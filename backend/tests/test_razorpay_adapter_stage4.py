import httpx
import pytest

from app.services.payments import (
    GatewayCapabilityUnavailableError,
    GatewayCredentials,
    GatewayPaymentLinkRequest,
    GatewayRefundRequest,
    GatewayTimeoutError,
    RazorpayAdapter,
    RazorpayGatewayError,
)


def _creds(mode: str = "test") -> GatewayCredentials:
    return GatewayCredentials(
        provider="razorpay",
        mode=mode,
        key_id="rzp_test_adapter_1",
        key_secret="rzp_test_adapter_secret_1",
        webhook_secret="whsec_adapter_1",
    )


def test_razorpay_adapter_refund_and_payment_link_operations():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/payments/pay_100/refund":
            return httpx.Response(
                200,
                json={
                    "id": "rfnd_100",
                    "payment_id": "pay_100",
                    "amount": 15000,
                    "currency": "INR",
                    "status": "processed",
                },
            )
        if request.method == "GET" and request.url.path == "/v1/refunds/rfnd_100":
            return httpx.Response(
                200,
                json={
                    "id": "rfnd_100",
                    "payment_id": "pay_100",
                    "amount": 15000,
                    "currency": "INR",
                    "status": "pending",
                },
            )
        if request.method == "POST" and request.url.path == "/v1/payment_links":
            return httpx.Response(
                200,
                json={
                    "id": "plink_100",
                    "reference_id": "PL-ORD-100",
                    "short_url": "https://rzp.io/i/plink_100",
                    "amount": 50000,
                    "amount_paid": 0,
                    "currency": "INR",
                    "status": "created",
                    "expire_by": 1796000000,
                },
            )
        if request.method == "POST" and request.url.path == "/v1/payment_links/plink_100/cancel":
            return httpx.Response(
                200,
                json={
                    "id": "plink_100",
                    "reference_id": "PL-ORD-100",
                    "short_url": "https://rzp.io/i/plink_100",
                    "amount": 50000,
                    "amount_paid": 0,
                    "currency": "INR",
                    "status": "cancelled",
                },
            )
        if request.method == "GET" and request.url.path == "/v1/settlements":
            return httpx.Response(200, json={"items": []})
        return httpx.Response(404)

    adapter = RazorpayAdapter(transport=httpx.MockTransport(handler))

    refund = adapter.create_refund(
        GatewayRefundRequest(
            provider_payment_id="pay_100",
            amount_minor=15000,
            currency="INR",
            idempotency_key="idemp-1",
        ),
        _creds(),
    )
    assert refund.provider_refund_id == "rfnd_100"
    assert refund.status == "PROCESSED"

    synced = adapter.fetch_refund("rfnd_100", _creds())
    assert synced.status == "PENDING"

    link = adapter.create_payment_link(
        GatewayPaymentLinkRequest(
            reference_id="PL-ORD-100",
            amount_minor=50000,
            currency="INR",
            description="Order #100",
            customer_name="Meera",
            customer_email="meera@example.com",
        ),
        _creds(),
    )
    assert link.provider_link_id == "plink_100"
    assert link.status == "ACTIVE"
    assert link.short_url == "https://rzp.io/i/plink_100"

    cancelled = adapter.cancel_payment_link("plink_100", _creds())
    assert cancelled.status == "CANCELLED"

    # Empty Razorpay test-mode settlements raises explicit capability unavailability (no fake data)
    with pytest.raises(GatewayCapabilityUnavailableError):
        adapter.fetch_settlements(None, None, _creds())

    # Live mode always rejected
    with pytest.raises(RazorpayGatewayError):
        adapter.fetch_refund("rfnd_100", _creds("live"))


def test_razorpay_adapter_maps_timeouts_explicitly():
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated gateway timeout", request=request)

    adapter = RazorpayAdapter(transport=httpx.MockTransport(timeout_handler))
    with pytest.raises(GatewayTimeoutError):
        adapter.create_refund(
            GatewayRefundRequest(
                provider_payment_id="pay_timeout",
                amount_minor=5000,
                currency="INR",
            ),
            _creds(),
        )
