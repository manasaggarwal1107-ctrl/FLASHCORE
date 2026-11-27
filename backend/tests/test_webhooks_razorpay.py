import hashlib
import hmac
import json

import httpx
from sqlalchemy import text

from app.services import payment_service
from app.services.payments import RazorpayAdapter


def _webhook_sig(raw_body: bytes, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()


def _setup_checkout_order(client, monkeypatch, suffix: str = "1"):
    u = client.post(
        "/api/auth/signup",
        json={
            "email": f"wh-owner-{suffix}@example.com",
            "password": "Flashcore-Webhook-Pass-99",
        },
    ).json()
    token = u["access_token"]
    org_id = client.post(
        "/api/organisations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": f"WH Org {suffix}", "slug": f"wh-org-{suffix}"},
    ).json()["organisation_id"]
    hdrs = {"Authorization": f"Bearer {token}", "X-Organisation-Id": str(org_id)}

    webhook_secret = f"whsec_test_secret_{suffix}"
    cfg = client.put(
        "/api/v1/payments/accounts/razorpay",
        headers=hdrs,
        json={
            "mode": "test",
            "key_id": f"rzp_test_wh_{suffix}",
            "key_secret": f"keysec_wh_{suffix}",
            "webhook_secret": webhook_secret,
        },
    )
    assert cfg.status_code == 200

    prod = client.post(
        "/api/v1/products",
        headers=hdrs,
        json={
            "sku": f"WH-SKU-{suffix}",
            "name": f"Webhook Product {suffix}",
            "price_minor": 30000,
            "currency": "INR",
        },
    ).json()
    loc = client.post(
        "/api/v1/inventory/locations",
        headers=hdrs,
        json={"name": f"WH Loc {suffix}", "code": f"WHL-{suffix}"},
    ).json()
    adj = client.post(
        "/api/v1/inventory/adjustments",
        headers=hdrs,
        json={
            "product_id": int(prod["id"]),
            "location_id": int(loc["id"]),
            "quantity_delta": 5,
            "reason": "opening_stock",
        },
    )
    assert adj.status_code == 200

    cust = client.post(
        "/api/v1/customers",
        headers=hdrs,
        json={"name": "Priya Nair", "email": f"priya-{suffix}@example.com"},
    ).json()

    order = client.post(
        "/api/v1/orders",
        headers={**hdrs, "Idempotency-Key": f"wh-ord-{suffix}"},
        json={
            "customer_id": int(cust["id"]),
            "location_id": int(loc["id"]),
            "items": [{"product_id": int(prod["id"]), "quantity": 2}],
        },
    ).json()
    assert order["total_minor"] == 60000

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/orders":
            payload = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "id": f"order_rzp_wh_{suffix}",
                    "amount": payload["amount"],
                    "currency": "INR",
                    "receipt": payload["receipt"],
                    "status": "created",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        payment_service,
        "default_adapter_factory",
        lambda p: RazorpayAdapter(transport=transport),
    )

    po = client.post(
        f"/api/v1/orders/{order['id']}/checkout",
        headers={**hdrs, "Idempotency-Key": f"wh-co-{suffix}"},
    )
    assert po.status_code == 201, po.text
    return {
        "org_id": org_id,
        "hdrs": hdrs,
        "webhook_secret": webhook_secret,
        "order_id": int(order["id"]),
        "product_id": int(prod["id"]),
        "location_id": int(loc["id"]),
        "po": po.json(),
    }


def test_webhook_rejects_invalid_and_missing_signatures(client, db_session, monkeypatch):
    ctx = _setup_checkout_order(client, monkeypatch, "invalid")
    body = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_rzp_bad_1",
                        "order_id": ctx["po"]["provider_order_id"],
                        "amount": 60000,
                        "currency": "INR",
                        "status": "captured",
                        "method": "card",
                    }
                }
            },
        }
    ).encode("utf-8")

    missing = client.post("/api/v1/webhooks/razorpay", content=body)
    assert missing.status_code == 400

    bad = client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={
            "X-Razorpay-Signature": "deadbeef" * 8,
            "X-Razorpay-Event-Id": "evt_bad_sig_1",
        },
    )
    assert bad.status_code == 401

    ev = db_session.execute(
        text(
            "SELECT signature_valid, processing_status FROM payment_webhook_events "
            "WHERE provider_event_id = 'evt_bad_sig_1'"
        )
    ).one()
    assert ev.signature_valid is False
    assert ev.processing_status == "rejected_signature"

    ord_state = db_session.execute(
        text("SELECT order_status, payment_status FROM orders WHERE id = :id"),
        {"id": ctx["order_id"]},
    ).one()
    assert ord_state.order_status == "PENDING_PAYMENT"
    assert ord_state.payment_status == "CREATED"


def test_webhook_captured_idempotency_and_out_of_order_protection(
    client, db_session, monkeypatch
):
    ctx = _setup_checkout_order(client, monkeypatch, "capture")
    captured_payload = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_rzp_wh_cap_1",
                        "order_id": ctx["po"]["provider_order_id"],
                        "amount": 60000,
                        "currency": "INR",
                        "status": "captured",
                        "method": "upi",
                    }
                }
            },
        }
    ).encode("utf-8")
    sig = _webhook_sig(captured_payload, ctx["webhook_secret"])

    # First delivery processes capture & confirms stock reservations
    r1 = client.post(
        "/api/v1/webhooks/razorpay",
        content=captured_payload,
        headers={
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": "evt_cap_1",
        },
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "processed"

    ord_state = db_session.execute(
        text("SELECT order_status, payment_status FROM orders WHERE id = :id"),
        {"id": ctx["order_id"]},
    ).one()
    assert ord_state.order_status == "PAID"
    assert ord_state.payment_status == "CAPTURED"

    bal = db_session.execute(
        text(
            "SELECT quantity, reserved_quantity FROM inventory_balances "
            "WHERE product_id = :pid AND location_id = :lid"
        ),
        {"pid": ctx["product_id"], "lid": ctx["location_id"]},
    ).one()
    assert bal.quantity == 3
    assert bal.reserved_quantity == 0

    # Duplicate delivery must be ignored without double-deducting or adding txn
    r2 = client.post(
        "/api/v1/webhooks/razorpay",
        content=captured_payload,
        headers={
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": "evt_cap_1",
        },
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "ignored_duplicate"

    txn_count = db_session.execute(
        text(
            "SELECT COUNT(*) FROM payment_transactions WHERE order_id = :oid AND event_type = 'CAPTURED'"
        ),
        {"oid": ctx["order_id"]},
    ).scalar_one()
    assert txn_count == 1

    # Late / out-of-order payment.failed must NOT downgrade CAPTURED/PAID
    failed_late = json.dumps(
        {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_rzp_wh_cap_1",
                        "order_id": ctx["po"]["provider_order_id"],
                        "amount": 60000,
                        "currency": "INR",
                        "status": "failed",
                        "method": "upi",
                        "error_code": "LATE_FAIL",
                    }
                }
            },
        }
    ).encode("utf-8")
    r3 = client.post(
        "/api/v1/webhooks/razorpay",
        content=failed_late,
        headers={
            "X-Razorpay-Signature": _webhook_sig(failed_late, ctx["webhook_secret"]),
            "X-Razorpay-Event-Id": "evt_late_fail_1",
        },
    )
    assert r3.status_code == 200
    assert r3.json()["status"] == "ignored_out_of_order"

    db_session.expire_all()
    ord_after = db_session.execute(
        text("SELECT order_status, payment_status FROM orders WHERE id = :id"),
        {"id": ctx["order_id"]},
    ).one()
    assert ord_after.order_status == "PAID"
    assert ord_after.payment_status == "CAPTURED"


def test_webhook_failed_then_retried_captured_recovery(
    client, db_session, monkeypatch
):
    ctx = _setup_checkout_order(client, monkeypatch, "retry")
    fail_body = json.dumps(
        {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_rzp_fail_first",
                        "order_id": ctx["po"]["provider_order_id"],
                        "amount": 60000,
                        "currency": "INR",
                        "status": "failed",
                        "method": "netbanking",
                        "error_code": "BAD_REQUEST_ERROR",
                        "error_description": "Bank declined",
                    }
                }
            },
        }
    ).encode("utf-8")
    r1 = client.post(
        "/api/v1/webhooks/razorpay",
        content=fail_body,
        headers={
            "X-Razorpay-Signature": _webhook_sig(fail_body, ctx["webhook_secret"]),
            "X-Razorpay-Event-Id": "evt_fail_first_1",
        },
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "processed"

    ord_mid = db_session.execute(
        text("SELECT order_status, payment_status FROM orders WHERE id = :id"),
        {"id": ctx["order_id"]},
    ).one()
    assert ord_mid.order_status == "PENDING_PAYMENT"
    assert ord_mid.payment_status == "FAILED"

    cap_body = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_rzp_retry_ok",
                        "order_id": ctx["po"]["provider_order_id"],
                        "amount": 60000,
                        "currency": "INR",
                        "status": "captured",
                        "method": "card",
                    }
                }
            },
        }
    ).encode("utf-8")
    r2 = client.post(
        "/api/v1/webhooks/razorpay",
        content=cap_body,
        headers={
            "X-Razorpay-Signature": _webhook_sig(cap_body, ctx["webhook_secret"]),
            "X-Razorpay-Event-Id": "evt_retry_ok_1",
        },
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "processed"

    db_session.expire_all()
    ord_final = db_session.execute(
        text("SELECT order_status, payment_status FROM orders WHERE id = :id"),
        {"id": ctx["order_id"]},
    ).one()
    assert ord_final.order_status == "PAID"
    assert ord_final.payment_status == "CAPTURED"


def test_webhook_rejects_incomplete_or_mismatched_financial_payloads(
    client, db_session, monkeypatch
):
    ctx = _setup_checkout_order(client, monkeypatch, "finval")
    base_cases = [
        (
            "missing_amount_captured",
            "payment.captured",
            {"id": "pay_fin_1", "order_id": ctx["po"]["provider_order_id"], "currency": "INR"},
        ),
        (
            "missing_currency_captured",
            "payment.captured",
            {"id": "pay_fin_2", "order_id": ctx["po"]["provider_order_id"], "amount": 60000},
        ),
        (
            "malformed_amount_string",
            "payment.captured",
            {"id": "pay_fin_3", "order_id": ctx["po"]["provider_order_id"], "amount": "60000", "currency": "INR"},
        ),
        (
            "malformed_amount_float",
            "payment.captured",
            {"id": "pay_fin_4", "order_id": ctx["po"]["provider_order_id"], "amount": 600.5, "currency": "INR"},
        ),
        (
            "malformed_amount_bool",
            "payment.captured",
            {"id": "pay_fin_5", "order_id": ctx["po"]["provider_order_id"], "amount": True, "currency": "INR"},
        ),
        (
            "zero_amount_captured",
            "payment.captured",
            {"id": "pay_fin_6", "order_id": ctx["po"]["provider_order_id"], "amount": 0, "currency": "INR"},
        ),
        (
            "mismatched_amount_captured",
            "payment.captured",
            {"id": "pay_fin_7", "order_id": ctx["po"]["provider_order_id"], "amount": 59900, "currency": "INR"},
        ),
        (
            "mismatched_currency_captured",
            "payment.captured",
            {"id": "pay_fin_8", "order_id": ctx["po"]["provider_order_id"], "amount": 60000, "currency": "USD"},
        ),
        (
            "missing_payment_id_captured",
            "payment.captured",
            {"order_id": ctx["po"]["provider_order_id"], "amount": 60000, "currency": "INR"},
        ),
        (
            "missing_amount_authorized",
            "payment.authorized",
            {"id": "pay_fin_10", "order_id": ctx["po"]["provider_order_id"], "currency": "INR"},
        ),
        (
            "mismatched_amount_authorized",
            "payment.authorized",
            {"id": "pay_fin_11", "order_id": ctx["po"]["provider_order_id"], "amount": 100, "currency": "INR"},
        ),
        (
            "missing_currency_failed",
            "payment.failed",
            {"id": "pay_fin_12", "order_id": ctx["po"]["provider_order_id"], "amount": 60000},
        ),
        (
            "zero_amount_failed",
            "payment.failed",
            {"id": "pay_fin_13", "order_id": ctx["po"]["provider_order_id"], "amount": 0, "currency": "INR"},
        ),
    ]

    for case_name, evt_type, entity in base_cases:
        evt_id = f"evt_{case_name}"
        raw = json.dumps(
            {
                "event": evt_type,
                "payload": {"payment": {"entity": entity}},
            }
        ).encode("utf-8")
        sig = _webhook_sig(raw, ctx["webhook_secret"])

        resp = client.post(
            "/api/v1/webhooks/razorpay",
            content=raw,
            headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": evt_id},
        )
        assert resp.status_code == 422, f"{case_name}: expected 422 got {resp.status_code} {resp.text}"

        # Duplicate replay of the rejected malformed event remains idempotent without IntegrityError
        replay = client.post(
            "/api/v1/webhooks/razorpay",
            content=raw,
            headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": evt_id},
        )
        assert replay.status_code == 422

        ev = db_session.execute(
            text(
                "SELECT signature_valid, processing_status FROM payment_webhook_events "
                "WHERE provider_event_id = :eid"
            ),
            {"eid": evt_id},
        ).one()
        assert ev.signature_valid is True
        assert ev.processing_status == "failed"

    # Zero financial transactions or attempts created, order remains PENDING_PAYMENT & CREATED
    assert (
        db_session.execute(
            text("SELECT COUNT(*) FROM payment_transactions WHERE order_id = :oid"),
            {"oid": ctx["order_id"]},
        ).scalar_one()
        == 0
    )
    assert (
        db_session.execute(
            text("SELECT COUNT(*) FROM payment_attempts WHERE order_id = :oid"),
            {"oid": ctx["order_id"]},
        ).scalar_one()
        == 0
    )
    ord_state = db_session.execute(
        text("SELECT order_status, payment_status FROM orders WHERE id = :oid"),
        {"oid": ctx["order_id"]},
    ).one()
    assert ord_state.order_status == "PENDING_PAYMENT"
    assert ord_state.payment_status == "CREATED"
