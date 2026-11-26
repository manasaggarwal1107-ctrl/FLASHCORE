# Frontend Architecture

## Folder structure

```
src/
  app/               providers (QueryClient)
  components/
    ui/              Button, Badge/OriginBadge/StatusBadge, Panel, Field, StatTile, States, Skeleton, Pagination, ProgressBar, Popover
    layout/          AppShell, Sidebar, Header, Breadcrumbs, CommandPalette, StatusIndicators, ErrorBoundary, nav model
    charts/          chartTheme, TimeSeriesChart, BreakdownBar, ChartPanel
    tables/          DataTable (presentational), ResourceTable (data-bound)
  features/<name>/   one folder per nav section (pages, schemas, local logic)
    shared/          DetailPage, DetailList, FormFooter, SeriesPanel
  hooks/             useResourceList / useResource / useEndpointMutation, connectivity, auth token, debounce
  lib/               config, money (decimal-safe), format, case, cn
  services/api/      client, errors, auth, connectivity, endpoints (registry), pagination, queryClient
  types/api.ts       resource types (PROVISIONAL until contract)
  routes/            router + lazy pages
  styles/            tokens + Tailwind layers
  test/              setup + render helpers
```

## Layering

`UI components` → `feature pages` → `hooks` → `services/api`. Pages never call `fetch`. All HTTP goes through `apiRequest`; all paths live in `endpoints.ts`.

## The endpoint registry is the integration switch

Each endpoint is `{ id, method, path, status }`. While `status: 'pending-contract'` (path `null`):

- `useResourceList` / `useResource` disable their query → **no request is sent**;
- `useEndpointMutation` rejects without sending;
- `ResourceTable`, `ChartPanel`, `DetailPage` render `AwaitingContractState`;
- buttons that would call it are disabled with an explanatory tooltip.

Confirming an endpoint (set `path`, `status: 'confirmed'`) lights up every page bound to it. No page code changes.

## Honest-data rules (enforced structurally)

- `StatTile` accepts a `MetricState` union: value | loading | error | unavailable. There is no default number.
- Nullable API fields render `—`; ratios use `safeRatio` (null, never NaN/Infinity/0).
- Errors render `ErrorState` with the real error; there is no fallback-to-sample-data path anywhere.
- Every record list shows an `OriginBadge` (real / imported / manual / simulation / "Origin unknown").
- Physical inventory and flash-sale allocation are separate types and separate UI groups.
- Concurrency Lab is isolated: own routes, persistent simulation banner, simulation colour token reserved for it.

## Request behaviour

- Timeout via `AbortController` (default 15 s). Caller cancellation distinguished from timeout.
- Errors normalised to `ApiError` with `kind`: network, timeout, aborted, unauthorized, forbidden, not-found, validation, server, http, contract.
- **Retry policy:** queries retry ≤2× only for network/timeout/502/503/504. **Mutations are never retried.** The client itself never retries any request. Purchase-type POSTs must supply an idempotency key (`idempotencyKey` option → configurable header) and any re-submit must be an explicit user action reusing that key.
- Responses are snake_case→camelCase normalised (no-op for camelCase), values untouched.
- Connectivity indicator derives only from real request outcomes (unknown until the first request).

## Money

Money is a decimal **string** end-to-end. `formatMoney` parses to BigInt minor units, rounds half-away-from-zero, and formats via `Intl` parts — no float arithmetic. Forms validate prices as decimal strings and never convert to `number`.

## Forms

React Hook Form + Zod resolvers. Schemas are exported and unit-tested. `FormFooter` standardises: not-connected notice, server error, success.

## Security / privacy

- Bearer token kept in `sessionStorage` only (cleared when the tab closes); never logged.
- Customers shown by reference; no PII fields in types or UI.
- Authentication scheme is a placeholder pending the contract (`services/api/auth.ts` is the only file to change).

## Code splitting

Every route page is `React.lazy`; Recharts is only pulled into pages that use charts.
