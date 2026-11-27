# FLASHCORE Production Runbook & Dual-Environment Isolation Policy

This document governs the separation between the preserved legacy academic evaluation deployment and the independent FLASHCORE platform infrastructure (`staging` and future `production`).

---

## 1. Environment Isolation Matrix

| Resource | Legacy Academic Production (Protected) | FLASHCORE Staging | FLASHCORE Production (Prepared, Inactive) |
| :--- | :--- | :--- | :--- |
| **GitHub Repository** | `manasaggarwal1107-ctrl/DATABASE-MANAGEMENT-SYSTEM` | `manasaggarwal1107-ctrl/FLASHCORE` (`feat/stage-4-financial-operations`) | `manasaggarwal1107-ctrl/FLASHCORE` (`main`) |
| **Vercel Project** | `flashcore` (`prj_uPmglNWLEYCOSj5QY8WvvjJqmE4m`) | `flashcore-staging` (`prj_qOJJRPX1M8h9Lex4xrK6ElYwulv7`) | `flashcore-platform` (adapted name; legacy owns `flashcore`) |
| **Frontend URL** | `https://flashcore-psi.vercel.app` | `https://flashcore-staging.vercel.app` | Custom production domain (pending approval) |
| **Render Service** | `database-management-system-s1g5.onrender.com` | `flashcore-api-staging` (Blueprint: `render.yaml`) | `flashcore-api` (Template: `infra/production/render.production.yaml`) |
| **PostgreSQL DB** | `flashcore_postgres_temp` | `flashcore_staging` | `flashcore_production` |
| **Credentials / Keys** | Legacy credentials (untouched) | Staging-only secrets | Fresh production-only secrets (generated at activation) |
| **Deployment Mode** | Preserved as-is | Active staging | **Blocked until explicit owner approval** |

### Non-Negotiable Isolation Rules
1. Never modify, redeploy, disconnect, or change environment variables/domains on `DATABASE-MANAGEMENT-SYSTEM`, Vercel `flashcore`, `database-management-system-s1g5.onrender.com`, or `flashcore_postgres_temp`.
2. Never point any `FLASHCORE` frontend or backend to `database-management-system-s1g5.onrender.com` or `flashcore_postgres_temp`.
3. Never reuse `JWT_SECRET_KEY`, `FLASHCORE_CREDENTIAL_ENCRYPTION_KEY`, or database passwords across Legacy, Staging, and Production.

---

## 2. Production Activation Approval Gates

Do **not** provision billable production resources or deploy `FLASHCORE Production` until all of the following approvals are explicitly granted by the project owner:

1. **Architecture & Infrastructure Approval:** Sign-off on `infra/production/render.production.yaml` and `infra/production/vercel.production.json` (project name `flashcore-platform`, domain, and hosting tier).
2. **Database Provisioning Approval:** Sign-off to create managed `flashcore-production-db` (`flashcore_production`) with automated daily backups and point-in-time recovery (PITR) enabled.
3. **Secrets & Domain Approval:** Generation of fresh `JWT_SECRET_KEY`, `FLASHCORE_CREDENTIAL_ENCRYPTION_KEY` (32-byte URL-safe base64 AES-256 master key), and verified production DNS / `FRONTEND_ORIGIN`.
4. **Payment Provider Mode Gate:** Confirm whether Razorpay remains in Test Mode or receives explicitly authorized Live credentials per merchant organisation (never reuse test or legacy keys).

---

## 3. Monitoring & Health Verification

All backend deployments expose four verification endpoints (never exposing database credentials or connection strings):

- `GET /` — Application identity (`{"project": "FLASHCORE", "status": "running"}`).
- `GET /health` — Lightweight liveness check (`200 {"status": "healthy"}`).
- `GET /health/database` — Database connectivity (`200` connected / `503` unavailable).
- `GET /ready` — Deep deployment readiness gate checking PostgreSQL connectivity AND Alembic schema revision (`0004_financial_operations`), plus runtime `environment` and `commit_sha`. Returns `503` if DB is unreachable or migrations are outdated/missing.
- `GET /api/health` — Dashboard System Health payload.

### Production Alert Targets
- Configure Render health checks on `/ready`.
- Alert on sustained HTTP `5xx` responses, `/ready` returning `503`, webhook signature failures, or reconciliation discrepancy alerts.

---

## 4. Backup, Migration & Rollback Procedures

### Pre-Migration Checklist (Staging and Future Production)
1. Confirm legacy production URLs are completely excluded from deployment commands and `DATABASE_URL`.
2. Verify automated backup / snapshot freshness on the target database before applying schema changes:
   ```bash
   pg_dump --format=custom --no-owner --no-acl "$TARGET_DATABASE_URL" > pre_migration_$(date -u +%Y%m%dT%H%M%SZ).dump
   ```
3. Confirm `autoDeploy: false` on `flashcore-api` so schema changes only roll out under controlled release approval.

### Applying Migrations
- Render executes `preDeployCommand: alembic upgrade head` cleanly before booting the new application revision.
- After deploy, verify schema and service readiness via `scripts/verify_staging.py` (or target URL against `/ready` checking `migrations == "ready"`).

### Rollback Procedure
1. Freeze inbound writes / revert the Vercel deployment (`flashcore-platform`) and Render application revision to the previous known-good release.
2. Inspect Alembic state and execute targeted reversible downgrade **only if compatible** with the deployed revision:
   ```bash
   cd backend
   alembic current
   alembic downgrade <previous_verified_revision>
   ```
3. If an irreversible data state occurred, restore the isolated `flashcore_production` database from the pre-migration snapshot/PITR checkpoint without touching staging or legacy academic databases.
4. Re-verify `GET /ready` (`200` and expected `alembic_revision`) before resuming traffic.
