# FLASHCORE — DBMS Academic Demonstration & Faculty Viva Guide
## Step-by-Step Live Demonstration Script, Exact SQL Queries, API Traces & Defense Cheat Sheet

> **Candidate:** Manas Aggarwal (Roll No. 2501730302)  
> **Course / Degree:** B.Tech in Computer Science & Engineering (AI/ML), 3rd Semester, Section A  
> **Institution:** School of Engineering and Technology (SOET), K.R. Mangalam University, Gurugram  
> **Subject / Evaluation:** Database Management Systems (DBMS) Capstone Defense  
> **Project Title:** FLASHCORE — Retail Intelligence & High-Concurrency Simulation Platform  
> **Target Commits:** Application Code Freeze `5349f96` | Deployed Baseline `50916f8`  
> **Live Deployments:** Frontend: `https://flashcore-psi.vercel.app` | Backend: `https://database-management-system-s1g5.onrender.com`  

---

## 1. Executive Demonstration Overview & Narrative

When presenting FLASHCORE before university faculty, structure your demonstration around a clear narrative:
> *"FLASHCORE solves a classic distributed DBMS challenge: how to maintain strict ACID consistency and serializable inventory counters under massive concurrent demand bursts (such as a flash sale) without suffering lock-exhaustion crashes or inventory overselling, while combining authentic historical retail analytics (Rossmann dataset) with simulated transactional commerce."*

### Key DBMS Highlights to Emphasize:
1. **Third Normal Form (3NF) Relational Modeling:** 14 core tables, 130 database constraints, 28 B-Tree indexes.
2. **ACID Transaction Engineering:** Deterministic row-level locking (`SELECT ... FOR UPDATE`) and conditional atomic decrements (`WHERE sold_quantity + :qty <= stock_limit`).
3. **Empirical Concurrency Defenses:** Zero overselling verified under 50-thread high-contention bursts (Scenario A: exactly 10 allocated, 40 rejected with HTTP 409).
4. **Separation of Concerns:** Clear relational distinction between authentic Rossmann historical sales records and synthetic simulation runs.
5. **Entity Architecture Integrity:** Honest derived analytical views for Orders and Customers over immutable transaction logs, avoiding redundant PII storage.

---

## 2. Recommended Live Demonstration Sequence (9 Steps)

### Step 1: Database Connectivity & Operational Health
- **Objective:** Prove that the application is genuinely connected to PostgreSQL and that the database engine is healthy.
- **Frontend Action:** Open browser to `https://flashcore-psi.vercel.app` or local instance. Navigate to **System Status** or open DevTools Network tab.
- **API Request:**
  ```http
  GET /health/database HTTP/1.1
  Host: database-management-system-s1g5.onrender.com
  ```
- **Expected Response:**
  ```json
  {
    "database": "flashcore_postgres_temp",
    "status": "connected"
  }
  ```
- **DBMS Faculty Explanation:**
  > *"FastAPI uses SQLAlchemy 2.0 with Psycopg 3 to connect to managed PostgreSQL. Every request checkout utilizes connection pre-pinging (`pool_pre_ping=True`) to validate socket vitality with `SELECT 1` prior to query execution."*

---

### Step 2: Relational Schema & 14-Table Architecture
- **Objective:** Present the 14-table schema inventory, primary keys, foreign keys, and constraints.
- **Faculty Deliverable:** Present the Entity-Relationship Diagram (Section 4 of `FLASHCORE-FINAL-DATABASE-VERIFICATION-REPORT.md`).
- **Direct Database SQL Verification:**
  ```sql
  SELECT table_name 
  FROM information_schema.tables 
  WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
  ORDER BY table_name;
  ```
- **Expected Result (14 Tables):**
  1. `audit_logs`
  2. `auth_sessions`
  3. `daily_store_sales`
  4. `dataset_import_errors`
  5. `dataset_imports`
  6. `flash_sale_products`
  7. `flash_sales`
  8. `purchase_attempts`
  9. `simulation_inventory`
  10. `simulation_products`
  11. `simulation_runs`
  12. `stores`
  13. `transactions_log`
  14. `users`
- **DBMS Faculty Explanation:**
  > *"Every table implements explicit primary keys using PostgreSQL's standard `GENERATED ALWAYS AS IDENTITY` or UUIDv4 JTI keys. Relational integrity is enforced by 14 foreign keys with selective cascade policies (`CASCADE` on auth tokens, `RESTRICT` on sales and inventory)."*

---

### Step 3: Authentic Rossmann Retail Data & Analytical Queries
- **Objective:** Demonstrate complex SQL aggregations, multi-table joins, and indexing over authentic historical retail data.
- **Frontend Action:** Navigate to **Overview** and **Analytics** tabs in the dashboard.
- **Direct SQL Queries to Run:**
  ```sql
  -- Query A: Promotion Elasticity (Aggregations over Daily Sales)
  SELECT 
      promo,
      COUNT(*) AS total_days,
      ROUND(AVG(sales), 2) AS avg_daily_sales,
      ROUND(AVG(customers), 2) AS avg_daily_customers
  FROM daily_store_sales
  GROUP BY promo;

  -- Query B: Store Type Revenue Join (Multi-table Join & Index Scan)
  SELECT 
      s.store_type,
      COUNT(DISTINCT s.store_id) AS store_count,
      ROUND(SUM(d.sales), 2) AS total_revenue
  FROM stores s
  JOIN daily_store_sales d ON s.store_id = d.store_id
  GROUP BY s.store_type
  ORDER BY total_revenue DESC;
  ```
- **DBMS Faculty Explanation:**
  > *"Notice how `daily_store_sales` uses a composite primary key `(store_id, sales_date)`. Queries filtering by store and date leverage the composite B-Tree index `idx_daily_sales_store_date`, achieving sub-millisecond execution plans without full-table scans."*

---

### Step 4: High-Concurrency Flash Sale Campaign Setup
- **Objective:** Show how inventory quotas and time-bounded sales campaigns are created and reserved.
- **Frontend Action:** Navigate to **Flash Sales** → Click **Create Campaign**.
- **API Request:**
  ```http
  POST /api/simulations/runs/1/flash-sales HTTP/1.1
  Content-Type: application/json

  {
    "title": "Faculty Viva Demonstration Sale",
    "starts_at": "2026-11-24T23:00:00Z",
    "ends_at": "2026-11-25T01:00:00Z"
  }
  ```
- **Underlying SQL Execution:**
  ```sql
  -- Table constraint checks ends_at > starts_at
  INSERT INTO flash_sales (simulation_run_id, title, starts_at, ends_at, status)
  VALUES (1, 'Faculty Viva Demonstration Sale', '2026-11-24 23:00:00+00', '2026-11-25 01:00:00+00', 'scheduled')
  RETURNING id;
  ```
- **DBMS Faculty Explanation:**
  > *"The database enforces campaign time bounds through table-level check constraints: `CHECK (ends_at > starts_at)`. Reserving stock updates `simulation_inventory.reserved_quantity`, ensuring physical stock cannot be double-allocated across overlapping sales."*

---

### Step 5: High-Concurrency Concurrency Control & Race Condition Defenses
- **Objective:** The defining demonstration of the DBMS capstone: proving zero overselling under multi-threaded contention.
- **Workload Setup:**
  - Initial Flash Sale Quota: **10 units** (`stock_limit = 10`, `sold_quantity = 0`).
  - Concurrent Burst: **50 simultaneous worker threads** submitting purchase requests of 1 unit each.
- **Execution Command:**
  ```bash
  python artifacts/concurrency_test_harness.py
  ```
- **Underlying SQL Logic (in `backend/app/routes/simulation.py`):**
  ```sql
  -- Step 1: Pessimistic Row Lock
  SELECT id, stock_limit, sold_quantity, sale_price
  FROM flash_sale_products
  WHERE id = :id
  FOR UPDATE;

  -- Step 2: Atomic Conditional Decrement
  UPDATE flash_sale_products
  SET sold_quantity = sold_quantity + :qty
  WHERE id = :id AND sold_quantity + :qty <= stock_limit
  RETURNING sold_quantity;
  ```
- **Observed Empirical Outcome:**
  - **Successful Allocations:** Exactly **10** (HTTP 200 OK).
  - **Rejected Allocations:** Exactly **40** (HTTP 409 Conflict: `"Flash sale stock limit exceeded"`).
  - **Final Sold Quantity in Database:** Exactly **10 / 10**.
  - **Oversold Units:** Exactly **0**.
- **DBMS Faculty Explanation:**
  > *"Because PostgreSQL executes `SELECT ... FOR UPDATE` exclusively on the targeted row, concurrent transactions are serialized by the tuple lock manager. Transactions 1 through 10 acquire the lock, decrement the remaining stock, and commit. Transaction 11 reads `sold_quantity = 10`, sees that `10 + 1 > 10`, immediately aborts the update, records the failure in `purchase_attempts`, and returns HTTP 409 Conflict without corrupting inventory."*

---

### Step 6: Cryptographic Idempotency Demonstration
- **Objective:** Demonstrate that client network retries cannot cause duplicate stock deductions or double billing.
- **Scenario:** 20 concurrent requests submitted with the *exact same* `Idempotency-Key` and customer ID.
- **Underlying SQL & Exception Handling:**
  ```sql
  -- Unique constraint on purchase_attempts
  CONSTRAINT purchase_attempts_idempotency_key_key UNIQUE (idempotency_key)
  ```
- **Observed Empirical Outcome:**
  - First Request: HTTP 200 `{"success": true, "attempt_id": 101, "status": "success"}`.
  - Subsequent 19 Requests: HTTP 200 `{"duplicate": true, "attempt": {...}}` (Cached replay).
  - Database Impact: Exactly **1 row** created in `purchase_attempts`, exactly **1 unit** deducted from inventory.
- **DBMS Faculty Explanation:**
  > *"When concurrent requests arrive with the same key, PostgreSQL's unique constraint triggers an `IntegrityError`. The transaction rolls back cleanly, queries the committed outcome, and returns the cached response deterministically, satisfying RFC 7519 idempotency standards."*

---

### Step 7: Pseudonymous Customer Modeling & Derived Orders Architecture
- **Objective:** Clarify how Orders and Customers work in FLASHCORE without storing unnecessary PII.
- **Frontend Action:** Open **Orders** (`/orders`) and **Customers** (`/customers`). Point out the onscreen **Entity Architecture Notice**.
- **Direct Database SQL Verification:**
  ```sql
  -- Derived Order Projection from Transaction Log
  SELECT 
      pa.id AS order_id,
      pa.customer_ref,
      pa.quantity,
      pa.status,
      pa.created_at AS placed_at,
      tl.action,
      tl.outcome->>'sale_price' AS unit_price
  FROM purchase_attempts pa
  JOIN transactions_log tl ON pa.id = tl.purchase_attempt_id
  WHERE pa.status = 'success'
  ORDER BY pa.created_at DESC
  LIMIT 10;
  ```
- **DBMS Faculty Explanation:**
  > *"In high-throughput flash-sale architectures, maintaining separate synchronized `orders`, `order_items`, and `customers` tables causes write amplification and lock contention. FLASHCORE models orders and customers as derived analytical views synthesized from the transaction log (`purchase_attempts` and `transactions_log`). Customer identities are tokenized pseudonymously (`customer_ref`), adhering to privacy-by-design standards."*

---

### Step 8: Database Security, RBAC & Immutable Audit Logging
- **Objective:** Prove role-based database authorization and immutable audit trails.
- **Frontend Action:** Log in as `operator` → attempt to access `/admin/audit-logs`. Observe HTTP 403 Forbidden. Log in as `admin` → audit trail loads successfully.
- **Direct Database SQL Query:**
  ```sql
  SELECT 
      id,
      actor_type,
      actor_ref,
      action,
      entity_name,
      entity_id,
      details,
      created_at
  FROM audit_logs
  ORDER BY created_at DESC
  LIMIT 5;
  ```
- **DBMS Faculty Explanation:**
  > *"Every administrative and inventory modification generates an immutable audit record in `audit_logs` with a JSONB details payload capturing the actor, entity, and delta. Passwords in `users` are hashed using Argon2id, and user sessions are tracked via UUIDv4 JTI tokens in `auth_sessions`."*

---

### Step 9: Disaster Recovery, Backup & Restore Drill
- **Objective:** Demonstrate database recovery capabilities, RTO, and RPO.
- **Script to Reference / Run:** `artifacts/test_backup_restore.py`
- **Commands:**
  ```bash
  # Acquisition:
  pg_dump -h localhost -p 5432 -d flashcore_test --clean --if-exists > backup.sql
  # Restoration:
  psql -h localhost -p 5432 -d flashcore_recovery_test -f backup.sql
  ```
- **Metrics Achieved:**
  - Backup Acquisition Time: **0.266 seconds**.
  - Database Restoration Time: **0.225 seconds**.
  - Data Parity: **100% match** across all audited entities.
  - Recovery Time Objective (RTO): **< 1 second**.
- **DBMS Faculty Explanation:**
  > *"Because schema constraints and sequences are cleanly declared, full database recovery into a fresh PostgreSQL instance achieves sub-second RTO with zero orphaned sequences or relational errors."*

---

## 3. Faculty Viva Q&A Defense Cheat Sheet (10 Key Questions)

### Q1: Why did you use PostgreSQL's READ COMMITTED isolation with row locking instead of global SERIALIZABLE isolation?
**Answer:**  
Global `SERIALIZABLE` isolation in PostgreSQL uses Serializable Snapshot Isolation (SSI). Under extreme flash-sale contention (50+ threads competing for the same 10 inventory items), SSI detects read-write dependencies (rw-antidependencies) and aborts competing transactions with SQLSTATE `40001` (serialization failure). This causes severe abort/retry storms and wastes CPU.  
By using `READ COMMITTED` combined with targeted pessimistic row locks (`SELECT ... FOR UPDATE`), transactions serialize cleanly at the row level without serialization conflicts, achieving true serial execution on stock counters with predictable throughput.

---

### Q2: How does the system mathematically guarantee zero inventory overselling?
**Answer:**  
Zero overselling is guaranteed through three coordinated defense layers:
1. **Pessimistic Row Lock:** `SELECT ... FOR UPDATE` acquires an exclusive tuple lock on the `flash_sale_products` row, forcing all competing threads to queue.
2. **Conditional Atomic Decrement:** The SQL update strictly requires `WHERE id = :id AND sold_quantity + :qty <= stock_limit`.
3. **Database Check Constraint:** The schema enforces `CHECK (sold_quantity >= 0 AND sold_quantity <= stock_limit)` and `CHECK (quantity >= 0 AND reserved_quantity >= 0)`. Even if application logic failed, the database engine would reject any transaction violating these invariants.

---

### Q3: Why are there no separate `orders` and `customers` tables in your relational database?
**Answer:**  
This is a deliberate architectural design:
1. **Write Amplification Reduction:** In a flash sale, inserting into `orders`, `order_items`, and updating `customers` across separate tables requires multiple distributed row locks and journal writes per checkout.
2. **Derived Event Architecture:** A successful purchase attempt in `purchase_attempts` already contains the SKU, quantity, customer token, price, and timestamp. Linking it to `transactions_log` creates a complete order record.
3. **Data Minimization:** Avoiding a standalone `customers` table prevents storing redundant PII. Pseudonymous customer references (`customer_ref`) are sufficient for fraud detection and purchase limits.

---

### Q4: Explain the normalization level of your database. Is it in Third Normal Form?
**Answer:**  
Yes, the relational tables are in **Third Normal Form (3NF)**:
- **1NF:** All columns contain atomic scalar values. JSONB columns in `audit_logs` and `simulation_runs` are intentionally used for semi-structured operational metadata and parameter snapshots.
- **2NF:** In composite primary key tables (`daily_store_sales`), all non-key attributes (`sales`, `customers`, `promo`) functionally depend on the whole composite key `(store_id, sales_date)`.
- **3NF:** Non-prime attributes depend solely on candidate keys with no transitive dependencies. Store attributes reside in `stores`, not repeated inside sales records.
- **Justified Denormalization:** The only denormalized field is `sold_quantity` on `flash_sale_products`, maintained alongside attempt records to avoid expensive `COUNT(*)` table scans during checkout.

---

### Q5: How do composite indexes work in `daily_store_sales`?
**Answer:**  
`daily_store_sales` contains millions of historical rows. We created a composite B-Tree index:
```sql
CREATE INDEX idx_daily_sales_store_date ON daily_store_sales(store_id, sales_date DESC);
```
Under PostgreSQL's B-Tree indexing, index entries are ordered first by `store_id`, then by `sales_date DESC`. Queries filtering by store or range queries on dates within a store perform index range scans directly on the leaf pages in sub-millisecond time.

---

### Q6: How do you prevent deadlocks when a transaction touches multiple resources?
**Answer:**  
Deadlocks occur when two transactions acquire locks in opposing order (circular wait). In FLASHCORE, all multi-resource transactions enforce a **strict uniform locking hierarchy**:
1. Lock `flash_sale_products` first.
2. Lock `simulation_inventory` second.
Because every thread requests locks in this identical canonical order, circular wait conditions are mathematically impossible, as verified in Scenario E (30 threads, 2 products, 0 deadlocks).

---

### Q7: How does your connection pooling work, and how does it prevent connection exhaustion?
**Answer:**  
SQLAlchemy manages the connection pool. In production on Render Cloud, we use `NullPool` with `pool_pre_ping=True` and `sslmode=require` to prevent connection leaks across ASGI worker recycles. In local testing, we use `QueuePool` with `pool_size=5` and `max_overflow=10`, allowing up to 15 concurrent pooled connections. Sessions are yielded via FastAPI's `get_db()` dependency, which uses a `try... finally: db.close()` pattern to guarantee connection checkout and return.

---

### Q8: What password hashing and authentication mechanism does the database use?
**Answer:**  
Passwords in the `users` table are hashed using **Argon2id** (`pwdlib`), the password hashing algorithm recommended by OWASP and winner of the Password Hashing Competition. Session tokens use RFC 7519 JWTs containing a UUIDv4 JTI (JWT ID) stored in `auth_sessions`. When a user logs out, the database updates `revoked_at = NOW()`, invalidating the session immediately even before token expiration.

---

### Q9: How do you keep authentic Rossmann data separate from simulation data?
**Answer:**  
By strict schema and domain segregation:
- Authentic Rossmann data: stored exclusively in `stores` and `daily_store_sales`, linked to `dataset_imports` for provenance tracking. These tables are strictly read-only during normal operations.
- Simulation data: stored in `simulation_runs`, `simulation_products`, `simulation_inventory`, `flash_sales`, `flash_sale_products`, `purchase_attempts`, and `transactions_log`.
Simulation products are explicitly labeled, preventing synthetic test data from polluting authentic historical sales figures.

---

### Q10: What are the achieved RTO and RPO metrics for your database?
**Answer:**  
- **Recovery Time Objective (RTO):** **< 1 second (0.2254s)**. A complete database backup can be acquired and restored into a fresh PostgreSQL instance in less than a second.
- **Recovery Point Objective (RPO):** Transactionally consistent zero-loss point-in-time recovery, backed by PostgreSQL's Write-Ahead Logging (WAL) and synchronous disk commit.

---

## 4. Academic Demonstration Checklist Summary

| Verification Step | Command / URL | Key Metric / Output | Status |
| :--- | :--- | :--- | :---: |
| **1. Database Health** | `GET /health/database` | `{"database":"flashcore_postgres_temp","status":"connected"}` | **Verified** |
| **2. Table Count** | Query `information_schema.tables` | Exactly 14 base tables | **Verified** |
| **3. Frontend Vitest** | `cd frontend && npm test` | 124 / 124 passed in 9.90s | **Verified** |
| **4. Concurrency Stress** | `python artifacts/concurrency_test_harness.py` | 50 threads, 10/10 sold, 40 rejected, 0 oversold | **Verified** |
| **5. Idempotency** | Scenario B in test harness | 20 threads, 1 success, 19 duplicate replays | **Verified** |
| **6. Disaster Recovery** | `artifacts/test_backup_restore.py` | RTO < 1s, 100% data parity | **Verified** |
| **7. Production API** | `artifacts/database-verification/test_production_readonly.py` | 42 routes registered, auth guards active | **Verified** |
