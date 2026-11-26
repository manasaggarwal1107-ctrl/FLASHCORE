
-- ============================================================
-- FLASHCORE DATABASE
-- High-Concurrency E-Commerce Flash Sale & Inventory Engine
-- PostgreSQL 18
-- ============================================================

BEGIN;

-- 1. CATEGORIES
CREATE TABLE categories (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE,
    parent_id BIGINT REFERENCES categories(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. PRODUCTS
CREATE TABLE products (
    id BIGSERIAL PRIMARY KEY,
    category_id BIGINT REFERENCES categories(id),
    name VARCHAR(200) NOT NULL,
    sku VARCHAR(80) NOT NULL UNIQUE,
    description TEXT,
    price NUMERIC(12,2) NOT NULL CHECK (price >= 0),
    currency CHAR(3) NOT NULL DEFAULT 'INR',
    origin VARCHAR(20) NOT NULL DEFAULT 'manual'
        CHECK (origin IN ('imported', 'manual', 'simulation')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. INVENTORY
CREATE TABLE inventory (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL UNIQUE REFERENCES products(id),
    quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    reserved_quantity INTEGER NOT NULL DEFAULT 0
        CHECK (reserved_quantity >= 0),
    low_stock_threshold INTEGER NOT NULL DEFAULT 5
        CHECK (low_stock_threshold >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (reserved_quantity <= quantity)
);

-- 4. CUSTOMERS
CREATE TABLE customers (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(30),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. FLASH SALES
CREATE TABLE flash_sales (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'scheduled', 'active', 'completed', 'cancelled')),
    origin VARCHAR(20) NOT NULL DEFAULT 'manual'
        CHECK (origin IN ('imported', 'manual', 'simulation')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (ends_at > starts_at)
);

-- 6. FLASH SALE PRODUCTS
CREATE TABLE flash_sale_products (
    id BIGSERIAL PRIMARY KEY,
    flash_sale_id BIGINT NOT NULL REFERENCES flash_sales(id),
    product_id BIGINT NOT NULL REFERENCES products(id),
    sale_price NUMERIC(12,2) NOT NULL CHECK (sale_price >= 0),
    allocated_quantity INTEGER NOT NULL CHECK (allocated_quantity > 0),
    sold_quantity INTEGER NOT NULL DEFAULT 0 CHECK (sold_quantity >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (flash_sale_id, product_id),
    CHECK (sold_quantity <= allocated_quantity)
);

-- 7. ORDERS
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT REFERENCES customers(id),
    order_number VARCHAR(60) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'confirmed'
        CHECK (status IN ('confirmed', 'cancelled', 'refunded')),
    total_amount NUMERIC(12,2) NOT NULL CHECK (total_amount >= 0),
    origin VARCHAR(20) NOT NULL DEFAULT 'manual'
        CHECK (origin IN ('imported', 'manual', 'simulation')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. ORDER ITEMS
CREATE TABLE order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id),
    product_id BIGINT NOT NULL REFERENCES products(id),
    flash_sale_product_id BIGINT REFERENCES flash_sale_products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0),
    subtotal NUMERIC(12,2) NOT NULL CHECK (subtotal >= 0)
);

-- 9. ORDER RETURNS
CREATE TABLE order_returns (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id),
    return_number VARCHAR(60) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'requested'
        CHECK (status IN ('requested', 'approved', 'rejected', 'completed')),
    reason TEXT,
    refund_amount NUMERIC(12,2) NOT NULL DEFAULT 0
        CHECK (refund_amount >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. ORDER RETURN ITEMS
CREATE TABLE order_return_items (
    id BIGSERIAL PRIMARY KEY,
    return_id BIGINT NOT NULL REFERENCES order_returns(id),
    order_item_id BIGINT NOT NULL REFERENCES order_items(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    refund_amount NUMERIC(12,2) NOT NULL CHECK (refund_amount >= 0)
);

-- 11. DATASET IMPORTS
CREATE TABLE dataset_imports (
    id BIGSERIAL PRIMARY KEY,
    dataset_name VARCHAR(200) NOT NULL,
    source_organisation VARCHAR(200),
    source_url TEXT,
    licence TEXT,
    file_hash VARCHAR(128),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    total_rows INTEGER NOT NULL DEFAULT 0 CHECK (total_rows >= 0),
    imported_rows INTEGER NOT NULL DEFAULT 0 CHECK (imported_rows >= 0),
    rejected_rows INTEGER NOT NULL DEFAULT 0 CHECK (rejected_rows >= 0),
    duplicate_rows INTEGER NOT NULL DEFAULT 0 CHECK (duplicate_rows >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (total_rows = imported_rows + rejected_rows + duplicate_rows)
);

-- 12. DATASET IMPORT ERRORS
CREATE TABLE dataset_import_errors (
    id BIGSERIAL PRIMARY KEY,
    import_id BIGINT NOT NULL REFERENCES dataset_imports(id),
    source_row_number INTEGER NOT NULL CHECK (source_row_number > 0),
    error_type VARCHAR(80) NOT NULL,
    error_message TEXT NOT NULL,
    raw_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 13. IDEMPOTENCY KEYS
CREATE TABLE idempotency_keys (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customers(id),
    key_value VARCHAR(255) NOT NULL,
    request_hash VARCHAR(128) NOT NULL,
    response_data JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'processing'
        CHECK (status IN ('processing', 'completed', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (customer_id, key_value)
);

-- 14. SIMULATION RUNS
CREATE TABLE simulation_runs (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    strategy VARCHAR(30) NOT NULL
        CHECK (strategy IN ('atomic_update', 'select_for_update')),
    concurrent_requests INTEGER NOT NULL CHECK (concurrent_requests > 0),
    initial_stock INTEGER NOT NULL CHECK (initial_stock >= 0),
    successful_purchases INTEGER NOT NULL DEFAULT 0,
    rejected_purchases INTEGER NOT NULL DEFAULT 0,
    overselling_incidents INTEGER NOT NULL DEFAULT 0,
    throughput NUMERIC(12,3),
    average_latency_ms NUMERIC(12,3),
    p95_latency_ms NUMERIC(12,3),
    p99_latency_ms NUMERIC(12,3),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 15. PURCHASE ATTEMPTS
CREATE TABLE purchase_attempts (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT REFERENCES customers(id),
    flash_sale_product_id BIGINT NOT NULL
        REFERENCES flash_sale_products(id),
    order_id BIGINT REFERENCES orders(id),
    idempotency_key_id BIGINT REFERENCES idempotency_keys(id),
    simulation_run_id BIGINT REFERENCES simulation_runs(id),
    status VARCHAR(20) NOT NULL
        CHECK (status IN ('success', 'rejected', 'failed')),
    failure_reason TEXT,
    origin VARCHAR(20) NOT NULL DEFAULT 'manual'
        CHECK (origin IN ('imported', 'manual', 'simulation')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- At most one successful purchase per customer per listing.
CREATE UNIQUE INDEX uq_successful_customer_listing
ON purchase_attempts(customer_id, flash_sale_product_id)
WHERE status = 'success' AND customer_id IS NOT NULL;

-- 16. TRANSACTIONS LOG
CREATE TABLE transactions_log (
    id BIGSERIAL PRIMARY KEY,
    purchase_attempt_id BIGINT REFERENCES purchase_attempts(id),
    transaction_type VARCHAR(80) NOT NULL,
    status VARCHAR(20) NOT NULL
        CHECK (status IN ('success', 'failed', 'rolled_back')),
    duration_ms NUMERIC(12,3),
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 17. AUDIT LOGS
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor VARCHAR(150),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id BIGINT,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- PERFORMANCE INDEXES
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_inventory_quantity ON inventory(quantity);
CREATE INDEX idx_flash_sales_status ON flash_sales(status);
CREATE INDEX idx_flash_sales_dates ON flash_sales(starts_at, ends_at);
CREATE INDEX idx_flash_sale_products_product ON flash_sale_products(product_id);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_created ON orders(created_at);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_purchase_attempts_listing ON purchase_attempts(flash_sale_product_id);
CREATE INDEX idx_purchase_attempts_simulation ON purchase_attempts(simulation_run_id);
CREATE INDEX idx_transactions_created ON transactions_log(created_at);
CREATE INDEX idx_audit_created ON audit_logs(created_at);
CREATE INDEX idx_import_errors_import ON dataset_import_errors(import_id);

COMMIT;
