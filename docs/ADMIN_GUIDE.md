# FLASHCORE — System Administrator Handbook
## Inventory Controls, Flash Sale Scheduling, Concurrency Simulator & Audit Operations

> **Student:** Manas Aggarwal (Roll No. 2501730302)  
> **Course / Programme:** B.Tech CSE (AI/ML), 3rd Semester, Section A  
> **Supervisor:** Ms. Mansi Kajal, Assistant Professor, SOET, K.R. Mangalam University  

---

# FLASHCORE — System Administrator Handbook & Site Reliability Guide
## Platform Operations, Governance, Disaster Recovery & SRE Runbooks

> **Project:** FLASHCORE — Retail Intelligence & High-Concurrency Simulation Platform  
> **Target Audience:** Platform Administrators, Site Reliability Engineers (SRE), Database Administrators (DBA)  
> **Production Stack:** FastAPI on Render PaaS | React on Vercel CDN | Managed PostgreSQL 18  
> **Document Version:** 1.0.0 (Stage 4 Final Submission)  

---

## 1. System Administration Overview & Responsibilities

The FLASHCORE Platform Administrator is entrusted with maintaining platform reliability, security boundaries, user lifecycle governance, database integrity, and cloud infrastructure continuity.

### Key Administrative Responsibilities:
1. **User Identity & Access Governance:** Enforcing the principle of least privilege, promoting/demoting user roles, suspending compromised accounts, and auditing authentication sessions.
2. **Security & Audit Monitoring:** Inspecting immutable audit logs, validating secret sanitization, and investigating unauthorized access attempts (HTTP 401/403).
3. **Database Health & Disaster Recovery:** Overseeing PostgreSQL connection pooling, monitoring query latency, executing automated database backups, and running recovery drills (meeting RTO < 2.0s, RPO < 5m).
4. **Cloud Infrastructure Orchestration:** Managing Render backend container deployments, Vercel frontend edge routing, CORS policies, and environment variable rotations.
5. **Incident Response & Runbooks:** Executing documented remediation procedures during database socket drops, traffic surges, or credential exposures.

---

## 2. Infrastructure Architecture & Operations Topology

```
+--------------------------------------------------------------------------------+
|                             INTERNET / PUBLIC CLIENTS                          |
+--------------------------------------------------------------------------------+
                                    |
                    HTTPS (TLS 1.3) / Port 443
                                    v
+--------------------------------------------------------------------------------+
|                             VERCEL EDGE CDN                                    |
|   Project: flashcore-psi.vercel.app | Root: CAPSTONE/FLASHCORE-FRESH/frontend  |
|   - Static Asset Caching (HTML5, JS, CSS, SVG)                                 |
|   - Client-side Routing Rewrite rules (`/*` -> `/index.html`)                  |
|   - Edge Security & DDoS Mitigation                                            |
+--------------------------------------------------------------------------------+
                                    |
                    API REST Calls / JSON over HTTPS
                                    v
+--------------------------------------------------------------------------------+
|                             RENDER DOCKER PAAS                                 |
|   Service ID: srv-dc2hspuk1f9s7382fcog | Workspace: tea-dc2gi7jncjis73ctnekg   |
|   Container: Python 3.13 / FastAPI / Uvicorn (Port $PORT)                      |
|   Root: CAPSTONE/FLASHCORE-FRESH/backend                                       |
|   Command: uvicorn main:app --host 0.0.0.0 --port $PORT                        |
+--------------------------------------------------------------------------------+
                                    |
                    Encrypted PostgreSQL Wire (Port 5432)
                                    v
+--------------------------------------------------------------------------------+
|                             POSTGRESQL DATABASE                                |
|   Database: flashcore_postgres_temp                                            |
|   Connection Engine: SQLAlchemy 2.0 with QueuePool (pool_size=10, max_overflow=20)|
|   14 Relational Tables | 130 Integrity Constraints | 28 B-Tree Indexes         |
+--------------------------------------------------------------------------------+
```

---

## 3. User Lifecycle Management & RBAC Governance

### 3.1 Role Hierarchy & Permissions Matrix
The platform enforces three distinct user roles with strict separation of duties:

| Role | Permitted Capabilities | Restricted Operations |
| :--- | :--- | :--- |
| **`admin`** | Full superuser access: manage users, promote/demote roles, toggle user status, view full audit logs, execute all simulation and analytics endpoints. | Cannot demote or disable self; cannot demote the last remaining active administrator. |
| **`analyst`** | Read-only access to Rossmann store directories, sales trends, promotional lift analysis, simulation runs, products, inventory, transactions, and conversion metrics. | Cannot create/modify simulation runs, allocate inventory, schedule flash sales, execute purchases, or view user/audit logs. |
| **`operator`** | Write access to simulation runs, product provisioning, inventory allocations, stock adjustments, flash sale scheduling, and purchase execution. | Cannot view Rossmann historical store sales or promotional analysis; cannot access administration or audit logs. |

### 3.2 User Administration Endpoints
All user administration routes require Bearer authentication with role `admin`:
- `GET /api/admin/users`: Lists all registered users (password hashes are strictly excluded from the serialization model).
- `PATCH /api/admin/users/{user_id}/role`: Updates user role (`admin`, `analyst`, `operator`).
- `PATCH /api/admin/users/{user_id}/status`: Updates user status (`active`, `disabled`).

### 3.3 Administrative Safety Guards
The backend implements multi-layered safety guards in `backend/app/routes/admin.py`:
1. **Self-Modification Guard:** An administrator cannot change their own role or disable their own account (`HTTP 409 Conflict: Cannot modify own role or status`).
2. **Last-Administrator Protection:** Demoting or disabling an admin executes a pessimistic row check (`SELECT COUNT(*) FROM users WHERE role='admin' AND status='active' FOR UPDATE`). If only one active admin exists, the mutation is rejected (`HTTP 409 Conflict: Cannot demote or disable the last active administrator`).
3. **Automated Session Revocation:** When an admin changes a user's role or status, the system executes `revoke_user_sessions(db, user_id)`. This updates all active records in `auth_sessions` to set `revoked_at = NOW()`, instantly invalidating the user's active JWT tokens across all devices.

---

## 4. Audit Logging & Security Observability

### 4.1 Immutable Audit Log Engine
The `audit_logs` table records an append-only ledger of platform events:
- `id`: Auto-incrementing integer identifier.
- `user_id`: ID of the actor (foreign key referencing `users.id`, sets `NULL` on user deletion).
- `action`: Standard action verb (`USER_CREATED`, `ROLE_UPDATED`, `STATUS_UPDATED`, `INVENTORY_ADJUSTED`, `FLASH_SALE_ACTIVATED`).
- `entity_type`: Target domain (`user`, `inventory`, `flash_sale`, `simulation_run`).
- `entity_id`: String identifier of target entity.
- `metadata`: JSONB dictionary containing contextual parameters.
- `created_at`: UTC timestamp of event.

### 4.2 Automated Secret Scrubbing
Before any metadata payload is committed to `audit_logs` or returned via `GET /api/admin/audit-logs`, the backend executes `_sanitize_metadata()`. This recursively scans all JSON keys and replaces sensitive values matching `password`, `token`, `secret`, `hash`, or `credential` with `[REDACTED]`.

### 4.3 Querying Audit Logs
- **Endpoint:** `GET /api/admin/audit-logs`
- **Supported Query Parameters:**
  - `page`: Page index (1-based).
  - `pageSize`: Records per page (default `20`, maximum `100`).
  - `action`: Filter by exact action verb (e.g., `ROLE_UPDATED`).
  - `entityType`: Filter by target entity (e.g., `user`).
  - `from`: ISO timestamp start bound.
  - `to`: ISO timestamp end bound.
  - `search`: Free-text search matching action, entity, or actor email.

---

## 5. System Health Probes & Monitoring

FLASHCORE exposes four discrete health probes designed for different operational layers:

### 5.1 Probe Matrix

| Probe Endpoint | Purpose | Target Consumer | Expected Response |
| :--- | :--- | :--- | :--- |
| `GET /` | Root application identity | Smoke testing / Human | `{"project": "FLASHCORE", "database": "flashcore_postgres_temp", "status": "running"}` |
| `GET /health` | Fast container liveness | Render Orchestrator / Kubernetes | `{"status": "healthy"}` (HTTP 200) |
| `GET /health/database` | Direct database socket ping | Infrastructure Alerting | `{"database": "flashcore_postgres_temp", "status": "connected"}` |
| `GET /api/health` | Comprehensive component telemetry | Frontend Dashboard / Datadog | Component breakdown with versions and timestamps |
| `GET /api/health/database` | API-scoped DB probe | API Gateway Health Check | `{"database": "flashcore_postgres_temp", "status": "connected"}` |

### 5.2 Interpreting Health Telemetry (`GET /api/health`)
The aggregated health endpoint returns structured JSON:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "flashcore_postgres_temp",
  "services": [
    {
      "name": "FastAPI Application",
      "status": "healthy",
      "detail": "Operational (v1.0.0)"
    },
    {
      "name": "PostgreSQL Database",
      "status": "healthy",
      "detail": "Connected to flashcore_postgres_temp"
    }
  ],
  "checked_at": "2026-11-24T20:25:00Z"
}
```
**Degraded State Handling:** If the database connection drops, `/api/health` does **not** crash. It catches the socket exception, marks PostgreSQL as `"status": "unhealthy"`, sets overall status to `"status": "degraded"`, and returns HTTP 200, allowing monitoring systems to diagnose root cause without container restart thrashing.

---

## 6. Database Administration & Disaster Recovery

### 6.1 Connection Pool Architecture
The application connects via SQLAlchemy 2.0 utilizing `QueuePool`:
- `pool_size = 10`: Ten permanent persistent database connections.
- `max_overflow = 20`: Up to 20 transient burst connections during high load.
- `pool_timeout = 30`: Seconds to wait for an available connection before raising `TimeoutError`.
- `pool_recycle = 1800`: Reconnects idle sockets after 30 minutes to prevent firewall drops.
- `pool_pre_ping = True`: Executes a lightweight `SELECT 1` ping prior to checkout, transparently discarding dead sockets.

### 6.2 Disaster Recovery Targets
- **Recovery Point Objective (RPO):** < 5 minutes (Snapshot capability takes ~0.26s).
- **Recovery Time Objective (RTO):** < 2.0 seconds (Restoration verified at 0.225s).

### 6.3 Backup Procedure (Automated / Manual)
To capture a consistent, production-safe snapshot:
```powershell
# Set database environment credentials
$env:PGPASSWORD = "YourSecurePassword"

# Generate compressed plain-SQL dump with schema and data
pg_dump.exe -h localhost -p 5432 -U flashcore_user -d flashcore_test -F p -b -v -f "artifacts/backups/flashcore_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"
```

### 6.4 Restoration Procedure
To restore from a backup snapshot:
```powershell
# Terminate existing connections and drop target recovery database
psql.exe -h localhost -p 5432 -U postgres -c "DROP DATABASE IF EXISTS flashcore_recovery_test;"
psql.exe -h localhost -p 5432 -U postgres -c "CREATE DATABASE flashcore_recovery_test OWNER flashcore_user;"

# Restore schema, constraints, indexes, and records
psql.exe -h localhost -p 5432 -U flashcore_user -d flashcore_recovery_test -f "artifacts/backups/flashcore_backup_20261124.sql"
```

### 6.5 Schema Parity Verification Checklist
Following restoration, execute the verification query:
```sql
SELECT table_name, (xpath('/row/cnt/text()', xml_count))[1]::text::int as row_count
FROM (
  SELECT table_name, query_to_xml(format('select count(*) as cnt from %I', table_name), false, true, '') as xml_count
  FROM information_schema.tables
  WHERE table_schema = 'public'
) t;
```
Ensure that all 14 tables report row counts identical to the source database.

---

## 7. Cloud Deployment Operations & Verification

### 7.1 Vercel Frontend Deployment
- **Project Name:** `flashcore-fresh-frontend` (Alias: `https://flashcore-psi.vercel.app`)
- **Root Directory:** `CAPSTONE/FLASHCORE-FRESH/frontend`
- **Build Command:** `npm run build` (outputs to `dist/`)
- **Environment Variables:**
  - `VITE_API_URL`: `https://database-management-system-s1g5.onrender.com/api`

### 7.2 Render Backend Deployment
- **Service ID:** `srv-dc2hspuk1f9s7382fcog` (Name: `database-management-system-s1g5`)
- **Root Directory:** `CAPSTONE/FLASHCORE-FRESH/backend`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Environment Variables:**
  - `DATABASE_URL`: Managed connection string to `flashcore_postgres_temp`
  - `SECRET_KEY`: Production 256-bit cryptographic key
  - `ALLOWED_ORIGINS`: `https://flashcore-psi.vercel.app`

### 7.3 Post-Deployment Verification Checklist
Whenever a new commit is deployed to production:
1. Verify `/health` returns `200 OK`.
2. Verify `/openapi.json` registers exactly **42 paths**.
3. Verify `GET /api/imports` returns HTTP 401 on unauthenticated calls.
4. Verify CORS pre-flight:
   ```bash
   curl -I -X OPTIONS "https://database-management-system-s1g5.onrender.com/api/rossmann/stores" \
     -H "Origin: https://flashcore-psi.vercel.app" \
     -H "Access-Control-Request-Method: GET"
   ```
   Confirm response header contains `Access-Control-Allow-Origin: https://flashcore-psi.vercel.app`.

---

## 8. Incident Response & Operational Runbooks

### Runbook 1: Database Connection Loss / Pool Exhaustion
1. **Detection:** Alerts fire on `/health/database` reporting 500 or timeout.
2. **Immediate Action:** Inspect Render service logs for `QueuePool limit of size 10 overflow 20 reached`.
3. **Remediation:**
   - Check PostgreSQL active connections:
     ```sql
     SELECT pid, usename, client_addr, state, query_start, query FROM pg_stat_activity WHERE datname = 'flashcore_postgres_temp';
     ```
   - Terminate hanging idle-in-transaction connections:
     ```sql
     SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND query_start < NOW() - INTERVAL '5 minutes';
     ```
   - If Render container continues to block, trigger a service restart via Render dashboard.

### Runbook 2: Flash Sale Contention Surge
1. **Detection:** Elevated P95 latency on `POST /purchase` (> 1000ms).
2. **Diagnosis:** High thread contention on specific `flash_sale_product_id` acquiring row locks.
3. **Assessment:** Verify whether requests are rejecting gracefully. If error rate is 0.0% and rejections state `"stock limit exceeded"`, this is expected behavior under pessimistic locking.
4. **Action:** Ensure client applications throttle retry attempts using exponential backoff with jitter.

### Runbook 3: Secret Rotation (JWT Signing Key)
1. **Preparation:** Inform active users of scheduled maintenance.
2. **Execution:**
   - Generate a secure 64-character hex secret: `openssl rand -hex 32`.
   - Update `SECRET_KEY` in Render service environment settings.
   - Restart the Render web service.
3. **Impact:** Existing JWT tokens become immediately invalid. All users must log in again to receive newly signed tokens.

---
*End of FLASHCORE System Administrator Handbook.*
