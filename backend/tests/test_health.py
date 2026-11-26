def test_root_endpoint_reports_application_identity(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "project": "FLASHCORE",
        "database": "flashcore_test",
        "status": "running",
    }


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_database_health_reports_actual_database(client):
    response = client.get("/health/database")

    assert response.status_code == 200
    assert response.json() == {
        "database": "flashcore_test",
        "status": "connected",
    }
