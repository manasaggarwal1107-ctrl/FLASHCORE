from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.models.rossmann import AuditLog, Store


def _signup(client, email: str, password: str = "Flashcore-Tenant-Pass-99") -> dict:
    resp = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _auth_headers(token: str, org_id: int | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if org_id is not None:
        headers["X-Organisation-Id"] = str(org_id)
    return headers


def test_organisation_creation_and_platform_admin_separation(client):
    signup = _signup(client, "org-creator@example.com")
    token = signup["access_token"]

    # User starts in default-workspace as analyst
    orgs = client.get("/api/organisations", headers=_auth_headers(token))
    assert orgs.status_code == 200
    assert any(o["slug"] == "default-workspace" for o in orgs.json())

    # Create a dedicated organisation -> user becomes 'owner' of that org
    created = client.post(
        "/api/organisations",
        headers=_auth_headers(token),
        json={"name": "Acme Retail India", "slug": "acme-retail-india"},
    )
    assert created.status_code == 201, created.text
    org_data = created.json()
    assert org_data["slug"] == "acme-retail-india"
    assert org_data["role"] == "owner"

    # Duplicate slug is rejected
    dup = client.post(
        "/api/organisations",
        headers=_auth_headers(token),
        json={"name": "Acme Duplicate", "slug": "acme-retail-india"},
    )
    assert dup.status_code == 409

    # Organisation owner must NOT automatically become platform administrator
    platform_users = client.get(
        "/api/admin/users",
        headers=_auth_headers(token, org_data["organisation_id"]),
    )
    assert platform_users.status_code == 403


def test_membership_management_rbac_and_revocation(client):
    owner = _signup(client, "owner-a@example.com")
    member = _signup(client, "member-a@example.com")
    outsider = _signup(client, "outsider@example.com")

    org_resp = client.post(
        "/api/organisations",
        headers=_auth_headers(owner["access_token"]),
        json={"name": "Org Alpha", "slug": "org-alpha"},
    )
    assert org_resp.status_code == 201
    org_id = org_resp.json()["organisation_id"]

    # Add member as operator
    added = client.post(
        f"/api/organisations/{org_id}/memberships",
        headers=_auth_headers(owner["access_token"], org_id),
        json={"email": "member-a@example.com", "role": "operator"},
    )
    assert added.status_code == 201, added.text
    assert added.json()["role"] == "operator"

    # Outsider cannot list memberships
    assert (
        client.get(
            f"/api/organisations/{org_id}/memberships",
            headers=_auth_headers(outsider["access_token"]),
        ).status_code
        == 403
    )

    # Operator cannot list memberships or access audit logs
    assert (
        client.get(
            f"/api/organisations/{org_id}/memberships",
            headers=_auth_headers(member["access_token"], org_id),
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/admin/audit-logs",
            headers=_auth_headers(member["access_token"], org_id),
        ).status_code
        == 403
    )

    # Operator CAN create a run in Org Alpha
    run_ok = client.post(
        "/api/simulations/runs",
        headers=_auth_headers(member["access_token"], org_id),
        json={"run_name": "Alpha Run", "configuration": {}},
    )
    assert run_ok.status_code == 201

    # Cannot demote or revoke the last active owner
    assert (
        client.patch(
            f"/api/organisations/{org_id}/memberships/{owner['user']['id']}",
            headers=_auth_headers(owner["access_token"], org_id),
            json={"role": "admin"},
        ).status_code
        == 409
    )

    # Revoke member's access to Org Alpha
    revoked = client.patch(
        f"/api/organisations/{org_id}/memberships/{member['user']['id']}",
        headers=_auth_headers(owner["access_token"], org_id),
        json={"status": "revoked"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"

    # Revoked member is blocked immediately from Org Alpha
    assert (
        client.get(
            "/api/simulations/runs",
            headers=_auth_headers(member["access_token"], org_id),
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/auth/me",
            headers=_auth_headers(member["access_token"], org_id),
        ).status_code
        == 403
    )

    # /api/auth/me without header no longer lists Org Alpha
    me = client.get("/api/auth/me", headers=_auth_headers(member["access_token"]))
    assert me.status_code == 200
    assert all(
        o["organisation_id"] != org_id for o in me.json()["organisations"]
    )


def test_user_with_multiple_organisations_has_distinct_per_org_roles(client, db_session):
    user = _signup(client, "multi-org@example.com")
    token = user["access_token"]
    user_id = user["user"]["id"]

    # Even if user is a platform admin globally, org membership role must govern org routes
    db_session.execute(
        text("UPDATE users SET role = 'admin' WHERE id = :id"),
        {"id": user_id},
    )
    db_session.commit()

    org_a = client.post(
        "/api/organisations",
        headers=_auth_headers(token),
        json={"name": "Org One", "slug": "org-one"},
    ).json()["organisation_id"]

    other_owner = _signup(client, "other-owner@example.com")
    org_b = client.post(
        "/api/organisations",
        headers=_auth_headers(other_owner["access_token"]),
        json={"name": "Org Two", "slug": "org-two"},
    ).json()["organisation_id"]

    # Add multi-org user as 'analyst' (read-only) in Org Two
    add_b = client.post(
        f"/api/organisations/{org_b}/memberships",
        headers=_auth_headers(other_owner["access_token"], org_b),
        json={"user_id": user_id, "role": "analyst"},
    )
    assert add_b.status_code == 201

    # In Org One (owner) -> can create simulation run
    assert (
        client.post(
            "/api/simulations/runs",
            headers=_auth_headers(token, org_a),
            json={"run_name": "Org One Run", "configuration": {}},
        ).status_code
        == 201
    )

    # In Org Two (analyst) -> blocked 403 from creating simulation run, allowed GET
    assert (
        client.post(
            "/api/simulations/runs",
            headers=_auth_headers(token, org_b),
            json={"run_name": "Org Two Forbidden", "configuration": {}},
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/simulations/runs",
            headers=_auth_headers(token, org_b),
        ).status_code
        == 200
    )


def test_cross_tenant_isolation_blocks_read_update_delete_and_id_guessing(
    client, db_session
):
    db_session.add(
        Store(
            store_id=701,
            store_type="a",
            assortment="a",
            competition_distance=300,
            promo2=False,
        )
    )
    db_session.commit()

    user_a = _signup(client, "tenant-a@example.com")
    user_b = _signup(client, "tenant-b@example.com")
    tok_a = user_a["access_token"]
    tok_b = user_b["access_token"]

    org_a = client.post(
        "/api/organisations",
        headers=_auth_headers(tok_a),
        json={"name": "Tenant A", "slug": "tenant-a"},
    ).json()["organisation_id"]
    org_b = client.post(
        "/api/organisations",
        headers=_auth_headers(tok_b),
        json={"name": "Tenant B", "slug": "tenant-b"},
    ).json()["organisation_id"]

    # Seed full simulation workflow inside Tenant B
    run_b = client.post(
        "/api/simulations/runs",
        headers=_auth_headers(tok_b, org_b),
        json={"run_name": "Tenant B Secret Run", "configuration": {}},
    ).json()["id"]
    prod_b = client.post(
        "/api/simulations/products",
        headers=_auth_headers(tok_b, org_b),
        json={"sku": "SHARED-SKU-001", "name": "Tenant B Product"},
    ).json()["id"]
    inv_b = client.post(
        "/api/simulations/inventory",
        headers=_auth_headers(tok_b, org_b),
        json={"store_id": 701, "product_id": prod_b, "quantity": 50},
    ).json()["id"]

    now = datetime.now(timezone.utc)
    sale_b = client.post(
        f"/api/simulations/runs/{run_b}/flash-sales",
        headers=_auth_headers(tok_b, org_b),
        json={
            "title": "Tenant B Flash Sale",
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(hours=2)).isoformat(),
        },
    ).json()["id"]
    assert (
        client.post(
            f"/api/simulations/flash-sales/{sale_b}/activate",
            headers=_auth_headers(tok_b, org_b),
        ).status_code
        == 200
    )
    fsp_b = client.post(
        f"/api/simulations/flash-sales/{sale_b}/products",
        headers=_auth_headers(tok_b, org_b),
        json={"inventory_id": inv_b, "sale_price": "199.00", "stock_limit": 10},
    ).json()["id"]
    purchase_b = client.post(
        f"/api/simulations/flash-sale-products/{fsp_b}/purchase",
        headers=_auth_headers(tok_b, org_b),
        json={
            "customer_ref": "CUST-B-1",
            "idempotency_key": "SHARED-IDEMP-KEY-1",
            "quantity": 1,
        },
    )
    assert purchase_b.status_code == 200
    attempt_b_id = purchase_b.json()["attempt"]["id"]

    # Tenant A can create its own product with the SAME SKU and purchase with the SAME idempotency key!
    prod_a_resp = client.post(
        "/api/simulations/products",
        headers=_auth_headers(tok_a, org_a),
        json={"sku": "SHARED-SKU-001", "name": "Tenant A Product"},
    )
    assert prod_a_resp.status_code == 201
    prod_a = prod_a_resp.json()["id"]

    run_a = client.post(
        "/api/simulations/runs",
        headers=_auth_headers(tok_a, org_a),
        json={"run_name": "Tenant A Run", "configuration": {}},
    ).json()["id"]
    inv_a = client.post(
        "/api/simulations/inventory",
        headers=_auth_headers(tok_a, org_a),
        json={"store_id": 701, "product_id": prod_a, "quantity": 20},
    ).json()["id"]
    sale_a = client.post(
        f"/api/simulations/runs/{run_a}/flash-sales",
        headers=_auth_headers(tok_a, org_a),
        json={
            "title": "Tenant A Flash Sale",
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(hours=2)).isoformat(),
        },
    ).json()["id"]
    client.post(
        f"/api/simulations/flash-sales/{sale_a}/activate",
        headers=_auth_headers(tok_a, org_a),
    )
    fsp_a = client.post(
        f"/api/simulations/flash-sales/{sale_a}/products",
        headers=_auth_headers(tok_a, org_a),
        json={"inventory_id": inv_a, "sale_price": "99.00", "stock_limit": 5},
    ).json()["id"]
    purchase_a = client.post(
        f"/api/simulations/flash-sale-products/{fsp_a}/purchase",
        headers=_auth_headers(tok_a, org_a),
        json={
            "customer_ref": "CUST-A-1",
            "idempotency_key": "SHARED-IDEMP-KEY-1",
            "quantity": 1,
        },
    )
    assert purchase_a.status_code == 200
    assert purchase_a.json().get("duplicate") is not True
    assert purchase_a.json()["attempt"]["id"] != attempt_b_id

    # 1. Tenant A forging X-Organisation-Id for Tenant B is rejected (403)
    assert (
        client.get(
            "/api/simulations/runs",
            headers=_auth_headers(tok_a, org_b),
        ).status_code
        == 403
    )

    # 2. Tenant A guessing Tenant B's IDs under Tenant A's context is blocked (404/409)
    assert (
        client.get(
            f"/api/simulations/runs/{run_b}/summary",
            headers=_auth_headers(tok_a, org_a),
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/simulations/inventory",
            headers=_auth_headers(tok_a, org_a),
            json={"store_id": 701, "product_id": prod_b, "quantity": 5},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/simulations/inventory/{inv_b}/adjust",
            headers=_auth_headers(tok_a, org_a),
            json={"quantity_delta": 5, "reason": "Cross-tenant tamper attempt"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/simulations/runs/{run_b}/flash-sales",
            headers=_auth_headers(tok_a, org_a),
            json={
                "title": "Cross-tenant sale",
                "starts_at": (now + timedelta(hours=1)).isoformat(),
                "ends_at": (now + timedelta(hours=2)).isoformat(),
            },
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/simulations/flash-sales/{sale_b}/activate",
            headers=_auth_headers(tok_a, org_a),
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/simulations/flash-sales/{sale_b}/products",
            headers=_auth_headers(tok_a, org_a),
            json={"inventory_id": inv_a, "sale_price": "10.00", "stock_limit": 1},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/simulations/flash-sales/{sale_a}/products",
            headers=_auth_headers(tok_a, org_a),
            json={"inventory_id": inv_b, "sale_price": "10.00", "stock_limit": 1},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/simulations/flash-sale-products/{fsp_b}/purchase",
            headers=_auth_headers(tok_a, org_a),
            json={
                "customer_ref": "ATTACKER",
                "idempotency_key": "CROSS-TENANT-PURCHASE",
                "quantity": 1,
            },
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/simulations/transactions/{attempt_b_id}",
            headers=_auth_headers(tok_a, org_a),
        ).status_code
        == 404
    )

    # 3. Tenant A list & analytics endpoints return ONLY Tenant A's data
    runs_a = client.get("/api/simulations/runs", headers=_auth_headers(tok_a, org_a)).json()
    assert [r["id"] for r in runs_a] == [run_a]

    prods_a = client.get("/api/simulations/products", headers=_auth_headers(tok_a, org_a)).json()
    assert [p["id"] for p in prods_a] == [prod_a]

    invs_a = client.get("/api/simulations/inventory", headers=_auth_headers(tok_a, org_a)).json()
    assert [i["id"] for i in invs_a] == [inv_a]

    txns_a = client.get("/api/simulations/transactions", headers=_auth_headers(tok_a, org_a)).json()
    assert txns_a["total"] == 1
    assert int(txns_a["items"][0]["id"]) == purchase_a.json()["attempt"]["id"]

    alloc_a = client.get(
        "/api/simulations/analytics/inventory-allocation",
        headers=_auth_headers(tok_a, org_a),
    ).json()
    assert alloc_a["physical"]["on_hand"] == 19
    assert alloc_a["physical"]["sold"] == 1

    audits_a = client.get("/api/admin/audit-logs", headers=_auth_headers(tok_a, org_a)).json()
    assert all(
        "Tenant B" not in str(item) and "CUST-B-1" not in str(item)
        for item in audits_a["items"]
    )


def test_audit_actor_identity_admin_auditing_and_pagination_fixes(
    client, authenticated_client, db_session
):
    # Create a simulation run -> audit log must identify the authenticated user, not "system"
    run_resp = authenticated_client.post(
        "/api/simulations/runs",
        json={"run_name": "Audit Actor Run", "configuration": {}},
    )
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]

    audit = db_session.execute(
        text(
            "SELECT actor_type, actor_ref FROM audit_logs "
            "WHERE entity_name = 'simulation_runs' AND entity_id = :id"
        ),
        {"id": str(run_id)},
    ).mappings().one()
    assert audit["actor_type"] == "admin"
    assert audit["actor_ref"] == "test-admin@flashcore.local"

    # Admin role/status update creates audit log entries
    target = _signup(client, "audit-target@example.com")
    role_res = authenticated_client.patch(
        f"/api/admin/users/{target['user']['id']}/role",
        json={"role": "operator"},
    )
    assert role_res.status_code == 200

    status_res = authenticated_client.patch(
        f"/api/admin/users/{target['user']['id']}/status",
        json={"status": "disabled"},
    )
    assert status_res.status_code == 200

    role_audit = db_session.execute(
        text(
            "SELECT actor_type, actor_ref, action, details FROM audit_logs "
            "WHERE action = 'user_role_updated' AND entity_id = :uid"
        ),
        {"uid": str(target["user"]["id"])},
    ).mappings().one()
    assert role_audit["actor_ref"] == "test-admin@flashcore.local"
    assert role_audit["details"]["new_role"] == "operator"

    # Outcome pagination must filter in SQL before LIMIT/OFFSET
    org_id = db_session.execute(
        text("SELECT id FROM organisations WHERE slug = 'default-workspace'")
    ).scalar_one()
    for idx in range(3):
        db_session.add(
            AuditLog(
                organisation_id=org_id,
                actor_type="admin",
                actor_ref="test-admin@flashcore.local",
                action="outcome_test_failed",
                entity_name="test_entity",
                entity_id=str(idx),
                details={"status": "failed"},
            )
        )
    for idx in range(4):
        db_session.add(
            AuditLog(
                organisation_id=org_id,
                actor_type="admin",
                actor_ref="test-admin@flashcore.local",
                action="outcome_test_success",
                entity_name="test_entity",
                entity_id=str(idx),
                details={"status": "success"},
            )
        )
    db_session.commit()

    page1 = authenticated_client.get(
        "/api/admin/audit-logs",
        params={"entityType": "test_entity", "outcome": "failed", "page": 1, "pageSize": 2},
    )
    assert page1.status_code == 200
    d1 = page1.json()
    assert d1["total"] == 3
    assert len(d1["items"]) == 2
    assert all(i["outcome"] == "failed" for i in d1["items"])

    page2 = authenticated_client.get(
        "/api/admin/audit-logs",
        params={"entityType": "test_entity", "outcome": "failed", "page": 2, "pageSize": 2},
    )
    assert page2.status_code == 200
    d2 = page2.json()
    assert d2["total"] == 3
    assert len(d2["items"]) == 1


def test_transaction_date_validation_returns_422(authenticated_client):
    bad_from = authenticated_client.get(
        "/api/simulations/transactions",
        params={"from": "not-a-valid-date"},
    )
    assert bad_from.status_code == 422

    bad_to = authenticated_client.get(
        "/api/simulations/transactions",
        params={"to": "2025-99-99"},
    )
    assert bad_to.status_code == 422

    reversed_dates = authenticated_client.get(
        "/api/simulations/transactions",
        params={"from": "2025-05-10", "to": "2025-05-01"},
    )
    assert reversed_dates.status_code == 422
