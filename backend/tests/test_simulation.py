from sqlalchemy import text


def test_create_simulation_run(authenticated_client):
    response = authenticated_client.post(
        "/api/simulations/runs",
        json={
            "run_name": "Test Retail Simulation",
            "description": "Automated backend test",
            "configuration": {
                "store_count": 2,
                "duration_days": 7,
            },
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["run_name"] == "Test Retail Simulation"
    assert data["description"] == "Automated backend test"
    assert data["configuration"] == {
        "store_count": 2,
        "duration_days": 7,
    }
    assert data["status"] == "created"
    assert data["id"] is not None


def test_created_run_is_listed(authenticated_client):
    created = authenticated_client.post(
        "/api/simulations/runs",
        json={"run_name": "Listed Run"},
    )

    assert created.status_code == 201
    run_id = created.json()["id"]

    response = authenticated_client.get("/api/simulations/runs")

    assert response.status_code == 200

    runs = response.json()

    assert len(runs) == 1
    assert runs[0]["id"] == run_id
    assert runs[0]["run_name"] == "Listed Run"


def test_run_creation_writes_audit_record(authenticated_client, db_session):
    response = authenticated_client.post(
        "/api/simulations/runs",
        json={"run_name": "Audited Run"},
    )

    assert response.status_code == 201

    run_id = response.json()["id"]

    audit = db_session.execute(
        text("""
            SELECT action, entity_name, entity_id
            FROM audit_logs
            WHERE entity_name = 'simulation_runs'
              AND entity_id = :run_id
        """),
        {"run_id": str(run_id)},
    ).mappings().one()

    assert audit["action"] == "simulation_created"
    assert audit["entity_name"] == "simulation_runs"
    assert audit["entity_id"] == str(run_id)


def test_new_run_has_empty_summary(authenticated_client):
    created = authenticated_client.post(
        "/api/simulations/runs",
        json={"run_name": "Empty Summary Run"},
    )

    assert created.status_code == 201

    run_id = created.json()["id"]

    response = authenticated_client.get(
        f"/api/simulations/runs/{run_id}/summary"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["run"]["id"] == run_id
    assert data["purchases"]["total_attempts"] == 0
    assert data["purchases"]["successful"] == 0
    assert data["purchases"]["rejected"] == 0
    assert data["purchases"]["failed"] == 0
    assert data["purchases"]["units_sold"] == 0
    assert data["flash_sales"] == []


def test_missing_simulation_run_returns_404(authenticated_client):
    response = authenticated_client.get(
        "/api/simulations/runs/999999/summary"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Simulation run not found"


def test_run_creation_rejects_empty_name(authenticated_client):
    response = authenticated_client.post(
        "/api/simulations/runs",
        json={"run_name": ""},
    )

    assert response.status_code == 422


def test_create_simulation_product(authenticated_client):
    response = authenticated_client.post(
        "/api/simulations/products",
        json={
            "sku": "TEST-SKU-001",
            "name": "Test Product",
            "description": "Product for automated testing",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["sku"] == "TEST-SKU-001"
    assert data["name"] == "Test Product"
    assert data["description"] == "Product for automated testing"
    assert data["id"] is not None


def test_created_product_appears_in_product_list(authenticated_client):
    created = authenticated_client.post(
        "/api/simulations/products",
        json={
            "sku": "LIST-SKU-001",
            "name": "Listed Product",
        },
    )

    assert created.status_code == 201

    product_id = created.json()["id"]

    response = authenticated_client.get("/api/simulations/products")

    assert response.status_code == 200

    products = response.json()

    assert len(products) == 1
    assert products[0]["id"] == product_id
    assert products[0]["sku"] == "LIST-SKU-001"


def test_duplicate_product_sku_returns_409(authenticated_client):
    payload = {
        "sku": "DUPLICATE-SKU",
        "name": "Original Product",
    }

    first = authenticated_client.post(
        "/api/simulations/products",
        json=payload,
    )

    second = authenticated_client.post(
        "/api/simulations/products",
        json={
            "sku": "DUPLICATE-SKU",
            "name": "Second Product",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_product_creation_rejects_empty_fields(authenticated_client):
    response = authenticated_client.post(
        "/api/simulations/products",
        json={
            "sku": "",
            "name": "",
        },
    )

    assert response.status_code == 422


def test_product_creation_writes_audit_record(authenticated_client, db_session):
    response = authenticated_client.post(
        "/api/simulations/products",
        json={
            "sku": "AUDIT-SKU",
            "name": "Audited Product",
        },
    )

    assert response.status_code == 201

    product_id = response.json()["id"]

    audit = db_session.execute(
        text("""
            SELECT action, entity_name, details
            FROM audit_logs
            WHERE entity_name = 'simulation_products'
              AND entity_id = :product_id
        """),
        {"product_id": str(product_id)},
    ).mappings().one()

    assert audit["action"] == "product_created"
    assert audit["entity_name"] == "simulation_products"
    assert audit["details"]["sku"] == "AUDIT-SKU"
    assert audit["details"]["name"] == "Audited Product"
