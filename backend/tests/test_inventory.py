from decimal import Decimal

import pytest
from sqlalchemy import text

from app.models.rossmann import Store


@pytest.fixture
def inventory_setup(authenticated_client, db_session):
    store = Store(
        store_id=201,
        store_type="a",
        assortment="a",
        competition_distance=500,
        promo2=False,
    )

    db_session.add(store)
    db_session.commit()

    product_response = authenticated_client.post(
        "/api/simulations/products",
        json={
            "sku": "INVENTORY-TEST-001",
            "name": "Inventory Test Product",
        },
    )

    assert product_response.status_code == 201

    return {
        "store_id": 201,
        "product_id": product_response.json()["id"],
        "sku": "INVENTORY-TEST-001",
    }


def test_create_inventory(authenticated_client, inventory_setup):
    response = authenticated_client.post(
        "/api/simulations/inventory",
        json={
            "store_id": inventory_setup["store_id"],
            "product_id": inventory_setup["product_id"],
            "quantity": 100,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["store_id"] == 201
    assert data["product_id"] == inventory_setup["product_id"]
    assert data["quantity"] == 100
    assert data["reserved_quantity"] == 0
    assert data["id"] is not None


def test_inventory_list_includes_product_details(
    authenticated_client, inventory_setup
):
    authenticated_client.post(
        "/api/simulations/inventory",
        json={
            "store_id": 201,
            "product_id": inventory_setup["product_id"],
            "quantity": 50,
        },
    )

    response = authenticated_client.get("/api/simulations/inventory")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["store_id"] == 201
    assert data[0]["sku"] == inventory_setup["sku"]
    assert data[0]["product_name"] == "Inventory Test Product"
    assert data[0]["quantity"] == 50


def test_inventory_creation_writes_initial_stock_audit(
    authenticated_client, db_session, inventory_setup
):
    response = authenticated_client.post(
        "/api/simulations/inventory",
        json={
            "store_id": 201,
            "product_id": inventory_setup["product_id"],
            "quantity": 75,
        },
    )

    assert response.status_code == 201

    inventory_id = response.json()["id"]

    audit = db_session.execute(
        text("""
            SELECT action, entity_name, entity_id, details
            FROM audit_logs
            WHERE entity_name = 'simulation_inventory'
              AND entity_id = :inventory_id
        """),
        {"inventory_id": str(inventory_id)},
    ).mappings().one()

    assert audit["action"] == "inventory_created"
    assert audit["details"]["quantity"] == 75


def test_zero_quantity_inventory_is_allowed(authenticated_client, inventory_setup):
    response = authenticated_client.post(
        "/api/simulations/inventory",
        json={
            "store_id": 201,
            "product_id": inventory_setup["product_id"],
            "quantity": 0,
        },
    )

    assert response.status_code == 201
    assert response.json()["quantity"] == 0
    assert response.json()["reserved_quantity"] == 0


def test_negative_inventory_quantity_is_rejected(
    authenticated_client, inventory_setup
):
    response = authenticated_client.post(
        "/api/simulations/inventory",
        json={
            "store_id": 201,
            "product_id": inventory_setup["product_id"],
            "quantity": -1,
        },
    )

    assert response.status_code == 422


def test_duplicate_store_product_inventory_returns_409(
    authenticated_client, inventory_setup
):
    payload = {
        "store_id": 201,
        "product_id": inventory_setup["product_id"],
        "quantity": 100,
    }

    first = authenticated_client.post("/api/simulations/inventory", json=payload)
    second = authenticated_client.post("/api/simulations/inventory", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


def test_missing_store_reference_returns_409(authenticated_client, inventory_setup):
    response = authenticated_client.post(
        "/api/simulations/inventory",
        json={
            "store_id": 999999,
            "product_id": inventory_setup["product_id"],
            "quantity": 10,
        },
    )

    assert response.status_code == 409


def test_missing_product_reference_returns_409(authenticated_client):
    response = authenticated_client.post(
        "/api/simulations/inventory",
        json={
            "store_id": 999999,
            "product_id": 999999,
            "quantity": 10,
        },
    )

    assert response.status_code == 409


def test_nonpositive_inventory_ids_are_rejected(authenticated_client):
    response = authenticated_client.post(
        "/api/simulations/inventory",
        json={
            "store_id": 0,
            "product_id": -1,
            "quantity": 10,
        },
    )

    assert response.status_code == 422


def test_inventory_adjustment_increases_stock(
    authenticated_client, inventory_setup, db_session
):
    created = authenticated_client.post(
        "/api/simulations/inventory",
        json={
            "store_id": 201,
            "product_id": inventory_setup["product_id"],
            "quantity": 100,
        },
    )
    assert created.status_code == 201
    inventory_id = created.json()["id"]

    response = authenticated_client.post(
        f"/api/simulations/inventory/{inventory_id}/adjust",
        json={
            "quantity_delta": 25,
            "reason": "Received additional stock",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["quantity_before"] == 100
    assert data["quantity_delta"] == 25
    assert data["quantity_after"] == 125
    assert data["reserved_quantity"] == 0
    assert data["available_quantity"] == 125

    audit = db_session.execute(
        text("""
            SELECT action, details
            FROM audit_logs
            WHERE entity_name = 'simulation_inventory'
              AND entity_id = :inventory_id
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"inventory_id": str(inventory_id)},
    ).mappings().one()

    assert audit["action"] == "inventory_adjusted"
    assert audit["details"]["quantity_before"] == 100
    assert audit["details"]["quantity_delta"] == 25
    assert audit["details"]["quantity_after"] == 125
    assert audit["details"]["reason"] == "Received additional stock"


def test_inventory_adjustment_decreases_stock(
    authenticated_client, inventory_setup
):
    created = authenticated_client.post(
        "/api/simulations/inventory",
        json={
            "store_id": 201,
            "product_id": inventory_setup["product_id"],
            "quantity": 100,
        },
    )
    inventory_id = created.json()["id"]

    response = authenticated_client.post(
        f"/api/simulations/inventory/{inventory_id}/adjust",
        json={
            "quantity_delta": -30,
            "reason": "Damaged stock removed",
        },
    )

    assert response.status_code == 200
    assert response.json()["quantity_after"] == 70
    assert response.json()["available_quantity"] == 70


def test_inventory_adjustment_cannot_reduce_stock_below_reserved(
    authenticated_client, inventory_setup, db_session
):
    created = authenticated_client.post(
        "/api/simulations/inventory",
        json={
            "store_id": 201,
            "product_id": inventory_setup["product_id"],
            "quantity": 100,
        },
    )
    inventory_id = created.json()["id"]

    db_session.execute(
        text("""
            UPDATE simulation_inventory
            SET reserved_quantity = 40
            WHERE id = :id
        """),
        {"id": inventory_id},
    )
    db_session.commit()

    response = authenticated_client.post(
        f"/api/simulations/inventory/{inventory_id}/adjust",
        json={
            "quantity_delta": -70,
            "reason": "Attempted stock removal",
        },
    )

    assert response.status_code == 409

    inventory = db_session.execute(
        text("""
            SELECT quantity, reserved_quantity
            FROM simulation_inventory
            WHERE id = :id
        """),
        {"id": inventory_id},
    ).mappings().one()

    assert inventory["quantity"] == 100
    assert inventory["reserved_quantity"] == 40


def test_inventory_adjustment_rejects_zero_delta(
    authenticated_client, inventory_setup
):
    created = authenticated_client.post(
        "/api/simulations/inventory",
        json={
            "store_id": 201,
            "product_id": inventory_setup["product_id"],
            "quantity": 100,
        },
    )
    inventory_id = created.json()["id"]

    response = authenticated_client.post(
        f"/api/simulations/inventory/{inventory_id}/adjust",
        json={
            "quantity_delta": 0,
            "reason": "No change",
        },
    )

    assert response.status_code == 422


def test_inventory_adjustment_rejects_missing_inventory(
    authenticated_client,
):
    response = authenticated_client.post(
        "/api/simulations/inventory/999999/adjust",
        json={
            "quantity_delta": 10,
            "reason": "Test missing inventory",
        },
    )

    assert response.status_code == 404
