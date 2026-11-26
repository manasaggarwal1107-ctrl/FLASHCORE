# FLASHCORE: Retail Intelligence & High-Concurrency Simulation Platform

**B.Tech Capstone Project in Computer Science & Engineering (AI/ML)**  
*School of Engineering and Technology (SOET), K.R. Mangalam University, Gurugram*

---

### **Academic Submission Details**

- **Student / Candidate:** Manas Aggarwal
- **Roll Number / Student ID:** 2501730302
- **Programme:** Bachelor of Technology (B.Tech) in Computer Science & Engineering (AI/ML)
- **Section & Semester:** Section A, 3rd Semester
- **Project Supervisor:** Ms. Mansi Kajal, Assistant Professor, SOET
- **Repository:** `https://github.com/manasaggarwal1107-ctrl/DATABASE-MANAGEMENT-SYSTEM.git`
- **Target Branch:** `main`
- **Active Technical Commit:** `5349f96c180090e4a873f53ece3d48fbf37ad548` (`5349f96`)
- **Documentation Architecture Standard:** Modeled on DAA-CAPSTONE Academic Documentation Framework

---

## 1. Project Overview

**FLASHCORE** is an enterprise-grade retail intelligence, e-commerce transaction processing, and high-concurrency simulation platform. It models real-world retail store dynamics based on historical Rossmann retail datasets while providing an ACID-compliant transaction engine capable of handling flash-sale demand spikes with guaranteed zero inventory overselling.

The platform addresses a fundamental distributed database challenge: how to maintain serializable inventory balances under concurrent customer purchase bursts without incurring lock-exhaustion crashes or unconstrained overselling.

### Key Capabilities & Achievements
- **High-Concurrency Concurrency Control:** Implements pessimistic row-level locking (`SELECT ... FOR UPDATE`) and conditional atomic decrements (`WHERE stock >= qty`) to completely eliminate Time-of-Check to Time-of-Use (TOCTOU) race conditions.
- **Zero Overselling Guarantee:** Empirically verified across 100, 250, and 500 concurrent worker threads (2,500 total requests) with exactly zero oversold units and zero negative inventory anomalies.
- **Cryptographic Idempotency Guard:** RFC 7519 compliant Bearer tokens and SHA-256 fingerprinting via the `Idempotency-Key` header ensure client network retries deterministically return cached outcomes without double-decrementing stock.
- **Applied Retail Analytics:** Ingests and indexes historical Rossmann retail datasets (stores, daily sales, promotion schedules) to evaluate promotional elasticity, customer conversion rates, and revenue impact across store formats.
- **Role-Based Access Control (RBAC):** Three distinct security roles (`admin`, `analyst`, `operator`) enforced via Argon2id password hashing and JWT access tokens.
- **Exhaustive Automated Testing:** 144 backend pytest tests (100% passing) and 124 frontend vitest tests (100% passing).

---

## 2. Actual Technology Stack

| Layer | Technologies & Frameworks | Pinned Version | Architectural Role |
| :--- | :--- | :---: | :--- |
| **Backend Framework** | FastAPI / Starlette ASGI | 0.165.0 | High-performance asynchronous web routing, OpenAPI 3.1 contract generation |
| **ASGI Web Server** | Uvicorn | 0.54.0 | Asynchronous Server Gateway Interface HTTP worker |
| **Database ORM & Driver** | SQLAlchemy / Psycopg 3 | 2.1.9 / 3.3.9 | Relational mapping, async connection pooling, raw PostgreSQL locking |
| **Relational Database** | PostgreSQL / Neon Cloud | 16.3+ | 14 tables, 130 constraints, 28 indexes, Read Committed isolation |
| **Validation & Schemas** | Pydantic v2 | 2.14.4 | Rust-backed request/response serialization and schema enforcement |
| **Authentication & Crypto** | PyJWT / Pwdlib (Argon2id) | 2.15.1 / 0.4.2 | RFC 7519 JSON Web Tokens, state-of-the-art password hashing |
| **Frontend Framework** | React 18 / TypeScript | 18.3.1 / ~5.6.3 | Component architecture, strict static typing |
| **Build Tool & Bundler** | Vite 5 / Tailwind CSS | 5.4.10 / 3.4.14 | Rapid HMR, code-splitting, responsive utility-first CSS |
| **Client State & Cache** | TanStack Query v5 / React Router | 5.59.0 / 6.28.0 | Server-state caching, optimistic updates, declarative routing |
| **Data Visualization** | Recharts | 2.13.0 | Time-series trends, promotional breakdowns, conversion charts |
| **Test Suites** | Pytest / Vitest | 9.2.0 / 2.1.4 | 144 backend unit/integration tests, 124 frontend component tests |

---

## 3. High-Level Architecture Summary

```text
+-----------------------------------------------------------------------------------+
|                                  CLIENT TIER                                      |
|  React 18 / TypeScript Single Page Application (Desktop 1440x900 & Mobile 390x844)|
|  TanStack Query Server Cache | React Router v6 | Tailwind CSS 3.4 Design System   |
+-----------------------------------------------------------------------------------+
                                        | HTTPS / JSON REST API
                                        v
+-----------------------------------------------------------------------------------+
|                              APPLICATION ENGINE (ASGI)                            |
|  FastAPI 0.165.0 / Starlette | Pydantic v2 Validation | Argon2id Auth & JWT Guard |
|  Pessimistic Row-Locking Manager (SELECT FOR UPDATE) | Idempotency Replay Cache   |
|  High-Concurrency Burst Simulator (Poisson Arrival Modeling, 10–500 Worker Threads)|
+-----------------------------------------------------------------------------------+
                                        | Encrypted SSL Connection Pool
                                        v
+-----------------------------------------------------------------------------------+
|                                 RELATIONAL DATA TIER                              |
|  PostgreSQL 16+ Engine / Neon Serverless Relational Database                      |
|  14 Tables | 130 Integrity Constraints | 28 B-Tree Indexes | ACID Isolation       |
|  Rossmann Retail Intelligence Schema & High-Concurrency Commerce Order Ledgers    |
+-----------------------------------------------------------------------------------+
```

---

## 4. Documentation Portfolio Index

The complete documentation suite is organized within the [`docs/`](docs/README.md) directory:

### Core Technical Volumes

| Document | Path | Scope & Description |
| :--- | :--- | :--- |
| **Project Report** | [docs/PROJECT_REPORT.md](docs/PROJECT_REPORT.md) | Complete 34-section academic thesis, theoretical foundations, system SRS, and evaluation. |
| **System Architecture** | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | High-level 3-tier architecture, component models, data flows, and subsystem interactions. |
| **Database Design** | [docs/DATABASE_DESIGN.md](docs/DATABASE_DESIGN.md) | Relational schema documentation: 14 tables, 130 constraints, 28 indexes, isolation levels. |
| **API Reference** | [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | Complete OpenAPI specification for 42 endpoints, request/response models, and RBAC matrix. |
| **Simulation Engine** | [docs/SIMULATION_AND_TRANSACTION_ENGINE.md](docs/SIMULATION_AND_TRANSACTION_ENGINE.md) | Concurrency deep-dive: row-level locking, atomic decrements, burst modeling, zero overselling. |
| **Security & Supply Chain** | [docs/SECURITY.md](docs/SECURITY.md) | Argon2id hashing, JWT RFC 7519, 3-role RBAC, and honest Stage 3 npm audit disclosure. |
| **Testing Documentation** | [docs/TESTING.md](docs/TESTING.md) | Test engineering summary: 144 backend pytest tests, 124 frontend vitest tests. |
| **Performance Benchmarks** | [docs/PERFORMANCE_AND_CONCURRENCY.md](docs/PERFORMANCE_AND_CONCURRENCY.md) | Empirical throughput benchmarks (283.5 RPS read, 100.9–103.9 RPS write), latency percentiles. |
| **Cloud Deployment** | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production architecture: FastAPI ASGI on Render Cloud, React 18 on Vercel Edge, Neon DB. |
| **Install & Run Guide** | [docs/INSTALL_AND_RUN.md](docs/INSTALL_AND_RUN.md) | Step-by-step developer guide: local environment setup, database seeding, execution commands. |
| **User Handbook** | [docs/USER_MANUAL.md](docs/USER_MANUAL.md) | End-user guide: product discovery, flash sale participation, checkout operations. |
| **Administrator Guide** | [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md) | System administration guide: inventory management, simulation controls, audit inspection. |
| **Viva Defense Preparation** | [docs/VIVA.md](docs/VIVA.md) | 40+ rigorous oral defense questions & answers covering database internals and concurrency. |
| **Evidence Gap Report** | [docs/EVIDENCE_GAP_REPORT.md](docs/EVIDENCE_GAP_REPORT.md) | Academic honesty audit: verified implementations vs. known limitations and risks. |

### Official Documentation Portfolio

Located in [`docs/OFFICIAL DOCUMENTATION/`](docs/OFFICIAL%20DOCUMENTATION/README.md):
- **Database Documentation PDF:** [`Database_Documentation.pdf`](docs/OFFICIAL%20DOCUMENTATION/Database_Documentation.pdf)
- **Testing and Validation PDF:** [`Testing_and_Validation.pdf`](docs/OFFICIAL%20DOCUMENTATION/Testing_and_Validation.pdf)
- **Screenshot Portfolio PDF:** [`Screenshot_Portfolio.pdf`](docs/OFFICIAL%20DOCUMENTATION/Screenshot_Portfolio.pdf)
- **Source Verification Appendix PDF:** [`Source_Verification_Appendix.pdf`](docs/OFFICIAL%20DOCUMENTATION/Source_Verification_Appendix.pdf)
- **System Diagrams:** [`docs/OFFICIAL DOCUMENTATION/B_Diagrams/`](docs/OFFICIAL%20DOCUMENTATION/B_Diagrams/README.md) (19 Editable `.mmd`, rendered `.png`, and vector `.svg`)
- **Editable Source Files:** [`docs/OFFICIAL DOCUMENTATION/Portfolio_Editable_Source/`](docs/OFFICIAL%20DOCUMENTATION/Portfolio_Editable_Source/README.md) (Python ReportLab build scripts and assets)

---

## 5. Installation, Execution & Quick Start

### 5.1 Backend Execution
```bash
# Clone the repository
git clone https://github.com/manasaggarwal1107-ctrl/DATABASE-MANAGEMENT-SYSTEM.git
cd DATABASE-MANAGEMENT-SYSTEM/CAPSTONE/FLASHCORE-FRESH/backend

# Create virtual environment & install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Start backend ASGI server
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
API Root: `http://127.0.0.1:8000` | OpenAPI Docs: `http://127.0.0.1:8000/docs`

### 5.2 Frontend Execution
```bash
cd ../frontend
npm install
npm run dev
```
Client URL: `http://localhost:5173`

---

## 6. Testing & Automated Verification

### Run Backend Pytest Suite (144 Tests)
```bash
cd backend
pytest tests/ -v
```
Expected output: `144 passed in ~4.5s`.

### Run Frontend Vitest Suite (124 Tests)
```bash
cd frontend
npm run test
```
Expected output: `124 passed in ~3.8s`.

### Run Concurrency Stress Test Harness
```bash
python artifacts/concurrency_test_harness.py
```
Validates zero overselling across 100 concurrent checkout worker threads.

---

## 7. Known Limitations & Outstanding Risks

In compliance with academic honesty standards:
1. **Stage 3 Status:** Stage 3 is explicitly maintained as **CONDITIONALLY ACCEPTED** due to nine unpatched frontend build/dev dependency advisories cataloged in `npm audit` (`tinypool`, `esbuild`, `vitest`, `react-router-dom`, `zod`). Unilateral forced updates (`npm audit fix --force`) were withheld to prevent breaking regressions with React Router v6 and Vite 5.
2. **Academic DOCX and PPTX Formats:** The formal academic thesis `.docx` and presentation `.pptx` slides are prepared separately through Claude for faculty formatting review and are not compiled in this automated repository release.
3. **Excluded Dangerous Scripts:** `backend/import_rossmann_render.py` (which mutates live cloud databases) and `FLASHCORE-MASTER-RECONCILE.ps1` (unsafe auto-push) have been strictly quarantined and excluded from commits.
4. **Physical Signatures:** Institutional certificates and declarations contain formal signature placeholders awaiting the oral viva defense examination.
