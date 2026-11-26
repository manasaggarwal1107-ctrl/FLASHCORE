from datetime import datetime, timezone
from sqlalchemy import text
from app.models.rossmann import DatasetImport, DatasetImportError, AuditLog


def test_health_endpoints(client):
    r1 = client.get("/health")
    assert r1.status_code == 200
    assert r1.json() == {"status": "healthy"}

    r2 = client.get("/health/database")
    assert r2.status_code == 200
    assert r2.json()["status"] == "connected"

    r3 = client.get("/api/health")
    assert r3.status_code == 200
    data = r3.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["version"] == "1.0.0"
    assert "database" in data
    assert isinstance(data["services"], list)
    assert len(data["services"]) >= 1

    r4 = client.get("/api/health/database")
    assert r4.status_code == 200
    assert r4.json()["status"] == "connected"


def test_imports_list_empty(authenticated_client):
    res = authenticated_client.get("/api/imports")
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_imports_list_and_detail(authenticated_client, db_session):
    imp = DatasetImport(
        source_name="Rossmann Store Sales",
        source_url="https://kaggle.com/c/rossmann",
        source_file="train.csv",
        source_split="train",
        checksum_sha256="abc123sha",
        total_rows=100,
        successful_rows=95,
        rejected_rows=5,
        status="completed",
    )
    db_session.add(imp)
    db_session.commit()

    err = DatasetImportError(
        import_id=imp.id,
        source_row_number=12,
        raw_record={"store_id": "bad"},
        error_message="Invalid store_id format",
    )
    db_session.add(err)
    db_session.commit()

    # List
    res = authenticated_client.get("/api/imports")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["filename"] == "train.csv"
    assert data["items"][0]["imported_rows"] == 95
    assert data["items"][0]["rejected_rows"] == 5

    # Detail
    res_det = authenticated_client.get(f"/api/imports/{imp.id}")
    assert res_det.status_code == 200
    det = res_det.json()
    assert det["filename"] == "train.csv"
    assert len(det["errors"]) == 1
    assert det["errors"][0]["row"] == 12
    assert "Invalid store_id" in det["errors"][0]["message"]

    # 404
    res_404 = authenticated_client.get("/api/imports/999999")
    assert res_404.status_code == 404


def test_imports_authorization(client, db_session):
    # Unauthenticated
    assert client.get("/api/imports").status_code == 401

    # Operator role (forbidden)
    signup = client.post(
        "/api/auth/signup",
        json={
            "email": "operator-imports@flashcore.local",
            "password": "Flashcore-Test-Pass-1234",
        },
    )
    assert signup.status_code == 201
    token = signup.json()["access_token"]

    db_session.execute(
        text("UPDATE users SET role = 'operator' WHERE email = 'operator-imports@flashcore.local'")
    )
    db_session.commit()

    res = client.get("/api/imports", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_audit_logs_list(authenticated_client, db_session):
    log = AuditLog(
        actor_type="admin",
        actor_ref="admin@flashcore.local",
        action="user_role_updated",
        entity_name="users",
        entity_id="10",
        details={
            "role": "operator",
            "secret_token": "supersecret",
            "password_hash": "hash123",
            "status": "success",
        },
    )
    db_session.add(log)
    db_session.commit()

    res = authenticated_client.get("/api/admin/audit-logs")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    item = next(i for i in data["items"] if i["id"] == str(log.id))
    assert item["action"] == "user_role_updated"
    assert item["entity_type"] == "users"
    assert item["entity_ref"] == "10"
    assert item["outcome"] == "success"
    # Ensure sensitive fields are redacted!
    assert item["metadata"]["secret_token"] == "[REDACTED]"
    assert item["metadata"]["password_hash"] == "[REDACTED]"


def test_audit_logs_authorization(client, db_session):
    # Unauthenticated
    assert client.get("/api/admin/audit-logs").status_code == 401

    # Analyst role (forbidden for admin routes)
    signup = client.post(
        "/api/auth/signup",
        json={
            "email": "analyst-audit@flashcore.local",
            "password": "Flashcore-Test-Pass-1234",
        },
    )
    assert signup.status_code == 201
    token = signup.json()["access_token"]
    # default role is analyst

    res = client.get(
        "/api/admin/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_simulation_strategies(client):
    res = client.get("/api/simulations/strategies")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    ids = [s["id"] for s in data["items"]]
    assert "atomic_update" in ids
    assert "select_for_update" in ids


def test_simulation_overview_analytics(authenticated_client):
    r1 = authenticated_client.get("/api/simulations/analytics/purchase-outcomes")
    assert r1.status_code == 200
    d1 = r1.json()
    assert "successful" in d1
    assert "failed" in d1
    assert "origin" in d1

    r2 = authenticated_client.get("/api/simulations/analytics/inventory-allocation")
    assert r2.status_code == 200
    d2 = r2.json()
    assert "physical" in d2
    assert "flash_sale" in d2

    r3 = authenticated_client.get("/api/simulations/analytics/flash-sales-overview")
    assert r3.status_code == 200
    d3 = r3.json()
    assert "items" in d3

    r4 = authenticated_client.get("/api/simulations/analytics/activity")
    assert r4.status_code == 200
    d4 = r4.json()
    assert "items" in d4
