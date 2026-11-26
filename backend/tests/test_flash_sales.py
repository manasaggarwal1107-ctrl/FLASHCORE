from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.models.rossmann import Store
from main import app


@pytest.fixture
def flash_sale_setup(authenticated_client, db_session):
    store = Store(
        store_id=301,
        store_type="a",
        assortment="a",
        competition_distance=500,
        promo2=False,
    )
    db_session.add(store)
    db_session.commit()

    run_response = authenticated_client.post(
        "/api/simulations/runs",
        json={
            "run_name": "FLASH-SALE-TEST",
            "description": "Automated flash sale tests",
            "configuration": {},
        },
    )
    assert run_response.status_code == 201
    run_id = run_response.json()["id"]

    product_response = authenticated_client.post(
        "/api/simulations/products",
        json={
            "sku": "FLASH-SALE-TEST-001",
            "name": "Flash Sale Test Product",
        },
    )
    assert product_response.status_code == 201
    product_id = product_response.json()["id"]

    inventory_response = authenticated_client.post(
        "/api/simulations/inventory",
        json={
            "store_id": 301,
            "product_id": product_id,
            "quantity": 100,
        },
    )
    assert inventory_response.status_code == 201

    return {
        "run_id": run_id,
        "store_id": 301,
        "product_id": product_id,
        "inventory_id": inventory_response.json()["id"],
    }


def create_sale(authenticated_client, run_id, starts_at=None, ends_at=None):
    now = datetime.now(timezone.utc)

    if starts_at is None:
        starts_at = now + timedelta(hours=1)

    if ends_at is None:
        ends_at = now + timedelta(hours=2)

    return authenticated_client.post(
        f"/api/simulations/runs/{run_id}/flash-sales",
        json={
            "title": "Test Flash Sale",
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
        },
    )


def test_create_flash_sale(authenticated_client, flash_sale_setup):
    response = create_sale(authenticated_client, flash_sale_setup["run_id"])

    assert response.status_code == 201

    data = response.json()
    assert data["title"] == "Test Flash Sale"
    assert data["simulation_run_id"] == flash_sale_setup["run_id"]
    assert data["status"] == "draft"
    assert data["id"] is not None


def test_flash_sale_creation_writes_audit(
    authenticated_client, db_session, flash_sale_setup
):
    response = create_sale(authenticated_client, flash_sale_setup["run_id"])
    assert response.status_code == 201

    sale_id = response.json()["id"]

    audit = db_session.execute(
        text("""
            SELECT action, entity_name, entity_id
            FROM audit_logs
            WHERE entity_name = 'flash_sales'
              AND entity_id = :entity_id
        """),
        {"entity_id": str(sale_id)},
    ).mappings().first()

    assert audit is not None
    assert audit["action"] == "flash_sale_created"


def test_flash_sale_rejects_naive_datetime(
    authenticated_client, flash_sale_setup
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    response = authenticated_client.post(
        f"/api/simulations/runs/{flash_sale_setup['run_id']}/flash-sales",
        json={
            "title": "Naive Datetime Sale",
            "starts_at": now.isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
        },
    )

    assert response.status_code == 422
    assert "timezone" in response.text.lower()


def test_flash_sale_rejects_equal_start_and_end(
    authenticated_client, flash_sale_setup
):
    now = datetime.now(timezone.utc)

    response = create_sale(
        authenticated_client,
        flash_sale_setup["run_id"],
        starts_at=now,
        ends_at=now,
    )

    assert response.status_code == 422


def test_flash_sale_rejects_end_before_start(
    authenticated_client, flash_sale_setup
):
    now = datetime.now(timezone.utc)

    response = create_sale(
        authenticated_client,
        flash_sale_setup["run_id"],
        starts_at=now + timedelta(hours=2),
        ends_at=now + timedelta(hours=1),
    )

    assert response.status_code == 422


def test_flash_sale_requires_existing_run(authenticated_client):
    response = create_sale(authenticated_client, 999999)

    assert response.status_code == 404
    assert response.json()["detail"] == "Simulation run not found"


def test_activate_future_sale_sets_scheduled_status(
    authenticated_client, flash_sale_setup
):
    now = datetime.now(timezone.utc)

    sale_response = create_sale(
        authenticated_client,
        flash_sale_setup["run_id"],
        starts_at=now + timedelta(days=1),
        ends_at=now + timedelta(days=2),
    )
    assert sale_response.status_code == 201

    sale_id = sale_response.json()["id"]

    response = authenticated_client.post(
        f"/api/simulations/flash-sales/{sale_id}/activate"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "scheduled"


def test_activate_current_sale_sets_active_status(
    authenticated_client, flash_sale_setup
):
    now = datetime.now(timezone.utc)

    sale_response = create_sale(
        authenticated_client,
        flash_sale_setup["run_id"],
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=1),
    )
    assert sale_response.status_code == 201

    sale_id = sale_response.json()["id"]

    response = authenticated_client.post(
        f"/api/simulations/flash-sales/{sale_id}/activate"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_activate_missing_sale_returns_404(authenticated_client):
    response = authenticated_client.post(
        "/api/simulations/flash-sales/999999/activate"
    )

    assert response.status_code == 404


def test_activate_expired_sale_returns_409(
    authenticated_client, flash_sale_setup
):
    now = datetime.now(timezone.utc)

    sale_response = create_sale(
        authenticated_client,
        flash_sale_setup["run_id"],
        starts_at=now - timedelta(days=2),
        ends_at=now - timedelta(days=1),
    )
    assert sale_response.status_code == 201

    sale_id = sale_response.json()["id"]

    response = authenticated_client.post(
        f"/api/simulations/flash-sales/{sale_id}/activate"
    )

    assert response.status_code == 409
    assert "expired" in response.text.lower()


def test_allocate_stock_successfully(
    authenticated_client, db_session, flash_sale_setup
):
    sale_response = create_sale(
        authenticated_client, flash_sale_setup["run_id"]
    )
    assert sale_response.status_code == 201

    sale_id = sale_response.json()["id"]

    response = authenticated_client.post(
        f"/api/simulations/flash-sales/{sale_id}/products",
        json={
            "inventory_id": flash_sale_setup["inventory_id"],
            "sale_price": "49.99",
            "stock_limit": 30,
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["flash_sale_id"] == sale_id
    assert data["inventory_id"] == flash_sale_setup["inventory_id"]
    assert data["stock_limit"] == 30

    inventory = db_session.execute(
        text("""
            SELECT quantity, reserved_quantity
            FROM simulation_inventory
            WHERE id = :id
        """),
        {"id": flash_sale_setup["inventory_id"]},
    ).mappings().one()

    assert inventory["quantity"] == 100
    assert inventory["reserved_quantity"] == 30


def test_allocation_writes_audit(
    authenticated_client, db_session, flash_sale_setup
):
    sale_response = create_sale(
        authenticated_client, flash_sale_setup["run_id"]
    )
    sale_id = sale_response.json()["id"]

    response = authenticated_client.post(
        f"/api/simulations/flash-sales/{sale_id}/products",
        json={
            "inventory_id": flash_sale_setup["inventory_id"],
            "sale_price": "39.99",
            "stock_limit": 20,
        },
    )
    assert response.status_code == 201

    sale_product_id = response.json()["id"]

    audit = db_session.execute(
        text("""
            SELECT action, entity_name, entity_id
            FROM audit_logs
            WHERE entity_name = 'flash_sale_products'
              AND entity_id = :entity_id
        """),
        {"entity_id": str(sale_product_id)},
    ).mappings().first()

    assert audit is not None
    assert audit["action"] == "stock_allocated"


def test_allocation_rejects_insufficient_stock(
    authenticated_client, db_session, flash_sale_setup
):
    sale_response = create_sale(
        authenticated_client, flash_sale_setup["run_id"]
    )
    sale_id = sale_response.json()["id"]

    response = authenticated_client.post(
        f"/api/simulations/flash-sales/{sale_id}/products",
        json={
            "inventory_id": flash_sale_setup["inventory_id"],
            "sale_price": "49.99",
            "stock_limit": 101,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["available"] == 100
    assert response.json()["detail"]["requested"] == 101

    inventory = db_session.execute(
        text("""
            SELECT reserved_quantity
            FROM simulation_inventory
            WHERE id = :id
        """),
        {"id": flash_sale_setup["inventory_id"]},
    ).scalar_one()

    assert inventory == 0


def test_allocation_rejects_missing_sale(
    authenticated_client, flash_sale_setup
):
    response = authenticated_client.post(
        "/api/simulations/flash-sales/999999/products",
        json={
            "inventory_id": flash_sale_setup["inventory_id"],
            "sale_price": "49.99",
            "stock_limit": 10,
        },
    )

    assert response.status_code == 404


def test_allocation_rejects_missing_inventory(
    authenticated_client, flash_sale_setup
):
    sale_response = create_sale(
        authenticated_client, flash_sale_setup["run_id"]
    )
    sale_id = sale_response.json()["id"]

    response = authenticated_client.post(
        f"/api/simulations/flash-sales/{sale_id}/products",
        json={
            "inventory_id": 999999,
            "sale_price": "49.99",
            "stock_limit": 10,
        },
    )

    assert response.status_code == 404


def test_allocation_rejects_nonpositive_stock(
    authenticated_client, flash_sale_setup
):
    sale_response = create_sale(
        authenticated_client, flash_sale_setup["run_id"]
    )
    sale_id = sale_response.json()["id"]

    response = authenticated_client.post(
        f"/api/simulations/flash-sales/{sale_id}/products",
        json={
            "inventory_id": flash_sale_setup["inventory_id"],
            "sale_price": "49.99",
            "stock_limit": 0,
        },
    )

    assert response.status_code == 422


def test_multiple_allocations_cannot_oversubscribe_inventory(
    authenticated_client, db_session, flash_sale_setup
):
    sale_response = create_sale(
        authenticated_client, flash_sale_setup["run_id"]
    )
    sale_id = sale_response.json()["id"]
    inventory_id = flash_sale_setup["inventory_id"]

    first = authenticated_client.post(
        f"/api/simulations/flash-sales/{sale_id}/products",
        json={
            "inventory_id": inventory_id,
            "sale_price": "49.99",
            "stock_limit": 70,
        },
    )
    assert first.status_code == 201

    second = authenticated_client.post(
        f"/api/simulations/flash-sales/{sale_id}/products",
        json={
            "inventory_id": inventory_id,
            "sale_price": "39.99",
            "stock_limit": 40,
        },
    )

    assert second.status_code == 409
    assert second.json()["detail"]["available"] == 30

    reserved = db_session.execute(
        text("""
            SELECT reserved_quantity
            FROM simulation_inventory
            WHERE id = :id
        """),
        {"id": inventory_id},
    ).scalar_one()

    assert reserved == 70

def test_concurrent_allocations_cannot_oversubscribe_inventory(
    authenticated_client, db_session, flash_sale_setup
):
    from concurrent.futures import ThreadPoolExecutor
    from fastapi.testclient import TestClient

    inventory_id = flash_sale_setup["inventory_id"]
    run_id = flash_sale_setup["run_id"]

    sale_a = create_sale(authenticated_client, run_id)
    sale_b = create_sale(authenticated_client, run_id)

    assert sale_a.status_code == 201
    assert sale_b.status_code == 201

    headers = dict(authenticated_client.headers)

    def allocate(sale_id):
        with TestClient(app, headers=headers) as client:
            return client.post(
                f"/api/simulations/flash-sales/{sale_id}/products",
                json={
                    "inventory_id": inventory_id,
                    "sale_price": "49.99",
                    "stock_limit": 70,
                },
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(
            allocate,
            [sale_a.json()["id"], sale_b.json()["id"]],
        ))

    assert sorted(response.status_code for response in responses) == [201, 409]

    reserved = db_session.execute(
        text("""
            SELECT reserved_quantity
            FROM simulation_inventory
            WHERE id = :id
        """),
        {"id": inventory_id},
    ).scalar_one()

    assert reserved == 70

    allocations = db_session.execute(
        text("""
            SELECT COUNT(*), COALESCE(SUM(stock_limit), 0)
            FROM flash_sale_products
            WHERE inventory_id = :id
        """),
        {"id": inventory_id},
    ).one()

    assert allocations[0] == 1
    assert allocations[1] == 70
