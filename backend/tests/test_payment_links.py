import hashlib
import hmac
import json

import httpx

from app.services import payment_service
from app.services.payments import RazorpayAdapter


def _wh_sig(raw_body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def _signup(client, email: str) -> dict:
    r = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "Flashcore-PayLink-Pass-99"},
    )
    assert r.status_code == 201
    return r.json()


def _setup_order_for_links(client, monkeypatch, suffix: str = "1"):
    u = _signup(client, f"pl-owner-{suffix}@example.com")
    token = u["access_token"]
    org_id = client.post(
        "/api/organisations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": f"Link Org {suffix}", "slug": f"pl-org-{suffix}"},
    ).json()["organisation_id"]
    hdrs = {"Authorization": f"Bearer {token}", "X-Organisation-Id": str(org_id)}

    wh_secret = f"whsec_pl_{suffix}"
    assert (
        client.put(
            "/api/v1/payments/accounts/razorpay",
            headers=hdrs,
            json={
                "mode": "test",
                "key_id": f"rzp_test_pl_{suffix}",
                "key_secret": f"rzp_sec_pl_{suffix}",
                "webhook_secret": wh_secret,
            },
        ).status_code
        == 200
    )

    cust = client.post(
        "/api/v1/customers",
        headers=hdrs,
        json={"name": "Rohan Das", "email": "rohan@example.com", "phone": "+919876500001"},
    ).json()
    prod = client.post(
        "/api/v1/products",
        headers=hdrs,
        json={"sku": f"PL-SKU-{suffix}", "name": "Enterprise Scanner", "price_minor": 45000},
    ).json()
    client.post(
        "/api/v1/inventory/adjustments",
        headers=hdrs,
        json={"product_id": int(prod["id"]), "quantity_delta": 4, "reason": "Init"},
    )
    order = client.post(
        "/api/v1/orders",
        headers=hdrs,
        json={"customer_id": int(cust["id"]), "items": [{"product_id": int(prod["id"]), "quantity": 1}]},
    ).json()

    state = {"create_calls": 0, "link_status": "created", "amount_paid": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/payment_links":
            state["create_calls"] += 1
            body = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "id": f"plink_{suffix}_{state['create_calls']}",
                    "reference_id": body["reference_id"],
                    "short_url": f"https://rzp.io/i/plink_{suffix}_{state['create_calls']}",
                    "amount": body["amount"],
                    "amount_paid": 0,
                    "currency": "INR",
                    "status": state["link_status"],
                    "expire_by": body.get("expire_by"),
                },
            )
        if request.method == "POST" and request.url.path.endswith("/cancel"):
            pid = request.url.path.split("/")[-2]
            return httpx.Response(
                200,
                json={
                    "id": pid,
                    "reference_id": "PL-REF",
                    "short_url": f"https://rzp.io/i/{pid}",
                    "amount": 45000,
                    "amount_paid": 0,
                    "currency": "INR",
                    "status": "cancelled",
                },
            )
        if request.method == "GET" and request.url.path.startswith("/v1/payment_links/"):
            pid = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(
                200,
                json={
                    "id": pid,
                    "reference_id": "PL-REF",
                    "short_url": f"https://rzp.io/i/{pid}",
                    "amount": 45000,
                    "amount_paid": state["amount_paid"],
                    "currency": "INR",
                    "status": state["link_status"],
                },
            )
        return httpx.Response(404)

    monkeypatch.setattr(
        payment_service,
        "default_adapter_factory",
        lambda _p: RazorpayAdapter(transport=httpx.MockTransport(handler)),
    )

    return {
        "hdrs": hdrs,
        "order_id": int(order["id"]),
        "wh_secret": wh_secret,
        "state": state,
    }


def test_payment_link_creation_idempotency_validation_cancel_and_isolation(
    client, monkeypatch
):
    ctx = _setup_order_for_links(client, monkeypatch, "crud")

    # Amount > order total or partial without accept_partial rejected cleanly
    assert (
        client.post(
            "/api/v1/payments/links",
            headers=ctx["hdrs"],
            json={"order_id": ctx["order_id"], "amount_minor": 99999, "description": "Too high"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/payments/links",
            headers=ctx["hdrs"],
            json={"order_id": ctx["order_id"], "amount_minor": 10000, "description": "Partial disallowed"},
        ).status_code
        == 422
    )

    # Valid link creation + Idempotency-Key deduplication
    r1 = client.post(
        "/api/v1/payments/links",
        headers={**ctx["hdrs"], "Idempotency-Key": "pl-idemp-1"},
        json={"order_id": ctx["order_id"], "description": "Invoice link for order"},
    )
    assert r1.status_code == 201, r1.text
    link = r1.json()
    assert link["status"] == "ACTIVE"
    assert link["amount_minor"] == 45000
    assert link["short_url"].startswith("https://rzp.io/i/")

    r2 = client.post(
        "/api/v1/payments/links",
        headers={**ctx["hdrs"], "Idempotency-Key": "pl-idemp-1"},
        json={"order_id": ctx["order_id"], "description": "Invoice link for order"},
    )
    assert r2.status_code == 201
    assert r2.json()["id"] == link["id"]
    assert ctx["state"]["create_calls"] == 1

    # Cross-org caller cannot view, sync, or cancel
    other = _signup(client, "pl-other@example.com")
    other_org = client.post(
        "/api/organisations",
        headers={"Authorization": f"Bearer {other['access_token']}"},
        json={"name": "Other PL Org", "slug": "other-pl-org"},
    ).json()["organisation_id"]
    other_hdrs = {"Authorization": f"Bearer {other['access_token']}", "X-Organisation-Id": str(other_org)}
    assert client.get(f"/api/v1/payments/links/{link['id']}", headers=other_hdrs).status_code == 404
    assert client.post(f"/api/v1/payments/links/{link['id']}/cancel", headers=other_hdrs).status_code == 404

    # Sync expired state without marking order PAID
    ctx["state"]["link_status"] = "expired"
    synced_exp = client.post(f"/api/v1/payments/links/{link['id']}/sync", headers=ctx["hdrs"])
    assert synced_exp.status_code == 200
    assert synced_exp.json()["status"] == "EXPIRED"
    assert client.get(f"/api/v1/orders/{ctx['order_id']}", headers=ctx["hdrs"]).json()["status"] == "PENDING_PAYMENT"

    # Fresh link cancelled explicitly
    ctx["state"]["link_status"] = "created"
    r3 = client.post(
        "/api/v1/payments/links",
        headers=ctx["hdrs"],
        json={"order_id": ctx["order_id"], "description": "Second link"},
    ).json()
    cancelled = client.post(f"/api/v1/payments/links/{r3['id']}/cancel", headers=ctx["hdrs"])
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"


def test_payment_link_webhook_confirms_order_only_on_captured_payment(
    client, db_session, monkeypatch
):
    ctx = _setup_order_for_links(client, monkeypatch, "whpaid")
    link = client.post(
        "/api/v1/payments/links",
        headers=ctx["hdrs"],
        json={"order_id": ctx["order_id"], "description": "Webhook confirmation link"},
    ).json()

    # Opening / syncing without verified payment does NOT mark order paid
    ctx["state"]["link_status"] = "paid"
    ctx["state"]["amount_paid"] = 45000
    client.post(f"/api/v1/payments/links/{link['id']}/sync", headers=ctx["hdrs"])
    assert client.get(f"/api/v1/orders/{ctx['order_id']}", headers=ctx["hdrs"]).json()["status"] == "PENDING_PAYMENT"

    # Trusted payment_link.paid webhook with captured payment marks link PAID & captures order
    body = json.dumps(
        {
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": link["provider_link_id"],
                        "amount": 45000,
                        "amount_paid": 45000,
                        "currency": "INR",
                        "status": "paid",
                    }
                },
                "payment": {
                    "entity": {
                        "id": "pay_plink_cap_1",
                        "order_id": f"order_for_{link['provider_link_id']}",
                        "amount": 45000,
                        "currency": "INR",
                        "status": "captured",
                        "method": "upi",
                    }
                },
            },
        }
    ).encode("utf-8")
    wh = client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={
            "X-Razorpay-Signature": _wh_sig(body, ctx["wh_secret"]),
            "X-Razorpay-Event-Id": "evt_plink_paid_1",
        },
    )
    assert wh.status_code == 200, wh.text

    ord_after = client.get(f"/api/v1/orders/{ctx['order_id']}", headers=ctx["hdrs"]).json()
    assert ord_after["status"] == "PAID"
    assert ord_after["payment_status"] == "CAPTURED"
