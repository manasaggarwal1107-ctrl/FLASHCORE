from datetime import date
from decimal import Decimal

import pytest

from app.models.rossmann import DatasetImport, Store, DailyStoreSale


@pytest.fixture
def rossmann_data(db_session):
    """Create a small, controlled historical dataset."""

    imported = DatasetImport(
        source_name="FLASHCORE_TEST",
        source_file="test_rossmann.csv",
        source_split="test",
        total_rows=3,
        successful_rows=3,
        rejected_rows=0,
        status="completed",
    )

    db_session.add(imported)
    db_session.flush()

    stores = [
        Store(
            store_id=101,
            store_type="a",
            assortment="a",
            competition_distance=500,
            promo2=True,
        ),
        Store(
            store_id=102,
            store_type="b",
            assortment="c",
            competition_distance=1000,
            promo2=False,
        ),
    ]

    db_session.add_all(stores)
    db_session.flush()

    sales = [
        DailyStoreSale(
            store_id=101,
            sales_date=date(2025, 1, 1),
            day_of_week=3,
            sales=Decimal("100.00"),
            customers=10,
            is_open=True,
            promo=True,
            state_holiday="0",
            school_holiday=False,
            import_id=imported.id,
        ),
        DailyStoreSale(
            store_id=101,
            sales_date=date(2025, 1, 2),
            day_of_week=4,
            sales=Decimal("200.00"),
            customers=20,
            is_open=True,
            promo=False,
            state_holiday="0",
            school_holiday=False,
            import_id=imported.id,
        ),
        DailyStoreSale(
            store_id=102,
            sales_date=date(2025, 1, 1),
            day_of_week=3,
            sales=Decimal("300.00"),
            customers=30,
            is_open=True,
            promo=True,
            state_holiday="0",
            school_holiday=True,
            import_id=imported.id,
        ),
    ]

    db_session.add_all(sales)
    db_session.commit()

    return {
        "store_ids": [101, 102],
        "import_id": imported.id,
    }


def test_list_stores_returns_seeded_stores(authenticated_client, rossmann_data):
    response = authenticated_client.get("/api/rossmann/stores")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert [item["store_id"] for item in data] == [101, 102]


def test_store_filtering(authenticated_client, rossmann_data):
    response = authenticated_client.get(
        "/api/rossmann/stores",
        params={"store_type": "a"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["store_id"] == 101


def test_store_assortment_filtering(authenticated_client, rossmann_data):
    response = authenticated_client.get(
        "/api/rossmann/stores",
        params={"assortment": "c"},
    )

    assert response.status_code == 200
    assert [item["store_id"] for item in response.json()] == [102]


def test_store_pagination(authenticated_client, rossmann_data):
    response = authenticated_client.get(
        "/api/rossmann/stores",
        params={"limit": 1, "offset": 1},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["store_id"] == 102


def test_get_existing_store(authenticated_client, rossmann_data):
    response = authenticated_client.get("/api/rossmann/stores/101")

    assert response.status_code == 200
    assert response.json()["store_id"] == 101
    assert response.json()["store_type"] == "a"


def test_get_missing_store_returns_404(authenticated_client):
    response = authenticated_client.get("/api/rossmann/stores/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Store not found"


def test_sales_filtering_by_store_and_date(authenticated_client, rossmann_data):
    response = authenticated_client.get(
        "/api/rossmann/sales",
        params={
            "store_id": 101,
            "start_date": "2025-01-01",
            "end_date": "2025-01-01",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["store_id"] == 101
    assert data[0]["sales_date"] == "2025-01-01"
    assert Decimal(data[0]["sales"]) == Decimal("100.00")


def test_sales_pagination(authenticated_client, rossmann_data):
    response = authenticated_client.get(
        "/api/rossmann/sales",
        params={"limit": 1, "offset": 0},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["sales_date"] == "2025-01-02"


def test_sales_rejects_invalid_date_range(authenticated_client):
    response = authenticated_client.get(
        "/api/rossmann/sales",
        params={
            "start_date": "2025-01-03",
            "end_date": "2025-01-01",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "start_date cannot be after end_date"
    )


def test_sales_summary_calculates_exact_totals(authenticated_client, rossmann_data):
    response = authenticated_client.get("/api/rossmann/sales/summary")

    assert response.status_code == 200

    data = response.json()

    assert data["total_records"] == 3
    assert Decimal(data["total_sales"]) == Decimal("600.00")
    assert data["average_sales"] == 200.0
    assert Decimal(data["highest_sales"]) == Decimal("300.00")
    assert data["total_customers"] == 60


def test_sales_summary_respects_store_filter(authenticated_client, rossmann_data):
    response = authenticated_client.get(
        "/api/rossmann/sales/summary",
        params={"store_id": 101},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_records"] == 2
    assert Decimal(data["total_sales"]) == Decimal("300.00")
    assert data["average_sales"] == 150.0
    assert Decimal(data["highest_sales"]) == Decimal("200.00")
    assert data["total_customers"] == 30


def test_sales_trend_aggregates_daily_sales(authenticated_client, rossmann_data):
    response = authenticated_client.get(
        "/api/rossmann/sales/trend",
        params={
            "from": "2025-01-01T00:00:00Z",
            "to": "2025-01-02T23:59:59Z",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["origin"] == "imported"
    assert data["period_start"] == "2025-01-01"
    assert data["period_end"] == "2025-01-02"
    assert data["points"] == [
        {"t": "2025-01-01", "value": 400.0},
        {"t": "2025-01-02", "value": 200.0},
    ]


def test_customers_trend_aggregates_daily_customers(
    authenticated_client, rossmann_data
):
    response = authenticated_client.get(
        "/api/rossmann/sales/customers-trend",
        params={
            "from": "2025-01-01T00:00:00Z",
            "to": "2025-01-02T23:59:59Z",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["origin"] == "imported"
    assert data["points"] == [
        {"t": "2025-01-01", "value": 40.0},
        {"t": "2025-01-02", "value": 20.0},
    ]


def test_sales_trend_rejects_reversed_period(authenticated_client):
    response = authenticated_client.get(
        "/api/rossmann/sales/trend",
        params={
            "from": "2025-01-03T00:00:00Z",
            "to": "2025-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "from cannot be after to"


def test_empty_historical_dataset_returns_empty_results(authenticated_client):
    stores = authenticated_client.get("/api/rossmann/stores")
    sales = authenticated_client.get("/api/rossmann/sales")
    trend = authenticated_client.get("/api/rossmann/sales/trend")
    customers = authenticated_client.get("/api/rossmann/sales/customers-trend")

    assert stores.status_code == 200
    assert stores.json() == []

    assert sales.status_code == 200
    assert sales.json() == []

    assert trend.status_code == 200
    assert trend.json()["points"] == []
    assert trend.json()["period_start"] is None
    assert trend.json()["period_end"] is None

    assert customers.status_code == 200
    assert customers.json()["points"] == []


def test_promotion_analysis_compares_open_store_days(
    authenticated_client, rossmann_data
):
    response = authenticated_client.get(
        "/api/rossmann/sales/promotion-analysis"
    )

    assert response.status_code == 200
    data = response.json()

    assert data["origin"] == "imported"
    assert data["comparison_basis"] == "open_store_days"

    assert data["promoted"] == {
        "open_store_days": 2,
        "total_sales": 400.0,
        "average_sales_per_store_day": 200.0,
        "total_customers": 40,
        "average_customers_per_store_day": 20.0,
    }

    assert data["non_promoted"] == {
        "open_store_days": 1,
        "total_sales": 200.0,
        "average_sales_per_store_day": 200.0,
        "total_customers": 20,
        "average_customers_per_store_day": 20.0,
    }

    assert data["period_start"] == "2025-01-01"
    assert data["period_end"] == "2025-01-02"


def test_promotion_analysis_respects_date_filters(
    authenticated_client, rossmann_data
):
    response = authenticated_client.get(
        "/api/rossmann/sales/promotion-analysis",
        params={
            "from": "2025-01-02T00:00:00Z",
            "to": "2025-01-02T23:59:59Z",
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["promoted"]["open_store_days"] == 0
    assert data["promoted"]["average_sales_per_store_day"] is None
    assert data["non_promoted"]["open_store_days"] == 1
    assert data["non_promoted"]["total_sales"] == 200.0


def test_promotion_analysis_returns_empty_groups_without_data(
    authenticated_client,
):
    response = authenticated_client.get(
        "/api/rossmann/sales/promotion-analysis"
    )

    assert response.status_code == 200
    data = response.json()

    assert data["promoted"]["open_store_days"] == 0
    assert data["promoted"]["total_sales"] is None
    assert data["non_promoted"]["open_store_days"] == 0
    assert data["non_promoted"]["total_sales"] is None
    assert data["period_start"] is None
    assert data["period_end"] is None


def test_promotion_analysis_rejects_reversed_period(
    authenticated_client,
):
    response = authenticated_client.get(
        "/api/rossmann/sales/promotion-analysis",
        params={
            "from": "2025-01-03T00:00:00Z",
            "to": "2025-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "from cannot be after to"