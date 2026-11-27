import hashlib
import hmac
import json

import httpx
import pytest
from sqlalchemy import text

from app.core.crypto import decrypt_secret, encrypt_secret
from app.services import payment_service
from app.services.payments import RazorpayAdapter


def _signup(client, email: str) -> dict:
    resp = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "Flashcore-Payment-Pass-99"},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_org(client, token: str, name: str, slug: str) -> int:
    resp = client.post(
        "/api/organisations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "slug": slug},
    )
    assert resp.status_code == 201
    return resp.json()["organisation_id"]


def _headers(token: str, org_id: int, idemp: str | None = None) -> dict[str, str]:
    h = {"Authorization": f"Bearer {token}", "X-Organisation-Id": str(org_id)}
    if idemp:
        h["Idempotency-Key"] = idemp
    return h


def _rzp_signature(order_id: str, payment_id: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        f"{order_id}|{payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def test_credential_encryption_roundtrip_and_aad_isolation(monkeypatch):
    cipher = encrypt_secret("rzp_secret_value_1", aad="org:1:provider:razorpay")
    assert "rzp_secret_value_1" not in cipher
    assert decrypt_secret(cipher, aad="org:1:provider:razorpay") == "rzp_secret_value_1"

    # Transplanting ciphertext to another org AAD fails authenticated decryption
    with pytest.raises(Exception):
        decrypt_secret(cipher, aad="org:2:provider:razorpay")

    # Missing env key fails loudly (no silent fallback)
    monkeypatch.delenv("FLASHCORE_CREDENTIAL_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError):
        encrypt_secret("secret", aad="org:1:provider:razorpay")


def test_razorpay_account_config_rejects_live_mode_and_hides_secrets(
    client, db_session
):
    u = _signup(client, "gw-owner@example.com")
    org_id = _create_org(client, u["access_token"], "GW Org", "gw-org")
    hdrs = _headers(u["access_token"], org_id)

    # Live mode rejected in Stage 3
    live = client.put(
        "/api/v1/payments/accounts/razorpay",
        headers=hdrs,
        json={
            "mode": "live",
            "key_id": "rzp_live_12345678",
            "key_secret": "live_secret_1234",
            "webhook_secret": "live_whsec_1234",
        },
    )
    assert live.status_code == 422

    # Valid test-mode configuration
    saved = client.put(
        "/api/v1/payments/accounts/razorpay",
        headers=hdrs,
        json={
            "mode": "test",
            "key_id": "rzp_test_org1_key",
            "key_secret": "test_secret_org1",
            "webhook_secret": "whsec_test_org1",
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["key_id"] == "rzp_test_org1_key"
    assert body["mode"] == "test"
    assert "key_secret" not in body
    assert "webhook_secret" not in body
    assert "test_secret_org1" not in str(body)

    # Verify DB row stores encrypted secrets, not plaintext
    raw_row = db_session.execute(
        text(
            "SELECT encrypted_key_secret, encrypted_webhook_secret "
            "FROM payment_provider_accounts WHERE organisation_id = :org_id"
        ),
        {"org_id": org_id},
    ).mappings().one()
    assert "test_secret_org1" not in raw_row["encrypted_key_secret"]
    assert "whsec_test_org1" not in raw_row["encrypted_webhook_secret"]


def test_checkout_order_creation_signature_verification_and_cross_tenant_isolation(
    client, monkeypatch
):
    u_a = _signup(client, "pay-a@example.com")
    u_b = _signup(client, "pay-b@example.com")
    org_a = _create_org(client, u_a["access_token"], "Pay Org A", "pay-org-a")
    org_b = _create_org(client, u_b["access_token"], "Pay Org B", "pay-org-b")

    hdrs_a = _headers(u_a["access_token"], org_a)
    hdrs_b = _headers(u_b["access_token"], org_b)

    secret_a = "rzp_test_secret_alpha"
    client.put(
        "/api/v1/payments/accounts/razorpay",
        headers=hdrs_a,
        json={
            "mode": "test",
            "key_id": "rzp_test_alpha_1",
            "key_secret": secret_a,
            "webhook_secret": "whsec_alpha_1",
        },
    )

    prod = client.post(
        "/api/v1/products",
        headers=hdrs_a,
        json={"sku": "PAY-1", "name": "Smart Watch", "price_minor": 299900},
    ).json()
    prod_id = int(prod["id"])
    client.post(
        "/api/v1/inventory/adjustments",
        headers=hdrs_a,
        json={"product_id": prod_id, "quantity_delta": 5, "reason": "Opening"},
    )

    order = client.post(
        "/api/v1/orders",
        headers=hdrs_a,
        json={"items": [{"product_id": prod_id, "quantity": 1}]},
    ).json()
    order_id = int(order["id"])

    # Mock Razorpay HTTP transport
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/orders":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["amount"] == 299900
            assert payload["currency"] == "INR"
            return httpx.Response(
                200,
                json={
                    "id": "order_RzpTest001",
                    "amount": payload["amount"],
                    "currency": "INR",
                    "receipt": payload["receipt"],
                    "status": "created",
                },
            )
        if request.method == "GET" and request.url.path == "/v1/payments/pay_RzpTest001":
            return httpx.Response(
                200,
                json={
                    "id": "pay_RzpTest001",
                    "order_id": "order_RzpTest001",
                    "amount": 299900,
                    "currency": "INR",
                    "status": "captured",
                    "method": "upi",
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    monkeypatch.setattr(
        payment_service,
        "default_adapter_factory",
        lambda _p: RazorpayAdapter(transport=httpx.MockTransport(handler)),
    )

    # Initiate checkout for Org A order
    po_resp = client.post(
        f"/api/v1/orders/{order_id}/checkout",
        headers=_headers(u_a["access_token"], org_a, idemp="CHK-1"),
    )
    assert po_resp.status_code == 201, po_resp.text
    po = po_resp.json()
    assert po["provider_order_id"] == "order_RzpTest001"
    assert po["key_id"] == "rzp_test_alpha_1"
    assert po["amount_minor"] == 299900
    po_id = po["id"]

    # Cross-tenant checkout / read / verify blocked (404)
    assert (
        client.post(f"/api/v1/orders/{order_id}/checkout", headers=hdrs_b).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/payments/orders/{po_id}", headers=hdrs_b).status_code == 404
    )

    # Invalid signature rejected (400) and order remains PENDING_PAYMENT
    bad_sig = client.post(
        f"/api/v1/payments/orders/{po_id}/verify",
        headers=hdrs_a,
        json={
            "razorpay_order_id": "order_RzpTest001",
            "razorpay_payment_id": "pay_RzpTest001",
            "razorpay_signature": "0" * 64,
        },
    )
    assert bad_sig.status_code == 400
    assert (
        client.get(f"/api/v1/orders/{order_id}", headers=hdrs_a).json()["status"]
        == "PENDING_PAYMENT"
    )

    # Valid signature succeeds, confirms stock reservation, marks order PAID
    valid_sig = _rzp_signature("order_RzpTest001", "pay_RzpTest001", secret_a)
    ok_verify = client.post(
        f"/api/v1/payments/orders/{po_id}/verify",
        headers=hdrs_a,
        json={
            "razorpay_order_id": "order_RzpTest001",
            "razorpay_payment_id": "pay_RzpTest001",
            "razorpay_signature": valid_sig,
        },
    )
    assert ok_verify.status_code == 200, ok_verify.text
    vdata = ok_verify.json()
    assert vdata["verified"] is True
    assert vdata["order_status"] == "PAID"
    assert vdata["payment_status"] == "CAPTURED"
    assert vdata["idempotent_replay"] is False

    # Replay verify is idempotent and does not double-decrement inventory
    replay = client.post(
        f"/api/v1/payments/orders/{po_id}/verify",
        headers=hdrs_a,
        json={
            "razorpay_order_id": "order_RzpTest001",
            "razorpay_payment_id": "pay_RzpTest001",
            "razorpay_signature": valid_sig,
        },
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True

    inv = client.get("/api/v1/inventory", headers=hdrs_a).json()
    assert inv["items"][0]["on_hand"] == 4
    assert inv["items"][0]["reserved"] == 0
    assert inv["items"][0]["available"] == 4

    txns = client.get("/api/v1/payments/transactions", headers=hdrs_a).json()
    assert txns["total"] == 1
    assert txns["items"][0]["provider_payment_id"] == "pay_RzpTest001"
    assert txns["items"][0]["status"] == "CAPTURED"

    # Org B cannot see Org A's payment transactions
    assert client.get("/api/v1/payments/transactions", headers=hdrs_b).json()["total"] == 0


def _setup_authorized_scenario(client, monkeypatch, suffix: str):
    u = _signup(client, f"auth-idem-{suffix}@example.com")
    org_id = _create_org(client, u["access_token"], f"Auth Org {suffix}", f"auth-org-{suffix}")
    hdrs = _headers(u["access_token"], org_id)

    key_secret = f"rzp_test_sec_{suffix}"
    wh_secret = f"whsec_auth_{suffix}"
    cfg = client.put(
        "/api/v1/payments/accounts/razorpay",
        headers=hdrs,
        json={
            "mode": "test",
            "key_id": f"rzp_test_key_{suffix}",
            "key_secret": key_secret,
            "webhook_secret": wh_secret,
        },
    )
    assert cfg.status_code == 200

    prod = client.post(
        "/api/v1/products",
        headers=hdrs,
        json={"sku": f"AUTH-SKU-{suffix}", "name": "Auth Product", "price_minor": 50000},
    ).json()
    client.post(
        "/api/v1/inventory/adjustments",
        headers=hdrs,
        json={"product_id": int(prod["id"]), "quantity_delta": 3, "reason": "Opening"},
    )
    order = client.post(
        "/api/v1/orders",
        headers=hdrs,
        json={"items": [{"product_id": int(prod["id"]), "quantity": 1}]},
    ).json()
    order_id = int(order["id"])

    gw_state = {"status": "authorized"}
    rzp_order_id = f"order_rzp_auth_{suffix}"
    rzp_pay_id = f"pay_rzp_auth_{suffix}"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/orders":
            payload = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "id": rzp_order_id,
                    "amount": payload["amount"],
                    "currency": "INR",
                    "receipt": payload["receipt"],
                    "status": "created",
                },
            )
        if request.method == "GET" and request.url.path == f"/v1/payments/{rzp_pay_id}":
            return httpx.Response(
                200,
                json={
                    "id": rzp_pay_id,
                    "order_id": rzp_order_id,
                    "amount": 50000,
                    "currency": "INR",
                    "status": gw_state["status"],
                    "method": "card",
                },
            )
        return httpx.Response(404)

    monkeypatch.setattr(
        payment_service,
        "default_adapter_factory",
        lambda _p: RazorpayAdapter(transport=httpx.MockTransport(handler)),
    )

    po = client.post(f"/api/v1/orders/{order_id}/checkout", headers=hdrs).json()
    sig = _rzp_signature(rzp_order_id, rzp_pay_id, key_secret)
    return {
        "hdrs": hdrs,
        "order_id": order_id,
        "po_id": po["id"],
        "rzp_order_id": rzp_order_id,
        "rzp_pay_id": rzp_pay_id,
        "sig": sig,
        "wh_secret": wh_secret,
        "gw_state": gw_state,
    }


def _webhook_sig(raw_body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def test_authorized_verification_idempotency_and_capture_transition(
    client, db_session, monkeypatch
):
    ctx = _setup_authorized_scenario(client, monkeypatch, "v1")
    verify_body = {
        "razorpay_order_id": ctx["rzp_order_id"],
        "razorpay_payment_id": ctx["rzp_pay_id"],
        "razorpay_signature": ctx["sig"],
    }

    # 1. First authorized verification
    r1 = client.post(
        f"/api/v1/payments/orders/{ctx['po_id']}/verify",
        headers=ctx["hdrs"],
        json=verify_body,
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["verified"] is True
    assert r1.json()["payment_status"] == "AUTHORIZED"
    assert r1.json()["order_status"] == "PENDING_PAYMENT"
    assert r1.json()["idempotent_replay"] is False

    # 2. Repeated authorized verification must not hit IntegrityError or duplicate rows
    r2 = client.post(
        f"/api/v1/payments/orders/{ctx['po_id']}/verify",
        headers=ctx["hdrs"],
        json=verify_body,
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["idempotent_replay"] is True

    # 4. Checkout verification followed by authorized webhook stays single attempt & single txn
    auth_wh = json.dumps(
        {
            "event": "payment.authorized",
            "payload": {
                "payment": {
                    "entity": {
                        "id": ctx["rzp_pay_id"],
                        "order_id": ctx["rzp_order_id"],
                        "amount": 50000,
                        "currency": "INR",
                        "status": "authorized",
                        "method": "card",
                    }
                }
            },
        }
    ).encode("utf-8")
    wh1 = client.post(
        "/api/v1/webhooks/razorpay",
        content=auth_wh,
        headers={
            "X-Razorpay-Signature": _webhook_sig(auth_wh, ctx["wh_secret"]),
            "X-Razorpay-Event-Id": "evt_auth_after_verify_1",
        },
    )
    assert wh1.status_code == 200

    assert (
        db_session.execute(
            text("SELECT COUNT(*) FROM payment_attempts WHERE provider_payment_id = :pid"),
            {"pid": ctx["rzp_pay_id"]},
        ).scalar_one()
        == 1
    )
    assert (
        db_session.execute(
            text(
                "SELECT COUNT(*) FROM payment_transactions "
                "WHERE provider_payment_id = :pid AND event_type = 'AUTHORIZED'"
            ),
            {"pid": ctx["rzp_pay_id"]},
        ).scalar_one()
        == 1
    )

    # 5. Authorized-to-captured transition preserves single attempt and records CAPTURED txn + PAID order
    ctx["gw_state"]["status"] = "captured"
    cap = client.post(
        f"/api/v1/payments/orders/{ctx['po_id']}/verify",
        headers=ctx["hdrs"],
        json=verify_body,
    )
    assert cap.status_code == 200, cap.text
    assert cap.json()["order_status"] == "PAID"
    assert cap.json()["payment_status"] == "CAPTURED"
    assert (
        db_session.execute(
            text("SELECT status FROM payment_attempts WHERE provider_payment_id = :pid"),
            {"pid": ctx["rzp_pay_id"]},
        ).scalar_one()
        == "CAPTURED"
    )
    assert (
        db_session.execute(
            text("SELECT COUNT(*) FROM payment_transactions WHERE provider_payment_id = :pid"),
            {"pid": ctx["rzp_pay_id"]},
        ).scalar_one()
        == 2
    )


def test_authorized_webhook_followed_by_checkout_verification_is_idempotent(
    client, db_session, monkeypatch
):
    ctx = _setup_authorized_scenario(client, monkeypatch, "w2v")
    auth_wh = json.dumps(
        {
            "event": "payment.authorized",
            "payload": {
                "payment": {
                    "entity": {
                        "id": ctx["rzp_pay_id"],
                        "order_id": ctx["rzp_order_id"],
                        "amount": 50000,
                        "currency": "INR",
                        "status": "authorized",
                        "method": "card",
                    }
                }
            },
        }
    ).encode("utf-8")

    # 3. Authorized webhook arrives first
    wh = client.post(
        "/api/v1/webhooks/razorpay",
        content=auth_wh,
        headers={
            "X-Razorpay-Signature": _webhook_sig(auth_wh, ctx["wh_secret"]),
            "X-Razorpay-Event-Id": "evt_auth_first_1",
        },
    )
    assert wh.status_code == 200
    assert wh.json()["status"] == "processed"

    # Followed by checkout verification while still authorized
    v = client.post(
        f"/api/v1/payments/orders/{ctx['po_id']}/verify",
        headers=ctx["hdrs"],
        json={
            "razorpay_order_id": ctx["rzp_order_id"],
            "razorpay_payment_id": ctx["rzp_pay_id"],
            "razorpay_signature": ctx["sig"],
        },
    )
    assert v.status_code == 200, v.text
    assert v.json()["idempotent_replay"] is True
    assert v.json()["payment_status"] == "AUTHORIZED"

    assert (
        db_session.execute(
            text("SELECT COUNT(*) FROM payment_attempts WHERE provider_payment_id = :pid"),
            {"pid": ctx["rzp_pay_id"]},
        ).scalar_one()
        == 1
    )
    assert (
        db_session.execute(
            text("SELECT COUNT(*) FROM payment_transactions WHERE provider_payment_id = :pid"),
            {"pid": ctx["rzp_pay_id"]},
        ).scalar_one()
        == 1
    )
