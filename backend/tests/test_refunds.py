import hashlib
import hmac
import json

import httpx
from sqlalchemy import text

from app.services import payment_service
from app.services.payments import RazorpayAdapter


def _rzp_sig(order_id: str, payment_id: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        f"{order_id}|{payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _wh_sig(raw_body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def _create_user(client, email: str) -> dict:
    r = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "Flashcore-Refund-Pass-99"},
    )
    assert r.status_code == 201
    return r.json()


def _setup_captured_payment(client, db_session, monkeypatch, *, price_minor: int = 80000, suffix: str = "1"):
    owner = _create_user(client, f"rf-owner-{suffix}@example.com")
    token = owner["access_token"]
    org_id = client.post(
        "/api/organisations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": f"Refund Org {suffix}", "slug": f"rf-org-{suffix}"},
    ).json()["organisation_id"]
    hdrs = {"Authorization": f"Bearer {token}", "X-Organisation-Id": str(org_id)}

    # Also add an operator + analyst in this org cleanly via invite/db
    op = _create_user(client, f"rf-op-{suffix}@example.com")
    op_hdrs = {"Authorization": f"Bearer {op['access_token']}", "X-Organisation-Id": str(org_id)}
    db_session.execute(
        text(
            "INSERT INTO organisation_memberships (organisation_id, user_id, role, status) "
            "VALUES (:oid, :uid, 'operator', 'active')"
        ),
        {"oid": org_id, "uid": op["user"]["id"]},
    )
    db_session.commit()

    key_secret = f"rzp_sec_{suffix}"
    wh_secret = f"whsec_rf_{suffix}"
    assert (
        client.put(
            "/api/v1/payments/accounts/razorpay",
            headers=hdrs,
            json={
                "mode": "test",
                "key_id": f"rzp_test_rf_{suffix}",
                "key_secret": key_secret,
                "webhook_secret": wh_secret,
            },
        ).status_code
        == 200
    )

    prod = client.post(
        "/api/v1/products",
        headers=hdrs,
        json={"sku": f"RF-SKU-{suffix}", "name": "Refundable Item", "price_minor": price_minor},
    ).json()
    client.post(
        "/api/v1/inventory/adjustments",
        headers=hdrs,
        json={"product_id": int(prod["id"]), "quantity_delta": 5, "reason": "Init"},
    )
    order = client.post(
        "/api/v1/orders",
        headers=hdrs,
        json={"items": [{"product_id": int(prod["id"]), "quantity": 1}]},
    ).json()

    rzp_order_id = f"order_rf_{suffix}"
    rzp_pay_id = f"pay_rf_{suffix}"
    state = {"refund_seq": 0, "refund_status": "processed", "mode": "ok", "sync_status": "processed"}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/orders":
            return httpx.Response(
                200,
                json={
                    "id": rzp_order_id,
                    "amount": price_minor,
                    "currency": "INR",
                    "receipt": order["reference"],
                    "status": "created",
                },
            )
        if request.method == "GET" and request.url.path == f"/v1/payments/{rzp_pay_id}":
            return httpx.Response(
                200,
                json={
                    "id": rzp_pay_id,
                    "order_id": rzp_order_id,
                    "amount": price_minor,
                    "currency": "INR",
                    "status": "captured",
                    "method": "card",
                },
            )
        if request.method == "POST" and request.url.path == f"/v1/payments/{rzp_pay_id}/refund":
            if state["mode"] == "timeout":
                raise httpx.ReadTimeout("timeout", request=request)
            if state["mode"] == "fail":
                return httpx.Response(400, json={"error": {"description": "Refund rejected"}})
            body = json.loads(request.content.decode("utf-8"))
            state["refund_seq"] += 1
            return httpx.Response(
                200,
                json={
                    "id": f"rfnd_{suffix}_{state['refund_seq']}",
                    "payment_id": rzp_pay_id,
                    "amount": body["amount"],
                    "currency": "INR",
                    "status": state["refund_status"],
                },
            )
        if request.method == "GET" and request.url.path.startswith("/v1/refunds/"):
            rid = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(
                200,
                json={
                    "id": rid,
                    "payment_id": rzp_pay_id,
                    "amount": state.get("sync_amount", price_minor),
                    "currency": "INR",
                    "status": state["sync_status"],
                },
            )
        return httpx.Response(404)

    monkeypatch.setattr(
        payment_service,
        "default_adapter_factory",
        lambda _p: RazorpayAdapter(transport=httpx.MockTransport(handler)),
    )

    po = client.post(f"/api/v1/orders/{order['id']}/checkout", headers=hdrs).json()
    v = client.post(
        f"/api/v1/payments/orders/{po['id']}/verify",
        headers=hdrs,
        json={
            "razorpay_order_id": rzp_order_id,
            "razorpay_payment_id": rzp_pay_id,
            "razorpay_signature": _rzp_sig(rzp_order_id, rzp_pay_id, key_secret),
        },
    )
    assert v.status_code == 200
    txns = client.get("/api/v1/payments/transactions", headers=hdrs).json()["items"]
    txn_id = int(txns[0]["id"])
    return {
        "org_id": org_id,
        "hdrs": hdrs,
        "op_hdrs": op_hdrs,
        "txn_id": txn_id,
        "order_id": int(order["id"]),
        "wh_secret": wh_secret,
        "state": state,
        "rzp_pay_id": rzp_pay_id,
    }


def test_full_and_multiple_partial_refunds_with_over_refund_and_idempotency(
    client, db_session, monkeypatch
):
    ctx = _setup_captured_payment(client, db_session, monkeypatch, price_minor=80000, suffix="partial")

    # Partial refund 1 (INR 300.00 <= default 1000.00 threshold -> processed directly)
    r1 = client.post(
        f"/api/v1/payments/transactions/{ctx['txn_id']}/refunds",
        headers={**ctx["hdrs"], "Idempotency-Key": "rf-idemp-1"},
        json={"amount_minor": 30000, "reason": "Damaged unit 1"},
    )
    assert r1.status_code == 201, r1.text
    assert r1.json()["status"] == "PROCESSED"
    assert r1.json()["refund_type"] == "PARTIAL"
    assert r1.json()["provider_refund_id"] == "rfnd_partial_1"

    # Duplicate idempotency key does NOT create second gateway call
    r1_dup = client.post(
        f"/api/v1/payments/transactions/{ctx['txn_id']}/refunds",
        headers={**ctx["hdrs"], "Idempotency-Key": "rf-idemp-1"},
        json={"amount_minor": 30000, "reason": "Damaged unit 1"},
    )
    assert r1_dup.status_code == 201
    assert r1_dup.json()["id"] == r1.json()["id"]
    assert ctx["state"]["refund_seq"] == 1

    # Partial refund 2 (INR 250.00 -> total refunded 550.00)
    r2 = client.post(
        f"/api/v1/payments/transactions/{ctx['txn_id']}/refunds",
        headers=ctx["hdrs"],
        json={"amount_minor": 25000, "reason": "Customer requested item return"},
    )
    assert r2.status_code == 201
    assert r2.json()["status"] == "PROCESSED"

    # Over-refund (remaining is 25000, requesting 25001) must reject with 409
    over = client.post(
        f"/api/v1/payments/transactions/{ctx['txn_id']}/refunds",
        headers=ctx["hdrs"],
        json={"amount_minor": 25001, "reason": "Over-refund attempt"},
    )
    assert over.status_code == 409

    # Remaining balance full refund (amount_minor omitted -> takes remaining 25000)
    r3 = client.post(
        f"/api/v1/payments/transactions/{ctx['txn_id']}/refunds",
        headers=ctx["hdrs"],
        json={"reason": "Final remainder refund"},
    )
    assert r3.status_code == 201
    assert r3.json()["amount_minor"] == 25000
    assert r3.json()["refund_type"] == "PARTIAL"

    # Captured payment transaction amount remains immutable
    txn = client.get(f"/api/v1/payments/transactions/{ctx['txn_id']}", headers=ctx["hdrs"]).json()
    assert txn["amount_minor"] == 80000
    assert txn["status"] == "CAPTURED"


def test_high_value_refund_approval_workflow_permissions_and_isolation(
    client, db_session, monkeypatch
):
    ctx = _setup_captured_payment(client, db_session, monkeypatch, price_minor=150000, suffix="appr")

    # Configure threshold at 500.00 INR (50000 minor); operator denied
    assert (
        client.put(
            "/api/v1/payments/policies/refunds",
            headers=ctx["op_hdrs"],
            json={"refund_approval_threshold_minor": 50000, "currency": "INR"},
        ).status_code
        == 403
    )
    pol = client.put(
        "/api/v1/payments/policies/refunds",
        headers=ctx["hdrs"],
        json={"refund_approval_threshold_minor": 50000, "currency": "INR"},
    )
    assert pol.status_code == 200

    # Operator requests full refund (150000 > 50000) -> enters APPROVAL_PENDING without submitting to gateway
    req = client.post(
        f"/api/v1/payments/transactions/{ctx['txn_id']}/refunds",
        headers=ctx["op_hdrs"],
        json={"reason": "Full high-value refund"},
    )
    assert req.status_code == 201, req.text
    rj = req.json()
    assert rj["status"] == "APPROVAL_PENDING"
    assert rj["refund_type"] == "FULL"
    assert rj["requires_approval"] is True
    assert ctx["state"]["refund_seq"] == 0

    # Operator cannot self-approve (403)
    assert (
        client.post(
            f"/api/v1/payments/refunds/{rj['id']}/approve",
            headers=ctx["op_hdrs"],
        ).status_code
        == 403
    )

    # Other org cannot read or approve (404)
    other = _create_user(client, "rf-other@example.com")
    other_org = client.post(
        "/api/organisations",
        headers={"Authorization": f"Bearer {other['access_token']}"},
        json={"name": "Other Org", "slug": "other-rf-org"},
    ).json()["organisation_id"]
    other_hdrs = {"Authorization": f"Bearer {other['access_token']}", "X-Organisation-Id": str(other_org)}
    assert client.get(f"/api/v1/payments/refunds/{rj['id']}", headers=other_hdrs).status_code == 404
    assert client.post(f"/api/v1/payments/refunds/{rj['id']}/approve", headers=other_hdrs).status_code == 404

    # Owner approves -> single-use approval consumed and submitted to Razorpay
    app_resp = client.post(
        f"/api/v1/payments/refunds/{rj['id']}/approve",
        headers=ctx["hdrs"],
        json={"decision_note": "Verified return receipt"},
    )
    assert app_resp.status_code == 200, app_resp.text
    assert app_resp.json()["status"] == "PROCESSED"
    assert app_resp.json()["approval_request"]["status"] == "CONSUMED"
    assert ctx["state"]["refund_seq"] == 1

    # Re-approving same refund cannot reuse approval (409)
    assert (
        client.post(f"/api/v1/payments/refunds/{rj['id']}/approve", headers=ctx["hdrs"]).status_code
        == 409
    )


def test_refund_timeout_failure_sync_and_webhook_update(
    client, db_session, monkeypatch
):
    ctx = _setup_captured_payment(client, db_session, monkeypatch, price_minor=40000, suffix="sync")

    # Gateway failure leaves balance free and does NOT falsely mark refund successful
    ctx["state"]["mode"] = "fail"
    fail_resp = client.post(
        f"/api/v1/payments/transactions/{ctx['txn_id']}/refunds",
        headers=ctx["hdrs"],
        json={"amount_minor": 10000, "reason": "Retryable failure"},
    )
    assert fail_resp.status_code == 502

    # Timeout returns 504 and preserves PENDING tentative state
    ctx["state"]["mode"] = "timeout"
    to_resp = client.post(
        f"/api/v1/payments/transactions/{ctx['txn_id']}/refunds",
        headers=ctx["hdrs"],
        json={"amount_minor": 10000, "reason": "Timeout case"},
    )
    assert to_resp.status_code == 504

    # Next create_refund returns 'pending' from provider, then sync & webhook transition it to PROCESSED
    ctx["state"]["mode"] = "ok"
    ctx["state"]["refund_status"] = "pending"
    p_resp = client.post(
        f"/api/v1/payments/transactions/{ctx['txn_id']}/refunds",
        headers=ctx["hdrs"],
        json={"amount_minor": 15000, "reason": "Async refund"},
    )
    assert p_resp.status_code == 201
    rf = p_resp.json()
    assert rf["status"] == "PENDING"

    # Webhook updates refund.processed cleanly
    wh_body = json.dumps(
        {
            "event": "refund.processed",
            "payload": {
                "refund": {
                    "entity": {
                        "id": rf["provider_refund_id"],
                        "payment_id": ctx["rzp_pay_id"],
                        "amount": 15000,
                        "currency": "INR",
                        "status": "processed",
                    }
                }
            },
        }
    ).encode("utf-8")
    wh = client.post(
        "/api/v1/webhooks/razorpay",
        content=wh_body,
        headers={
            "X-Razorpay-Signature": _wh_sig(wh_body, ctx["wh_secret"]),
            "X-Razorpay-Event-Id": "evt_rfnd_proc_1",
        },
    )
    assert wh.status_code == 200, wh.text

    refetched = client.get(f"/api/v1/payments/refunds/{rf['id']}", headers=ctx["hdrs"]).json()
    assert refetched["status"] == "PROCESSED"

    # Manual sync also executes cleanly
    ctx["state"]["sync_amount"] = 15000
    sync = client.post(f"/api/v1/payments/refunds/{rf['id']}/sync", headers=ctx["hdrs"])
    assert sync.status_code == 200
    assert sync.json()["status"] == "PROCESSED"
