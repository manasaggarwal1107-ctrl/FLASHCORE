from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from main import app


def _signup(client, email: str) -> dict:
    resp = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "Flashcore-Orders-Pass-99"},
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


def test_customers_orders_price_snapshots_lifecycle_and_tenant_isolation(client):
    u_a = _signup(client, "ord-a@example.com")
    u_b = _signup(client, "ord-b@example.com")
    org_a = _create_org(client, u_a["access_token"], "Orders A", "orders-org-a")
    org_b = _create_org(client, u_b["access_token"], "Orders B", "orders-org-b")

    hdrs_a = _headers(u_a["access_token"], org_a)
    hdrs_b = _headers(u_b["access_token"], org_b)

    cust_a = client.post(
        "/api/v1/customers",
        headers=hdrs_a,
        json={"name": "Aarav Sharma", "email": "aarav@retail.in", "phone": "+919876543210"},
    )
    assert cust_a.status_code == 201
    cust_a_id = int(cust_a.json()["id"])

    # Cross-tenant customer isolation
    assert client.get(f"/api/v1/customers/{cust_a_id}", headers=hdrs_b).status_code == 404

    prod = client.post(
        "/api/v1/products",
        headers=hdrs_a,
        json={
            "sku": "COFFEE-500",
            "name": "Malabar Roast 500g",
            "price_minor": 45000,  # ₹450.00
            "currency": "INR",
            "tax_rate_bps": 1800,  # 18% GST -> 8100 paise per unit
        },
    ).json()
    prod_id = int(prod["id"])

    client.post(
        "/api/v1/inventory/adjustments",
        headers=hdrs_a,
        json={"product_id": prod_id, "quantity_delta": 10, "reason": "Initial stock"},
    )

    # Create order with Idempotency-Key (2 units): subtotal 90000, tax 16200, discount 5000 -> total 101200
    order_payload = {
        "customer_id": cust_a_id,
        "items": [{"product_id": prod_id, "quantity": 2}],
        "discount_minor": 5000,
    }
    o_resp = client.post(
        "/api/v1/orders",
        headers=_headers(u_a["access_token"], org_a, idemp="ORD-KEY-1"),
        json=order_payload,
    )
    assert o_resp.status_code == 201, o_resp.text
    order = o_resp.json()
    assert order["status"] == "PENDING_PAYMENT"
    assert order["payment_status"] == "UNPAID"
    assert order["subtotal_minor"] == 90000
    assert order["tax_minor"] == 16200
    assert order["discount_minor"] == 5000
    assert order["total_minor"] == 101200
    assert order["total"] == "1012.00"
    assert order["lines"][0]["unit_price_minor"] == 45000

    # Idempotent replay returns same order; mismatched payload returns 409
    replay = client.post(
        "/api/v1/orders",
        headers=_headers(u_a["access_token"], org_a, idemp="ORD-KEY-1"),
        json=order_payload,
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == order["id"]

    mismatch = client.post(
        "/api/v1/orders",
        headers=_headers(u_a["access_token"], org_a, idemp="ORD-KEY-1"),
        json={"customer_id": cust_a_id, "items": [{"product_id": prod_id, "quantity": 3}]},
    )
    assert mismatch.status_code == 409

    # Updating product price later must NOT alter historical order snapshot
    client.patch(
        f"/api/v1/products/{prod_id}",
        headers=hdrs_a,
        json={"price_minor": 99900},
    )
    fetched = client.get(f"/api/v1/orders/{order['id']}", headers=hdrs_a).json()
    assert fetched["total_minor"] == 101200
    assert fetched["lines"][0]["unit_price_minor"] == 45000

    # Cross-tenant order isolation
    assert client.get(f"/api/v1/orders/{order['id']}", headers=hdrs_b).status_code == 404

    # Arbitrary transition to PROCESSING/FULFILLED before PAID must fail (409)
    assert (
        client.post(
            f"/api/v1/orders/{order['id']}/transition",
            headers=hdrs_a,
            json={"target_status": "PROCESSING"},
        ).status_code
        == 409
    )

    # Cancel order -> transitions to CANCELLED and releases 2 reserved units
    cancelled = client.post(
        f"/api/v1/orders/{order['id']}/transition",
        headers=hdrs_a,
        json={"target_status": "CANCELLED", "reason": "Customer requested cancel"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["payment_status"] == "CANCELLED"

    inv = client.get("/api/v1/inventory", headers=hdrs_a).json()
    assert inv["items"][0]["on_hand"] == 10
    assert inv["items"][0]["reserved"] == 0
    assert inv["items"][0]["available"] == 10


def test_concurrent_order_checkout_cannot_oversell_inventory(client):
    u = _signup(client, "conc-ord@example.com")
    tok = u["access_token"]
    org_id = _create_org(client, tok, "Concurrent Shop", "conc-shop")
    hdrs = _headers(tok, org_id)

    prod = client.post(
        "/api/v1/products",
        headers=hdrs,
        json={"sku": "LIM-5", "name": "Limited Item", "price_minor": 50000},
    ).json()
    prod_id = int(prod["id"])

    loc = client.post(
        "/api/v1/inventory/locations",
        headers=hdrs,
        json={"code": "DEL-1", "name": "Delhi Store"},
    ).json()
    loc_id = loc["id"]

    client.post(
        "/api/v1/inventory/adjustments",
        headers=hdrs,
        json={
            "product_id": prod_id,
            "location_id": loc_id,
            "quantity_delta": 5,
            "reason": "Seed 5 units",
        },
    )

    def place_order(idx):
        with TestClient(app, headers=hdrs) as c:
            return c.post(
                "/api/v1/orders",
                headers={"Idempotency-Key": f"CONC-ORD-{idx}"},
                json={
                    "items": [{"product_id": prod_id, "location_id": loc_id, "quantity": 1}]
                },
            )

    with ThreadPoolExecutor(max_workers=10) as pool:
        responses = list(pool.map(place_order, range(10)))

    created = [r for r in responses if r.status_code == 201]
    rejected = [r for r in responses if r.status_code == 409]
    assert len(created) == 5
    assert len(rejected) == 5

    inv = client.get("/api/v1/inventory", headers=hdrs).json()
    assert inv["items"][0]["on_hand"] == 5
    assert inv["items"][0]["reserved"] == 5
    assert inv["items"][0]["available"] == 0
