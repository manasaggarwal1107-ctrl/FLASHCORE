import os

# Force the isolated test database before importing the application.
os.environ["DB_NAME"] = "flashcore_test"

from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
import pytest

from app.core.database import DATABASE_URL, engine, SessionLocal, get_db

# Hard safety guard: tests must never run against the real data database.
if DATABASE_URL.database != "flashcore_test":
    raise RuntimeError(
        f"Unsafe test database: {DATABASE_URL.database!r}"
    )

with engine.connect() as connection:
    actual_database = connection.execute(
        text("SELECT current_database()")
    ).scalar_one()

if actual_database != "flashcore_test":
    raise RuntimeError(
        f"Connected to unexpected database: {actual_database!r}"
    )

from main import app


TABLES = (
    "auth_sessions, users, "
    "audit_logs, "
    "transactions_log, "
    "purchase_attempts, "
    "flash_sale_products, "
    "flash_sales, "
    "simulation_inventory, "
    "simulation_products, "
    "simulation_runs, "
    "daily_store_sales, "
    "dataset_import_errors, "
    "dataset_imports, "
    "stores"
)


@pytest.fixture(autouse=True)
def clean_test_database():
    """Keep every test isolated using only the dedicated test database."""
    with engine.begin() as connection:
        connection.execute(
            text(f"TRUNCATE TABLE {TABLES} RESTART IDENTITY CASCADE")
        )

    yield

    with engine.begin() as connection:
        connection.execute(
            text(f"TRUNCATE TABLE {TABLES} RESTART IDENTITY CASCADE")
        )


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """FastAPI client with independent database sessions per request."""

    previous_overrides = app.dependency_overrides.copy()

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.fixture
def authenticated_client(client, db_session):
    """Authenticated Admin client for existing business integration tests."""
    email = "test-admin@flashcore.local"

    response = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "Flashcore-Test-Admin-Password-9",
        },
    )
    assert response.status_code == 201

    db_session.execute(
        text("UPDATE users SET role = 'admin' WHERE email = :email"),
        {"email": email},
    )
    db_session.commit()

    client.headers.update({
        "Authorization": f"Bearer {response.json()['access_token']}"
    })
    return client


@pytest.fixture
def purchase_setup(authenticated_client, db_session):
    """Shared setup for purchase and analytics integration tests."""
    from datetime import datetime, timedelta, timezone
    from app.models.rossmann import Store

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
