# Integration Handover

## 1. Verification status — read first

| Check | Status |
| --- | --- |
| `npm install` | **Not run** — authoring sandbox had no registry access |
| `npm run typecheck` | **Not run** |
| `npm run lint` | **Not run** |
| `npm test` | **Not run** |
| `npm run build` | **Not run** |
| Visual check in a browser / at 1440 px / on mobile | **Not done** |
| Pure logic (`money.ts`, `case.ts`, `format.ts`) | Run under Node with assertions mirroring the unit tests — **passed** (25 assertions). This is *not* a Vitest run. |

The project has therefore never been compiled. Expect a small number of type/lint/test fixes on first run (most likely: dependency version drift, a Recharts/Framer typing nit, a test selector). Run in this order and fix as you go:

```bash
npm install && npm run typecheck && npm run lint && npm test && npm run build && npm run dev
```

Then review each page at 1440 px, ~768 px and ~390 px.

## 2. Folder structure
See `FRONTEND_ARCHITECTURE.md`.

## 3. Install & run
`cp .env.example .env.local && npm install && npm run dev`. Build: `npm run build` → `dist/`. Tests: `npm test`.

## 4. Environment variables
`VITE_API_BASE_URL`, `VITE_APP_ENV`, `VITE_API_TIMEOUT_MS`, `VITE_DEV_PROXY_TARGET`, `VITE_IDEMPOTENCY_HEADER` (documented in `.env.example`). Build-time only; no secrets belong here.

## 5. Backend endpoints expected
See `API_CONTRACT.md` table (all 40-odd registry entries).

## 6. Endpoints not yet available
**All of them** — none are confirmed. Every page renders an honest "Awaiting API contract" state until its endpoint is confirmed.

## 7. Integration steps
1. Receive the backend `API_CONTRACT.md`; answer the "Questions" list in this repo's `API_CONTRACT.md`.
2. Update the adapters (auth, errors, pagination).
3. Reconcile `types/api.ts` with real schemas (add Zod response validation if desired).
4. Confirm endpoints one at a time in `endpoints.ts`; update `endpoints.test.ts` (its "no invented paths" test will intentionally start failing for confirmed entries — change it to assert the confirmed paths).
5. Verify each page: loading, empty, error, populated; origin badges; money formatting.
6. Verify no simulation data appears outside the Concurrency Lab.
7. Add authentication UI/login flow if the contract requires one (only a bearer-token field exists in Settings).

## 8. Known limitations / honest gaps
- **Not compiled or run** (section 1).
- Types in `types/api.ts` are provisional.
- Auth is a bearer-token placeholder; no login flow, no user identity in the account menu.
- Command search navigates pages only; no record search (no endpoint).
- Notifications panel has no source; it says so.
- Concurrency Lab: strategy comparison has no data source; run progress polling is not implemented (the contract must say whether runs are synchronous). Run detail loads on selection.
- Analytics export button is disabled until an export endpoint is defined; period is requested as `from`/`to` (assumed).
- Product/flash-sale **edit** forms start empty — they are not pre-filled from the existing record.
- Inventory page has no per-product drill-down; low-stock uses the backend-supplied threshold only (unknown when absent).
- Order/transaction filters use free-text status inputs where valid values aren't known.
- No light theme; no i18n beyond `Intl` formatting in the browser locale.
- No automated accessibility audit; no e2e tests; bundle size unmeasured.
- A purchase-creation UI is intentionally not built (not in the brief's page list). The client supports `idempotencyKey` for when/if it is.
