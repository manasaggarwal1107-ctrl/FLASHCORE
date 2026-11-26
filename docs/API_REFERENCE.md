# FLASHCORE — Complete RESTful API Reference Specification
## OpenAPI 3.1 Contract: 42 Endpoints, Request/Response Models, RBAC & Idempotency

> **Student:** Manas Aggarwal (Roll No. 2501730302)  
> **Course / Programme:** B.Tech CSE (AI/ML), 3rd Semester, Section A  
> **Supervisor:** Ms. Mansi Kajal, Assistant Professor, SOET, K.R. Mangalam University  
> **Framework:** FastAPI (Python 3.13 / Starlette ASGI)  
> **Verification Status:** 42 Verified Production Routes, Validated via Automated Test Matrix  

---

# FLASHCORE — Complete API Specification & Endpoint Reference Manual
## Exhaustive Reference of 42 Registered OpenAPI Paths & 45 HTTP Operations

> **Project:** FLASHCORE — Retail Intelligence & High-Concurrency Simulation Platform  
> **Course:** B.Tech Capstone Project in Computer Science & Engineering  
> **Framework:** FastAPI / OpenAPI 3.1.0 Specification  
> **Production API Base:** `https://database-management-system-s1g5.onrender.com/api`  
> **Target Commit:** `50916f873066e0e25e7a0fec0673efb875a1a0df` (`50916f8`)  
> **Status:** Stage 4 Final Academic API Reference  

---

## 1. Authentication & Security Conventions

- **Authentication Scheme:** HTTP Bearer authentication using JSON Web Tokens (JWT) signed with HS256.
- **Authorization Header:** `Authorization: Bearer <jwt_access_token>`
- **Token Lifetime:** 30 minutes from issuance (`expires_at`).
- **Session Tracking:** Every token carries a unique UUIDv4 `jti` claim mapped to `auth_sessions`.
- **Role Hierarchy:**
  - `admin`: Superuser access to user management, role modification, status toggling, and audit logs.
  - `analyst`: Read access to historical analytics, store data, simulation telemetry, and conversion metrics.
  - `operator`: Write access to simulation runs, products, inventory allocations, flash sales, and purchase executions.
- **Error Conventions:** Standard RFC 7807 formatted error bodies: `{"detail": "<error_message>"}`.

---

## 2. Infrastructure & System Health Endpoints

### 2.1 `GET /` — Project Identity & Root Status
- **Purpose:** Health check confirming running FastAPI container.
- **Authentication:** Public (None).
- **Responses:**
  - `200 OK`: `{"project": "FLASHCORE", "database": "flashcore_postgres_temp", "status": "running"}`

### 2.2 `GET /health` — Container Liveness Probe
- **Purpose:** Fast container orchestrator probe (Render liveness check).
- **Authentication:** Public (None).
- **Responses:**
  - `200 OK`: `{"status": "healthy"}`

### 2.3 `GET /health/database` — Direct Database Socket Probe
- **Purpose:** Direct SQL ping to PostgreSQL (`SELECT current_database()`).
- **Authentication:** Public (None).
- **Responses:**
  - `200 OK`: `{"database": "flashcore_postgres_temp", "status": "connected"}`

### 2.4 `GET /api/health` — Structured System Telemetry
- **Purpose:** Comprehensive component-level telemetry for frontend dashboard.
- **Authentication:** Public (None).
- **Responses:**
  - `200 OK`: 
    ```json
    {
      "status": "healthy",
      "version": "1.0.0",
      "database": "flashcore_postgres_temp",
      "services": [
        {"name": "FastAPI Application", "status": "healthy", "detail": "Operational (v1.0.0)"},
        {"name": "PostgreSQL Database", "status": "healthy", "detail": "Connected to flashcore_postgres_temp"}
      ],
      "checked_at": "2026-11-24T20:25:00Z"
    }
    ```

### 2.5 `GET /api/health/database` — API Database Health
- **Purpose:** API-scoped database connectivity probe.
- **Authentication:** Public (None).
- **Responses:**
  - `200 OK`: `{"database": "flashcore_postgres_temp", "status": "connected"}`

---

## 3. Authentication & Session Management

### 3.1 `POST /api/auth/signup` — User Registration
- **Purpose:** Self-service user account creation (assigns default role `analyst`).
- **Authentication:** Public (None).
- **Request Body:**
  ```json
  {"email": "analyst@retail.example.com", "password": "SecurePassword123!"}
  ```
- **Validation:** Email regex validated, normalized lowercase; password `min_length: 12`.
- **Responses:**
  - `201 Created`: `{"access_token": "ey...", "token_type": "bearer", "expires_at": "...", "user": {"id": 1, "email": "...", "role": "analyst", "status": "active"}}`
  - `409 Conflict`: Duplicate email registration.
  - `422 Unprocessable Entity`: Password < 12 characters or malformed email.

### 3.2 `POST /api/auth/login` — Authentication Gateway
- **Purpose:** Authenticates user via Argon2id password hash verification; issues JWT.
- **Authentication:** Public (None).
- **Request Body:**
  ```json
  {"email": "analyst@retail.example.com", "password": "SecurePassword123!"}
  ```
- **Responses:**
  - `200 OK`: Returns access token and user metadata.
  - `401 Unauthorized`: Invalid email or password.
  - `403 Forbidden`: Account is disabled.

### 3.3 `GET /api/auth/me` — Current User Profile
- **Purpose:** Retrieves authenticated user's profile and active role.
- **Authentication:** Bearer JWT required (Any active role).
- **Responses:**
  - `200 OK`: `{"id": 1, "email": "...", "role": "analyst", "status": "active", "created_at": "..."}`
  - `401 Unauthorized`: Missing, expired, or revoked token.
  - `403 Forbidden`: Account is disabled.

### 3.4 `POST /api/auth/logout` — Session Invalidation
- **Purpose:** Explicitly revokes active JWT session token in `auth_sessions`.
- **Authentication:** Bearer JWT required.
- **Responses:**
  - `204 No Content`: Session successfully revoked (`revoked_at` set to current timestamp).

---

## 4. Administration & User Management

### 4.1 `GET /api/admin/users` — List Platform Users
- **Purpose:** Lists all registered users (passwords and hashes strictly excluded).
- **Authentication:** Bearer JWT (`role: admin` only).
- **Responses:**
  - `200 OK`: `[{"id": 1, "email": "admin@flashcore.test", "role": "admin", "status": "active", "created_at": "..."}]`
  - `403 Forbidden`: Insufficient permissions.

### 4.2 `PATCH /api/admin/users/{user_id}/role` — Update User Role
- **Purpose:** Promotes or demotes user role (`admin`, `analyst`, `operator`).
- **Authentication:** Bearer JWT (`role: admin` only).
- **Request Body:** `{"role": "operator"}`
- **Responses:**
  - `200 OK`: Updated user profile.
  - `409 Conflict`: Admin attempting to mutate self or demote the last active admin.

### 4.3 `PATCH /api/admin/users/{user_id}/status` — Enable / Disable User
- **Purpose:** Suspends or activates user account; revokes all active sessions upon disabling.
- **Authentication:** Bearer JWT (`role: admin` only).
- **Request Body:** `{"status": "disabled"}`
- **Responses:**
  - `200 OK`: Updated user profile.
  - `409 Conflict`: Admin attempting to disable own account.

### 4.4 `GET /api/admin/audit-logs` — Immutable Audit Trail
- **Purpose:** Query platform audit logs with pagination and secret sanitization.
- **Authentication:** Bearer JWT (`role: admin` only).
- **Query Parameters:** `page`, `pageSize`, `action`, `entityType`, `from`, `to`, `search`.
- **Responses:**
  - `200 OK`: Paginated audit log records with sanitized metadata.

---

## 5. Dataset Imports & Ingestion History

### 5.1 `GET /api/imports` — Ingestion History List
- **Purpose:** Lists dataset imports with source file, split, row counts, and checksums.
- **Authentication:** Bearer JWT (`admin`, `analyst`).
- **Query Parameters:** `page`, `pageSize`, `search`.
- **Responses:**
  - `200 OK`: `{"items": [{"id": "1", "filename": "train.csv", "status": "completed", ...}], "total": 1}`

### 5.2 `GET /api/imports/{import_id}` — Import Details & Errors
- **Purpose:** Detailed provenance record and row-level error log.
- **Authentication:** Bearer JWT (`admin`, `analyst`).
- **Responses:**
  - `200 OK`: Detail payload with `errors` array.
  - `404 Not Found`: Import ID missing.

---

## 6. Rossmann Historical Retail Analytics

### 6.1 `GET /api/rossmann/stores` — Store Directory
- **Purpose:** Paginated list of Rossmann retail pharmacy stores.
- **Authentication:** Bearer JWT (`admin`, `analyst`).
- **Query Parameters:** `store_type` (`a,b,c,d`), `assortment` (`a,b,c`), `limit`, `offset`.
- **Responses:**
  - `200 OK`: Array of `StoreOut` objects.

### 6.2 `GET /api/rossmann/stores/{store_id}` — Store Profile
- **Purpose:** Detailed metadata for a single store (competition distance, promo2 flags).
- **Authentication:** Bearer JWT (`admin`, `analyst`).
- **Responses:**
  - `200 OK`: `StoreOut` metadata.
  - `404 Not Found`: Store ID not found.

### 6.3 `GET /api/rossmann/sales` — Daily Store Sales
- **Purpose:** Filtered daily store sales history.
- **Authentication:** Bearer JWT (`admin`, `analyst`).
- **Query Parameters:** `store_id`, `start_date`, `end_date`, `limit`, `offset`.
- **Responses:**
  - `200 OK`: Array of `DailyStoreSaleOut` records.
  - `400 Bad Request`: `start_date > end_date`.

### 6.4 `GET /api/rossmann/sales/summary` — Aggregate Historical Totals
- **Purpose:** Computes total sales revenue, customer footfall, average basket size, and open store days.
- **Authentication:** Bearer JWT (`admin`, `analyst`).
- **Query Parameters:** `store_id`, `start_date`, `end_date`.
- **Responses:**
  - `200 OK`: `{"total_sales": 5420500.0, "total_customers": 550000, "average_basket": 9.86, ...}`

### 6.5 `GET /api/rossmann/sales/trend` — Daily Revenue Trend
- **Purpose:** Daily aggregated revenue time series.
- **Authentication:** Bearer JWT (`admin`, `analyst`).
- **Responses:**
  - `200 OK`: Array of daily revenue points.

### 6.6 `GET /api/rossmann/sales/customers-trend` — Daily Customer Trend
- **Purpose:** Daily aggregated footfall time series.
- **Authentication:** Bearer JWT (`admin`, `analyst`).
- **Responses:**
  - `200 OK`: Array of daily customer count points.

### 6.7 `GET /api/rossmann/sales/promotion-analysis` — Promo Impact Comparison
- **Purpose:** Evaluates promotional efficacy comparing Promo Days vs Non-Promo Days.
- **Authentication:** Bearer JWT (`admin`, `analyst`).
- **Responses:**
  - `200 OK`: Comparative performance metrics with sales uplift percentages.

---

## 7. Retail Simulation Engine & Catalog

### 7.1 `GET /api/simulations/strategies` — Simulation Concurrency Strategies
- **Purpose:** Algorithmic concurrency strategies supported by the platform.
- **Authentication:** Public (None).
- **Responses:**
  - `200 OK`: Returns strategy profiles (`atomic_update`, `select_for_update`).

### 7.2 `GET /api/simulations/runs` — List Simulation Runs
- **Purpose:** Lists active and historical simulation runs.
- **Authentication:** Bearer JWT (`admin`, `analyst`, `operator`).
- **Responses:**
  - `200 OK`: Array of simulation runs.

### 7.3 `POST /api/simulations/runs` — Create Simulation Run
- **Purpose:** Initializes a new retail simulation run.
- **Authentication:** Bearer JWT (`admin`, `operator`).
- **Request Body:**
  ```json
  {"run_name": "Peak Weekend Simulation", "description": "High load run", "configuration": {}}
  ```
- **Responses:**
  - `201 Created`: Simulation run profile (`status: created`).

### 7.4 `GET /api/simulations/runs/{run_id}/summary` — Simulation Performance Summary
- **Purpose:** Aggregates run-level purchase attempts, conversion rate, and flash sale status.
- **Authentication:** Bearer JWT (`admin`, `analyst`, `operator`).
- **Responses:**
  - `200 OK`: Run summary telemetry.
  - `404 Not Found`: Run ID does not exist.

### 7.5 `GET /api/simulations/products` — Product Catalog
- **Purpose:** Lists simulation products.
- **Authentication:** Bearer JWT (`admin`, `analyst`, `operator`).
- **Responses:**
  - `200 OK`: Array of products with SKUs.

### 7.6 `POST /api/simulations/products` — Provision Product
- **Purpose:** Registers a new SKU product in the simulation catalog.
- **Authentication:** Bearer JWT (`admin`, `operator`).
- **Request Body:** `{"sku": "SKU-9901", "name": "Immune Defense Multi-Pack"}`
- **Responses:**
  - `201 Created`: Product record.
  - `409 Conflict`: SKU already exists.

### 7.7 `GET /api/simulations/inventory` — Physical Inventory
- **Purpose:** Multi-store stock inventory listings.
- **Authentication:** Bearer JWT (`admin`, `analyst`, `operator`).
- **Responses:**
  - `200 OK`: Array of inventory records with physical and reserved quantities.

### 7.8 `POST /api/simulations/inventory` — Assign Store Stock
- **Purpose:** Allocates physical stock to a specific store for a product.
- **Authentication:** Bearer JWT (`admin`, `operator`).
- **Request Body:** `{"store_id": 1, "product_id": 10, "quantity": 500}`
- **Responses:**
  - `201 Created`: Inventory record.
  - `409 Conflict`: Store-product combination already registered.

### 7.9 `POST /api/simulations/inventory/{inventory_id}/adjust` — Stock Adjustment
- **Purpose:** Adjusts physical inventory with mandatory delta and audit reason.
- **Authentication:** Bearer JWT (`admin`, `operator`).
- **Request Body:** `{"quantity_delta": -10, "reason": "Damaged goods return"}`
- **Responses:**
  - `200 OK`: Updated inventory record.
  - `409 Conflict`: Delta would cause physical stock to fall below reserved stock.

---

## 8. Flash Sales & High-Concurrency Commerce

### 8.1 `POST /api/simulations/runs/{run_id}/flash-sales` — Schedule Flash Sale
- **Purpose:** Schedules a time-bounded flash sale under a simulation run.
- **Authentication:** Bearer JWT (`admin`, `operator`).
- **Request Body:**
  ```json
  {"title": "Midnight Drop", "starts_at": "2026-11-25T00:00:00Z", "ends_at": "2026-11-25T02:00:00Z"}
  ```
- **Responses:**
  - `201 Created`: Flash sale record (`status: draft`).

### 8.2 `POST /api/simulations/flash-sales/{sale_id}/activate` — Activate Flash Sale
- **Purpose:** Shifts flash sale status to `active`.
- **Authentication:** Bearer JWT (`admin`, `operator`).
- **Responses:**
  - `200 OK`: Updated flash sale record (`status: active`).

### 8.3 `POST /api/simulations/flash-sales/{sale_id}/products` — Allocate Sale Quota
- **Purpose:** Reserves inventory quota for a flash sale at a discounted price.
- **Authentication:** Bearer JWT (`admin`, `operator`).
- **Request Body:** `{"inventory_id": 1, "sale_price": "14.99", "stock_limit": 100}`
- **Responses:**
  - `201 Created`: Flash sale product quota record.

### 8.4 `POST /api/simulations/flash-sale-products/{sale_product_id}/purchase` — Atomic Purchase
- **Purpose:** Executes high-concurrency purchase with row locking and idempotency protection.
- **Authentication:** Bearer JWT (`admin`, `operator`).
- **Request Body:**
  ```json
  {"customer_ref": "CUST-90210", "idempotency_key": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d", "quantity": 1}
  ```
- **Responses:**
  - `200 OK (Success)`: `{"success": true, "attempt": {"id": 105, "status": "success"}, "message": "Purchase completed successfully"}`
  - `200 OK (Duplicate Idempotent)`: `{"duplicate": true, "attempt": {"id": 105, ...}}`
  - `200 OK (Rejected)`: `{"success": false, "attempt": {"status": "rejected"}, "message": "Flash sale stock limit exceeded"}`
  - `409 Conflict`: Idempotency key reused with mismatched purchase payload.

---

## 9. Simulation Analytics & Real-Time Intelligence

### 9.1 `GET /api/simulations/transactions` — Transaction Feed
- **Purpose:** Real-time log of customer purchase attempts.
- **Authentication:** Bearer JWT (`admin`, `analyst`, `operator`).
- **Responses:**
  - `200 OK`: Array of purchase transactions.

### 9.2 `GET /api/simulations/transactions/{attempt_id}` — Transaction Detail
- **Purpose:** Detailed purchase attempt record and failure rationale.
- **Authentication:** Bearer JWT (`admin`, `analyst`, `operator`).
- **Responses:**
  - `200 OK`: Transaction details.

### 9.3 `GET /api/simulations/analytics/conversion` — Conversion Time Series
- **Purpose:** Time series of completed vs successful purchases.
- **Authentication:** Bearer JWT (`admin`, `analyst`).

### 9.4 `GET /api/simulations/analytics/failure-rates` — Failure Rate Analytics
- **Purpose:** Time series of failure/rejection rates.
- **Authentication:** Bearer JWT (`admin`, `analyst`).

### 9.5 `GET /api/simulations/analytics/inventory-utilisation` — Inventory Utilization
- **Purpose:** Stock depletion and reservation ratios.
- **Authentication:** Bearer JWT (`admin`, `analyst`).

### 9.6 `GET /api/simulations/analytics/flash-sale-performance` — Performance Metrics
- **Purpose:** Sold volume, sell-through percentage, and revenue generated per flash sale.
- **Authentication:** Bearer JWT (`admin`, `analyst`).

### 9.7 `GET /api/simulations/analytics/purchase-outcomes` — Purchase Outcome Breakdown
- **Purpose:** Quantitative categorization of success, out-of-stock, and customer limit rejections.
- **Authentication:** Bearer JWT (`admin`, `analyst`).

### 9.8 `GET /api/simulations/analytics/activity` — Real-Time Activity Feed
- **Purpose:** High-level activity telemetry across simulation runs.
- **Authentication:** Bearer JWT (`admin`, `analyst`).
