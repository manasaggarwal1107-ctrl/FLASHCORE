# Changelog — FLASHCORE Platform

All notable changes, documentation releases, and architectural milestones for **FLASHCORE** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0-docs] - 2026-11-24

### Added
- **Academic Documentation Portfolio (`docs/`):**
  - `docs/PROJECT_REPORT.md`: Comprehensive 34-section B.Tech capstone thesis and technical report featuring exact student details (Manas Aggarwal, Roll No: 2501730302, B.Tech CSE (AI/ML), Sec A, Sem 3, Guide: Ms. Mansi Kajal, SOET, K.R. Mangalam University), theoretical foundations, SRS, database models, and evaluation.
  - `docs/ARCHITECTURE.md`: High-level 3-tier architecture, component models, and data flows.
  - `docs/DATABASE_DESIGN.md`: PostgreSQL relational schema specification: 14 tables, 130 constraints, 28 indexes, isolation levels, and row-level locking.
  - `docs/API_REFERENCE.md`: OpenAPI 3.1 specification cataloging all 42 RESTful endpoints, request/response schemas, and RBAC matrix.
  - `docs/SIMULATION_AND_TRANSACTION_ENGINE.md`: Detailed concurrency control engineering: `SELECT ... FOR UPDATE`, atomic decrements, Poisson arrival burst modeling, and zero-oversell verification.
  - `docs/SECURITY.md`: Argon2id password hashing, JWT RFC 7519 authentication, 3-role RBAC, and honest Stage 3 supply-chain dependency audit.
  - `docs/TESTING.md`: Quality assurance summary covering 144 backend pytest tests (100% pass) and 124 frontend vitest tests (100% pass).
  - `docs/PERFORMANCE_AND_CONCURRENCY.md`: Empirical throughput benchmarks (283.5 RPS read, 100.9–103.9 RPS write) and latency percentiles.
  - `docs/DEPLOYMENT.md`: Cloud deployment runbook covering FastAPI ASGI on Render Cloud, React 18 on Vercel Edge Network, and Neon Serverless DB.
  - `docs/INSTALL_AND_RUN.md`: Comprehensive local developer installation, database initialization, and test execution instructions.
  - `docs/USER_MANUAL.md`: End-user handbook for product discovery, flash sales, and order tracking.
  - `docs/ADMIN_GUIDE.md`: Administrator operations manual for inventory management, simulation runs, and audit inspection.
  - `docs/VIVA.md`: 40+ rigorous academic and technical viva preparation questions & answers across database systems and concurrency.
  - `docs/EVIDENCE_GAP_REPORT.md`: Academic integrity audit detailing verified implementations, known technical limitations, and conditional acceptances.
  - `docs/README.md`: Master documentation index, technology stack overview, and reading guide.

- **Official Documentation Portfolio (`docs/OFFICIAL DOCUMENTATION/`):**
  - `Database_Documentation.pdf`: Formally compiled relational schema documentation, table data dictionary, and ER diagrams (325 KB).
  - `Testing_and_Validation.pdf`: Formal test execution report and multi-worker concurrency benchmark evidence (140 KB).
  - `Screenshot_Portfolio.pdf`: High-resolution 20-screen UI screenshot portfolio (887 KB).
  - `Source_Verification_Appendix.pdf`: Forensic Git commit audit, code inventory, and supply-chain security disclosure (170 KB).
  - `README.md`: Formal portfolio index and re-compilation instructions.

- **Architectural & Flow Diagrams (`docs/OFFICIAL DOCUMENTATION/B_Diagrams/`):**
  - 19 editable Mermaid source files (`mermaid/*.mmd`).
  - 19 high-resolution raster diagrams rendered at 2x scale (`png/*.png`).
  - 19 scalable vector graphics diagrams (`svg/*.svg`).
  - `README.md`: Complete diagram catalog with figure numbers and descriptions.

- **Portfolio Editable Sources (`docs/OFFICIAL DOCUMENTATION/Portfolio_Editable_Source/`):**
  - `lib.py`: Shared ReportLab styling engine, typography, and `NumberedCanvas` (Page X of Y).
  - `build_portfolio.py`, `build_database_doc.py`, `build_testing_doc.py`, `build_source_appendix.py`, and `build_all_pdfs.py`.
  - `assets/screenshots/`: 20 canonical UI screen captures across desktop (1440x900) and mobile (390x844).
  - `README.md`: Source compilation guide and dependency requirements.

- **Screenshot Evidence Index (`docs/screenshots/`):**
  - 20 genuine application screenshots captured directly from the running React 18 SPA via headless Chromium.
  - `README.md`: Evidence catalog detailing routes, viewports, components, and verification status.

- **Root Documentation:**
  - `README.md`: Project overview, features, technology stack, architecture summary, quick start, and documentation index.
  - `CHANGELOG.md`: Release notes and change history.

### Changed
- Updated academic candidate enrollment to official Roll Number: `2501730302`.
- Formatted university certificate and candidate declaration with official blank signature placeholders for academic evaluation.

### Security
- Preserved Stage 3 **CONDITIONAL ACCEPTANCE** status. Fully disclosed all nine frontend npm audit advisories (`tinypool`, `esbuild`, `vitest`, `react-router-dom`, `zod`) with CVE citations and risk assessments.
- Quarantined and excluded `backend/import_rossmann_render.py` and `FLASHCORE-MASTER-RECONCILE.ps1` from version control.
- Scanned and verified zero credentials, tokens, or connection strings committed to Git.
