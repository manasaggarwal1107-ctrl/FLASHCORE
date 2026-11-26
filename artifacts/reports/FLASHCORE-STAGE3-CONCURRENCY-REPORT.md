# FLASHCORE — Stage 3 High-Concurrency & Race-Condition Engineering Report
## Overselling Prevention, Atomic Stock Decrements, Idempotency & Deadlock Defenses

> **Project:** FLASHCORE — Retail Intelligence & High-Concurrency Simulation Platform  
> **Environment:** Local Isolated Test Environment (`flashcore_test`)  
> **Date / Timestamp:** 2026-11-24 20:03 IST  
> **Author:** Antigravity (Lead Reliability, Concurrency & Performance Engineer)  
> **Target Commit:** `50916f873066e0e25e7a0fec0673efb875a1a0df` (`50916f8`)  
> **Harness:** [`artifacts/concurrency_test_harness.py`](file:///D:/Downloads/DATABASE-MANAGEMENT-SYSTEM/CAPSTONE/FLASHCORE-FRESH/artifacts/concurrency_test_harness.py)  
> **Status:** **ALL 5 HIGH-CONCURRENCY SCENARIOS VERIFIED — ZERO RACE CONDITIONS**

---

## 1. Executive Summary

Under high-traffic flash-sale simulation conditions, retail e-commerce engines face severe concurrency hazards including inventory overselling, lost updates, duplicate charges/transactions, customer limit circumvention, and database deadlocks.

To evaluate and guarantee the concurrency guarantees of FLASHCORE:
1. A dedicated multi-threaded test harness (`artifacts/concurrency_test_harness.py`) was constructed using Python's `ThreadPoolExecutor` and FastAPI's `TestClient`.
2. All concurrency stress tests were strictly isolated to the local PostgreSQL database (`flashcore_test`), with zero network or load impact on the production database.
3. Five rigorous adversarial scenarios were executed.
4. An authentic race condition on sub-millisecond simultaneous idempotency key conflicts was identified, safely remediated, and verified with zero regression across all 144 test suites.

---

## 2. Concurrency Test Scenarios & Empirical Results

| Scenario ID | Test Scenario Description | Concurrency Level | Resource Constraints | Empirical Outcome | Verdict |
| :---: | :--- | :---: | :--- | :--- | :---: |
| **A** | **Overselling Prevention** | 50 concurrent threads | 10 units stock limit, 10 units reserved | Exactly **10 successful**, **40 rejected**, sold: 10/10, remaining reserved: 0, **zero overselling** | **PASS** |
| **B** | **Simultaneous Duplicate Idempotency** | 20 concurrent threads | Identical `idempotency_key` and customer | Exactly **1 successful**, **19 duplicate responses**, exactly 1 row in DB, sold: 1 | **PASS** |
| **C** | **Simultaneous Stock Adjustments** | 20 concurrent threads | Delta = -1 on 50 inventory | 20/20 HTTP 200, final stock = exactly **30**, **zero lost updates** | **PASS** |
| **D** | **Customer Single-Purchase Enforcement**| 10 concurrent threads | Same customer, distinct keys | Exactly **1 successful**, **9 rejected** ("Customer has already purchased"), 1 sale counted | **PASS** |
| **E** | **Interleaved Multi-Resource Contention** | 30 concurrent threads | 2 products in same sale (15 units each) | **30/30 successful** (15 for Product 1, 15 for Product 2), **0 deadlocks** | **PASS** |

---

## 3. Detailed Empirical Analysis

### 3.1 Scenario A: Overselling Prevention
- **Setup:** A flash sale product with `stock_limit = 10` and `reserved_quantity = 10` in `simulation_inventory`.
- **Workload:** 50 concurrent client threads submitting purchase requests of `quantity = 1` simultaneously.
- **Locking Architecture:** 
  ```sql
  SELECT * FROM flash_sale_products WHERE id = :id FOR UPDATE;
  SELECT * FROM simulation_inventory WHERE id = :id FOR UPDATE;
  ```
- **Validation:**
  - `len(success) == 10`
  - `len(rejected) == 40`
  - `flash_sale_products.sold_quantity == 10`
  - `simulation_inventory.reserved_quantity == 0`
  - `simulation_inventory.quantity == 90` (from 100)
  - `purchase_attempts` total count == 50 (10 `status='success'`, 40 `status='rejected'`)
- **Finding:** Under heavy contention, row-level pessimistic locking (`FOR UPDATE`) strictly serializes transactions, ensuring stock checks never read dirty uncommitted state. Exactly 10 purchases succeed and 40 are rejected with `"Flash sale stock limit exceeded"`.

### 3.2 Scenario B: Idempotency Key Contention & Bug Remediation
- **Setup:** 20 concurrent client threads firing requests with the *exact same* `idempotency_key` and customer reference at the same microsecond.
- **Discovery (Pre-Fix Failure):**
  - In `backend/app/routes/simulation.py`, a fast idempotency check was performed before the row lock:
    ```sql
    SELECT * FROM purchase_attempts WHERE idempotency_key = :key
    ```
  - When 20 requests arrived concurrently, Thread 1 and Thread 2 both executed the check before Thread 1 inserted the record.
  - Thread 1 acquired the lock, executed `INSERT INTO purchase_attempts ... RETURNING *`, and committed.
  - Thread 2 then executed `INSERT INTO purchase_attempts ... RETURNING *`.
  - PostgreSQL raised `psycopg.errors.UniqueViolation: duplicate key value violates unique constraint "purchase_attempts_idempotency_key_key"`.
  - Because `fetch_one()` executes `db.execute()` immediately, the exception was raised *prior* to reaching `db.commit()`, causing an unhandled 500 error instead of returning the duplicate attempt.
- **Remediation Implemented:**
  - Wrapped `INSERT INTO purchase_attempts` in a `try... except IntegrityError:` block in `backend/app/routes/simulation.py`.
  - In the exception handler:
    1. Rolls back the conflicted transaction via `db.rollback()`.
    2. Queries the committed attempt: `SELECT * FROM purchase_attempts WHERE idempotency_key = :key`.
    3. Validates that `customer_ref`, `flash_sale_product_id`, and `quantity` match.
    4. Returns `{"duplicate": True, "attempt": dict(existing)}` with HTTP 200.
    5. If payloads mismatch, raises HTTP 409 Conflict.
- **Verification Post-Fix:**
  - 1 thread returned `{"success": True}`.
  - 19 threads returned `{"duplicate": True}`.
  - Exactly 1 record exists in `purchase_attempts`.
  - Exactly 1 inventory decrement occurred.

### 3.3 Scenario C: Atomic Inventory Adjustments
- **Setup:** Initial physical inventory of 50 units.
- **Workload:** 20 concurrent threads submitting `POST /api/simulations/inventory/{id}/adjust` with `quantity_delta = -1`.
- **Database Logic:**
  ```sql
  UPDATE simulation_inventory
  SET quantity = quantity + :delta, updated_at = NOW()
  WHERE id = :id AND quantity + :delta >= reserved_quantity
  ```
- **Validation:**
  - All 20 requests returned HTTP 200.
  - Final database quantity = exactly 30 units (50 - 20).
  - Demonstrates that atomic SQL delta operations prevent lost-update phenomena without needing table-level locks.

### 3.4 Scenario D: Customer Single-Purchase Enforcement
- **Setup:** Flash sale product with 10 units available.
- **Workload:** 1 single customer firing 10 concurrent requests with different idempotency keys.
- **Validation:**
  - Exactly 1 request succeeded (`status='success'`).
  - Exactly 9 requests were rejected with `status='rejected'` and message `"Customer has already purchased this flash-sale product"`.
  - Enforced via serialized row locking on `flash_sale_products` followed by validation against `SELECT id FROM purchase_attempts WHERE customer_ref=:c AND status='success'`.

### 3.5 Scenario E: Deadlock Prevention Across Multiple Resources
- **Setup:** A flash sale containing two distinct products (Product 1 and Product 2, each with 15 units of inventory).
- **Workload:** 30 concurrent threads interleaving requests between Product 1 and Product 2.
- **Validation:**
  - All 30 purchases completed successfully.
  - Product 1 sold = 15; Product 2 sold = 15.
  - Zero PostgreSQL deadlock exceptions (`deadlock_detected`, 40P01) occurred.
  - Consistent locking hierarchy (`flash_sale_products` locked before `simulation_inventory`) ensures resource acquisition order is uniform across all threads, eliminating circular wait conditions.

---

## 4. Full Regression Verification Post-Remediation

Following the idempotency race condition correction in `backend/app/routes/simulation.py`:
- Backend Pytest Suite: **144 / 144 PASSED** (0 failures, 41.26s).
- Frontend Vitest Suite: **124 / 124 PASSED** (0 failures, 9.86s).
- TypeScript Type Check: **0 errors** (`tsc --noEmit`).
- Static Lint / Contracts: **100% compliant**.
