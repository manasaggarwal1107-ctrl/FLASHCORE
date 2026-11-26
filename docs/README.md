# FLASHCORE — Documentation Portfolio Index
## Retail Intelligence & High-Concurrency Simulation Platform

> **Student:** Manas Aggarwal (Roll No. 2501730302)  
> **Course:** Bachelor of Technology (B.Tech) in Computer Science & Engineering (AI/ML)  
> **Section:** A | **Semester:** 3rd Semester  
> **Project Supervisor:** Ms. Mansi Kajal, Assistant Professor, SOET, K.R. Mangalam University  
> **Academic Session:** 2025–2026  
> **GitHub Repository:** `https://github.com/manasaggarwal1107-ctrl/DATABASE-MANAGEMENT-SYSTEM.git`  
> **Target Branch:** `main`  
> **Reference Standard:** DAA-CAPSTONE Academic Documentation Architecture  

---

## Portfolio Navigation & Architecture Index

This documentation portfolio provides comprehensive academic, architectural, and operational documentation for the **FLASHCORE** platform.

### Core Documentation Volumes

| Volume / Document | File Path | Scope & Key Contents |
| :--- | :--- | :--- |
| **Comprehensive Project Report** | [docs/PROJECT_REPORT.md](PROJECT_REPORT.md) | Full 34-section academic thesis, theoretical foundations, SRS, database models, implementation details, and evaluation. |
| **System Architecture** | [docs/ARCHITECTURE.md](ARCHITECTURE.md) | High-level 3-tier architecture, component models, data flows, and subsystem interactions. |
| **Database Design** | [docs/DATABASE_DESIGN.md](DATABASE_DESIGN.md) | PostgreSQL relational schema: 14 tables, 130 constraints, 28 indexes, isolation levels, and locking mechanics. |
| **API Reference Specification** | [docs/API_REFERENCE.md](API_REFERENCE.md) | Complete OpenAPI 3.1 specification for 42 endpoints, request/response models, RBAC, and error contracts. |
| **Simulation & Transaction Engine** | [docs/SIMULATION_AND_TRANSACTION_ENGINE.md](SIMULATION_AND_TRANSACTION_ENGINE.md) | Concurrency control deep-dive: row-level locking, atomic decrements, burst modeling, and idempotency guards. |
| **Security & Supply Chain** | [docs/SECURITY.md](SECURITY.md) | Argon2id password hashing, JWT RFC 7519 authentication, 3-role RBAC, and honest Stage 3 npm audit review. |
| **Testing & Verification** | [docs/TESTING.md](TESTING.md) | Test engineering summary: 144 backend pytest tests, 124 frontend vitest tests, and concurrency stress harness. |
| **Performance & Concurrency** | [docs/PERFORMANCE_AND_CONCURRENCY.md](PERFORMANCE_AND_CONCURRENCY.md) | Empirical throughput benchmarks (283.5 RPS read, 100.9–103.9 RPS write), latency percentiles, and lock contention. |
| **Cloud Deployment** | [docs/DEPLOYMENT.md](DEPLOYMENT.md) | Production architecture: FastAPI ASGI on Render Cloud, React 18 on Vercel Edge, Neon PostgreSQL. |
| **Install & Run Guide** | [docs/INSTALL_AND_RUN.md](INSTALL_AND_RUN.md) | Step-by-step developer guide: local environment setup, database seeding, server execution, and test commands. |
| **User Handbook** | [docs/USER_MANUAL.md](USER_MANUAL.md) | End-user guide: product discovery, flash sale participation, checkout operations, and order tracking. |
| **Administrator Guide** | [docs/ADMIN_GUIDE.md](ADMIN_GUIDE.md) | System administration guide: inventory management, flash sale scheduling, simulation controls, and audit inspection. |
| **Viva Defense Preparation** | [docs/VIVA.md](VIVA.md) | 40+ rigorous oral defense questions & answers covering database internals, concurrency, algorithms, and security. |
| **Evidence Gap Report** | [docs/EVIDENCE_GAP_REPORT.md](EVIDENCE_GAP_REPORT.md) | Academic honesty audit: verified implementations vs. known limitations, conditional acceptances, and risks. |

---

### Official Documentation Portfolio

Located in [`docs/OFFICIAL DOCUMENTATION/`](OFFICIAL%20DOCUMENTATION/README.md):
- **Database Documentation PDF:** [`Database_Documentation.pdf`](OFFICIAL%20DOCUMENTATION/Database_Documentation.pdf)
- **Testing and Validation PDF:** [`Testing_and_Validation.pdf`](OFFICIAL%20DOCUMENTATION/Testing_and_Validation.pdf)
- **Screenshot Portfolio PDF:** [`Screenshot_Portfolio.pdf`](OFFICIAL%20DOCUMENTATION/Screenshot_Portfolio.pdf)
- **Source Verification Appendix PDF:** [`Source_Verification_Appendix.pdf`](OFFICIAL%20DOCUMENTATION/Source_Verification_Appendix.pdf)
- **System Diagrams:** [`docs/OFFICIAL DOCUMENTATION/B_Diagrams/`](OFFICIAL%20DOCUMENTATION/B_Diagrams/README.md) (Editable `.mmd`, rendered `.png`, and vector `.svg`)
- **Editable Source Files:** [`docs/OFFICIAL DOCUMENTATION/Portfolio_Editable_Source/`](OFFICIAL%20DOCUMENTATION/Portfolio_Editable_Source/README.md) (Python ReportLab build scripts and assets)

---

## Technology Stack Summary

```text
+-----------------------------------------------------------------------+
|                            FLASHCORE SYSTEM                           |
+-----------------------------------------------------------------------+
|  CLIENT TIER:                                                         |
|  - React 18.3 / Vite 5 / TypeScript / Tailwind CSS 3.4                |
|  - TanStack Query v5 / React Router v6 / React Hook Form / Zod        |
|  - Responsive Layouts: Desktop (1440x900) & Mobile (390x844)          |
+-----------------------------------------------------------------------+
|  APPLICATION TIER:                                                    |
|  - Python 3.13 / FastAPI 0.165.0 / Starlette ASGI                     |
|  - SQLAlchemy 2.1.9 ORM (Async & Sync Engine)                         |
|  - Pydantic v2 Schema Validation / PyJWT 2.15.1 / Pwdlib (Argon2id)   |
|  - Concurrency Engine: Pessimistic Row Locking (SELECT FOR UPDATE)    |
|  - Cryptographic Idempotency Guard (SHA-256 + UUIDv4 Replay Cache)   |
+-----------------------------------------------------------------------+
|  DATA TIER:                                                           |
|  - PostgreSQL 16+ Relational Database / Neon Serverless               |
|  - 14 Tables / 130 Integrity Constraints / 28 Optimized Indexes      |
|  - ACID Isolation Level: Read Committed / Repeatable Read             |
|  - Rossmann Retail Intelligence Schema & High-Concurrency E-Commerce  |
+-----------------------------------------------------------------------+
```

---

## Academic Integrity & Governance Statement

1. **Stage 3 Status:** Stage 3 is explicitly preserved as **CONDITIONALLY ACCEPTED** due to nine unpatched frontend dev/build advisories cataloged in `npm audit`. Forced updates were withheld to preserve stability.
2. **Signature Areas:** All supervisor, HOD, and external examiner signature blocks remain unendorsed placeholders awaiting formal evaluation. The candidate declaration contains a student signature placeholder.
3. **DOCX / PPTX Notice:** Detailed thesis `.docx` and `.pptx` defense slides will be compiled separately through Claude.
