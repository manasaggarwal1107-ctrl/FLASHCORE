from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.models.rossmann import Store
from main import app


@pytest.fixture
def purchase_setup(authenticated_client, db_session):
    store = Store(
        store_id=401,
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
            "run_name": "PURCHASE-TEST",
            "description": "Automated purchase engine tests",
            "configuration": {},
        },
    )
    assert run_response.status_code == 201
    run_id = run_response.json()["id"]

    product_response = authenticated_client.post(
        "/api/simulations/products",
        json={
            "sku": "PURCHASE-TEST-001",
            "name": "Purchase Test Product",
        },
    )
    assert product_response.status_code == 201
    product_id = product_response.json()["id"]

    inventory_response = authenticated_client.post(
        "/api/simulations/inventory",
        json={
            "store_id": 401,
            "product_id": product_id,
            "quantity": 100,
        },
    )
    assert inventory_response.status_code == 201
    inventory_id = inventory_response.json()["id"]

    now = datetime.now(timezone.utc)

    sale_response = authenticated_client.post(
        f"/api/simulations/runs/{run_id}/flash-sales",
        json={
            "title": "Purchase Test Flash Sale",
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(hours=2)).isoformat(),
        },
    )
    assert sale_response.status_code == 201
    sale_id = sale_response.json()["id"]

    activation_response = authenticated_client.post(
        f"/api/simulations/flash-sales/{sale_id}/activate"
    )
    assert activation_response.status_code == 200
    assert activation_response.json()["status"] == "active"

    allocation_response = authenticated_client.post(
        f"/api/simulations/flash-sales/{sale_id}/products",
        json={
            "inventory_id": inventory_id,
            "sale_price": "49.99",
            "stock_limit": 10,
        },
    )
    assert allocation_response.status_code == 201
    sale_product_id = allocation_response.json()["id"]

    return {
        "run_id": run_id,
        "sale_id": sale_id,
        "sale_product_id": sale_product_id,
        "inventory_id": inventory_id,
        "product_id": product_id,
    }


def purchase_payload(
    customer="CUSTOMER-001",
    key="PURCHASE-KEY-001",
    quantity=1,
):
    return {
        "customer_ref": customer,
        "idempotency_key": key,
        "quantity": quantity,
    }


def purchase_url(setup):
    return (
        f"/api/simulations/flash-sale-products/"
        f"{setup['sale_product_id']}/purchase"
    )


def test_successful_purchase(authenticated_client, db_session, purchase_setup):
    response = authenticated_client.post(
        purchase_url(purchase_setup),
        json=purchase_payload(quantity=2),
    )

    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["attempt"]["status"] == "success"
    assert data["attempt"]["quantity"] == 2

    inventory = db_session.execute(
        text("""
            SELECT quantity, reserved_quantity
            FROM simulation_inventory
            WHERE id = :id
        """),
        {"id": purchase_setup["inventory_id"]},
    ).mappings().one()

    assert inventory["quantity"] == 98
    assert inventory["reserved_quantity"] == 8

    sale_product = db_session.execute(
        text("""
            SELECT sold_quantity, stock_limit
            FROM flash_sale_products
            WHERE id = :id
        """),
        {"id": purchase_setup["sale_product_id"]},
    ).mappings().one()

    assert sale_product["sold_quantity"] == 2
    assert sale_product["stock_limit"] == 10


def test_successful_purchase_writes_transaction_log(
    authenticated_client, db_session, purchase_setup
):
    response = authenticated_client.post(
        purchase_url(purchase_setup),
        json=purchase_payload(),
    )
    assert response.status_code == 200

    attempt_id = response.json()["attempt"]["id"]

    transaction = db_session.execute(
        text("""
            SELECT action, outcome
            FROM transactions_log
            WHERE purchase_attempt_id = :attempt_id
        """),
        {"attempt_id": attempt_id},
    ).mappings().one()

    assert transaction["action"] == "purchase_success"
    assert transaction["outcome"]["status"] == "success"


def test_successful_purchase_writes_customer_audit(
    authenticated_client, db_session, purchase_setup
):
    response = authenticated_client.post(
        purchase_url(purchase_setup),
        json=purchase_payload(customer="AUDIT-CUSTOMER"),
    )
    assert response.status_code == 200

    attempt_id = response.json()["attempt"]["id"]

    audit = db_session.execute(
        text("""
            SELECT action, actor_type, actor_ref
            FROM audit_logs
            WHERE entity_name = 'purchase_attempts'
              AND entity_id = :entity_id
        """),
        {"entity_id": str(attempt_id)},
    ).mappings().one()

    assert audit["action"] == "purchase_success"
    assert audit["actor_type"] == "customer"
    assert audit["actor_ref"] == "AUDIT-CUSTOMER"


def test_same_idempotency_key_returns_existing_attempt(
    authenticated_client, db_session, purchase_setup
):
    payload = purchase_payload()

    first = authenticated_client.post(purchase_url(purchase_setup), json=payload)
    assert first.status_code == 200
    assert first.json()["success"] is True

    second = authenticated_client.post(purchase_url(purchase_setup), json=payload)

    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert (
        second.json()["attempt"]["id"]
        == first.json()["attempt"]["id"]
    )

    inventory = db_session.execute(
        text("""
            SELECT quantity, reserved_quantity
            FROM simulation_inventory
            WHERE id = :id
        """),
        {"id": purchase_setup["inventory_id"]},
    ).mappings().one()

    assert inventory["quantity"] == 99
    assert inventory["reserved_quantity"] == 9


def test_idempotency_key_cannot_be_reused_with_different_data(
    authenticated_client, purchase_setup
):
    first = authenticated_client.post(
        purchase_url(purchase_setup),
        json=purchase_payload(
            customer="CUSTOMER-A",
            key="REUSED-KEY",
            quantity=1,
        ),
    )
    assert first.status_code == 200

    second = authenticated_client.post(
        purchase_url(purchase_setup),
        json=purchase_payload(
            customer="CUSTOMER-B",
            key="REUSED-KEY",
            quantity=1,
        ),
    )

    assert second.status_code == 409


def test_customer_cannot_purchase_same_sale_product_twice(
    authenticated_client, db_session, purchase_setup
):
    first = authenticated_client.post(
        purchase_url(purchase_setup),
        json=purchase_payload(
            customer="SAME-CUSTOMER",
            key="CUSTOMER-KEY-1",
        ),
    )
    assert first.status_code == 200
    assert first.json()["success"] is True

    second = authenticated_client.post(
        purchase_url(purchase_setup),
        json=purchase_payload(
            customer="SAME-CUSTOMER",
            key="CUSTOMER-KEY-2",
        ),
    )

    assert second.status_code == 200
    assert second.json()["success"] is False
    assert second.json()["attempt"]["status"] == "rejected"
    assert "already purchased" in second.json()["message"].lower()

    attempts = db_session.execute(
        text("""
            SELECT COUNT(*)
            FROM purchase_attempts
            WHERE customer_ref = 'SAME-CUSTOMER'
        """)
    ).scalar_one()

    assert attempts == 2


def test_purchase_rejects_quantity_above_sale_stock_limit(
    authenticated_client, db_session, purchase_setup
):
    response = authenticated_client.post(
        purchase_url(purchase_setup),
        json=purchase_payload(quantity=11),
    )

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert "stock limit" in response.json()["message"].lower()

    inventory = db_session.execute(
        text("""
            SELECT quantity, reserved_quantity
            FROM simulation_inventory
            WHERE id = :id
        """),
        {"id": purchase_setup["inventory_id"]},
    ).mappings().one()

    assert inventory["quantity"] == 100
    assert inventory["reserved_quantity"] == 10


def test_purchase_rejects_insufficient_reserved_inventory(
    authenticated_client, db_session, purchase_setup
):
    db_session.execute(
        text("""
            UPDATE simulation_inventory
            SET reserved_quantity = 0
            WHERE id = :id
        """),
        {"id": purchase_setup["inventory_id"]},
    )
    db_session.commit()

    response = authenticated_client.post(
        purchase_url(purchase_setup),
        json=purchase_payload(),
    )

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert "reserved inventory" in response.json()["message"].lower()

    quantity = db_session.execute(
        text("""
            SELECT quantity
            FROM simulation_inventory
            WHERE id = :id
        """),
        {"id": purchase_setup["inventory_id"]},
    ).scalar_one()

    assert quantity == 100


def test_purchase_rejects_inactive_flash_sale(
    authenticated_client, db_session, purchase_setup
):
    db_session.execute(
        text("""
            UPDATE flash_sales
            SET status = 'draft'
            WHERE id = :id
        """),
        {"id": purchase_setup["sale_id"]},
    )
    db_session.commit()

    response = authenticated_client.post(
        purchase_url(purchase_setup),
        json=purchase_payload(),
    )

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert "not active" in response.json()["message"].lower()

    quantity = db_session.execute(
        text("""
            SELECT quantity
            FROM simulation_inventory
            WHERE id = :id
        """),
        {"id": purchase_setup["inventory_id"]},
    ).scalar_one()

    assert quantity == 100


def test_missing_flash_sale_product_returns_404(authenticated_client):
    response = authenticated_client.post(
        "/api/simulations/flash-sale-products/999999/purchase",
        json=purchase_payload(),
    )

    assert response.status_code == 404


def test_invalid_purchase_payload_returns_422(
    authenticated_client, purchase_setup
):
    invalid_payloads = [
        {
            "customer_ref": "",
            "idempotency_key": "INVALID-1",
            "quantity": 1,
        },
        {
            "customer_ref": "CUSTOMER",
            "idempotency_key": "",
            "quantity": 1,
        },
        {
            "customer_ref": "CUSTOMER",
            "idempotency_key": "INVALID-3",
            "quantity": 0,
        },
    ]

    for payload in invalid_payloads:
        response = authenticated_client.post(
            purchase_url(purchase_setup),
            json=payload,
        )
        assert response.status_code == 422


def test_rejected_purchase_is_recorded_for_audit(
    authenticated_client, db_session, purchase_setup
):
    response = authenticated_client.post(
        purchase_url(purchase_setup),
        json=purchase_payload(quantity=11),
    )

    assert response.status_code == 200
    assert response.json()["success"] is False

    attempt_id = response.json()["attempt"]["id"]

    transaction = db_session.execute(
        text("""
            SELECT action, outcome
            FROM transactions_log
            WHERE purchase_attempt_id = :attempt_id
        """),
        {"attempt_id": attempt_id},
    ).mappings().one()

    assert transaction["action"] == "purchase_rejected"
    assert transaction["outcome"]["status"] == "rejected"

    audit = db_session.execute(
        text("""
            SELECT action
            FROM audit_logs
            WHERE entity_name = 'purchase_attempts'
              AND entity_id = :entity_id
        """),
        {"entity_id": str(attempt_id)},
    ).scalar_one()

    assert audit == "purchase_rejected"


def test_concurrent_purchases_cannot_oversell_inventory(
    db_session, purchase_setup, authenticated_client
):
    total_requests = 20

    def send_purchase(index):
        payload = purchase_payload(
            customer=f"CONCURRENT-CUSTOMER-{index}",
            key=f"CONCURRENT-KEY-{index}",
            quantity=1,
        )

        with TestClient(
            app,
            headers=dict(authenticated_client.headers),
        ) as concurrent_client:
            return concurrent_client.post(
                purchase_url(purchase_setup),
                json=payload,
            )

    with ThreadPoolExecutor(max_workers=total_requests) as executor:
        responses = list(
            executor.map(send_purchase, range(total_requests))
        )

    assert all(response.status_code == 200 for response in responses)

    successful = [
        response for response in responses
        if response.json()["success"] is True
    ]
    rejected = [
        response for response in responses
        if response.json()["success"] is False
    ]

    assert len(successful) == 10
    assert len(rejected) == 10

    inventory = db_session.execute(
        text("""
            SELECT quantity, reserved_quantity
            FROM simulation_inventory
            WHERE id = :id
        """),
        {"id": purchase_setup["inventory_id"]},
    ).mappings().one()

    assert inventory["quantity"] == 90
    assert inventory["reserved_quantity"] == 0

    sale_product = db_session.execute(
        text("""
            SELECT sold_quantity, stock_limit
            FROM flash_sale_products
            WHERE id = :id
        """),
        {"id": purchase_setup["sale_product_id"]},
    ).mappings().one()

    assert sale_product["sold_quantity"] == 10
    assert sale_product["sold_quantity"] <= sale_product["stock_limit"]

    attempt_count = db_session.execute(
        text("""
            SELECT COUNT(*)
            FROM purchase_attempts
            WHERE flash_sale_product_id = :id
        """),
        {"id": purchase_setup["sale_product_id"]},
    ).scalar_one()

    assert attempt_count == 20
