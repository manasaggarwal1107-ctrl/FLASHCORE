def test_signup_creates_analyst_and_returns_valid_token(client):
    response = client.post(
        "/api/auth/signup",
        json={
            "email": "analyst@example.com",
            "password": "Correct-Horse-Battery-9",
        },
    )

    assert response.status_code == 201
    data = response.json()

    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"]["email"] == "analyst@example.com"
    assert data["user"]["role"] == "analyst"
    assert data["user"]["status"] == "active"
    assert "password_hash" not in data["user"]

    profile = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )

    assert profile.status_code == 200
    assert profile.json()["email"] == "analyst@example.com"


def test_signup_rejects_duplicate_email_case_insensitively(client):
    payload = {
        "email": "duplicate@example.com",
        "password": "Correct-Horse-Battery-9",
    }

    first = client.post("/api/auth/signup", json=payload)
    second = client.post(
        "/api/auth/signup",
        json={
            "email": "DUPLICATE@example.com",
            "password": "Another-Strong-Password-9",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_signup_rejects_short_password(client):
    response = client.post(
        "/api/auth/signup",
        json={
            "email": "short@example.com",
            "password": "short",
        },
    )

    assert response.status_code == 422


def test_login_accepts_valid_credentials_case_insensitively(client):
    client.post(
        "/api/auth/signup",
        json={
            "email": "login@example.com",
            "password": "Correct-Horse-Battery-9",
        },
    )

    response = client.post(
        "/api/auth/login",
        json={
            "email": "LOGIN@example.com",
            "password": "Correct-Horse-Battery-9",
        },
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["user"]["role"] == "analyst"


def test_login_rejects_wrong_password(client):
    client.post(
        "/api/auth/signup",
        json={
            "email": "wrongpass@example.com",
            "password": "Correct-Horse-Battery-9",
        },
    )

    response = client.post(
        "/api/auth/login",
        json={
            "email": "wrongpass@example.com",
            "password": "Incorrect-Password-9",
        },
    )

    assert response.status_code == 401


def test_profile_rejects_missing_token(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_logout_revokes_session_and_token(client):
    signup = client.post(
        "/api/auth/signup",
        json={
            "email": "logout@example.com",
            "password": "Correct-Horse-Battery-9",
        },
    )

    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    before_logout = client.get("/api/auth/me", headers=headers)
    assert before_logout.status_code == 200

    logout = client.post("/api/auth/logout", headers=headers)
    assert logout.status_code == 204

    after_logout = client.get("/api/auth/me", headers=headers)
    assert after_logout.status_code == 401
