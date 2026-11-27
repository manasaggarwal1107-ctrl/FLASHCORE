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


def _signup(client, email: str) -> dict:
    r = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "Flashcore-Recon-Pass-99"},
    )
    assert r.status_code == 201
    return r.json()


def test_reconciliation_detects_all_discrepancy_classes_without_mutation(
    client, db_session, monkeypatch
):
    u = _signup(client, "rec-owner@example.com")
    token = u["access_token"]
    org_id = client.post(
        "/api/organisations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Recon Org", "slug": "recon-org"},
    ).json()["organisation_id"]
    hdrs = {"Authorization": f"Bearer {token}", "X-Organisation-Id": str(org_id)}

    op = _signup(client, "rec-op@example.com")
    op_hdrs = {"Authorization": f"Bearer {op['access_token']}", "X-Organisation-Id": str(org_id)}
    db_session.execute(
        text(
            "INSERT INTO organisation_memberships (organisation_id, user_id, role, status) "
            "VALUES (:oid, :uid, 'operator', 'active')"
        ),
        {"oid": org_id, "uid": op["user"]["id"]},
    )
    db_session.commit()

    key_secret = "rzp_sec_rec_1"
    assert (
        client.put(
            "/api/v1/payments/accounts/razorpay",
            headers=hdrs,
            json={
                "mode": "test",
                "key_id": "rzp_test_rec_1",
                "key_secret": key_secret,
                "webhook_secret": "whsec_rec_1",
            },
        ).status_code
        == 200
    )

    prod = client.post(
        "/api/v1/products",
        headers=hdrs,
        json={"sku": "REC-1", "name": "Recon SKU", "price_minor": 50000},
    ).json()
    client.post(
        "/api/v1/inventory/adjustments",
        headers=hdrs,
        json={"product_id": int(prod["id"]), "quantity_delta": 10, "reason": "Init"},
    )
    o1 = client.post("/api/v1/orders", headers=hdrs, json={"items": [{"product_id": int(prod["id"]), "quantity": 1}]}).json()
    o2 = client.post("/api/v1/orders", headers=hdrs, json={"items": [{"product_id": int(prod["id"]), "quantity": 1}]}).json()
    o3 = client.post("/api/v1/orders", headers=hdrs, json={"items": [{"product_id": int(prod["id"]), "quantity": 1}]}).json()
    o4 = client.post("/api/v1/orders", headers=hdrs, json={"items": [{"product_id": int(prod["id"]), "quantity": 1}]}).json()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/orders":
            b = json.loads(request.content.decode("utf-8"))
            mapping = {o1["reference"]: "ord_r1", o2["reference"]: "ord_r2", o3["reference"]: "ord_r3", o4["reference"]: "ord_r4"}
            return httpx.Response(200, json={"id": mapping[b["receipt"]], "amount": 50000, "currency": "INR", "receipt": b["receipt"], "status": "created"})
        if request.method == "GET" and request.url.path.startswith("/v1/payments/pay_r"):
            pid = request.url.path.rsplit("/", 1)[-1]
            oid = pid.replace("pay_r", "ord_r")
            return httpx.Response(200, json={"id": pid, "order_id": oid, "amount": 50000, "currency": "INR", "status": "captured", "method": "card"})
        if request.method == "GET" and request.url.path == "/v1/payments":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"id": "pay_r1", "order_id": "ord_r1", "amount": 50000, "currency": "INR", "status": "captured", "method": "card"},
                        # pay_r2 intentionally omitted -> MISSING_IN_PROVIDER
                        # pay_r3 amount mismatch -> AMOUNT_MISMATCH
                        {"id": "pay_r3", "order_id": "ord_r3", "amount": 49000, "currency": "INR", "status": "captured", "method": "card"},
                        # pay_r4 duplicate provider record -> DUPLICATE
                        {"id": "pay_r4", "order_id": "ord_r4", "amount": 50000, "currency": "INR", "status": "captured", "method": "card"},
                        {"id": "pay_r4", "order_id": "ord_r4", "amount": 50000, "currency": "INR", "status": "captured", "method": "card"},
                        # Unknown provider payment -> MISSING_IN_FLASHCORE
                        {"id": "pay_extra_gw", "order_id": "ord_extra_gw", "amount": 25000, "currency": "INR", "status": "captured", "method": "upi"},
                    ]
                },
            )
        return httpx.Response(404)

    monkeypatch.setattr(
        payment_service,
        "default_adapter_factory",
        lambda _p: RazorpayAdapter(transport=httpx.MockTransport(handler)),
    )

    for ord_obj, rzp_oid, rzp_pid in [
        (o1, "ord_r1", "pay_r1"),
        (o2, "ord_r2", "pay_r2"),
        (o3, "ord_r3", "pay_r3"),
        (o4, "ord_r4", "pay_r4"),
    ]:
        po = client.post(f"/api/v1/orders/{ord_obj['id']}/checkout", headers=hdrs).json()
        assert (
            client.post(
                f"/api/v1/payments/orders/{po['id']}/verify",
                headers=hdrs,
                json={"razorpay_order_id": rzp_oid, "razorpay_payment_id": rzp_pid, "razorpay_signature": _rzp_sig(rzp_oid, rzp_pid, key_secret)},
            ).status_code
            == 200
        )

    # Also seed a PENDING refund (NEEDS_REVIEW) & a mismatched settlement item (SETTLEMENT_MISMATCH)
    txns = client.get("/api/v1/payments/transactions", headers=hdrs).json()["items"]
    t1 = next(t for t in txns if t["provider_payment_id"] == "pay_r1")
    po1_id = int(t1["payment_order_id"])
    db_session.execute(
        text(
            "INSERT INTO payment_refunds (organisation_id, order_id, payment_order_id, payment_transaction_id, "
            "provider, provider_payment_id, provider_refund_id, amount_minor, currency, refund_type, status) "
            "VALUES (:oid, :ord_id, :po_id, :tid, 'razorpay', 'pay_r1', 'rfnd_pending_rev', 10000, 'INR', 'PARTIAL', 'PENDING')"
        ),
        {"oid": org_id, "ord_id": int(o1["id"]), "po_id": po1_id, "tid": int(t1["id"])},
    )
    stl_id = db_session.execute(
        text(
            "INSERT INTO payment_settlements (organisation_id, provider, provider_settlement_id, status, "
            "gross_amount_minor, refund_amount_minor, fee_minor, tax_minor, adjustment_minor, net_amount_minor, currency, source) "
            "VALUES (:oid, 'razorpay', 'setl_mismatch_1', 'PROCESSED', 50000, 0, 1000, 180, 0, 48820, 'INR', 'statement_import') RETURNING id"
        ),
        {"oid": org_id},
    ).scalar_one()
    db_session.execute(
        text(
            "INSERT INTO payment_settlement_items (organisation_id, settlement_id, payment_transaction_id, order_id, "
            "entity_type, provider_entity_id, gross_amount_minor, fee_minor, tax_minor, net_amount_minor, currency) "
            "VALUES (:oid, :sid, :tid, :ord_id, 'PAYMENT', 'pay_r1', 45000, 1000, 180, 43820, 'INR')"
        ),
        {"oid": org_id, "sid": stl_id, "tid": int(t1["id"]), "ord_id": int(o1["id"])},
    )
    db_session.commit()

    # Run reconciliation (idempotent with Idempotency-Key)
    r1 = client.post(
        "/api/v1/payments/reconciliation/runs",
        headers={**op_hdrs, "Idempotency-Key": "recon-run-1"},
        json={"provider": "razorpay", "currency": "INR", "include_provider_fetch": True},
    )
    assert r1.status_code == 201, r1.text
    run_id = r1.json()["id"]

    r2 = client.post(
        "/api/v1/payments/reconciliation/runs",
        headers={**op_hdrs, "Idempotency-Key": "recon-run-1"},
        json={"provider": "razorpay", "currency": "INR", "include_provider_fetch": True},
    )
    assert r2.status_code == 201
    assert r2.json()["id"] == run_id

    items = client.get(f"/api/v1/payments/reconciliation/runs/{run_id}/items", headers=hdrs).json()["items"]
    outcomes = {it["outcome"] for it in items}
    assert {
        "MATCHED",
        "MISSING_IN_PROVIDER",
        "MISSING_IN_FLASHCORE",
        "AMOUNT_MISMATCH",
        "DUPLICATE",
        "NEEDS_REVIEW",
        "SETTLEMENT_MISMATCH",
    }.issubset(outcomes)

    # Underlying financial records remain completely untouched (no silent mutation)
    assert client.get(f"/api/v1/orders/{o3['id']}", headers=hdrs).json()["total_minor"] == 50000

    # Manual resolution: operator blocked (403), owner succeeds (200) and writes AuditLog
    exc_item = next(it for it in items if it["outcome"] == "AMOUNT_MISMATCH")
    assert (
        client.post(
            f"/api/v1/payments/reconciliation/items/{exc_item['id']}/resolve",
            headers=op_hdrs,
            json={"resolution_status": "RESOLVED", "resolution_note": "Investigated partial fee"},
        ).status_code
        == 403
    )
    resolved = client.post(
        f"/api/v1/payments/reconciliation/items/{exc_item['id']}/resolve",
        headers=hdrs,
        json={"resolution_status": "RESOLVED", "resolution_note": "Verified partial capture difference"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["resolution_status"] == "RESOLVED"

    # Cross-tenant isolation
    other = _signup(client, "rec-other@example.com")
    other_org = client.post(
        "/api/organisations",
        headers={"Authorization": f"Bearer {other['access_token']}"},
        json={"name": "Other Rec", "slug": "other-rec"},
    ).json()["organisation_id"]
    other_hdrs = {"Authorization": f"Bearer {other['access_token']}", "X-Organisation-Id": str(other_org)}
    assert client.get(f"/api/v1/payments/reconciliation/runs/{run_id}", headers=other_hdrs).status_code == 404
    assert (
        client.post(
            f"/api/v1/payments/reconciliation/items/{exc_item['id']}/resolve",
            headers=other_hdrs,
            json={"resolution_status": "RESOLVED", "resolution_note": "Cross-org hijack"},
        ).status_code
        == 404
    )
