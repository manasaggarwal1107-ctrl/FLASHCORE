# FLASHCORE — Academic & Technical Viva Preparation Guide
## 40+ Comprehensive Oral Defense Questions & Answers across Database Systems & Concurrency

> **Candidate:** Manas Aggarwal (Roll No. 2501730302)  
> **Programme:** B.Tech Computer Science & Engineering (AI/ML), 3rd Semester, Section A  
> **Supervisor:** Ms. Mansi Kajal, Assistant Professor, SOET, K.R. Mangalam University  
> **Evaluation Domains:** Distributed Transactions, Concurrency Control, ACID Isolation, Security & Full-Stack Systems  

---

# FLASHCORE — Master Technical Viva Defense Preparation Guide
## 50 Rigorous Technical Examination Questions & Authoritative Model Answers

> **Project:** FLASHCORE — Retail Intelligence & High-Concurrency Simulation Platform  
> **Target Audience:** B.Tech Project Examiners, Evaluation Committee, Faculty Auditors, Candidate  
> **Candidate:** Manas Aggarwal (1107-CS-CAPSTONE)  
> **Course:** B.Tech in Computer Science & Engineering  
> **Document Version:** 1.0.0 (Stage 4 Final Submission)  

---

## DOMAIN 1: SYSTEM ARCHITECTURE & HIGH-LEVEL DESIGN CHOICES (Questions 1–6)

### Q1: Why did you choose a decoupled three-tier architecture (FastAPI + React + PostgreSQL) instead of a traditional full-stack monolithic framework like Django or Ruby on Rails?
**Model Answer:**  
Traditional monoliths tightly couple HTML template rendering with database transaction cycles on the server, creating server-side rendering bottlenecks and preventing independent horizontal scaling. By decoupling the architecture into a **React/TypeScript Single-Page Application (SPA)** distributed globally across Vercel's Edge CDN and an asynchronous **FastAPI** application running on Render PaaS, we achieved three primary engineering benefits:
1. **Independent Scalability:** Static frontend assets are cached globally at zero server compute cost, while backend compute is exclusively dedicated to processing JSON REST APIs and database transactions.
2. **Strict Contract-First Isolation:** Frontend and backend interact strictly via versioned OpenAPI 3.1 contracts validated via Pydantic models, enabling independent deployment and testing.
3. **Optimized Asynchronous I/O:** FastAPI leverages Python’s asynchronous `asyncio` event loop and Starlette ASGI foundation, enabling high non-blocking throughput (measured at up to 283.5 RPS) compared to WSGI-bound frameworks like Django.

### Q2: What are the primary trade-offs of using a relational database (PostgreSQL) rather than a NoSQL document store (MongoDB) for high-concurrency retail transactions?
**Model Answer:**  
NoSQL stores (like MongoDB or Cassandra) offer high write throughput and horizontal sharding, but typically adhere to **BASE** (Basically Available, Soft-state, Eventual Consistency) semantics. In retail flash sales, eventual consistency is catastrophic: when thousands of concurrent requests target a limited stock item, multi-master or asynchronously replicated document stores routinely suffer from the **overselling anomaly**, where available stock drops below zero.  
PostgreSQL provides strict **ACID** (Atomicity, Consistency, Isolation, Durability) guarantees. Utilizing PostgreSQL’s **Strict Two-Phase Locking (2PL)** via `SELECT ... FOR UPDATE` and relational integrity constraints (`CHECK (physical_quantity >= reserved_quantity)` and `UNIQUE (idempotency_key)`), FLASHCORE mathematically guarantees zero overselling and zero duplicate decrements directly at the storage engine level.

### Q3: How does FLASHCORE handle the fundamental tension between OLTP (flash sales) and OLAP (Rossmann sales analytics) within the same database engine?
**Model Answer:**  
We isolate transactional and analytical workloads through schema design, index separation, and query boundaries:
1. **Physical Schema Decomposition:** Analytical historical records (`stores`, `daily_store_sales`) are structurally decoupled from simulation tables (`inventory`, `flash_sale_products`, `purchase_attempts`).
2. **Dedicated Composite Indexing:** Analytical queries rely on composite B-Tree indexes (e.g., `(store_id, date)`) that allow index scans without table locks or full table scans.
3. **Lock Scope Minimization:** Flash sale transactions acquire short-lived row-level exclusive locks on single rows in `flash_sale_products` using `SELECT ... FOR UPDATE`, holding the lock for under 10ms, while analytical reporting queries execute purely read-only `SELECT` queries without acquiring table-level locks.

### Q4: Explain the role and lifecycle of the ASGI server (Uvicorn) in your application tier.
**Model Answer:**  
Uvicorn is an asynchronous server gateway interface (ASGI) web server implementation for Python based on `uvloop` and `httptools`. The lifecycle proceeds as follows:
1. **Connection Acceptance:** Uvicorn binds to the TCP socket (`0.0.0.0:$PORT`) and accepts incoming HTTP/1.1 and TLS connections asynchronously.
2. **Event Loop Dispatch:** Uvicorn parses the raw byte stream into an ASGI connection scope dictionary and dispatches it into Python's `asyncio` event loop.
3. **Application Execution:** FastAPI routes the request through middleware (CORS, timing, exception handling) and executes endpoint dependencies (`get_db`, `get_current_user`).
4. **Non-Blocking I/O:** While awaiting database network responses or cryptographic hashing, the event loop yields execution to handle concurrent requests on other worker threads.

### Q5: What architectural patterns were adopted to ensure clean separation of concerns in the backend?
**Model Answer:**  
We implemented a **Layered Clean Architecture** pattern:
- **Presentation / API Layer (`backend/app/routes/`):** Exposes HTTP endpoints, manages status codes, handles route authorization, and delegates to domain functions.
- **Data Validation & Transfer Layer (`backend/app/schemas/`):** Pydantic schemas enforce type validation, boundary checks, and response serialization.
- **Domain & Persistence Layer (`backend/app/models/`):** SQLAlchemy ORM declarative models define relational schemas, constraints, and relationships.
- **Core Infrastructure Layer (`backend/app/core/`):** Manages connection pool initialization (`database.py`), settings (`config.py`), and cryptographic routines (`security.py`).
- **Dependency Injection (`get_db`, `get_current_user`):** Decouples request handlers from session lifecycles, ensuring transactions automatically close and return to the pool upon request termination.

### Q6: How does FLASHCORE guarantee backward compatibility when deploying API updates?
**Model Answer:**  
1. **Contract-First Versioning:** All API endpoints are anchored under the `/api` namespace with semantic data models.
2. **Additive Schema Modifications:** Fields added to Pydantic models provide default values (e.g., `Optional[...] = None`), preventing serialization breakage for existing clients.
3. **Automated Verification:** OpenAPI JSON specifications are exported and verified using diff analyzers (`compare_routes.py`) to confirm that existing route paths and request schemas remain intact prior to deployment.

---

## DOMAIN 2: RELATIONAL DATABASE DESIGN & POSTGRESQL (Questions 7–12)

### Q7: Walk through the normalization process for the FLASHCORE database. Is it in 3NF or BCNF?
**Model Answer:**  
The database schema encompasses 14 tables normalized to **Third Normal Form (3NF)** and **Boyce-Codd Normal Form (BCNF)**:
1. **1NF:** Every table has a primary key; columns contain strictly atomic scalar values; no repeating groups or multivalued columns exist.
2. **2NF:** All non-key attributes are fully functionally dependent on the complete primary key. In composite junction entities such as `inventory (store_id, product_id)`, attributes like `physical_quantity` depend on both keys, not a partial subset.
3. **3NF:** No transitive functional dependencies exist ($X \to Y \to Z$). For example, store metadata (competition distance, store type) is stored in `stores` rather than repeated in `daily_store_sales`. The sales table references `stores.id` via a foreign key.
4. **BCNF:** For every non-trivial functional dependency $X \to Y$, $X$ is a superkey. All candidate keys in tables like `products` (`id`, `sku`) and `users` (`id`, `email`) are valid determinant superkeys.

### Q8: Explain how check constraints and foreign key cascades prevent data corruption in your schema.
**Model Answer:**  
FLASHCORE enforces **130 database-level constraints**:
1. **Check Constraints:** In `inventory`, `CHECK (physical_quantity >= reserved_quantity)` guarantees that reserved stock cannot exceed on-hand physical inventory. In `flash_sale_products`, `CHECK (sold_count <= stock_limit)` prevents overselling even if application code were bypassed.
2. **Foreign Key Cascades:** In `daily_store_sales`, `FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE CASCADE` ensures child sales records are cleaned up if a store is decommissioned. In `audit_logs`, `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL` ensures audit trail immutability: deleting a user preserves historical audit records while setting the actor reference to `NULL`.

### Q9: Why did you configure composite indexes on `daily_store_sales (store_id, date)`?
**Model Answer:**  
The `daily_store_sales` table contains thousands of rows. The most frequent analytical query patterns filter by a specific store across a time range:
```sql
SELECT SUM(sales), AVG(customers) FROM daily_store_sales 
WHERE store_id = :store_id AND date BETWEEN :start_date AND :end_date;
```
Without an index, PostgreSQL executes a sequential table scan ($O(N)$ complexity), reading every table page from disk. A composite B-tree index on `(store_id, date)` allows the query planner to perform an **Index Range Scan** ($O(\log N)$ complexity): it seeks directly to the first `store_id` matching the condition and scans only the contiguous leaf pages for the specified date interval, reducing execution time from hundreds of milliseconds to under 5ms.

### Q10: How does SQLAlchemy's connection pooling (`QueuePool`) work, and how did you prevent pool starvation?
**Model Answer:**  
SQLAlchemy's `QueuePool` maintains a pool of open, reusable TCP connections to PostgreSQL, avoiding the high overhead of establishing a new TLS/TCP handshake on every HTTP request.  
Configuration: `pool_size = 10`, `max_overflow = 20`, `pool_timeout = 30`, `pool_recycle = 1800`, `pool_pre_ping = True`.  
**Preventing Starvation:**
1. **Scoped Lifecycles:** Database sessions are yielded through FastAPI's `Depends(get_db)`. When the endpoint finishes, the `finally` block executes `db.close()`, returning the connection to `QueuePool`.
2. **Pre-Ping Verification:** `pool_pre_ping = True` issues a lightweight `SELECT 1` ping before handing a socket to the application, discarding dead or timed-out connections.
3. **Overflow Buffer:** Up to 20 temporary burst connections handle transient traffic spikes without blocking.

### Q11: What is the purpose of PostgreSQL Write-Ahead Logging (WAL) in relation to FLASHCORE's durability guarantees?
**Model Answer:**  
PostgreSQL uses Write-Ahead Logging to guarantee ACID **Durability**. When a flash sale transaction commits (`db.commit()`), PostgreSQL writes the change records sequentially to the WAL buffer and flushes them to disk before modifying the underlying data table pages. If a sudden container crash or power failure occurs, PostgreSQL replays the WAL log during recovery, reconstructing the committed state. This ensures committed purchases are never lost, even during server crashes.

### Q12: Why is the production database named `flashcore_postgres_temp`? Does this represent temporary storage?
**Model Answer:**  
No, this does not represent temporary storage. During initial Stage 1 cloud provisioning on Render, the managed PostgreSQL instance was created with the default database name `flashcore_postgres_temp`. Our comprehensive Stage 2 and Stage 3 audits verified:
1. The database runs on persistent cloud disk volumes with automatic backup retention.
2. It contains the full persistent schema of 14 tables, 130 constraints, and all production data.
3. Attempting to rename a live managed database in production carries high risk of connection string disruption. We documented this as a naming artifact with zero functional or persistence impact.

---

## DOMAIN 3: CONCURRENCY CONTROL, LOCKING & RACE CONDITIONS (Questions 13–20)

### Q13: What is the exact difference between Optimistic Concurrency Control (OCC) and Pessimistic Concurrency Control (PCC), and why did you choose PCC for flash sales?
**Model Answer:**  
- **Optimistic Concurrency Control (OCC):** Transactions read data without locking, record a version timestamp, and validate whether the record changed before committing. If a conflict is detected, the transaction aborts and must retry.
- **Pessimistic Concurrency Control (PCC):** Transactions acquire an exclusive lock (`SELECT ... FOR UPDATE`) on target rows upon reading, forcing conflicting transactions to wait in a queue until the lock is released.  
**Why PCC for Flash Sales:**  
In high-contention flash sales (e.g., 50 threads competing for 10 units), the conflict rate is near 100%. Under OCC, almost all contending transactions fail validation and abort, creating an "abort storm" where clients overwhelm the API with retries, spiking CPU and latency. Under PCC, PostgreSQL serializes requests cleanly in a kernel-level lock queue: exactly 10 requests acquire the lock, purchase, and commit, while subsequent requests read the updated `sold_count`, reject cleanly with HTTP 200, and exit without server crashes.

### Q14: Explain the SQL syntax and locking mechanics of `SELECT ... FOR UPDATE`.
**Model Answer:**  
```sql
SELECT * FROM flash_sale_products WHERE id = :sale_product_id FOR UPDATE;
```
When this query executes inside an open transaction:
1. The PostgreSQL lock manager checks if an exclusive tuple lock (`X` lock) exists on the target row.
2. If another transaction holds the lock, the requesting transaction blocks, transitioning to `waiting` state.
3. Once the previous transaction commits or rolls back, the waiting transaction wakes up, reads the *committed* state of that row, and places its own exclusive lock on it.
4. No other session can modify or lock this row until the current transaction executes `COMMIT` or `ROLLBACK`.

### Q15: In Scenario A of your concurrency test (50 threads on 10 stock units), how did you mathematically prove zero overselling?
**Model Answer:**  
In `artifacts/concurrency_test_harness.py`, 50 threads were launched simultaneously via `ThreadPoolExecutor(max_workers=50)` targeting a flash sale product with `stock_limit = 10`.  
Results recorded directly from database state:
- Successful transactions: **Exactly 10** (`status = 'success'`).
- Rejected transactions: **Exactly 40** (`status = 'rejected'`, reason: `'Flash sale stock limit exceeded'`).
- Final database record: `sold_count = 10` out of `stock_limit = 10`.
- Invariant verification: $\sum q_{\text{sold}} = 10 \le 10$. Overselling was **zero**.

### Q16: Detail the idempotency race condition discovered in Stage 3 and your exact remediation.
**Model Answer:**  
**The Race Condition:**  
In `POST /purchase`, the code previously performed an application check (`SELECT ... WHERE idempotency_key = :key`) followed by an `INSERT`. When two duplicate requests arrived within microseconds, both threads executed the read check before either had committed the write. Both threads concluded the key was new. Thread 1 executed `INSERT` and succeeded. Thread 2 executed `INSERT`, but triggered PostgreSQL's unique constraint `purchase_attempts_idempotency_key_key`. Because this occurred inside an active transaction without error handling, SQLAlchemy raised an unhandled `IntegrityError`, crashing with HTTP 500.  
**The Remediation (`backend/app/routes/simulation.py`):**  
We wrapped the insert statement in a `try... except IntegrityError:` block:
```python
try:
    attempt = fetch_one(db, "INSERT INTO purchase_attempts ... RETURNING *")
except IntegrityError:
    db.rollback()  # Resets the aborted transaction state
    existing = fetch_one(db, "SELECT * FROM purchase_attempts WHERE idempotency_key = :key")
    if existing.customer_ref == payload.customer_ref and existing.quantity == payload.quantity:
        return {"duplicate": True, "attempt": dict(existing)}
    raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
```
This catches the race at the database engine level, clears the aborted transaction state via `db.rollback()`, and returns the winning transaction cleanly with HTTP 200.

### Q17: Why was `db.rollback()` strictly required inside the `except IntegrityError` block? What happens if you omit it?
**Model Answer:**  
PostgreSQL enforces strict transaction block integrity. When a statement raises an error (such as a unique constraint violation), PostgreSQL marks the entire transaction block as **aborted** (`ERROR: current transaction is aborted, commands ignored until end of transaction block`, SQLSTATE `25P02`).  
If `db.rollback()` is omitted, any subsequent query executed on that database session (such as querying `SELECT * FROM purchase_attempts WHERE idempotency_key = :key`) will fail with SQLSTATE `25P02`. Executing `db.rollback()` rolls back to the transaction boundary or savepoint, restoring the connection to a clean state so subsequent queries execute successfully.

### Q18: What is a database deadlock, and how does FLASHCORE guarantee zero deadlocks across multi-product purchases?
**Model Answer:**  
A deadlock occurs when Transaction $T_1$ holds a lock on Resource $A$ and requests a lock on Resource $B$, while Transaction $T_2$ holds a lock on Resource $B$ and requests a lock on Resource $A$. Neither transaction can proceed, and PostgreSQL aborts one after its `deadlock_timeout` expires (SQLSTATE `40P01`).  
**FLASHCORE's Guarantee:**  
FLASHCORE enforces a **Global Lock Hierarchy**. In multi-resource transactions (e.g., updating physical `inventory` and `flash_sale_products`), locks are always acquired in a deterministic, globally sorted order (e.g., locking `flash_sale_products` first, followed by `inventory` ordered by primary key ID). Because all transactions acquire resources in identical sequence, circular wait conditions ($T_1 \to T_2 \to T_1$) are mathematically eliminated. In Scenario E (30 interleaved requests), zero deadlocks occurred.

### Q19: What is the "Lost Update" anomaly, and how did your testing prove it is prevented in stock adjustments?
**Model Answer:**  
A Lost Update occurs when two concurrent transactions read the same initial value $V$, compute an update $V + \Delta_1$ and $V + \Delta_2$ respectively, and write back without locking. The second write overwrites the first, losing $\Delta_1$.  
In Scenario C, 20 concurrent threads each executed an adjustment of $\Delta = -1$ on an inventory row with initial quantity $50$. In FLASHCORE, stock adjustments execute atomic SQL arithmetic (`UPDATE inventory SET physical_quantity = physical_quantity + :delta`), which locks the row during update. The final quantity was **exactly 30** ($50 - 20 = 30$), proving zero lost updates.

### Q20: Could Redis distributed locks (Redlock) be used instead of PostgreSQL row locking? What are the trade-offs?
**Model Answer:**  
Yes, Redis distributed locking (via Redlock or Lua scripts) can manage stock counters in memory at higher throughput (> 10,000 RPS).  
**Trade-offs:**  
1. **Split-Brain & Clock Drift Risk:** As documented by Martin Kleppmann, Redlock relies on synchronized physical wall clocks; process pauses or network partitions can cause lock expirations while a thread is still writing, causing dual-master writes.
2. **Dual-Store Synchronization Complexity:** If Redis updates stock, but the subsequent relational database write fails, the system is out of sync.
3. **Operational Overhead:** Requires managing and monitoring a high-availability Redis cluster alongside PostgreSQL.  
For retail systems processing up to 1,000 transactions/second, PostgreSQL's row-level locking provides superior reliability, transactional atomicity, and zero data loss risk.

---

## DOMAIN 4: FASTAPI & BACKEND ENGINEERING (Questions 21–26)

### Q21: What is the internal execution model of FastAPI when handling asynchronous (`async def`) vs. synchronous (`def`) endpoints?
**Model Answer:**  
- **`async def` endpoints:** FastAPI runs them directly on the main `asyncio` event loop thread. If an `async def` function performs blocking CPU work or synchronous I/O (like standard database calls), it blocks the entire event loop, freezing all concurrent requests.
- **`def` endpoints:** FastAPI automatically runs synchronous endpoints in a separate background thread pool (`anyio.to_thread.run_sync`).  
In FLASHCORE, because SQLAlchemy 2.0 sessions perform synchronous TCP socket I/O, endpoints are structured as standard `def` functions, allowing FastAPI to execute them across worker threads while keeping the main event loop responsive for concurrent requests.

### Q22: Explain how FastAPI Dependency Injection works in `get_db` and `get_current_user`.
**Model Answer:**  
FastAPI’s dependency injection system uses Python generator functions and type annotations:
```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
When a route declares `db: Session = Depends(get_db)`:
1. FastAPI calls `get_db()` before entering the route handler, acquiring a database session from `QueuePool`.
2. The session is injected into the route function.
3. Once the route finishes (or raises an unhandled exception), FastAPI executes the code after the `yield` statement (`db.close()`), returning the connection to the pool.  
`get_current_user` depends on `Depends(oauth2_scheme)` and `Depends(get_db)`, extracting the Bearer token, validating claims, checking revocation in `auth_sessions`, and injecting the active user model into the handler.

### Q23: How does Pydantic V2 enhance request validation and serialization performance in FLASHCORE?
**Model Answer:**  
Pydantic V2 is implemented with a Rust-based core (`pydantic-core`), providing 5x to 15x faster serialization and validation compared to V1. In FLASHCORE:
1. **Strict Type Coercion:** Request models (e.g., `PurchaseCreate`) enforce field constraints (`min_length`, regex validation, `gt=0` for quantities).
2. **Sanitized Response Serialization:** Response models (e.g., `UserOut`) strictly exclude sensitive internal fields like `hashed_password`. Even if the ORM user entity contains the hash, Pydantic's serialization schema drops it automatically.

### Q24: How does FLASHCORE format error responses, and why is RFC 7807 compliance important?
**Model Answer:**  
FLASHCORE formats all client errors as standard JSON error objects containing a `"detail"` string or array of validation errors, conforming to RFC 7807 (Problem Details for HTTP APIs).  
**Importance:**  
Standardized error contracts allow frontend clients (Axios interceptors) to parse error messages predictably. Rather than receiving arbitrary HTML error pages or unformatted text, the frontend extracts `error.response.data.detail` and displays user-friendly toast notifications.

### Q25: How does CORS middleware function, and how is it configured in `backend/main.py`?
**Model Answer:**  
Cross-Origin Resource Sharing (CORS) is a browser security mechanism that restricts web pages from making AJAX requests to a different domain.  
In `backend/main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://flashcore-psi.vercel.app", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
When a browser makes a cross-origin request from `https://flashcore-psi.vercel.app`, it first sends an `OPTIONS` pre-flight request. FastAPI's CORS middleware verifies the `Origin` header against the whitelist, returning `Access-Control-Allow-Origin: https://flashcore-psi.vercel.app`, allowing the browser to proceed with the actual API call.

### Q26: Explain the structure and purpose of the automated health check routes in `backend/main.py`.
**Model Answer:**  
FLASHCORE provides multiple health routes:
- `GET /health`: Liveness probe for Render's container orchestrator. Returns `{"status": "healthy"}` immediately without querying dependencies.
- `GET /health/database`: Readiness probe. Executes a lightweight direct SQL ping (`SELECT current_database()`) to verify database socket health.
- `GET /api/health`: Comprehensive system telemetry for the frontend dashboard. Inspects container uptime, application version, and database connectivity. If the database drops, it catches the error and reports `"status": "degraded"` rather than crashing with HTTP 500.

---

## DOMAIN 5: REACT, TYPESCRIPT & FRONTEND ARCHITECTURE (Questions 27–32)

### Q27: How does the frontend handle client-side routing, and how is SPA routing configured for production on Vercel?
**Model Answer:**  
The frontend uses **React Router v6** with a centralized route configuration (`AppRoutes.tsx`). Protected routes are wrapped in an `<AuthGuard>` component that checks the authentication state in LocalStorage; unauthenticated users are redirected to `/login`.  
**Vercel SPA Rewrite Configuration:**  
In single-page applications, browser navigation to `/analytics/stores` causes the browser to request that exact path from Vercel's server. Since that static file does not exist, Vercel would return a 404 error. We configured a rewrite rule in `frontend/vercel.json`:
```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```
This rewrites all incoming routes to `/index.html`, allowing React Router to handle the URL client-side.

### Q28: How do you prevent layout shifts and flickering when authenticated views are loading data?
**Model Answer:**  
We utilize two primary patterns:
1. **Skeleton Loaders:** Reusable skeleton components (`TableSkeleton`, `CardSkeleton`) display pulsing placeholder geometry matching the exact dimensions of tables and charts while API queries are in flight.
2. **Optimistic UI Caching:** Axios interceptors and React state retain previous data during background refreshes, preventing full page blanking when changing filter tabs or pagination controls.

### Q29: What is the purpose of TypeScript's strict type checking (`tsc --noEmit`), and what value did it bring to FLASHCORE?
**Model Answer:**  
`tsc --noEmit` runs the TypeScript compiler purely for static type verification without generating JavaScript files.  
**Value in FLASHCORE:**  
1. **Compile-Time Contract Enforcement:** TypeScript interfaces (e.g., `Store`, `FlashSaleProduct`, `PurchaseAttempt`) mirror the backend Pydantic schemas. If a backend field name changes or is marked optional, `tsc` catches the discrepancy at compile time.
2. **Zero Runtime Undefined Errors:** Eliminates `TypeError: Cannot read properties of undefined` in production React components.
3. **Verification:** In our regression suite, `tsc --noEmit` executed across all 2,676 frontend modules with **0 errors**.

### Q30: How does the frontend handle token storage, session expiration, and automatic redirects?
**Model Answer:**  
1. **Token Storage:** Upon successful login, the JWT access token and user metadata are stored in browser `localStorage`.
2. **Axios Request Interceptor:** An Axios request interceptor attaches the header `Authorization: Bearer <token>` to every outgoing HTTP request.
3. **Axios Response Interceptor:** An Axios response interceptor intercepts all incoming responses. If the backend returns `HTTP 401 Unauthorized` (indicating the token expired or was revoked), the interceptor clears `localStorage`, displays a notification ("Session expired. Please log in again."), and redirects the user to `/login`.

### Q31: Why did you choose TailwindCSS over standard CSS modules or styled-components?
**Model Answer:**  
1. **Zero Runtime Overhead:** Tailwind compiles down to pure static CSS at build time via PostCSS, eliminating the JavaScript runtime overhead associated with styled-components or CSS-in-JS.
2. **Design Consistency:** Utility classes (`bg-slate-900`, `text-emerald-400`, `rounded-xl`) enforce a standardized design system across all 12 feature views.
3. **Bundle Optimization:** PurgeCSS automatically strips unused classes, producing a production CSS bundle of only 38.6 KB.

### Q32: Explain how the frontend promotional analysis view computes and renders promotional lift.
**Model Answer:**  
The frontend calls `GET /api/rossmann/sales/promotion-analysis`. The backend computes:
$$\text{Sales Lift (\%)} = \left(\frac{\text{Avg Sales}_{\text{Promo}} - \text{Avg Sales}_{\text{Regular}}}{\text{Avg Sales}_{\text{Regular}}}\right) \times 100$$
$$\text{Customer Lift (\%)} = \left(\frac{\text{Avg Customers}_{\text{Promo}} - \text{Avg Customers}_{\text{Regular}}}{\text{Avg Customers}_{\text{Regular}}}\right) \times 100$$
The frontend receives the JSON response and passes it into Recharts `<BarChart>` and `<ResponsiveContainer>` components, rendering comparative bar charts with percentage lift badges.

---

## DOMAIN 6: SECURITY, JWT & ROLE-BASED ACCESS CONTROL (Questions 33–38)

### Q33: Why did you select Argon2id over bcrypt for password hashing?
**Model Answer:**  
Argon2id won the Password Hashing Competition (PHC) and is recommended by OWASP:
1. **Memory-Hardness:** Unlike bcrypt (which is CPU-bound), Argon2id requires configurable amounts of RAM (memory-hard). This makes hardware-accelerated attacks using GPUs or ASICs economically infeasible.
2. **Side-Channel & Trade-Off Resistance:** Argon2id is a hybrid variant combining Argon2i (resistant to side-channel cache attacks) and Argon2d (resistant to GPU cracking).
3. **Cryptographic Salt:** Automatically generates unique 128-bit cryptographic salts per password hash.

### Q34: What are the security weaknesses of purely stateless JWTs, and how does FLASHCORE's `auth_sessions` table eliminate them?
**Model Answer:**  
**Weakness of Stateless JWTs:**  
Once issued, a stateless JWT is valid until its expiration time (`exp`). If a user's account is suspended, their role is demoted, or their laptop is stolen, an attacker can continue using the token until expiry; the server has no mechanism to revoke it.  
**FLASHCORE's Solution:**  
Every JWT issued includes a unique UUID claim: `"jti": "<uuid4>"`. When issued, a corresponding record is written to `auth_sessions` (`token_jti`, `user_id`, `expires_at`, `revoked_at`).  
Whenever `get_current_user` validates a request:
```sql
SELECT revoked_at FROM auth_sessions WHERE token_jti = :jti;
```
If `revoked_at IS NOT NULL`, the token is rejected immediately with HTTP 401. When an admin disables a user, all active sessions are marked revoked instantly, terminating access across all devices in real time.

### Q35: Walk through the RBAC hierarchy in FLASHCORE. How is authorization verified on an endpoint like `PATCH /api/admin/users/{id}/role`?
**Model Answer:**  
FLASHCORE enforces three discrete roles: `admin`, `analyst`, `operator`.  
On `PATCH /api/admin/users/{id}/role`:
1. **Authentication Dependency:** `current_user: User = Depends(get_current_user)` validates the JWT signature and active session.
2. **Account Status Check:** Verifies `current_user.status == "active"`. If disabled, raises HTTP 403.
3. **Role Enforcement:** Verifies `current_user.role == "admin"`. If an `analyst` or `operator` calls this route, the dependency immediately raises `HTTP 403 Forbidden: Insufficient permissions`.
4. **Self-Modification Guard:** Verifies `current_user.id != target_user_id`. An admin cannot demote themselves.
5. **Last-Admin Guard:** If demoting an admin, verifies whether other active admins exist using pessimistic row locking. If only one remains, raises HTTP 409.

### Q36: What is an IDOR vulnerability, and how does FLASHCORE prevent it?
**Model Answer:**  
An Insecure Direct Object Reference (IDOR) occurs when an application exposes a direct database key in an API URL (e.g., `/api/admin/users/1/role`) and fails to verify whether the requesting user is authorized to manipulate that specific object.  
**Prevention in FLASHCORE:**  
1. All administrative manipulation routes require role `admin`. Regular users cannot modify any user ID.
2. Self-mutation checks prevent an administrator from escalating or altering their own profile maliciously.
3. Customer-scoped purchase attempts are bound to the authenticated identity, preventing cross-user manipulation.

### Q37: How does automated secret scrubbing work in `backend/app/routes/admin.py`?
**Model Answer:**  
The backend implements `_sanitize_metadata(metadata: dict) -> dict`:
1. It recursively traverses the JSON metadata dictionary.
2. If a key string contains substrings such as `"password"`, `"token"`, `"secret"`, `"hash"`, or `"credential"` (case-insensitive), its value is replaced with the literal string `"[REDACTED]"`.
3. Scrubbing is executed both *prior* to inserting the audit log into PostgreSQL and *prior* to serializing audit records in API responses.

### Q38: How does FLASHCORE mitigate SQL Injection attacks across all 42 endpoints?
**Model Answer:**  
SQL Injection is eliminated through **Parameterized Queries**:
1. 100% of queries in FLASHCORE utilize SQLAlchemy's expression language or parameterized raw SQL via `sqlalchemy.text()`.
2. Dynamic values are bound as parameters: `text("SELECT * FROM users WHERE email = :email").bindparams(email=user_email)`.
3. User inputs are never concatenated directly into SQL strings (`f"SELECT ... '{input}'"` is strictly prohibited). The PostgreSQL database driver treats parameter values strictly as literal values, never as executable SQL tokens.

---

## DOMAIN 7: PERFORMANCE ENGINEERING & LOAD BENCHMARKING (Questions 39–44)

### Q39: Reconcile your performance report numbers: Why did read operations achieve 283.5 RPS while write operations achieved 100.9–103.9 RPS?
**Model Answer:**  
These numbers represent fundamentally distinct workload profiles:
1. **Read Operations (`GET /api/simulations/strategies` — 283.5 RPS):**  
   Reads do not acquire row locks and do not write to the PostgreSQL Write-Ahead Log. Requests execute concurrently without serialization, scaling with CPU and connection pool availability.
2. **Write Operations (`POST .../purchase` — 100.9 to 103.9 RPS):**  
   All competing threads target the *exact same database row* in `flash_sale_products`. The PostgreSQL lock manager strictly serializes access: each transaction must acquire the row lock, evaluate quota, update two tables, insert an attempt record, and flush WAL logs to disk upon `db.commit()` before the next transaction can acquire the lock.  
The ~104 RPS ceiling represents the physical commit serialization limit of a single PostgreSQL row on the test hardware.

### Q40: What are p50, p95, and p99 latency percentiles, and why are percentiles superior to arithmetic mean for measuring system performance?
**Model Answer:**  
- **Arithmetic Mean:** The total latency divided by request count. It is easily skewed by outliers (e.g., one request pausing for garbage collection pulls up the average) and masks customer pain points.
- **p50 (Median):** 50% of requests experienced latency less than or equal to this value. Represents the typical user experience.
- **p95:** 95% of requests completed within this threshold. Represents the standard operational benchmark for SLA compliance.
- **p99:** 99% of requests completed within this threshold; isolates tail latency experienced by the slowest 1% of users.  
In FLASHCORE, under Tier 2 contention, p50 was **161.39ms**, while p95 was **382.34ms**, demonstrating predictable response times even under heavy lock contention.

### Q41: What query optimizations were applied to the Rossmann summary endpoint (`/api/rossmann/sales/summary`)?
**Model Answer:**  
1. **SQL-Level Aggregation:** Calculations (`SUM(sales)`, `SUM(customers)`, `COUNT(DISTINCT date)`) are executed directly inside PostgreSQL's C engine, returning a single summary row rather than transferring thousands of rows over the network to Python.
2. **Single-Pass Aggregation:** Uses PostgreSQL conditional aggregation:
   ```sql
   SELECT SUM(sales) AS total_sales, SUM(customers) AS total_customers,
          ROUND(SUM(sales) / NULLIF(SUM(customers), 0), 2) AS average_basket
   FROM daily_store_sales WHERE store_id = :id AND date BETWEEN :start AND :end;
   ```
3. **Composite Index Scan:** Filters via `idx_daily_sales_store_date`, avoiding full table scans.

### Q42: What is "Connection Pool Leakage," and how was it verified that FLASHCORE is leak-free?
**Model Answer:**  
A connection pool leak occurs when an endpoint checks out a database connection from the pool but fails to close it (for example, when an unhandled exception bypasses `db.close()`). Over time, the pool exhausts its connections, and all subsequent requests block until timing out.  
**Verification in FLASHCORE:**  
We verified that `Depends(get_db)` wraps every session in a `try... finally: db.close()` block. In `artifacts/audit_db_reliability.py`, we executed 700 consecutive requests and verified that `QueuePool.checkedout()` returned to **exactly 0**, with zero hanging connections.

### Q43: How did you test system behavior under extreme thread contention (Tier 3 load: 50 concurrent threads)?
**Model Answer:**  
Using `artifacts/performance_benchmark_harness.py`, we launched 50 concurrent worker threads executing 150 total purchases targeting a single flash sale item.  
**Observations:**  
- Mean latency: 410.43ms (p50: 439.42ms, p95: 526.25ms).
- Throughput: 103.9 req/s.
- Server error rate: **0.0%** (zero HTTP 500 errors).
- Requests that exceeded stock quota were rejected cleanly with HTTP 200 (`success: false`, reason: `"Flash sale stock limit exceeded"`).

### Q44: How would you scale FLASHCORE if flash sale demand increased by 100x (to 10,000 requests/second)?
**Model Answer:**  
To scale 100x beyond single-row PostgreSQL locking limits:
1. **In-Memory Quota Reservation (Redis + Lua):** Decrement stock quotas in Redis using an atomic Lua script in sub-millisecond memory time.
2. **Asynchronous Write-Behind (Apache Kafka):** Push successful reservation tokens onto a Kafka topic; worker microservices read from the topic and persist purchase records to PostgreSQL asynchronously.
3. **Inventory Sharding:** Partition stock across multiple virtual buckets (e.g., 10 inventory buckets of 100 units each) to allow 10 transactions to commit in parallel.

---

## DOMAIN 8: CLOUD DEPLOYMENT, DEVOPS & DISASTER RECOVERY (Questions 45–50)

### Q45: Walk through the root directory mismatch issue discovered on Vercel during Stage 2 and how you resolved it.
**Model Answer:**  
**The Issue:**  
The repository is a monorepo structured with `backend/` and `frontend/` nested under `CAPSTONE/FLASHCORE-FRESH/`. When Vercel originally deployed, the project Root Directory was configured as `.` (repository root). Vercel looked for `package.json` at the root, failed to find build scripts, and errored out.  
**The Resolution:**  
Via Vercel project settings, we updated the **Root Directory** to `CAPSTONE/FLASHCORE-FRESH/frontend`. Upon triggering redeployment, Vercel detected the correct `package.json`, installed dependencies, executed `npm run build`, and deployed cleanly to `https://flashcore-psi.vercel.app`.

### Q46: How did you discover and resolve the route count discrepancy (32 vs. 42 routes) on the live Render backend?
**Model Answer:**  
During Stage 2 verification, inspecting `https://database-management-system-s1g5.onrender.com/openapi.json` revealed only 32 registered routes instead of the expected 42.  
**Investigation:**  
Our git audit showed that commit `50916f8` contained the 10 missing routes (`/api/imports`, `/api/admin/audit-logs`, `/api/health`, and simulation analytics), but Render’s automatic deployment had not triggered. The active deployment was running an older commit (`adc392e`).  
**Resolution:**  
Render deployment of commit `50916f8` was activated. Once built, automated verification confirmed that all 42 OpenAPI paths were live and healthy.

### Q47: Detail your empirical Disaster Recovery test: How was it executed, and what was the measured RTO?
**Model Answer:**  
In `artifacts/test_backup_restore.py`:
1. **Snapshot Acquisition:** We captured an isolated snapshot of `flashcore_test` using native `pg_dump.exe`, taking **0.2663 seconds** (archive size: 32.6 KB).
2. **Disaster Simulation:** We created a brand-new, empty recovery database `flashcore_recovery_test`.
3. **Restoration Execution:** We restored the archive into the new database using `psql.exe`, measuring total execution time at **0.2254 seconds**.
4. **Parity Verification:** We queried both databases and verified a **100% record match** across all 14 tables, 130 constraints, and 28 indexes.  
The **Recovery Time Objective (RTO)** of **0.225 seconds** easily satisfied our requirement of RTO < 2.0s.

### Q48: Why did you defer running `npm audit fix --force` on the frontend codebase?
**Model Answer:**  
Running `npm audit` flagged 9 advisories in frontend dependencies. Inspecting the advisories revealed:
1. Two critical devDependencies (`tinypool`, `esbuild`) are build-time only and are not bundled into the production JavaScript served to users.
2. The runtime advisories (`react-router`, `zod`) require breaking major version upgrades (`react-router-dom@7`, `zod@4`).
3. Running `npm audit fix --force` would have rewritten package versions, breaking React Router v6 component conventions and Vite 5 configuration.
4. **Compensating Controls:** Our SPA has no server-side rendering (eliminating hydration vulnerabilities) and enforces strict input length bounds (`max_length=320`). We documented this as a controlled, non-breaking deferral.

### Q49: What is the purpose of an immutable audit trail, and how does FLASHCORE guarantee that audit records cannot be altered?
**Model Answer:**  
An immutable audit trail provides a legally defensible historical record of system events for compliance and security forensics.  
In FLASHCORE:
1. **Append-Only Table Design:** The `audit_logs` table exposes no `UPDATE` or `DELETE` API endpoints.
2. **Foreign Key Protection:** Deleting a user sets `audit_logs.user_id = NULL`, preserving the log entry.
3. **Pre-Insert Scrubbing:** Passwords and credentials are scrubbed before writing to disk, ensuring secrets cannot be exposed via audit logs.

### Q50: Summarize the five most significant technical contributions of the FLASHCORE project.
**Model Answer:**  
1. **Pessimistic Concurrency Guarantee:** Proved zero overselling and zero duplicate decrements under 50 simultaneous threads using row-level `SELECT ... FOR UPDATE`.
2. **Sub-Millisecond Race Condition Remediation:** Engineered savepoint rollback recovery to handle racing duplicate idempotency keys without server crashes.
3. **Unified Retail Intelligence:** Combined deep historical analytics over 1,115 stores with interactive flash sale simulation.
4. **Granular Enterprise RBAC:** Implemented an audited 42-path security matrix across 5 personas with Argon2id hashing and immediate session revocation.
5. **Sub-Second Disaster Recovery & Continuous Deployment:** Live in production across Render PaaS and Vercel CDN, achieving an RTO of 0.225s and 100% regression pass rates.

---
*End of FLASHCORE Master Technical Viva Defense Preparation Guide.*
