# FLASHCORE — Application Screenshot Portfolio & Evidence Index
## Authentic UI Screen Captures, Viewport Specifications & Verification Status

> **Student:** Manas Aggarwal (Roll No. 2501730302)  
> **Course / Programme:** B.Tech CSE (AI/ML), 3rd Semester, Section A  
> **Supervisor:** Ms. Mansi Kajal, Assistant Professor, SOET, K.R. Mangalam University  
> **Capture Engine:** Edge Headless (Chromium) on Running React 18 / Vite 5 SPA  

---

## 1. Screenshot Evidence Inventory

Every image in this repository is an authentic capture of the running FLASHCORE frontend application. No screenshots are synthetic mockups or fabricated images.

| Fig # | Image File | Route / Path | Viewport | Target Component | Verification Status |
| :---: | :--- | :--- | :---: | :--- | :---: |
| **01** | [`01-login-desktop.png`](01-login-desktop.png) | `/login` | 1440 × 900 | `LoginPage.tsx` (Guest View) | **VERIFIED** |
| **02** | [`02-login-mobile.png`](02-login-mobile.png) | `/login` | 390 × 844 | `LoginPage.tsx` (Mobile 390px) | **VERIFIED** |
| **03** | [`03-signup-desktop.png`](03-signup-desktop.png) | `/signup` | 1440 × 900 | `SignupPage.tsx` | **VERIFIED** |
| **04** | [`04-token-access-desktop.png`](04-token-access-desktop.png) | `/token-access` | 1440 × 900 | `SettingsPage.tsx` (Unauthenticated) | **VERIFIED** |
| **05** | [`05-overview-dashboard-desktop.png`](05-overview-dashboard-desktop.png) | `/overview` | 1440 × 900 | `OverviewPage.tsx` & `AppShell.tsx` | **VERIFIED** |
| **06** | [`06-overview-dashboard-mobile.png`](06-overview-dashboard-mobile.png) | `/overview` | 390 × 844 | `OverviewPage.tsx` (Mobile 390px) | **VERIFIED** |
| **07** | [`07-products-catalog-desktop.png`](07-products-catalog-desktop.png) | `/products` | 1440 × 900 | `ProductsPage.tsx` | **VERIFIED** |
| **08** | [`08-inventory-management-desktop.png`](08-inventory-management-desktop.png) | `/inventory` | 1440 × 900 | `InventoryPage.tsx` | **VERIFIED** |
| **09** | [`09-flash-sales-desktop.png`](09-flash-sales-desktop.png) | `/flash-sales` | 1440 × 900 | `FlashSalesPage.tsx` | **VERIFIED** |
| **10** | [`10-concurrency-simulation-desktop.png`](10-concurrency-simulation-desktop.png) | `/concurrency` | 1440 × 900 | `ConcurrencyPage.tsx` & `SimulationForm.tsx` | **VERIFIED** |
| **11** | [`11-concurrency-simulation-mobile.png`](11-concurrency-simulation-mobile.png) | `/concurrency` | 390 × 844 | `ConcurrencyPage.tsx` (Mobile 390px) | **VERIFIED** |
| **12** | [`12-transactions-monitor-desktop.png`](12-transactions-monitor-desktop.png) | `/transactions` | 1440 × 900 | `TransactionsPage.tsx` | **VERIFIED** |
| **13** | [`13-orders-management-desktop.png`](13-orders-management-desktop.png) | `/orders` | 1440 × 900 | `OrdersPage.tsx` | **VERIFIED** |
| **14** | [`14-customers-directory-desktop.png`](14-customers-directory-desktop.png) | `/customers` | 1440 × 900 | `CustomersPage.tsx` | **VERIFIED** |
| **15** | [`15-analytics-trends-desktop.png`](15-analytics-trends-desktop.png) | `/analytics` | 1440 × 900 | `AnalyticsPage.tsx` & Recharts panels | **VERIFIED** |
| **16** | [`16-imports-history-desktop.png`](16-imports-history-desktop.png) | `/imports` | 1440 × 900 | `ImportsPage.tsx` & `UploadPanel.tsx` | **VERIFIED** |
| **17** | [`17-audit-logs-desktop.png`](17-audit-logs-desktop.png) | `/audit` | 1440 × 900 | `AuditPage.tsx` | **VERIFIED** |
| **18** | [`18-system-health-desktop.png`](18-system-health-desktop.png) | `/system` | 1440 × 900 | `SystemHealthPage.tsx` | **VERIFIED** |
| **19** | [`19-settings-configuration-desktop.png`](19-settings-configuration-desktop.png) | `/settings` | 1440 × 900 | `SettingsPage.tsx` (Authenticated) | **VERIFIED** |
| **20** | [`20-not-found-404-desktop.png`](20-not-found-404-desktop.png) | `/*` | 1440 × 900 | `NotFoundPage.tsx` | **VERIFIED** |

---

## 2. Re-capturing Evidence

All screenshots can be re-captured automatically using the headless execution harness:

```bash
python scratch/capture_all_screenshots.py
```
This serves `frontend/dist`, launches headless Edge, visits each client route, and updates the screenshots index.
