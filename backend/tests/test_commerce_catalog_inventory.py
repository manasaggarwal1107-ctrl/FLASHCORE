from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.services import inventory_service


def _signup(client, email: str) -> dict:
    resp = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "Flashcore-Catalog-Pass-99"},
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


def _headers(token: str, org_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organisation-Id": str(org_id)}


def test_commerce_product_crud_tenant_scoped_sku_and_minor_units(client):
    u_a = _signup(client, "cat-a@example.com")
    u_b = _signup(client, "cat-b@example.com")
    org_a = _create_org(client, u_a["access_token"], "Org A", "cat-org-a")
    org_b = _create_org(client, u_b["access_token"], "Org B", "cat-org-b")

    # Org A creates product with INR minor units (10050 paise = ₹100.50)
    r_a = client.post(
        "/api/v1/products",
        headers=_headers(u_a["access_token"], org_a),
        json={
            "sku": "SKU-SHARED-1",
            "name": "Organic Green Tea",
            "category": "Beverages",
            "price_minor": 10050,
            "currency": "INR",
            "tax_rate_bps": 500,
        },
    )
    assert r_a.status_code == 201, r_a.text
    prod_a = r_a.json()
    assert prod_a["price_minor"] == 10050
    assert prod_a["price"] == "100.50"
    assert prod_a["origin"] == "real"

    # Duplicate SKU inside Org A -> 409
    assert (
        client.post(
            "/api/v1/products",
            headers=_headers(u_a["access_token"], org_a),
            json={"sku": "SKU-SHARED-1", "name": "Dup", "price_minor": 100},
        ).status_code
        == 409
    )

    # Same SKU inside Org B -> 201 (tenant-scoped SKU uniqueness)
    r_b = client.post(
        "/api/v1/products",
        headers=_headers(u_b["access_token"], org_b),
        json={"sku": "SKU-SHARED-1", "name": "Org B Tea", "price_minor": 25000},
    )
    assert r_b.status_code == 201
    prod_b_id = r_b.json()["id"]

    # Cross-tenant read & patch blocked (404)
    assert (
        client.get(
            f"/api/v1/products/{prod_b_id}",
            headers=_headers(u_a["access_token"], org_a),
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/products/{prod_b_id}",
            headers=_headers(u_a["access_token"], org_a),
            json={"name": "Tampered"},
        ).status_code
        == 404
    )

    # Update Org A product
    upd = client.patch(
        f"/api/v1/products/{prod_a['id']}",
        headers=_headers(u_a["access_token"], org_a),
        json={"price_minor": 12500, "status": "active"},
    )
    assert upd.status_code == 200
    assert upd.json()["price"] == "125.00"


def test_inventory_locations_adjustments_movements_and_reservations(
    client, db_session
):
    u = _signup(client, "inv-owner@example.com")
    tok = u["access_token"]
    org_id = _create_org(client, tok, "Inv Org", "inv-org")
    hdrs = _headers(tok, org_id)

    prod = client.post(
        "/api/v1/products",
        headers=hdrs,
        json={"sku": "INV-1", "name": "Desk Lamp", "price_minor": 199900},
    ).json()
    loc = client.post(
        "/api/v1/inventory/locations",
        headers=hdrs,
        json={"code": "BLR-WH1", "name": "Bengaluru Hub", "location_type": "warehouse"},
    )
    assert loc.status_code == 201
    loc_id = loc.json()["id"]

    adj = client.post(
        "/api/v1/inventory/adjustments",
        headers=hdrs,
        json={
            "product_id": int(prod["id"]),
            "location_id": loc_id,
            "quantity_delta": 10,
            "reason": "Initial opening stock",
        },
    )
    assert adj.status_code == 200, adj.text
    assert adj.json()["on_hand"] == 10
    assert adj.json()["available"] == 10

    # Reserve 4 units via service helper and confirm movement + invariant
    bal_id = adj.json()["id"]
    # Seed dummy order row directly for reservation unit test
    order_id = db_session.execute(
        text(
            """
            INSERT INTO orders (organisation_id, order_number, currency, subtotal_minor, total_minor, order_status, payment_status)
            VALUES (:org_id, 'ORD-RES-1', 'INR', 1000, 1000, 'PENDING_PAYMENT', 'UNPAID')
            RETURNING id
            """
        ),
        {"org_id": org_id},
    ).scalar_one()
    item_id = db_session.execute(
        text(
            """
            INSERT INTO order_items (organisation_id, order_id, product_id, location_id, sku_snapshot, name_snapshot, unit_price_minor, quantity, line_total_minor)
            VALUES (:org_id, :oid, :pid, :lid, 'INV-1', 'Desk Lamp', 199900, 4, 799600)
            RETURNING id
            """
        ),
        {"org_id": org_id, "oid": order_id, "pid": int(prod["id"]), "lid": loc_id},
    ).scalar_one()
    db_session.commit()

    inventory_service.reserve_stock_for_order(
        db_session,
        organisation_id=org_id,
        order_id=order_id,
        order_item_allocations=[(item_id, int(prod["id"]), loc_id, 4)],
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        actor_ref="inv-owner@example.com",
    )
    db_session.commit()

    # Negative adjustment below reserved (10 - 7 = 3 < 4 reserved) must be rejected 409
    bad_adj = client.post(
        "/api/v1/inventory/adjustments",
        headers=hdrs,
        json={
            "product_id": int(prod["id"]),
            "location_id": loc_id,
            "quantity_delta": -7,
            "reason": "Too large writeoff",
        },
    )
    assert bad_adj.status_code == 409

    # Expire stale reservation -> releases 4 back to available and marks order EXPIRED
    exp = client.post("/api/v1/inventory/reservations/expire", headers=hdrs)
    assert exp.status_code == 200
    assert exp.json()["expired_orders"] == 1

    balances = client.get("/api/v1/inventory", headers=hdrs).json()
    assert balances["items"][0]["on_hand"] == 10
    assert balances["items"][0]["reserved"] == 0
    assert balances["items"][0]["available"] == 10

    movements = client.get("/api/v1/inventory/movements", headers=hdrs).json()
    types = [m["type"] for m in movements["items"]]
    assert "adjustment" in types
    assert "reservation" in types
    assert "expiry" in types
