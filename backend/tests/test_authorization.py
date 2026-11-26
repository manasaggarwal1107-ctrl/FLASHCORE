def test_rossmann_rejects_unauthenticated_request(client):
    response = client.get("/api/rossmann/stores")
    assert response.status_code == 401


def test_rossmann_rejects_operator(client, db_session):
    signup = client.post(
        "/api/auth/signup",
        json={
            "email": "operator@example.com",
            "password": "Flashcore-Operator-Password-9",
        },
    )
    assert signup.status_code == 201

    token = signup.json()["access_token"]

    db_session.execute(
        __import__("sqlalchemy").text(
            "UPDATE users SET role = 'operator' WHERE email = :email"
        ),
        {"email": "operator@example.com"},
    )
    db_session.commit()

    response = client.get(
        "/api/rossmann/stores",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_rossmann_allows_analyst(authenticated_client):
    response = authenticated_client.get("/api/rossmann/stores")
    assert response.status_code == 200


def test_rossmann_allows_admin(authenticated_client):
    response = authenticated_client.get("/api/rossmann/stores")
    assert response.status_code == 200

def create_user_with_role(client, db_session, email, role):
    from sqlalchemy import text

    response = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "Flashcore-Role-Test-Password-9",
        },
    )
    assert response.status_code == 201

    token = response.json()["access_token"]

    db_session.execute(
        text("UPDATE users SET role = :role WHERE email = :email"),
        {"role": role, "email": email},
    )
    db_session.commit()

    return {"Authorization": f"Bearer {token}"}


def test_analyst_can_view_simulation_products(client, db_session):
    headers = create_user_with_role(
        client, db_session, "analyst-role@example.com", "analyst"
    )

    response = client.get("/api/simulations/products", headers=headers)
    assert response.status_code == 200


def test_analyst_cannot_create_simulation_run(client, db_session):
    headers = create_user_with_role(
        client, db_session, "analyst-create@example.com", "analyst"
    )

    response = client.post(
        "/api/simulations/runs",
        headers=headers,
        json={
            "run_name": "ANALYST-FORBIDDEN",
            "description": "Permission test",
            "configuration": {},
        },
    )
    assert response.status_code == 403


def test_operator_can_create_simulation_run(client, db_session):
    headers = create_user_with_role(
        client, db_session, "operator-role@example.com", "operator"
    )

    response = client.post(
        "/api/simulations/runs",
        headers=headers,
        json={
            "run_name": "OPERATOR-ALLOWED",
            "description": "Permission test",
            "configuration": {},
        },
    )
    assert response.status_code == 201


def test_operator_cannot_view_simulation_analytics(client, db_session):
    headers = create_user_with_role(
        client, db_session, "operator-analytics@example.com", "operator"
    )

    response = client.get(
        "/api/simulations/analytics/conversion",
        headers=headers,
    )
    assert response.status_code == 403


def test_simulation_rejects_unauthenticated_requests(client):
    response = client.get("/api/simulations/products")
    assert response.status_code == 401

def test_admin_can_list_users_without_exposing_password_hash(authenticated_client):
    response = authenticated_client.get("/api/admin/users")

    assert response.status_code == 200
    assert len(response.json()) >= 1

    for user in response.json():
        assert "password_hash" not in user
        assert "access_token" not in user


def test_analyst_cannot_access_admin_users(client, db_session):
    headers = create_user_with_role(
        client, db_session, "admin-denied-analyst@example.com", "analyst"
    )

    response = client.get("/api/admin/users", headers=headers)
    assert response.status_code == 403


def test_operator_cannot_access_admin_users(client, db_session):
    headers = create_user_with_role(
        client, db_session, "admin-denied-operator@example.com", "operator"
    )

    response = client.get("/api/admin/users", headers=headers)
    assert response.status_code == 403


def test_admin_role_change_revokes_existing_user_session(
    client, authenticated_client
):
    signup = client.post(
        "/api/auth/signup",
        json={
            "email": "role-change-target@example.com",
            "password": "Flashcore-Role-Test-Password-9",
        },
    )
    assert signup.status_code == 201

    target = signup.json()["user"]
    target_token = signup.json()["access_token"]

    response = authenticated_client.patch(
        f"/api/admin/users/{target['id']}/role",
        json={"role": "operator"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "operator"

    profile = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {target_token}"},
    )
    assert profile.status_code == 401


def test_admin_can_disable_user_and_revoke_sessions(
    client, authenticated_client
):
    signup = client.post(
        "/api/auth/signup",
        json={
            "email": "disable-target@example.com",
            "password": "Flashcore-Disable-Test-Password-9",
        },
    )
    assert signup.status_code == 201

    target = signup.json()["user"]
    token = signup.json()["access_token"]

    response = authenticated_client.patch(
        f"/api/admin/users/{target['id']}/status",
        json={"status": "disabled"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "disabled"

    profile = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert profile.status_code == 401

    login = client.post(
        "/api/auth/login",
        json={
            "email": "disable-target@example.com",
            "password": "Flashcore-Disable-Test-Password-9",
        },
    )
    assert login.status_code == 401


def test_admin_can_reenable_user_for_fresh_login(
    client, authenticated_client
):
    signup = client.post(
        "/api/auth/signup",
        json={
            "email": "reenable-target@example.com",
            "password": "Flashcore-Reenable-Test-Password-9",
        },
    )
    assert signup.status_code == 201

    target_id = signup.json()["user"]["id"]

    disabled = authenticated_client.patch(
        f"/api/admin/users/{target_id}/status",
        json={"status": "disabled"},
    )
    assert disabled.status_code == 200

    enabled = authenticated_client.patch(
        f"/api/admin/users/{target_id}/status",
        json={"status": "active"},
    )
    assert enabled.status_code == 200
    assert enabled.json()["status"] == "active"

    login = client.post(
        "/api/auth/login",
        json={
            "email": "reenable-target@example.com",
            "password": "Flashcore-Reenable-Test-Password-9",
        },
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_admin_cannot_change_own_role_or_status(authenticated_client):
    profile = authenticated_client.get("/api/auth/me")
    assert profile.status_code == 200

    user_id = profile.json()["id"]

    role_response = authenticated_client.patch(
        f"/api/admin/users/{user_id}/role",
        json={"role": "analyst"},
    )
    assert role_response.status_code == 409

    status_response = authenticated_client.patch(
        f"/api/admin/users/{user_id}/status",
        json={"status": "disabled"},
    )
    assert status_response.status_code == 409

    still_active = authenticated_client.get("/api/auth/me")
    assert still_active.status_code == 200


def test_admin_user_management_returns_404_for_missing_user(
    authenticated_client
):
    role_response = authenticated_client.patch(
        "/api/admin/users/999999999/role",
        json={"role": "operator"},
    )
    assert role_response.status_code == 404

    status_response = authenticated_client.patch(
        "/api/admin/users/999999999/status",
        json={"status": "disabled"},
    )
    assert status_response.status_code == 404
