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
        "organisations",
        "organisation_memberships",
        "commerce_products",
        "inventory_locations",
        "inventory_balances",
        "inventory_movements",
        "customers",
        "orders",
        "order_items",
        "inventory_reservations",
        "order_events",
        "payment_provider_accounts",
        "payment_orders",
        "payment_attempts",
        "payment_transactions",
        "payment_webhook_events",
        "payment_approval_policies",
        "payment_refunds",
        "payment_approval_requests",
        "payment_refund_events",
        "payment_links",
        "payment_statement_imports",
        "payment_settlements",
        "payment_settlement_items",
        "payment_reconciliation_runs",
        "payment_reconciliation_items",
        "stock_transfers",
        "suppliers",
        "purchase_orders",
        "purchase_order_items",
        "surge_campaigns",
        "surge_campaign_products",
        "promotions",
        "promotion_redemptions",
        "sales_records",
        "order_returns",
        "order_return_items",
        "notifications",
        "voice_sessions",
        "voice_messages",
        "ai_action_proposals",
        "ai_usage_logs",
        "org_tax_profiles",
        "invoices",
        "pos_shifts",
        "pos_held_bills",
        "order_payment_splits",
        "purchase_requisitions",
        "supplier_invoices",
        "loyalty_ledger",
        "automation_rules",
        "alembic_version",
    }

    assert set(tables) == expected_tables
