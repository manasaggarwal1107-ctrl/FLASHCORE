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
