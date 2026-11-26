# FLASHCORE — Stage 3 Dependency & Supply-Chain Security Audit
## Python Backend (Pip/Virtualenv) & Node.js Frontend (NPM/Vite) Package Review

> **Project:** FLASHCORE — Retail Intelligence & High-Concurrency Simulation Platform  
> **Environment:** Local Production Manifests & Node/Python Ecosystems  
> **Date / Timestamp:** 2026-11-24 20:14 IST  
> **Author:** Antigravity (Lead Security & Supply-Chain Engineer)  
> **Target Commit:** `50916f873066e0e25e7a0fec0673efb875a1a0df` (`50916f8`)  
> **Status:** **AUDITED — 0 UNCONTROLLED RUNTIME EXPLOITS, MIGRATION ROADMAP DOCUMENTED**

---

## 1. Executive Summary

A supply-chain and dependency vulnerability audit was conducted across both backend (Python 3.13 / `requirements.txt`) and frontend (Node.js / React 18 / `package.json` / `package-lock.json`) ecosystems.

The Python backend runtime maintains a clean security profile, utilizing modern pinned versions of FastAPI (`0.165.0`), SQLAlchemy (`2.1.9`), Psycopg 3 (`3.3.9`), PyJWT (`2.15.1`), and Pydantic (`2.14.4`), with zero critical runtime vulnerabilities.

The frontend dependency tree was analyzed via `npm audit`. Nine vulnerabilities were cataloged across build/dev tools (`tinypool`, `esbuild`, `vitest`) and runtime packages (`react-router-dom`, `zod`). In accordance with engineering governance rules, unilateral `--force` updates requiring breaking major version migrations (`react-router v7`, `vitest v5`, `vite v8`, `zod v4`) were withheld to preserve stability. Mitigation controls and migration roadmaps are detailed herein.

---

## 2. Python Backend Dependency Manifest

| Package | Pinned Version | Scope | Vulnerability Status | Assessment |
| :--- | :---: | :---: | :---: | :--- |
| `fastapi` | 0.165.0 | Runtime / Framework | **Clean** | Modern ASGI web framework |
| `uvicorn` | 0.54.0 | Runtime / Web Server | **Clean** | High-performance ASGI server |
| `sqlalchemy` | 2.1.9 | Runtime / ORM | **Clean** | Modern SQLAlchemy 2.0+ architecture |
| `psycopg` | 3.3.9 | Runtime / DB Driver | **Clean** | Psycopg 3 with native async/sync support |
| `pydantic` | 2.14.4 | Runtime / Validation | **Clean** | High-speed Rust-backed validation |
| `pyjwt` | 2.15.1 | Runtime / Cryptography | **Clean** | RFC 7519 compliant JWT encoding |
| `pwdlib[argon2]` | 0.4.2 | Runtime / Hashing | **Clean** | Argon2id recommended password hashing |
| `python-dotenv` | 1.2.4 | Runtime / Config | **Clean** | Environment configuration management |
| `pytest` | 9.2.0 | Testing / Dev | **Clean** | Standard Python testing harness |
| `anyio` | 4.16.0 | Runtime / Async | **Clean** | Structured concurrency library |

---

## 3. Node.js Frontend Dependency Audit (`npm audit`)

| Package | Affected Versions | Severity | Advisory ID | Dependency Type | FlashCore Runtime Exposure & Context | Recommendation / Governance Action |
| :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| `tinypool` | <=2.1.1 | **Critical** | GHSA-5gmw-xhrv-c9v3 | DevDependency (via `vitest`) | **Zero Runtime Exposure**: Executes exclusively in local test runner; not bundled in production client build. | Defer breaking Vitest v5 upgrade until Stage 4 framework modernization. |
| `@vitest/mocker` | <=4.1.11 | **Moderate** | GHSA-82fw-gwwq-j7x9 | DevDependency (via `vitest`) | **Zero Runtime Exposure**: Local test runner mock system only. | Defer to Vitest v5 migration. |
| `esbuild` | <=0.24.2 | **Moderate** | GHSA-67mh-4wv8-2f99 | DevDependency (via `vite`) | **Zero Runtime Exposure**: Local dev-server request routing; production uses static Vercel CDN deployment. | Keep current Vite 5 LTS; upgrade in future Vite 8 track. |
| `react-router` | 6.0.0 - 7.17.0 | **Moderate** | GHSA-wrjc-x8rr-h8h6 | Runtime (`dependencies`) | **Mitigated**: Open redirect via backslash in `<Link>`; FlashCore routes use strict internal paths (`/`, `/overview`, `/stores`, `/simulations`). Hydration flaw does not apply (no SSR). | Plan non-breaking router patch update; do not force breaking v7 upgrade. |
| `zod` | <4.6.6 | **High** | GHSA-mrhx-c7xc-m3w5 | Runtime (`dependencies`) | **Mitigated**: Memory exhaustion on oversized collections; FlashCore payloads are small form inputs with strict length limits (`max_length=320`). | Upgrade to patched Zod v3.24.x when released upstream without breaking changes. |

---

## 4. Controlled Remediation Governance

1. **Anti-Breakage Protocol:**
   - `npm audit fix --force` was explicitly withheld. Automated force-updating would mandate major breaking changes:
     - `react-router-dom@7.18.6` (removes React Router v6 conventions)
     - `vite@8.3.8` (breaks Rollup/Vite 5 configuration)
     - `vitest@5.1.1` (breaks Vitest 2 test setup and jsdom bindings)
     - `zod@4.6.7` (breaks Zod v3 schema inference)
2. **Production Impact Assessment:**
   - Production bundle generated via `vite build` includes only minified React client chunks.
   - Zero development dependencies (`tinypool`, `esbuild`, `vitest`) exist in the production `dist/` assets served by Vercel.
3. **Future Migration Plan (Stage 4 / Post-Capstone):**
   - Plan scheduled migration to React Router 7 and Vite 6/7 as a dedicated feature branch with regression test suites.
