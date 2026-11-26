from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text


def role_headers(client, db_session, email, role):
    signup = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "Flashcore-Security-Test-Password-9",
        },
    )
    assert signup.status_code == 201

    token = signup.json()["access_token"]

    db_session.execute(
        text("UPDATE users SET role = :role WHERE email = :email"),
        {"role": role, "email": email},
    )
    db_session.commit()

    return {"Authorization": f"Bearer {token}"}


def valid_run_payload():
    return {
        "run_name": "Authorization Test Run",
        "description": "Permission test",
        "configuration": {},
    }


def valid_product_payload():
    return {
        "sku": "AUTH-TEST-001",
        "name": "Authorization Test Product",
        "description": "Permission test",
    }


def valid_inventory_payload():
    return {
        "store_id": 1,
        "product_id": 1,
        "quantity": 10,
    }


def valid_flash_sale_payload():
    now = datetime.now(timezone.utc)
    return {
        "title": "Authorization Test Sale",
        "starts_at": (now + timedelta(days=1)).isoformat(),
        "ends_at": (now + timedelta(days=2)).isoformat(),
    }


def valid_sale_product_payload():
    return {
        "inventory_id": 1,
        "sale_price": "9.99",
        "stock_limit": 1,
    }


def valid_purchase_payload():
    return {
        "customer_ref": "AUTH-CUSTOMER-001",
        "idempotency_key": "AUTH-IDEMPOTENCY-001",
        "quantity": 1,
    }


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/api/simulations/runs", None),
        ("get", "/api/simulations/products", None),
        ("get", "/api/simulations/inventory", None),
        ("post", "/api/simulations/runs", valid_run_payload()),
        ("post", "/api/simulations/products", valid_product_payload()),
        ("post", "/api/simulations/inventory", valid_inventory_payload()),
        (
            "post",
            "/api/simulations/runs/999999/flash-sales",
            valid_flash_sale_payload(),
        ),
        (
            "post",
            "/api/simulations/flash-sales/999999/activate",
            None,
        ),
        (
            "post",
            "/api/simulations/flash-sales/999999/products",
            valid_sale_product_payload(),
        ),
        (
            "post",
            "/api/simulations/flash-sale-products/999999/purchase",
            valid_purchase_payload(),
        ),
    ],
)
def test_simulation_routes_reject_unauthenticated_requests(
    client, method, path, payload
):
    if payload is None:
        response = getattr(client, method)(path)
    else:
        response = getattr(client, method)(path, json=payload)

    assert response.status_code == 401, (
        f"{method.upper()} {path}: expected 401, got "
        f"{response.status_code}: {response.text}"
    )


def test_analyst_can_read_simulation_resources(client, db_session):
    headers = role_headers(
        client,
        db_session,
        "analyst-simulation-read@example.com",
        "analyst",
    )

    for path in (
        "/api/simulations/runs",
        "/api/simulations/products",
        "/api/simulations/inventory",
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, (
            f"GET {path}: {response.status_code}: {response.text}"
        )


def test_analyst_cannot_write_simulation_resources(client, db_session):
    headers = role_headers(
        client,
        db_session,
        "analyst-simulation-write@example.com",
        "analyst",
    )

    requests = [
        ("post", "/api/simulations/runs", valid_run_payload()),
        ("post", "/api/simulations/products", valid_product_payload()),
        ("post", "/api/simulations/inventory", valid_inventory_payload()),
        (
            "post",
            "/api/simulations/runs/999999/flash-sales",
            valid_flash_sale_payload(),
        ),
        (
            "post",
            "/api/simulations/flash-sales/999999/activate",
            None,
        ),
        (
            "post",
            "/api/simulations/flash-sales/999999/products",
            valid_sale_product_payload(),
        ),
        (
            "post",
            "/api/simulations/flash-sale-products/999999/purchase",
            valid_purchase_payload(),
        ),
    ]

    for method, path, payload in requests:
        if payload is None:
            response = getattr(client, method)(path, headers=headers)
        else:
            response = getattr(client, method)(
                path, json=payload, headers=headers
            )

        assert response.status_code == 403, (
            f"{method.upper()} {path}: expected 403, got "
            f"{response.status_code}: {response.text}"
        )


def test_operator_passes_flash_sale_write_authorization(client, db_session):
    headers = role_headers(
        client,
        db_session,
        "operator-simulation-write@example.com",
        "operator",
    )

    response = client.post(
        "/api/simulations/flash-sales/999999/activate",
        headers=headers,
    )

    # The missing sale should reach the handler, not be blocked by RBAC.
    assert response.status_code == 404


def test_admin_passes_flash_sale_write_authorization(authenticated_client):
    response = authenticated_client.post(
        "/api/simulations/flash-sales/999999/activate"
    )

    assert response.status_code == 404
