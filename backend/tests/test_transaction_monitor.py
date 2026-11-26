from datetime import datetime, timezone

from sqlalchemy import text


def insert_monitor_attempt(
    db_session,
    setup,
    *,
    status,
    customer_ref,
    key,
    created_at,
    failure_reason=None,
):
    return db_session.execute(
        text("""
            INSERT INTO purchase_attempts (
                simulation_run_id,
                flash_sale_product_id,
                customer_ref,
                idempotency_key,
                quantity,
                status,
                failure_reason,
                created_at
            )
            VALUES (
                :run_id,
                :product_id,
                :customer,
                :key,
                1,
                :status,
                :failure_reason,
                :created_at
            )
            RETURNING id
        """),
        {
            "run_id": setup["run_id"],
            "product_id": setup["sale_product_id"],
            "customer": customer_ref,
            "key": key,
            "status": status,
            "failure_reason": failure_reason,
            "created_at": created_at,
        },
    ).scalar_one()


def test_transaction_monitor_lists_purchase_attempts(
    authenticated_client, db_session, purchase_setup
):
    timestamps = [
        datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc),
        datetime(2025, 1, 3, 10, 0, tzinfo=timezone.utc),
    ]
    statuses = ["success", "failed", "rejected"]
    ids = []

    for index, (status, timestamp) in enumerate(zip(statuses, timestamps)):
        ids.append(
            insert_monitor_attempt(
                db_session,
                purchase_setup,
                status=status,
                customer_ref=f"MONITOR-CUSTOMER-{index}",
                key=f"MONITOR-KEY-{index}",
                created_at=timestamp,
                failure_reason="Insufficient stock" if status != "success" else None,
            )
        )

    db_session.commit()

    response = authenticated_client.get(
        "/api/simulations/transactions",
        params={"page": 1, "pageSize": 25},
    )

    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["total"] == 3
    assert payload["page"] == 1
    assert payload["page_size"] == 25
    assert len(payload["items"]) == 3

    by_id = {int(item["id"]): item for item in payload["items"]}

    assert by_id[ids[0]]["status"] == "succeeded"
    assert by_id[ids[1]]["status"] == "failed"
    assert by_id[ids[2]]["status"] == "rejected"

    for item in payload["items"]:
        assert item["origin"] == "simulation"
        assert "customer_ref" not in item
        assert "idempotency_key" not in item


def test_transaction_monitor_filters_status_and_dates(
    authenticated_client, db_session, purchase_setup
):
    insert_monitor_attempt(
        db_session,
        purchase_setup,
        status="success",
        customer_ref="FILTER-CUSTOMER-1",
        key="FILTER-KEY-1",
        created_at=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
    )
    expected_id = insert_monitor_attempt(
        db_session,
        purchase_setup,
        status="failed",
        customer_ref="FILTER-CUSTOMER-2",
        key="FILTER-KEY-2",
        created_at=datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc),
        failure_reason="Payment processing failed",
    )
    insert_monitor_attempt(
        db_session,
        purchase_setup,
        status="rejected",
        customer_ref="FILTER-CUSTOMER-3",
        key="FILTER-KEY-3",
        created_at=datetime(2025, 1, 3, 10, 0, tzinfo=timezone.utc),
    )
    db_session.commit()

    response = authenticated_client.get(
        "/api/simulations/transactions",
        params={
            "status": "failed",
            "from": "2025-01-02",
            "to": "2025-01-02",
            "origin": "simulation",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["total"] == 1
    assert int(payload["items"][0]["id"]) == expected_id
    assert payload["items"][0]["status"] == "failed"


def test_transaction_monitor_searches_attempt_id_and_failure_reason(
    authenticated_client, db_session, purchase_setup
):
    attempt_id = insert_monitor_attempt(
        db_session,
        purchase_setup,
        status="failed",
        customer_ref="SEARCH-CUSTOMER",
        key="SEARCH-KEY",
        created_at=datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc),
        failure_reason="Unique monitor search phrase",
    )
    db_session.commit()

    by_id = authenticated_client.get(
        "/api/simulations/transactions",
        params={"search": str(attempt_id)},
    )
    assert by_id.status_code == 200, by_id.text
    assert by_id.json()["total"] == 1
    assert int(by_id.json()["items"][0]["id"]) == attempt_id

    by_reason = authenticated_client.get(
        "/api/simulations/transactions",
        params={"search": "Unique monitor search phrase"},
    )
    assert by_reason.status_code == 200, by_reason.text
    assert by_reason.json()["total"] == 1
    assert int(by_reason.json()["items"][0]["id"]) == attempt_id


def test_transaction_monitor_paginates_and_sorts(
    authenticated_client, db_session, purchase_setup
):
    ids = []

    for day in (1, 2, 3):
        ids.append(
            insert_monitor_attempt(
                db_session,
                purchase_setup,
                status="success",
                customer_ref=f"PAGE-CUSTOMER-{day}",
                key=f"PAGE-KEY-{day}",
                created_at=datetime(
                    2025, 2, day, 10, 0, tzinfo=timezone.utc
                ),
            )
        )

    db_session.commit()

    response = authenticated_client.get(
        "/api/simulations/transactions",
        params={
            "page": 2,
            "pageSize": 1,
            "sort": "occurredAt",
            "order": "asc",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["total"] == 3
    assert payload["page"] == 2
    assert payload["page_size"] == 1
    assert len(payload["items"]) == 1
    assert int(payload["items"][0]["id"]) == ids[1]


def test_transaction_monitor_detail_and_missing_attempt(
    authenticated_client, db_session, purchase_setup
):
    attempt_id = insert_monitor_attempt(
        db_session,
        purchase_setup,
        status="rejected",
        customer_ref="DETAIL-CUSTOMER",
        key="DETAIL-KEY",
        created_at=datetime(2025, 3, 1, 10, 0, tzinfo=timezone.utc),
        failure_reason="Sale stock limit reached",
    )
    db_session.commit()

    response = authenticated_client.get(
        f"/api/simulations/transactions/{attempt_id}"
    )

    assert response.status_code == 200, response.text
    item = response.json()

    assert int(item["id"]) == attempt_id
    assert item["purchase_attempt_id"] == str(attempt_id)
    assert item["status"] == "rejected"
    assert item["failure_reason"] == "Sale stock limit reached"
    assert item["origin"] == "simulation"
    assert "customer_ref" not in item
    assert "idempotency_key" not in item

    missing = authenticated_client.get(
        "/api/simulations/transactions/999999999"
    )
    assert missing.status_code == 404


def test_transaction_monitor_requires_authentication(client):
    list_response = client.get("/api/simulations/transactions")
    detail_response = client.get("/api/simulations/transactions/1")

    assert list_response.status_code == 401
    assert detail_response.status_code == 401


def test_transaction_monitor_filters_pending_status(
    authenticated_client, db_session, purchase_setup
):
    expected_id = insert_monitor_attempt(
        db_session,
        purchase_setup,
        status="pending",
        customer_ref="PENDING-CUSTOMER",
        key="PENDING-KEY",
        created_at=datetime(2025, 4, 1, 10, 0, tzinfo=timezone.utc),
    )
    db_session.commit()

    response = authenticated_client.get(
        "/api/simulations/transactions",
        params={"status": "pending"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    assert int(payload["items"][0]["id"]) == expected_id
    assert payload["items"][0]["status"] == "pending"
    assert payload["items"][0]["origin"] == "simulation"