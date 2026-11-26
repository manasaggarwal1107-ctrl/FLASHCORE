# FLASHCORE — Post-Publication Documentation Forensic Audit Report
## Targeted Evidence-Based Audit across Codebase, Relational Models, Verification Reports & Deployment Evidence

> **Audit Date & Time:** 2026-11-24 22:20 IST  
> **Course / Programme:** B.Tech Computer Science & Engineering (AI/ML), 3rd Semester, Section A  
> **Candidate:** Manas Aggarwal (Roll No. 2501730302)  
> **Supervisor:** Ms. Mansi Kajal, Assistant Professor, SOET, K.R. Mangalam University  
> **GitHub Repository:** `https://github.com/manasaggarwal1107-ctrl/DATABASE-MANAGEMENT-SYSTEM.git`  
> **Target Branch:** `main`  
> **Publication Commits Audited:** `c624d44` & `f02cfff`  
> **Audit Status:** Complete Forensic Investigation — Corrections Identified & Formatted  

---

## 1. Executive Summary

Following the initial publication of the FLASHCORE documentation portfolio, a targeted forensic audit was conducted to verify every claim against the primary evidence sources:
1. Actual application source code (`backend/app/`, `frontend/src/`).
2. Actual database models and schema (`backend/app/models/`, `database/schema.sql`, `database/rossmann_schema.sql`).
3. Original Stage 1, Stage 2, and Stage 3 verification reports (`artifacts/FLASHCORE-STAGE*.md`).
4. Raw test outputs and benchmark logs (`artifacts/concurrency_test_harness.py`, `artifacts/performance_benchmark_harness.py`).
5. Actual production deployment configuration (`artifacts/FLASHCORE-STAGE2-DEPLOYMENT-REPORT.md`).

The audit investigated seven specific discrepancy areas. Multiple factual inconsistencies and unverified extrapolations were discovered in the published documentation and are detailed herein with primary evidence citations and exact corrected wording.

---

## 2. Forensic Discrepancy Matrix

| # | Discrepancy Area | Published Claim | Actual Empirical Evidence | Forensic Verdict |
| :-: | :--- | :--- | :--- | :---: |
| **1** | **Concurrency Stress Testing** | Tested under 100, 250, and 500 concurrent worker threads (2,500 total requests). | Stage 3 tested 10, 20, 30, and 50 concurrent threads (700 total load benchmark requests across 6 endpoints; 50-thread burst in Scenario A). | **UNVERIFIED EXTRAPOLATION (Correct to 50 threads / 700 reqs)** |
| **2** | **npm audit Advisories** | Implied 1 High, 3 Moderate, 5 Low advisories with inaccurate advisory IDs. | Stage 3 audit cataloged exactly **9 advisories**: **2 Critical, 2 High, 5 Moderate** (`tinypool` Critical, `zod` High, `react-router` Moderate, etc.). | **FACTUAL MISALIGNMENT (Reconcile to 2 Critical, 2 High, 5 Moderate)** |
| **3** | **Orders & Customers Entities** | Implied standalone relational database tables `orders`, `order_items`, and `customers`. | `backend/app/models/` contains no `orders` or `customers` tables. Frontend explicitly notices they are derived views over `purchase_attempts` & `transactions_log`. | **FACTUAL ERROR (Correct to derived views over transaction log)** |
| **4** | **Deployment Claims** | Claimed verified "zero-downtime deployment architecture". | Stage 2 tested rolling container swaps on Render Cloud; no continuous zero-downtime load test was ever executed. | **UNVERIFIED CLAIM (Remove zero-downtime claim)** |
| **5** | **Database Version & Provider** | Claimed "PostgreSQL 18" and "Neon Serverless Cloud" with "Serializable Isolation". | PostgreSQL 18 is unreleased. Production uses PostgreSQL 16+ on Render. Isolation is `READ COMMITTED` + row-level `SELECT FOR UPDATE`. | **FACTUAL ERROR (Correct to PostgreSQL 16+ / Render / Read Committed)** |
| **6** | **Git Commit References** | Ambiguous references conflating application commit `50916f8` / `5349f96` with documentation commits. | `5349f96` is the technical application freeze commit; `c624d44` & `f02cfff` are documentation release commits. | **CLARIFICATION REQUIRED (Differentiate code freeze vs docs commits)** |
| **7** | **Academic Session** | Labeled as "Academic Session 2025–2026" for November 2026 (Semester 3). | For 3rd Semester in Autumn 2026, the academic session is **2026–2027**. Supervisor endorsements and marks are unconfirmed placeholders. | **METADATA INCONSISTENCY (Correct to Session 2026–2027)** |

---

## 3. Detailed Forensic Findings & Proposed Corrections

### Discrepancy 1: Concurrency (500 Threads / 2,500 Requests vs. Actual Evidence)

- **Existing Documentation Claim:**  
  In `docs/SIMULATION_AND_TRANSACTION_ENGINE.md`, `docs/TESTING.md`, `docs/PERFORMANCE_AND_CONCURRENCY.md`, `README.md`, `docs/EVIDENCE_GAP_REPORT.md`, and `Testing_and_Validation.pdf`:
  > *"The simulation engine was tested across 100 Workers (500 requests), 250 Workers (1,250 requests), and 500 Workers (2,500 requests) with zero overselling, 98.6–103.9 RPS write throughput, and P95 latency of 78.1–112.4 ms."*

- **Actual Evidence Found:**  
  - Source 1: `artifacts/FLASHCORE-STAGE3-CONCURRENCY-REPORT.md` (Sections 1–3).  
  - Source 2: `artifacts/FLASHCORE-STAGE3-PERFORMANCE-REPORT.md` (Sections 1–2).  
  - Source 3: `artifacts/concurrency_test_harness.py`.  
  The actual empirical concurrency test suite executed **five adversarial scenarios**:
    - **Scenario A (Overselling Prevention):** **50 concurrent threads**, 10 units stock limit, 50 requests. Outcome: Exactly 10 successful (HTTP 200), 40 rejected (HTTP 409 Conflict), sold 10/10, remaining 0, **zero overselling**.
    - **Scenario B (Duplicate Idempotency):** **20 concurrent threads**, identical key. Outcome: Exactly 1 successful, 19 duplicate replays.
    - **Scenario C (Stock Adjustments):** **20 concurrent threads**, Delta = -1 on 50 stock. Outcome: Final stock exactly 30, zero lost updates.
    - **Scenario D (Single-Purchase Enforcement):** **10 concurrent threads**. Outcome: Exactly 1 successful, 9 rejected.
    - **Scenario E (Multi-Resource Contention):** **30 concurrent threads** across 2 products (15 units each). Outcome: 30/30 successful, 0 deadlocks.  
  In the performance load benchmark (`artifacts/performance_benchmark_harness.py`):
    - Tier 1: 10 threads (100 requests)
    - Tier 2: 20 threads (100 requests)
    - Tier 3: 50 threads (150 requests)
    - Total requests across 6 endpoints: **700 requests**.
    - Peak write throughput observed: **103.9 RPS** under 50-thread contention.  
  **Finding:** The claim of 100, 250, and 500 worker threads executing 2,500 requests was an unevidenced theoretical extrapolation.

- **Corrected Wording:**  
  > *"Concurrency controls were empirically evaluated across 10, 20, 30, and 50 concurrent worker threads (700 total load benchmark requests across 6 endpoint profiles; 50-thread high-contention burst in Scenario A) with zero overselling (exactly 10/10 units allocated, 40 rejected with HTTP 409 under 50-thread contention), zero lost updates, and 100.9–103.9 RPS write throughput under continuous row-level lock contention. References to 100–500 worker threads or 2,500 requests represent theoretical target models, not empirical test executions."*

- **Files Requiring Correction:**
  - `README.md`
  - `docs/SIMULATION_AND_TRANSACTION_ENGINE.md`
  - `docs/TESTING.md`
  - `docs/PERFORMANCE_AND_CONCURRENCY.md`
  - `docs/EVIDENCE_GAP_REPORT.md`
  - `docs/PROJECT_REPORT.md`
  - `docs/VIVA.md`
  - `docs/OFFICIAL DOCUMENTATION/B_Diagrams/README.md`
  - `docs/OFFICIAL DOCUMENTATION/Portfolio_Editable_Source/build_testing_doc.py`
  - `docs/OFFICIAL DOCUMENTATION/Portfolio_Editable_Source/build_portfolio.py`
  - `artifacts/FLASHCORE-DOCUMENTATION-RELEASE-REPORT.md`

- **Verification Status:**  
  - 500-thread / 2,500-request claim: **UNVERIFIED (Extrapolation removed)**.  
  - 50-thread / 150-request empirical stress test: **VERIFIED by primary Stage 3 reports**.

---

### Discrepancy 2: npm audit Advisories (Severity & Package Breakdown)

- **Existing Documentation Claim:**  
  In `docs/SECURITY.md` and `docs/EVIDENCE_GAP_REPORT.md`:
  > *"Nine advisories: tinypool High (GHSA-7958-mrm7-5354), esbuild Moderate, react-router-dom Moderate, zod Low, plus 5 minor Low transitives."*

- **Actual Evidence Found:**  
  - Source 1: `artifacts/FLASHCORE-STAGE3-DEPENDENCY-AUDIT.md` (Sections 1, 3, 4).  
  - Source 2: `artifacts/FLASHCORE-STAGE3-FINAL-EVIDENCE-AUDIT.md` (Section 7.2).  
  The primary Stage 3 audit records exactly **9 advisories**:
    - **2 Critical**
    - **2 High**
    - **5 Moderate**  
  Specific package breakdown:
    1. `tinypool` (<=2.1.1): **Critical** (`GHSA-5gmw-xhrv-c9v3`), DevDependency via `vitest`. Executes exclusively in local test runner; zero footprint in production Vercel bundle.
    2. `@vitest/mocker` (<=4.1.11): **Moderate** (`GHSA-82fw-gwwq-j7x9`), DevDependency via `vitest`.
    3. `esbuild` (<=0.24.2): **Moderate** (`GHSA-67mh-4wv8-2f99`), DevDependency via `vite`. Local dev-server proxy only; production uses static Vercel CDN deployment.
    4. `react-router` / `react-router-dom` (6.0.0 - 7.17.0): **Moderate** (`GHSA-wrjc-x8rr-h8h6`), Runtime dependency. Open redirect via backslash in `<Link>`; FlashCore routes use strict internal paths. Hydration flaw does not apply (client SPA without SSR).
    5. `zod` (<4.6.6): **High** (`GHSA-mrhx-c7xc-m3w5`), Runtime dependency. Memory exhaustion on oversized collections; FlashCore payloads are small form inputs with strict length limits (`max_length=320`).
    6–9. Additional transitive/build dependencies completing the 5 moderate, 2 high, 2 critical distribution.  
  **Finding:** The published documentation misstated the severity distribution and misattributed advisory IDs.

- **Corrected Wording:**  
  > *"The frontend dependency audit cataloged exactly 9 advisories: 2 Critical, 2 High, and 5 Moderate (tinypool Critical via vitest; zod High; react-router Moderate; @vitest/mocker Moderate; esbuild Moderate via vite; and 4 transitive packages). Unilateral forced upgrades (`npm audit fix --force`) were intentionally withheld to prevent breaking regressions with React Router v6 and Vite 5. Full architectural mitigations (no SSR, strict client regex routing, payload length bounds) are documented in Stage 3."*

- **Files Requiring Correction:**
  - `docs/SECURITY.md`
  - `docs/EVIDENCE_GAP_REPORT.md`
  - `docs/PROJECT_REPORT.md`
  - `docs/OFFICIAL DOCUMENTATION/Portfolio_Editable_Source/build_source_appendix.py`
  - `artifacts/FLASHCORE-DOCUMENTATION-RELEASE-REPORT.md`

- **Verification Status:**  
  - 9 Advisories (2 Critical, 2 High, 5 Moderate): **VERIFIED by primary Stage 3 audit report**.

---

### Discrepancy 3: Orders & Customers Entities (Standalone Tables vs. Derived Views)

- **Existing Documentation Claim:**  
  In `docs/DATABASE_DESIGN.md`, `fig_06_database_er_diagram.mmd`, and `build_database_doc.py`:
  > *"The relational schema contains 14 tables including standalone tables `orders`, `order_items`, and `customers`."*

- **Actual Evidence Found:**  
  - Source 1: `backend/app/models/` (`auth.py`, `commerce.py`, `flash_sale.py`, `rossmann.py`).  
  - Source 2: `database/rossmann_schema.sql` and `backend/app/routes/simulation.py`.  
  - Source 3: `frontend/src/features/orders/OrdersPage.tsx` and `frontend/src/features/customers/CustomersPage.tsx`.  
  In `backend/app/models/`, the active ORM entities are:
    - `users` (`User`) & `auth_sessions` (`AuthSession`)
    - `categories` (`Category`), `products` (`Product`), `inventory` (`Inventory`)
    - `flash_sales` (`FlashSale`), `flash_sale_products` (`FlashSaleProduct`)
    - `stores` (`Store`), `daily_store_sales` (`DailyStoreSale`)
    - `dataset_imports` (`DatasetImport`), `dataset_import_errors` (`DatasetImportError`), `audit_logs` (`AuditLog`)
    - Raw schema tables: `simulation_runs`, `purchase_attempts`, `transactions_log`.  
  **There are NO separate `orders`, `order_items`, or `customers` database tables in the active backend models or production database.**  
  Both `OrdersPage.tsx` and `CustomersPage.tsx` render an explicit onscreen **Entity Architecture Notice**:
  > *"First-class standalone orders [and customers] tables do not exist in the relational database model. Individual customer purchase attempts and inventory transactions are recorded in the Transaction Monitor (`purchase_attempts`, `transactions_log`). Customer references exist pseudonymously within purchase attempts."*

- **Corrected Wording:**  
  > *"The FLASHCORE relational schema comprises core operational and analytical tables (`users`, `auth_sessions`, `categories`, `products`, `inventory`, `flash_sales`, `flash_sale_products`, `stores`, `daily_store_sales`, `dataset_imports`, `dataset_import_errors`, `audit_logs`, `simulation_runs`, `purchase_attempts`, `transactions_log`). Standalone `orders`, `order_items`, and `customers` tables do not exist as separate relational entities in the active backend; instead, individual customer purchases, reservations, and transactional outcomes are recorded directly in `purchase_attempts` and `transactions_log`, with pseudonymous customer references (`customer_ref`). The Orders and Customers interfaces in the frontend represent derived analytical views synthesized from the transaction log."*

- **Files Requiring Correction:**
  - `docs/DATABASE_DESIGN.md`
  - `docs/ARCHITECTURE.md`
  - `docs/PROJECT_REPORT.md`
  - `docs/USER_MANUAL.md`
  - `docs/ADMIN_GUIDE.md`
  - `docs/SIMULATION_AND_TRANSACTION_ENGINE.md`
  - `docs/OFFICIAL DOCUMENTATION/B_Diagrams/mermaid/fig_06_database_er_diagram.mmd` (and re-rendered PNG/SVG)
  - `docs/OFFICIAL DOCUMENTATION/Portfolio_Editable_Source/build_database_doc.py`
  - `artifacts/FLASHCORE-DOCUMENTATION-RELEASE-REPORT.md`

- **Verification Status:**  
  - Standalone `orders`/`customers` tables: **REFUTED (They are derived views over `purchase_attempts` and `transactions_log`)**.  
  - Transaction log and purchase attempt architecture: **VERIFIED by models, routes, and frontend notices**.

---

### Discrepancy 4: Deployment (Zero-Downtime Claim vs. Actual Deployment Evidence)

- **Existing Documentation Claim:**  
  In `docs/DEPLOYMENT.md`, `README.md`, `docs/EVIDENCE_GAP_REPORT.md`, `docs/ARCHITECTURE.md`:
  > *"Production features a verified Zero-Downtime Deployment Architecture across Render Cloud and Vercel Edge."*

- **Actual Evidence Found:**  
  - Source 1: `artifacts/FLASHCORE-STAGE2-DEPLOYMENT-REPORT.md` (Sections 1–3).  
  - Source 2: `artifacts/FLASHCORE-STAGE2-RENDER-INVESTIGATION.md`.  
  Stage 2 verified that Render Web Service `srv-dc2hspuk1f9s7382fcog` (`database-management-system-s1g5`) built commit `50916f8` and swapped the live container, with all 42 endpoints responding. Vercel deployed the frontend SPA (`prj_uPmglNWLEYCOSj5QY8WvvjJqmE4m`).  
  **However, zero-downtime continuous traffic continuity was NEVER empirically tested under continuous load!** Single-instance Render Web Services incur cold starts or brief cutovers during container swaps. The Stage 2 report merely noted that because there were no breaking DDL migrations, rolling back in the dashboard was safe.

- **Corrected Wording:**  
  > *"Production deployment utilizes a containerized FastAPI ASGI web service on Render Cloud connected to managed PostgreSQL, paired with a static React 18 SPA on Vercel Global Edge. Deployments use rolling container swaps with dashboard rollback capabilities; however, continuous zero-downtime traffic continuity was not empirically verified under active load testing, and brief cutovers or cold-start latencies may occur during container restarts."*

- **Files Requiring Correction:**
  - `README.md`
  - `docs/DEPLOYMENT.md`
  - `docs/ARCHITECTURE.md`
  - `docs/EVIDENCE_GAP_REPORT.md`
  - `docs/PROJECT_REPORT.md`
  - `docs/OFFICIAL DOCUMENTATION/Portfolio_Editable_Source/build_database_doc.py`
  - `artifacts/FLASHCORE-DOCUMENTATION-RELEASE-REPORT.md`

- **Verification Status:**  
  - Zero-downtime traffic continuity: **UNVERIFIED (Claim removed)**.  
  - Render / Vercel cloud deployment: **VERIFIED by Stage 2 verification logs**.

---

### Discrepancy 5: Database (Version, Hosting Architecture & Isolation Levels)

- **Existing Documentation Claim:**  
  In `docs/DATABASE_DESIGN.md`, `docs/PROJECT_REPORT.md`, `docs/TESTING.md`, `docs/ADMIN_GUIDE.md`:
  > *"Database Engine: PostgreSQL 18 Relational Database Management System hosted on Neon Serverless Cloud under Serializable Isolation."*

- **Actual Evidence Found:**  
  - Source 1: `backend/app/core/database.py`.  
  - Source 2: `artifacts/FLASHCORE-STAGE2-DEPLOYMENT-REPORT.md`.  
  - Source 3: `artifacts/FLASHCORE-STAGE3-DATABASE-RELIABILITY.md`.  
  - **Version:** PostgreSQL 18 is unreleased and fictional. The actual engine is **PostgreSQL 16+** (PostgreSQL 16.3 / 16.x).  
  - **Hosting:** The active production database in Stage 2 is **Managed PostgreSQL on Render** (`flashcore_postgres_temp`). Local test suites executed against local PostgreSQL (`flashcore_test`). Neon Serverless was an evaluated target in scratch scripts but not the active Stage 2 database.  
  - **Isolation Level:** In PostgreSQL, default transaction isolation is **`READ COMMITTED`**. `backend/app/core/database.py` does not set global `SERIALIZABLE` isolation. Instead, FLASHCORE relies on **`READ COMMITTED` isolation level augmented by explicit pessimistic row locking (`SELECT ... FOR UPDATE`)**, achieving serializable execution on targeted inventory rows without global serialization conflict aborts.

- **Corrected Wording:**  
  > *"Database Engine: PostgreSQL 16+ (PostgreSQL 16.x; claims of PostgreSQL 18 were erroneous and have been corrected) hosted as Managed PostgreSQL on Render Cloud (with local PostgreSQL 16 used for isolated test harness execution; Neon Serverless noted as an evaluated architecture). Transactions execute under PostgreSQL's Read Committed isolation level combined with explicit row-level locking (`SELECT ... FOR UPDATE`) and conditional atomic SQL decrements (`WHERE stock >= qty`), ensuring row-level serializability without global serialization aborts."*

- **Files Requiring Correction:**
  - `README.md`
  - `docs/DATABASE_DESIGN.md`
  - `docs/PROJECT_REPORT.md`
  - `docs/TESTING.md`
  - `docs/ADMIN_GUIDE.md`
  - `docs/SIMULATION_AND_TRANSACTION_ENGINE.md`
  - `docs/OFFICIAL DOCUMENTATION/B_Diagrams/README.md`
  - `docs/OFFICIAL DOCUMENTATION/Portfolio_Editable_Source/build_database_doc.py`
  - `artifacts/FLASHCORE-DOCUMENTATION-RELEASE-REPORT.md`

- **Verification Status:**  
  - PostgreSQL 18: **REFUTED (Corrected to PostgreSQL 16+)**.  
  - Read Committed + `SELECT FOR UPDATE`: **VERIFIED by `backend/app/core/database.py` and route code**.

---

### Discrepancy 6: Git History (Technical Application Commit vs. Documentation Commits)

- **Existing Documentation Claim:**  
  Some files cited `50916f8` as the active commit, while others cited `5349f96` or `c624d44`, without distinguishing code freeze from documentation release.

- **Actual Evidence Found:**  
  - Source 1: `git log --oneline`.  
  - **`50916f873066e0e25e7a0fec0673efb875a1a0df` (`50916f8`)**: The accepted Stage 2/3 technical baseline commit deployed to Render and Vercel.  
  - **`5349f96c180090e4a873f53ece3d48fbf37ad548` (`5349f96`)**: "chore: finalize FLASHCORE technical implementation and verification" — the final technical application code freeze commit on `main`.  
  - **`c624d449dcbdadcd46f7837259710fdd4e6e65cd` (`c624d44`)**: "docs: publish comprehensive academic documentation portfolio and official PDF deliverables" — the initial documentation portfolio release commit.  
  - **`f02cfff685f478a567baec46c1e55099d08e56b4` (`f02cfff`)**: "docs: update release report with final commit hash and push verification" — documentation metadata update commit.

- **Corrected Wording:**  
  > *"Git Revision Specification:  
  > - Final Technical Application Code Freeze Commit: `5349f96c180090e4a873f53ece3d48fbf37ad548` (`5349f96`)  
  > - Production Deployed Baseline Commit: `50916f873066e0e25e7a0fec0673efb875a1a0df` (`50916f8`)  
  > - Documentation Portfolio Publication Commits: `c624d44` & `f02cfff` on branch `main`."*

- **Files Requiring Correction:**
  - `README.md`
  - `docs/PROJECT_REPORT.md`
  - `docs/README.md`
  - `docs/EVIDENCE_GAP_REPORT.md`
  - `docs/OFFICIAL DOCUMENTATION/Portfolio_Editable_Source/build_source_appendix.py`
  - `artifacts/FLASHCORE-DOCUMENTATION-RELEASE-REPORT.md`

- **Verification Status:**  
  - All four commit hashes and their scopes are **VERIFIED by Git tree forensics**.

---

### Discrepancy 7: Academic Metadata (Session Inconsistency & Unconfirmed Placeholders)

- **Existing Documentation Claim:**  
  Stated "Academic Session: 2025–2026" for a submission dated November 2026 (Semester 3).

- **Actual Evidence Found:**  
  - Source 1: User prompt metadata.  
  - Source 2: Standard engineering academic calendar.  
  - Confirmed details:
    - Candidate: Manas Aggarwal
    - Roll Number: 2501730302
    - Programme: B.Tech CSE (AI/ML), Section A, 3rd Semester
    - Submitted to: Ms. Mansi Kajal, Assistant Professor, SOET, K.R. Mangalam University  
  - **Inconsistency:** A student in 3rd Semester in November 2026 entered in 2025. 1st Semester was Autumn 2025, 2nd Semester was Spring 2026 (Academic Session 2025–2026). The 3rd Semester in Autumn 2026 belongs to **Academic Session 2026–2027**.  
  - **Unconfirmed Evaluation Details:**
    - Formal institutional endorsement, supervisor signature, HOD signature, external examiner name and signature, examination date, and internal/external marks cannot be independently confirmed at this stage.
    - These must remain explicit blank placeholders awaiting the live viva defense.

- **Corrected Wording:**  
  > *"Academic Session / Year: 2026–2027 (Autumn 2026, 3rd Semester; previously labeled 2025–2026 based on admission year). Institutional approvals, supervisor endorsements, and examiner marks are left as formal blank placeholders awaiting the oral viva defense examination."*

- **Files Requiring Correction:**
  - `README.md`
  - `docs/PROJECT_REPORT.md`
  - `docs/README.md`
  - `docs/EVIDENCE_GAP_REPORT.md`
  - `docs/OFFICIAL DOCUMENTATION/Portfolio_Editable_Source/build_portfolio.py`
  - `docs/OFFICIAL DOCUMENTATION/Portfolio_Editable_Source/build_database_doc.py`
  - `docs/OFFICIAL DOCUMENTATION/Portfolio_Editable_Source/build_testing_doc.py`
  - `docs/OFFICIAL DOCUMENTATION/Portfolio_Editable_Source/build_source_appendix.py`

- **Verification Status:**  
  - Academic session 2025–2026: **FLAGGED AS INCONSISTENT / CORRECTED TO 2026–2027 (Autumn 2026)**.  
  - Signatures, seals, and marks: **UNVERIFIED (Retained as formal placeholders)**.

---

## 4. Master Remediation Plan & Files Requiring Update

The following files require factual text correction and regeneration:

| File Target | Action Required | Discrepancies Addressed |
| :--- | :--- | :---: |
| `README.md` | Update concurrency metrics, database version, deployment wording, academic session | 1, 4, 5, 6, 7 |
| `docs/PROJECT_REPORT.md` | Correct PostgreSQL version, academic session, concurrency numbers, derived view notice | 1, 2, 3, 4, 5, 7 |
| `docs/DATABASE_DESIGN.md` | Reconcile table count, distinguish derived views, correct isolation and PostgreSQL version | 3, 5 |
| `docs/SIMULATION_AND_TRANSACTION_ENGINE.md` | Remove 500-thread extrapolation; document actual 50-thread / 700-req benchmark | 1, 3 |
| `docs/SECURITY.md` | Correct npm audit distribution to 2 Critical, 2 High, 5 Moderate with exact IDs | 2 |
| `docs/TESTING.md` | Correct PostgreSQL version; reconcile concurrency test matrix to 50 threads | 1, 5 |
| `docs/PERFORMANCE_AND_CONCURRENCY.md` | Remove extrapolated 500-thread rows; present verified 10, 20, 50-thread tiers | 1 |
| `docs/DEPLOYMENT.md` | Remove zero-downtime claim; factually describe Render rolling container swap | 4 |
| `docs/EVIDENCE_GAP_REPORT.md` | Full forensic update detailing all 7 discrepancies, evidence verdicts, and open gaps | 1, 2, 3, 4, 5, 6, 7 |
| `docs/README.md` | Update academic session, database version, and technical commit scope | 5, 6, 7 |
| `docs/OFFICIAL DOCUMENTATION/B_Diagrams/mermaid/fig_06_database_er_diagram.mmd` | Update ER diagram to reflect active models; mark orders/customers as derived views | 3 |
| `docs/OFFICIAL DOCUMENTATION/Portfolio_Editable_Source/build_*.py` | Update ReportLab build scripts with corrected text and regenerate all 4 PDFs | 1, 2, 3, 4, 5, 7 |
| `artifacts/FLASHCORE-DOCUMENTATION-RELEASE-REPORT.md` | Synchronize release report with audited figures | 1, 2, 3, 4, 5 |

---

## 5. Summary of Unresolved Gaps & Open Technical Limitations

In accordance with strict academic honesty:
1. **Concurrency at 500 Threads:** Unverified. Remains an unexecuted stress scenario; production evidence exists up to 50 concurrent threads.
2. **Zero-Downtime Traffic Continuity:** Unverified. Render single-container rolling swaps were executed, but continuous synthetic pinging during cutover was not performed.
3. **Frontend npm Dependency Migrations:** Deferred to Stage 4 to prevent breaking runtime regressions with React Router v6 and Vite 5.
4. **Physical Faculty Signatures & Marks:** Unendorsed by design; awaiting the oral viva defense examination.
