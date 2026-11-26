
BEGIN;

-- =========================================================
-- 1. DATASET IMPORT PROVENANCE
-- =========================================================

CREATE TABLE dataset_imports (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_name VARCHAR(150) NOT NULL,
    source_url TEXT,
    source_file VARCHAR(255) NOT NULL,
    source_split VARCHAR(30) NOT NULL,
    checksum_sha256 VARCHAR(64),
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_rows INTEGER NOT NULL DEFAULT 0,
    successful_rows INTEGER NOT NULL DEFAULT 0,
    rejected_rows INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    CONSTRAINT chk_import_status
        CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    CONSTRAINT chk_import_counts
        CHECK (
            total_rows >= 0 AND
            successful_rows >= 0 AND
            rejected_rows >= 0
        )
);

CREATE TABLE dataset_import_errors (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_id BIGINT NOT NULL REFERENCES dataset_imports(id),
    source_row_number INTEGER,
    raw_record JSONB,
    error_message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =========================================================
-- 2. AUTHENTIC ROSSMANN STORE METADATA
-- =========================================================

CREATE TABLE stores (
    store_id INTEGER PRIMARY KEY,
    store_type VARCHAR(1),
    assortment VARCHAR(1),
    competition_distance INTEGER,
    competition_open_since_month INTEGER,
    competition_open_since_year INTEGER,
    promo2 BOOLEAN,
    promo2_since_week INTEGER,
    promo2_since_year INTEGER,
    promo_interval VARCHAR(100),
    metadata_import_id BIGINT REFERENCES dataset_imports(id),

    CONSTRAINT chk_store_type
        CHECK (store_type IS NULL OR store_type IN ('a', 'b', 'c', 'd')),

    CONSTRAINT chk_assortment
        CHECK (assortment IS NULL OR assortment IN ('a', 'b', 'c')),

    CONSTRAINT chk_competition_distance
        CHECK (competition_distance IS NULL OR competition_distance >= 0)
);

-- =========================================================
-- 3. AUTHENTIC HISTORICAL DAILY SALES
-- =========================================================

CREATE TABLE daily_store_sales (
    store_id INTEGER NOT NULL REFERENCES stores(store_id),
    sales_date DATE NOT NULL,
    day_of_week SMALLINT NOT NULL,
    sales NUMERIC(12,2) NOT NULL,
    customers INTEGER NOT NULL,
    is_open BOOLEAN NOT NULL,
    promo BOOLEAN NOT NULL,
    state_holiday VARCHAR(1) NOT NULL DEFAULT '0',
    school_holiday BOOLEAN NOT NULL,
    import_id BIGINT NOT NULL REFERENCES dataset_imports(id),
    source_row_number INTEGER,

    PRIMARY KEY (store_id, sales_date),

    CONSTRAINT chk_day_of_week
        CHECK (day_of_week BETWEEN 1 AND 7),

    CONSTRAINT chk_sales
        CHECK (sales >= 0),

    CONSTRAINT chk_customers
        CHECK (customers >= 0),

    CONSTRAINT chk_state_holiday
        CHECK (state_holiday IN ('0', 'a', 'b', 'c'))
);

CREATE INDEX idx_daily_sales_date
    ON daily_store_sales(sales_date);

CREATE INDEX idx_daily_sales_store_date
    ON daily_store_sales(store_id, sales_date);

CREATE INDEX idx_daily_sales_promo
    ON daily_store_sales(promo);

-- =========================================================
-- 4. DBMS SIMULATION RUNS
-- =========================================================

CREATE TABLE simulation_runs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_name VARCHAR(150) NOT NULL,
    description TEXT,
    configuration JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'created',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_simulation_status
        CHECK (status IN ('created', 'running', 'completed', 'failed'))
);

-- =========================================================
-- 5. SIMULATED PRODUCTS
-- These are NOT authentic Rossmann products.
-- =========================================================

CREATE TABLE simulation_products (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku VARCHAR(80) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =========================================================
-- 6. SIMULATED STORE INVENTORY
-- =========================================================

CREATE TABLE simulation_inventory (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(store_id),
    product_id BIGINT NOT NULL REFERENCES simulation_products(id),
    quantity INTEGER NOT NULL DEFAULT 0,
    reserved_quantity INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_simulation_store_product
        UNIQUE (store_id, product_id),

    CONSTRAINT chk_simulation_quantity
        CHECK (quantity >= 0 AND reserved_quantity >= 0),

    CONSTRAINT chk_simulation_reserved
        CHECK (reserved_quantity <= quantity)
);

-- =========================================================
-- 7. SIMULATED FLASH-SALE CAMPAIGNS
-- =========================================================

CREATE TABLE flash_sales (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    simulation_run_id BIGINT NOT NULL REFERENCES simulation_runs(id),
    title VARCHAR(200) NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_flash_sale_dates
        CHECK (ends_at > starts_at),

    CONSTRAINT chk_flash_sale_status
        CHECK (status IN ('draft', 'scheduled', 'active', 'completed', 'cancelled'))
);

CREATE TABLE flash_sale_products (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    flash_sale_id BIGINT NOT NULL REFERENCES flash_sales(id),
    inventory_id BIGINT NOT NULL REFERENCES simulation_inventory(id),
    sale_price NUMERIC(12,2) NOT NULL,
    stock_limit INTEGER NOT NULL,
    sold_quantity INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT uq_flash_sale_inventory
        UNIQUE (flash_sale_id, inventory_id),

    CONSTRAINT chk_sale_price
        CHECK (sale_price >= 0),

    CONSTRAINT chk_sale_stock
        CHECK (
            stock_limit > 0 AND
            sold_quantity >= 0 AND
            sold_quantity <= stock_limit
        )
);

-- =========================================================
-- 8. SIMULATED PURCHASE ATTEMPTS
-- customer_ref is a simulation identifier, NOT a real customer.
-- =========================================================

CREATE TABLE purchase_attempts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    simulation_run_id BIGINT NOT NULL REFERENCES simulation_runs(id),
    flash_sale_product_id BIGINT NOT NULL REFERENCES flash_sale_products(id),
    customer_ref VARCHAR(100) NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL UNIQUE,
    quantity INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_purchase_quantity
        CHECK (quantity > 0),

    CONSTRAINT chk_purchase_status
        CHECK (status IN ('pending', 'success', 'rejected', 'failed'))
);

CREATE UNIQUE INDEX uq_successful_customer_purchase
    ON purchase_attempts(customer_ref, flash_sale_product_id)
    WHERE status = 'success';

CREATE INDEX idx_purchase_attempts_run
    ON purchase_attempts(simulation_run_id);

CREATE INDEX idx_purchase_attempts_status
    ON purchase_attempts(status);

-- =========================================================
-- 9. TRANSACTION LOG
-- =========================================================

CREATE TABLE transactions_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    simulation_run_id BIGINT NOT NULL REFERENCES simulation_runs(id),
    purchase_attempt_id BIGINT REFERENCES purchase_attempts(id),
    action VARCHAR(100) NOT NULL,
    outcome JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =========================================================
-- 10. AUDIT LOG
-- =========================================================

CREATE TABLE audit_logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_type VARCHAR(50),
    actor_ref VARCHAR(100),
    action VARCHAR(100) NOT NULL,
    entity_name VARCHAR(100) NOT NULL,
    entity_id VARCHAR(100),
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_entity
    ON audit_logs(entity_name, entity_id);

COMMIT;
