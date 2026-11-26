from datetime import datetime, timezone

import pytest
from sqlalchemy import text


def insert_attempt(
    db_session,
    setup,
    *,
    status,
    customer_ref,
    key,
    quantity=1,
    created_at=None,
):
    created_at = created_at or datetime(
        2025, 1, 1, 12, 0, tzinfo=timezone.utc
    )

    attempt_id = db_session.execute(
        text("""
            INSERT INTO purchase_attempts (
                simulation_run_id,
                flash_sale_product_id,
                customer_ref,
                idempotency_key,
                quantity,
                status,
                created_at
            )
            VALUES (
                :run_id,
                :product_id,
                :customer,
                :key,
                :quantity,
                :status,
                :created_at
            )
            RETURNING id
        """),
        {
            "run_id": setup["run_id"],
            "product_id": setup["sale_product_id"],
            "customer": customer_ref,
            "key": key,
            "quantity": quantity,
            "status": status,
            "created_at": created_at,
        },
    ).scalar_one()

    db_session.commit()
    return attempt_id


def test_conversion_excludes_pending_and_counts_rejected(
    authenticated_client, db_session, purchase_setup
):
    setup = purchase_setup

    statuses = [
        ("success", "CONV-1"),
        ("rejected", "CONV-2"),
        ("failed", "CONV-3"),
        ("pending", "CONV-4"),
    ]

    for status, key in statuses:
        insert_attempt(
            db_session,
            setup,
            status=status,
            customer_ref=key,
            key=key,
        )

    response = authenticated_client.get("/api/simulations/analytics/conversion")

    assert response.status_code == 200
    data = response.json()

    assert len(data["points"]) == 1
    assert data["points"][0]["value"] == pytest.approx(1 / 3)
    assert data["origin"] == "simulation"


def test_failure_rate_counts_only_failed_not_rejected_or_pending(
    authenticated_client, db_session, purchase_setup
):
    setup = purchase_setup

    statuses = [
        ("success", "FAIL-1"),
        ("rejected", "FAIL-2"),
        ("failed", "FAIL-3"),
        ("pending", "FAIL-4"),
    ]

    for status, key in statuses:
        insert_attempt(
            db_session,
            setup,
            status=status,
            customer_ref=key,
            key=key,
        )

    response = authenticated_client.get(
        "/api/simulations/analytics/failure-rates"
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data["points"]) == 1
    assert data["points"][0]["value"] == pytest.approx(1 / 3)


def test_pending_only_date_returns_zero_rates(
    authenticated_client, db_session, purchase_setup
):
    insert_attempt(
        db_session,
        purchase_setup,
        status="pending",
        customer_ref="PENDING-ONLY",
        key="PENDING-ONLY-KEY",
    )

    conversion = authenticated_client.get(
        "/api/simulations/analytics/conversion"
    )
    failure = authenticated_client.get(
        "/api/simulations/analytics/failure-rates"
    )

    assert conversion.status_code == 200
    assert failure.status_code == 200

    assert conversion.json()["points"][0]["value"] == 0
    assert failure.json()["points"][0]["value"] == 0


def test_purchase_analytics_date_filter(
    authenticated_client, db_session, purchase_setup
):
    insert_attempt(
        db_session,
        purchase_setup,
        status="success",
        customer_ref="DATE-1",
        key="DATE-KEY-1",
        created_at=datetime(
            2025, 1, 1, 12, 0, tzinfo=timezone.utc
        ),
    )

    insert_attempt(
        db_session,
        purchase_setup,
        status="failed",
        customer_ref="DATE-2",
        key="DATE-KEY-2",
        created_at=datetime(
            2025, 1, 2, 12, 0, tzinfo=timezone.utc
        ),
    )

    response = authenticated_client.get(
        "/api/simulations/analytics/conversion",
        params={
            "from": "2025-01-01T00:00:00+00:00",
            "to": "2025-01-01T23:59:59+00:00",
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data["points"]) == 1
    assert data["points"][0]["t"] == "2025-01-01"
    assert data["points"][0]["value"] == pytest.approx(1.0)


def test_purchase_analytics_rejects_reversed_date_range(authenticated_client):
    response = authenticated_client.get(
        "/api/simulations/analytics/conversion",
        params={
            "from": "2025-01-02T00:00:00+00:00",
            "to": "2025-01-01T00:00:00+00:00",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "from cannot be after to"


def test_purchase_analytics_empty_dataset(authenticated_client):
    conversion = authenticated_client.get(
        "/api/simulations/analytics/conversion"
    )
    failure = authenticated_client.get(
        "/api/simulations/analytics/failure-rates"
    )

    assert conversion.status_code == 200
    assert failure.status_code == 200

    assert conversion.json()["points"] == []
    assert failure.json()["points"] == []

    assert conversion.json()["period_start"] is None
    assert failure.json()["period_end"] is None


def test_inventory_utilisation_includes_reserved_stock(
    authenticated_client, purchase_setup
):
    response = authenticated_client.get(
        "/api/simulations/analytics/inventory-utilisation"
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data["points"]) == 1
    assert data["points"][0]["value"] == pytest.approx(0.10)
    assert data["origin"] == "simulation"


def test_inventory_utilisation_empty_dataset(authenticated_client):
    response = authenticated_client.get(
        "/api/simulations/analytics/inventory-utilisation"
    )

    assert response.status_code == 200
    data = response.json()

    assert data["points"] == []
    assert data["period_start"] is None
    assert data["period_end"] is None


def test_inventory_utilisation_requires_initial_stock_audit(
    authenticated_client, db_session, purchase_setup
):
    inventory_id = purchase_setup["inventory_id"]

    db_session.execute(
        text("""
            DELETE FROM audit_logs
            WHERE entity_name = 'simulation_inventory'
              AND entity_id = :entity_id
              AND action = 'inventory_created'
        """),
        {"entity_id": str(inventory_id)},
    )
    db_session.commit()

    response = authenticated_client.get(
        "/api/simulations/analytics/inventory-utilisation"
    )

    assert response.status_code == 409
    assert "initial-stock audit record" in response.json()["detail"]


def test_inventory_utilisation_rejects_zero_initial_stock(
    authenticated_client, db_session, purchase_setup
):
    inventory_id = purchase_setup["inventory_id"]

    db_session.execute(
        text("""
            UPDATE audit_logs
            SET details = '{"quantity": 0}'::jsonb
            WHERE entity_name = 'simulation_inventory'
              AND entity_id = :entity_id
              AND action = 'inventory_created'
        """),
        {"entity_id": str(inventory_id)},
    )
    db_session.commit()

    response = authenticated_client.get(
        "/api/simulations/analytics/inventory-utilisation"
    )

    assert response.status_code == 409
    assert "initial stock must be greater than zero" in (
        response.json()["detail"]
    )


def test_flash_sale_performance_counts_successful_quantities(
    authenticated_client, db_session, purchase_setup
):
    setup = purchase_setup

    insert_attempt(
        db_session,
        setup,
        status="success",
        customer_ref="PERF-1",
        key="PERF-KEY-1",
        quantity=2,
        created_at=datetime(
            2025, 1, 1, 10, 0, tzinfo=timezone.utc
        ),
    )

    insert_attempt(
        db_session,
        setup,
        status="success",
        customer_ref="PERF-2",
        key="PERF-KEY-2",
        quantity=3,
        created_at=datetime(
            2025, 1, 1, 14, 0, tzinfo=timezone.utc
        ),
    )

    insert_attempt(
        db_session,
        setup,
        status="rejected",
        customer_ref="PERF-3",
        key="PERF-KEY-3",
        quantity=4,
        created_at=datetime(
            2025, 1, 1, 16, 0, tzinfo=timezone.utc
        ),
    )

    response = authenticated_client.get(
        "/api/simulations/analytics/flash-sale-performance"
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data["points"]) == 1
    assert data["points"][0]["t"] == "2025-01-01"
    assert data["points"][0]["value"] == 5
    assert data["origin"] == "simulation"
