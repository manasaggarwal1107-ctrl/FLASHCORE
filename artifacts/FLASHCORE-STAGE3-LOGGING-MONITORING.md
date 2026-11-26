# FLASHCORE — Stage 3 Logging, Monitoring & Observability Report
## Telemetry Architecture, Audit Trail Coverage & Production Operational Monitoring

> **Project:** FLASHCORE — Retail Intelligence & High-Concurrency Simulation Platform  
> **Environment:** Backend FastAPI, PostgreSQL & Frontend Client Telemetry  
> **Date / Timestamp:** 2026-11-24 20:14 IST  
> **Author:** Antigravity (Lead Reliability, Monitoring & Observability Engineer)  
> **Target Commit:** `50916f873066e0e25e7a0fec0673efb875a1a0df` (`50916f8`)  
> **Status:** **OPERATIONAL & AUDITED — COMPLETE TELEMETRY COVERAGE**

---

## 1. Executive Summary

Operational visibility and traceability across the FLASHCORE platform are anchored on three complementary observability pillars:
1. **System Health & Liveness Probing (`/api/health`, `/api/health/database`):** Real-time component status checks for load balancers and automated monitoring agents.
2. **Database-Backed Immutable Audit Trails (`audit_logs` table):** Complete lifecycle auditing for security events, simulation execution, inventory changes, and purchase attempts with automated secret redaction.
3. **Structured Financial & Simulation Transactions Log (`transactions_log` table):** High-fidelity transaction tracking linking every purchase attempt to its parent simulation run and execution outcome.

---

## 2. Health & Telemetry Endpoints

The platform exposes standardized endpoints for infrastructure uptime checks and live monitoring:

| Endpoint | Method | Auth Required | Component Audited | Sample Response Payload | Operational Purpose |
| :--- | :---: | :---: | :--- | :--- | :--- |
| `GET /api/health` | `GET` | No | FastAPI Application & PostgreSQL Database | `{"status":"healthy","version":"1.0.0","database":"flashcore_postgres_temp","services":[{"name":"FastAPI Application","status":"healthy","detail":"Operational (v1.0.0)"},{"name":"PostgreSQL Database","status":"healthy","detail":"Connected to flashcore_postgres_temp"}],"checked_at":"2026-11-24T14:14:00Z"}` | Aggregated health check for uptime monitors & frontend dashboard |
| `GET /api/health/database` | `GET` | No | PostgreSQL Direct Ping | `{"database":"flashcore_postgres_temp","status":"connected"}` | Deep liveness probe for database socket connection |
| `GET /health` | `GET` | No | Container Heartbeat | `{"status":"healthy"}` | Render container orchestrator health probe |

### Graceful Degradation Handling
In `backend/main.py:api_system_health()`, if a database outage occurs:
- The exception is trapped gracefully.
- Response returns `"status": "degraded"` with HTTP 200 rather than crashing the worker.
- Service entry logs `status: "unhealthy"` with `"Database connection error"`, alerting operators without tearing down the HTTP gateway.

---

## 3. Immutable Audit Log Architecture (`audit_logs`)

All administrative and operational activities write structured JSON records to the relational `audit_logs` table:

```sql
CREATE TABLE audit_logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_type VARCHAR(50) NOT NULL,
    actor_ref VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    entity_name VARCHAR(100) NOT NULL,
    entity_id VARCHAR(100),
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);
```

### 3.1 Audit Event Coverage Matrix

| Event Domain | Action Triggered | Actor Recorded | Entity Name | Captured Details (JSONB) |
| :--- | :--- | :--- | :--- | :--- |
| **Authentication** | `user_created` | `system` | `users` | User email, assigned role (`analyst`) |
| **User Management** | `user_role_updated` | `admin:{id}` | `users` | Old role, new role |
| **User Management** | `user_status_updated` | `admin:{id}` | `users` | Status update (`disabled` / `active`) |
| **Simulation** | `simulation_created` | `operator:{id}` | `simulation_runs` | Run name, initial configuration |
| **Catalog** | `product_created` | `operator:{id}` | `simulation_products` | SKU, product name |
| **Inventory** | `inventory_created` | `operator:{id}` | `simulation_inventory` | Initial stock quantity |
| **Inventory** | `inventory_adjusted`| `operator:{id}` | `simulation_inventory` | Delta quantity, adjustment reason |
| **Flash Sales** | `flash_sale_activated`| `operator:{id}` | `flash_sales` | Start time, end time, status |
| **Commerce** | `purchase_success` | `customer:{ref}`| `purchase_attempts` | Quantity, attempt ID, status |
| **Commerce** | `purchase_rejected`| `customer:{ref}`| `purchase_attempts` | Rejection reason, stock limits |
| **Dataset Import** | `dataset_imported` | `system` | `dataset_imports` | Source file, row counts, provenance |

### 3.2 Secret Sanitization Layer
The administrative endpoint `GET /api/admin/audit-logs` processes every metadata JSON object through `_sanitize_metadata()`. Keys matching any sensitive substring (`password`, `token`, `secret`, `hash`, `key`, `auth`) are recursively scrubbed to `"[REDACTED]"` before leaving the server.

---

## 4. Frontend Observability & UI Monitoring

1. **System Health Page (`/health`):**
   - Implemented in `frontend/src/features/system/SystemHealthPage.tsx`.
   - Real-time polling of `/api/health` displays API uptime, database connection state, latency, and component health badges.
2. **API Client Telemetry (`client.ts`):**
   - Intercepts non-2xx responses, extracts standardized error messages, and routes auth expiration (401) to the central auth provider for automatic session expiration handling.
3. **Audit Log Inspection Page (`/audit`):**
   - Administrative UI for searching, filtering by date range, action type, entity type, and actor reference across all platform actions.
