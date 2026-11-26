from sqlalchemy import text


def test_database_connection_is_isolated(db_session):
    database_name = db_session.execute(
        text("SELECT current_database()")
    ).scalar_one()

    assert database_name == "flashcore_test"


def test_active_schema_contains_all_expected_tables(db_session):
    tables = db_session.execute(
        text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
        """)
    ).scalars().all()

    expected_tables = {
        "dataset_imports",
        "dataset_import_errors",
        "stores",
        "daily_store_sales",
        "simulation_runs",
        "simulation_products",
        "simulation_inventory",
        "flash_sales",
        "flash_sale_products",
        "purchase_attempts",
        "transactions_log",
        "audit_logs",
        "users",
        "auth_sessions",
    }

    assert set(tables) == expected_tables
