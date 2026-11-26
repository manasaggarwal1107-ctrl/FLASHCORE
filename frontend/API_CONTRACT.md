# FLASHCORE API Contract Specification

> **Status:** Reconciled and verified against FastAPI backend (`backend/main.py`) and live Render deployment.
> **API Base Prefix:** `/api` (relative to host or configured `VITE_API_BASE_URL`)
> **Transport:** JSON over REST / HTTP.
> **Authentication:** Bearer token via `Authorization: Bearer <token>` header. Token obtained from `/api/auth/login`.

---

## 1. Authentication & Security

- **Scheme:** Bearer JWT in the HTTP `Authorization` request header.
- **Login:** `POST /api/auth/login` (Body: `{ "username": "...", "password": "..." }`) returns `{ "access_token": "...", "token_type": "bearer", "role": "..." }`.
- **User Profile:** `GET /api/auth/me` returns current user record.
- **Signup:** `POST /api/auth/signup` creates a new account.
- **Logout:** `POST /api/auth/logout` revokes the session.
- **Role Enforcement:**
  - `admin`: Full administrative access (audit logs, user role assignment).
  - `analyst`: Access to analytics, historical sales, and import inspection.
  - `viewer` / unauthenticated: Read-only access to public routes or 401/403 on protected routes.
- **Protection:** All sensitive tokens, hashes, and secrets are strictly redacted in audit and logging endpoints.

---

## 2. Standard Envelopes & Conventions

### Pagination Envelope
Paginated collection endpoints return the canonical envelope:
```json
{
  "items": [ ... ],
  "total": 128,
  "page": 1,
  "pageSize": 25
}
```
Query parameters: `page` (default `1`), `pageSize` (default `25`, max `100`), `search` (optional string), plus endpoint-specific filter keys.

### Error Envelope
Standard FastAPI error representation:
```json
{
  "detail": "Descriptive error message"
}
```
Validation errors return `422 Unprocessable Entity` with field-level details under `detail`.

### Data Origin Distinction
Every analytical and simulation record includes an `origin` discriminator:
- `real`: Derived from historical authentic data (e.g. Rossmann dataset).
- `imported`: Derived from explicit CSV/dataset imports.
- `simulation`: Generated exclusively during high-concurrency simulation lab runs. Simulation data is isolated and never conflated with historical sales.

---

## 3. Verified Endpoints Registry

| Category | Method | Path | Status | Roles / Auth | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **System** | `GET` | `/health` | Confirmed | Public | Root and `/api/health` system and db status |
| **System** | `GET` | `/health/database` | Confirmed | Public | PostgreSQL connection verification |
| **Auth** | `POST` | `/api/auth/signup` | Confirmed | Public | User registration |
| **Auth** | `POST` | `/api/auth/login` | Confirmed | Public | Returns Bearer access token |
| **Auth** | `GET` | `/api/auth/me` | Confirmed | Authenticated | Current user identity & roles |
| **Auth** | `POST` | `/api/auth/logout` | Confirmed | Authenticated | Session invalidation |
| **Rossmann** | `GET` | `/api/rossmann/sales/summary` | Confirmed | Authenticated | Overall sales & record counts |
| **Rossmann** | `GET` | `/api/rossmann/sales/trend` | Confirmed | Authenticated | Daily sales time series (`from`, `to`) |
| **Rossmann** | `GET` | `/api/rossmann/sales/customers-trend` | Confirmed | Authenticated | Customer traffic time series |
| **Rossmann** | `GET` | `/api/rossmann/sales/promotion-analysis` | Confirmed | Authenticated | Promo vs non-promo comparison |
| **Simulation** | `GET` | `/api/simulations/products` | Confirmed | Authenticated | Simulation products catalogue |
| **Simulation** | `POST` | `/api/simulations/products` | Confirmed | Analyst, Admin | Create simulation product |
| **Simulation** | `GET` | `/api/simulations/inventory` | Confirmed | Authenticated | Physical inventory ledger |
| **Simulation** | `POST` | `/api/simulations/inventory/:id/adjust` | Confirmed | Admin | Stock adjustment |
| **Simulation** | `GET` | `/api/simulations/runs` | Confirmed | Authenticated | Simulation run history |
| **Simulation** | `POST` | `/api/simulations/runs` | Confirmed | Analyst, Admin | Launch concurrency simulation |
| **Simulation** | `GET` | `/api/simulations/runs/:id/summary` | Confirmed | Authenticated | Metrics & outcome summary |
| **Simulation** | `GET` | `/api/simulations/strategies` | Confirmed | Authenticated | Concurrency strategies (`atomic_update`, `select_for_update`) |
| **Simulation** | `POST` | `/api/simulations/runs/:id/flash-sales` | Confirmed | Analyst, Admin | Create flash sale |
| **Simulation** | `POST` | `/api/simulations/flash-sales/:id/activate` | Confirmed | Analyst, Admin | Activate flash sale |
| **Simulation** | `POST` | `/api/simulations/flash-sales/:id/products` | Confirmed | Analyst, Admin | Allocate stock to flash sale |
| **Simulation** | `GET` | `/api/simulations/transactions` | Confirmed | Authenticated | Purchase attempts & transaction log |
| **Simulation** | `GET` | `/api/simulations/transactions/:id` | Confirmed | Authenticated | Single purchase attempt detail |
| **Simulation** | `GET` | `/api/simulations/analytics/purchase-outcomes` | Confirmed | Authenticated | Distribution of simulation outcomes |
| **Simulation** | `GET` | `/api/simulations/analytics/inventory-allocation` | Confirmed | Authenticated | Physical vs flash-sale allocation |
| **Simulation** | `GET` | `/api/simulations/analytics/flash-sales-overview` | Confirmed | Authenticated | Per-sale allocation & sold units |
| **Simulation** | `GET` | `/api/simulations/analytics/activity` | Confirmed | Authenticated | Real-time transaction timeline |
| **Simulation** | `GET` | `/api/simulations/analytics/conversion` | Confirmed | Authenticated | Purchase conversion rates |
| **Simulation** | `GET` | `/api/simulations/analytics/inventory-utilisation` | Confirmed | Authenticated | Stock utilisation ratio |
| **Simulation** | `GET` | `/api/simulations/analytics/flash-sale-performance` | Confirmed | Authenticated | Flash sale sales performance |
| **Simulation** | `GET` | `/api/simulations/analytics/failure-rates` | Confirmed | Authenticated | Lock conflict & stockout rates |
| **Imports** | `GET` | `/api/imports` | Confirmed | Analyst, Admin | Paginated dataset import history |
| **Imports** | `GET` | `/api/imports/:id` | Confirmed | Analyst, Admin | Import details & row-level error reports |
| **Audit** | `GET` | `/api/admin/audit-logs` | Confirmed | Admin | Filterable, paginated audit entries |

---

## 4. Unsupported & Prohibited Capabilities

The following routes/capabilities are explicitly NOT implemented or supported because the underlying database schema and safety contracts do not support them:

1. **Standalone Orders (`/api/orders`, `/api/orders/:id`):**
   - *Status:* `pending-contract` / Unsupported.
   - *Reason:* No `orders` table exists in the relational database model. Individual customer purchase attempts are tracked in `purchase_attempts` and `transactions_log`. Frontend displays an informative unavailable state directing users to the Transaction Monitor.
2. **Standalone Customers (`/api/customers`, `/api/customers/:id`):**
   - *Status:* `pending-contract` / Unsupported.
   - *Reason:* No `customers` table exists. Customer identities are pseudonymised `customer_ref` strings. Frontend displays an informative unavailable state.
3. **Speculative CSV Upload (`POST /api/imports`):**
   - *Status:* `pending-contract` / Unsupported.
   - *Reason:* Live file upload to the database could corrupt existing historical Rossmann data or exceed server memory limits. Ingestion must follow verified staging protocols.
4. **Live Database Mutations via Prohibited Scripts:**
   - Scripts like `backend/import_rossmann_render.py` are strictly quarantined to prevent production table truncation or re-import corruption.
