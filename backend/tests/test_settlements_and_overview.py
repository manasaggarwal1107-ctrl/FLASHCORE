import hashlib
import hmac
import json

import httpx

from app.services import payment_service
from app.services.payments import RazorpayAdapter


def _rzp_sig(order_id: str, payment_id: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        f"{order_id}|{payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _signup(client, email: str) -> dict:
    r = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "Flashcore-Settle-Pass-99"},
    )
    assert r.status_code == 201
    return r.json()


def test_settlement_sync_unavailable_import_overview_and_export(client, monkeypatch):
    u = _signup(client, "stl-owner@example.com")
    token = u["access_token"]
    org_id = client.post(
        "/api/organisations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Settle Org", "slug": "stl-org"},
    ).json()["organisation_id"]
    hdrs = {"Authorization": f"Bearer {token}", "X-Organisation-Id": str(org_id)}

    key_secret = "rzp_sec_stl_1"
    assert (
        client.put(
            "/api/v1/payments/accounts/razorpay",
            headers=hdrs,
            json={
                "mode": "test",
                "key_id": "rzp_test_stl_1",
                "key_secret": key_secret,
                "webhook_secret": "whsec_stl_1",
            },
        ).status_code
        == 200
    )

    prod = client.post(
        "/api/v1/products",
        headers=hdrs,
        json={"sku": "STL-1", "name": "POS Kit", "price_minor": 100000},
    ).json()
    client.post(
        "/api/v1/inventory/adjustments",
        headers=hdrs,
        json={"product_id": int(prod["id"]), "quantity_delta": 5, "reason": "Init"},
    )
    o1 = client.post(
        "/api/v1/orders",
        headers=hdrs,
        json={"items": [{"product_id": int(prod["id"]), "quantity": 1}]},
    ).json()
    o2 = client.post(
        "/api/v1/orders",
        headers=hdrs,
        json={"items": [{"product_id": int(prod["id"]), "quantity": 1}]},
    ).json()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/orders":
            b = json.loads(request.content.decode("utf-8"))
            rid = "order_stl_1" if b["receipt"] == o1["reference"] else "order_stl_2"
            return httpx.Response(
                200,
                json={"id": rid, "amount": 100000, "currency": "INR", "receipt": b["receipt"], "status": "created"},
            )
        if request.method == "GET" and request.url.path == "/v1/payments/pay_stl_1":
            return httpx.Response(
                200,
                json={"id": "pay_stl_1", "order_id": "order_stl_1", "amount": 100000, "currency": "INR", "status": "captured", "method": "card"},
            )
        if request.method == "GET" and request.url.path == "/v1/payments/pay_stl_2":
            return httpx.Response(
                200,
                json={"id": "pay_stl_2", "order_id": "order_stl_2", "amount": 100000, "currency": "INR", "status": "captured", "method": "upi"},
            )
        if request.method == "POST" and request.url.path == "/v1/payments/pay_stl_1/refund":
            return httpx.Response(
                200,
                json={"id": "rfnd_stl_1", "payment_id": "pay_stl_1", "amount": 25000, "currency": "INR", "status": "processed"},
            )
        if request.method == "GET" and request.url.path == "/v1/settlements":
            return httpx.Response(404, json={"error": {"description": "Not available in test mode"}})
        return httpx.Response(404)

    monkeypatch.setattr(
        payment_service,
        "default_adapter_factory",
        lambda _p: RazorpayAdapter(transport=httpx.MockTransport(handler)),
    )

    # Capture 2 orders (total 2000.00 INR captured) and refund 250.00 INR on pay_stl_1
    for oid, rzp_oid, rzp_pid in [(o1["id"], "order_stl_1", "pay_stl_1"), (o2["id"], "order_stl_2", "pay_stl_2")]:
        po = client.post(f"/api/v1/orders/{oid}/checkout", headers=hdrs).json()
        assert (
            client.post(
                f"/api/v1/payments/orders/{po['id']}/verify",
                headers=hdrs,
                json={
                    "razorpay_order_id": rzp_oid,
                    "razorpay_payment_id": rzp_pid,
                    "razorpay_signature": _rzp_sig(rzp_oid, rzp_pid, key_secret),
                },
            ).status_code
            == 200
        )

    txns = client.get("/api/v1/payments/transactions", headers=hdrs).json()["items"]
    t1 = next(t for t in txns if t["provider_payment_id"] == "pay_stl_1")
    assert (
        client.post(
            f"/api/v1/payments/transactions/{t1['id']}/refunds",
            headers=hdrs,
            json={"amount_minor": 25000, "reason": "Partial adjustment"},
        ).status_code
        == 201
    )

    # Provider sync surfaces explicit capability unavailability without inventing settlements
    sync = client.post("/api/v1/payments/settlements/sync", headers=hdrs)
    assert sync.status_code == 200
    assert sync.json()["status"] == "capability_unavailable"

    # Malformed statement CSV (formula injection / bad math / currency mismatch) rejected
    bad_math_csv = (
        "provider_settlement_id,status,gross_amount_minor,refund_amount_minor,fee_minor,tax_minor,adjustment_minor,net_amount_minor,currency,provider_entity_id,entity_type\n"
        "setl_bad_1,PROCESSED,100000,0,2000,360,0,999999,INR,pay_stl_1,PAYMENT\n"
    )
    assert (
        client.post(
            "/api/v1/payments/settlements/import",
            headers=hdrs,
            json={"filename": "bad.csv", "csv_content": bad_math_csv},
        ).status_code
        == 422
    )
    currency_mismatch_csv = (
        "provider_settlement_id,status,gross_amount_minor,refund_amount_minor,fee_minor,tax_minor,adjustment_minor,net_amount_minor,currency,provider_entity_id,entity_type\n"
        "setl_bad_curr,PROCESSED,100000,0,2000,360,0,97640,USD,pay_stl_1,PAYMENT\n"
    )
    assert (
        client.post(
            "/api/v1/payments/settlements/import",
            headers=hdrs,
            json={"filename": "bad_curr.csv", "csv_content": currency_mismatch_csv},
        ).status_code
        == 422
    )

    # Valid settlement statement linking pay_stl_1 (leaving pay_stl_2 unsettled!)
    valid_csv = (
        "provider_settlement_id,status,gross_amount_minor,refund_amount_minor,fee_minor,tax_minor,adjustment_minor,net_amount_minor,currency,settlement_utr,provider_entity_id,entity_type\n"
        "setl_valid_1,PROCESSED,100000,0,2000,360,0,97640,INR,UTR20261127001,pay_stl_1,PAYMENT\n"
    )
    imp1 = client.post(
        "/api/v1/payments/settlements/import",
        headers=hdrs,
        json={"filename": "settlements-nov.csv", "csv_content": valid_csv},
    )
    assert imp1.status_code == 201, imp1.text
    assert imp1.json()["settlements_created"] == 1
    assert imp1.json()["idempotent_replay"] is False

    # Re-importing identical statement is idempotent
    imp2 = client.post(
        "/api/v1/payments/settlements/import",
        headers=hdrs,
        json={"filename": "settlements-nov.csv", "csv_content": valid_csv},
    )
    assert imp2.status_code == 201
    assert imp2.json()["idempotent_replay"] is True

    # Financial overview strictly distinguishes captured vs refunded vs settled vs unsettled
    ov = client.get("/api/v1/payments/overview", headers=hdrs).json()
    assert ov["gross_captured_minor"] == 200000
    assert ov["successful_payment_count"] == 2
    assert ov["partial_refund_count"] == 1
    assert ov["total_refunded_minor"] == 25000
    assert ov["gateway_fees_minor"] == 2000
    assert ov["gateway_tax_minor"] == 360
    assert ov["gross_settlements_minor"] == 100000
    assert ov["net_settlements_minor"] == 97640
    assert ov["unsettled_captured_minor"] == 100000  # pay_stl_2 still unsettled!

    # Export CSV report succeeds
    exp = client.get("/api/v1/payments/reports/export", headers=hdrs)
    assert exp.status_code == 200
    assert "GROSS_CAPTURED" in exp.text
    assert "pay_stl_2" in exp.text

    # Cross-org isolation on settlements & overview
    other = _signup(client, "stl-other@example.com")
    other_org = client.post(
        "/api/organisations",
        headers={"Authorization": f"Bearer {other['access_token']}"},
        json={"name": "Other STL", "slug": "other-stl"},
    ).json()["organisation_id"]
    other_hdrs = {"Authorization": f"Bearer {other['access_token']}", "X-Organisation-Id": str(other_org)}
    assert client.get("/api/v1/payments/settlements", headers=other_hdrs).json()["total"] == 0
    assert client.get("/api/v1/payments/overview", headers=other_hdrs).json()["gross_captured_minor"] == 0
