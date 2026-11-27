import main as main_module


def test_root_endpoint_reports_application_identity_without_db_leak(client):
    response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "project": "FLASHCORE",
        "status": "running",
    }
    assert "database" not in payload


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_database_health_reports_connected_without_db_name_leak(client):
    response = client.get("/health/database")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"status": "connected"}
    assert "flashcore" not in str(payload).lower()


def test_database_health_handles_outage_gracefully(client, monkeypatch):
    def broken_connect():
        raise RuntimeError("postgresql://secret:password@db.internal/prod_db")

    monkeypatch.setattr(main_module.engine, "connect", broken_connect)

    r1 = client.get("/health/database")
    assert r1.status_code == 503
    assert r1.json() == {"status": "unavailable"}

    r2 = client.get("/api/health")
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "degraded"
    assert body["database"] == "Unavailable"
    assert "secret" not in str(body)
    assert "prod_db" not in str(body)

    r3 = client.get("/ready")
    assert r3.status_code == 503
    ready_body = r3.json()
    assert ready_body["status"] == "not_ready"
    assert ready_body["database"] == "unavailable"
    assert "secret" not in str(ready_body)
    assert "prod_db" not in str(ready_body)


def test_readiness_and_api_health_report_revision_and_environment(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abcdef1234567890")

    ready = client.get("/ready")
    assert ready.status_code == 200
    payload = ready.json()
    assert payload["status"] == "ready"
    assert payload["environment"] == "staging"
    assert payload["commit_sha"] == "abcdef123456"
    assert payload["database"] == "connected"
    assert payload["migrations"] == "ready"
    assert payload["alembic_revision"] == main_module.EXPECTED_ALEMBIC_REVISION

    api_health = client.get("/api/health")
    assert api_health.status_code == 200
    health_payload = api_health.json()
    assert health_payload["status"] == "healthy"
    assert health_payload["environment"] == "staging"
    assert health_payload["commit_sha"] == "abcdef123456"
    assert health_payload["alembic_revision"] == main_module.EXPECTED_ALEMBIC_REVISION


def test_readiness_returns_503_when_migrations_are_outdated(client, monkeypatch):
    monkeypatch.setattr(main_module, "_read_alembic_revision", lambda _conn: "0003_commerce_and_payments")

    response = client.get("/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["migrations"] == "outdated"
    assert payload["alembic_revision"] == "0003_commerce_and_payments"
