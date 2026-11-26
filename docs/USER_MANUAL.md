# FLASHCORE — User Handbook & Operations Manual
## End-User Navigation, Product Catalog, Flash Sale Checkout & Order Tracking

> **Student:** Manas Aggarwal (Roll No. 2501730302)  
> **Course / Programme:** B.Tech CSE (AI/ML), 3rd Semester, Section A  
> **Supervisor:** Ms. Mansi Kajal, Assistant Professor, SOET, K.R. Mangalam University  

---

# FLASHCORE — End-User Operations Manual
## Comprehensive Operational Guide for Business Analysts, Store Managers & System Operators

> **Project:** FLASHCORE — Retail Intelligence & High-Concurrency Simulation Platform  
> **Target Audience:** Business Analysts, Category Managers, Inventory Operators, Retail Planners  
> **Production Access:** `https://flashcore-psi.vercel.app`  
> **API Gateway:** `https://database-management-system-s1g5.onrender.com/api`  
> **Document Version:** 1.0.0 (Stage 4 Final Submission)  

---

## 1. Introduction & Platform Overview

FLASHCORE is an enterprise retail intelligence and simulation platform engineered to address two core retail challenges:
1. **Historical Exploratory Analytics:** Uncovering multi-year sales trends, promotional lift, customer footfall patterns, and competitor distance effects across retail pharmacy networks (Rossmann dataset).
2. **High-Concurrency Retail Simulation:** Provisioning product catalogs, allocating store inventory, scheduling flash sales, and executing high-velocity purchase transactions protected against overselling and race conditions.

---

## 2. System Requirements & Access Prerequisites

### 2.1 Supported Browsers
- Google Chrome (Version 110+)
- Mozilla Firefox (Version 115+ ESR)
- Microsoft Edge (Version 110+)
- Apple Safari (Version 16.4+)

### 2.2 Network & Security
- Standard HTTPS (Port 443) outbound connectivity.
- WebSockets or high-frequency polling support for real-time telemetry updates.
- JavaScript and LocalStorage enabled in your browser.

### 2.3 Accessing the Platform
- **Production URL:** [https://flashcore-psi.vercel.app](https://flashcore-psi.vercel.app)
- **Local Development URL:** `http://localhost:5173` (with backend at `http://localhost:8000`)

---

## 3. Account Access & Identity Management

### 3.1 Self-Service Registration
1. Navigate to the platform root: `https://flashcore-psi.vercel.app/signup`.
2. Enter your work email address (must be valid format, e.g., `analyst@retail.example.com`).
3. Enter a secure password (minimum **12 characters** required by security policy).
4. Click **Create Account**.
5. Upon successful creation, the system assigns the default role of **Analyst** and automatically logs you in, redirecting to the **Rossmann Analytics Dashboard**.

### 3.2 Secure Login
1. Navigate to `https://flashcore-psi.vercel.app/login`.
2. Enter your registered email address and password.
3. Click **Sign In**.
4. The system validates your credentials against Argon2id cryptographic hashes and issues a 30-minute JWT session token.

### 3.3 User Profile & Active Role Indicator
- In the top-right corner of the application interface, your active email and role badge (`Admin`, `Analyst`, or `Operator`) are permanently displayed.
- Clicking the user profile avatar displays:
  - Account ID
  - Registered Email
  - Assigned Role
  - Session Expiry Time
  - Direct **Sign Out** button.

### 3.4 Explicit Session Logout
- Clicking **Sign Out** calls `POST /api/auth/logout`.
- This immediately revokes your active token session in the backend database (`auth_sessions`), clears browser LocalStorage tokens, and redirects you to the login screen.

---

## 4. Platform Navigation & User Interface Layout

The FLASHCORE Single Page Application is divided into three distinct operational zones:
1. **Top Navigation Bar:**
   - **Logo & Platform Name:** Quick return to default dashboard.
   - **System Health Pill:** Real-time indicator displaying database and backend status (`Healthy` / `Degraded` / `Offline`).
   - **User Identity Badge:** Active user email and role indicator.
2. **Left Sidebar Menu:**
   - **Analytics Section:**
     - *Overview Dashboard:* High-level KPI summary cards.
     - *Rossmann Stores:* Interactive directory of 1,115 stores.
     - *Sales Explorer:* Multi-dimensional sales and footfall charts.
     - *Promotions Analysis:* Lift calculation comparing promo vs non-promo periods.
   - **Simulation Section:**
     - *Simulation Runs:* Create and view active simulation environments.
     - *Product Catalog:* Register new SKUs and product titles.
     - *Store Inventory:* Physical stock management across stores.
     - *Flash Sales:* Schedule and activate time-bounded drops.
     - *Transactions:* Live feed of simulation purchase attempts.
   - **Commerce & Management Section:**
     - *Orders:* Customer order fulfillment registry.
     - *Customers:* Registered simulation shopper profiles.
     - *System Health:* Full infrastructure telemetry breakdown.
     - *Administration (Admin Only):* User management and audit logs.
3. **Main Content Viewport:** High-density responsive workspace featuring interactive charts (Recharts), tabular data grids with pagination, and action modals.

---

## 5. Rossmann Historical Retail Analytics Workflows

### 5.1 Exploring the Store Directory (`/analytics/stores`)
1. Click **Rossmann Stores** in the sidebar.
2. **Filtering Stores:**
   - Select **Store Type** filter: `a` (standard), `b` (extra assortment), `c` (shopping center), `d` (long-term competitor).
   - Select **Assortment** filter: `a` (basic), `b` (extra), `c` (extended).
3. **Inspecting Store Details:**
   - Click on any store row (e.g., *Store #1*).
   - The drawer reveals: Competition Distance (meters), Competition Opening Month/Year, Promo2 participation, and active promotional interval.

### 5.2 Analyzing Sales Performance & Trends (`/analytics/sales`)
1. Click **Sales Explorer** in the sidebar.
2. **Setting Date Filters:**
   - Choose a Start Date and End Date (e.g., `2015-01-01` to `2015-07-31`).
   - Optionally select a specific Store ID (or leave blank for cross-store totals).
3. **KPI Summary Cards:**
   - **Total Revenue:** Gross sales across the selected interval.
   - **Total Customers:** Aggregate footfall recorded.
   - **Average Basket Size:** Calculated as $\frac{\text{Total Revenue}}{\text{Total Customers}}$.
   - **Open Store Days:** Total operational store-days counted.
4. **Interactive Revenue & Customer Trends:**
   - View daily revenue line charts.
   - Hover over data points to inspect exact date, day of week, and daily sales value.

### 5.3 Evaluating Promotional Lift (`/analytics/promotions`)
1. Click **Promotions Analysis** in the sidebar.
2. The system executes server-side aggregation comparing **Promo Days (Promo = 1)** against **Non-Promo Days (Promo = 0)**.
3. Review metrics:
   - *Promo Average Sales* vs *Regular Average Sales*.
   - *Promotional Sales Lift (%):* Quantifies percentage revenue uplift generated by promotional campaigns.
   - *Promo Customer Footfall Lift (%):* Quantifies customer acquisition lift during promo cycles.

---

## 6. Retail Simulation Engine Workflows

### 6.1 Creating a Simulation Run (`/simulation/runs`)
*(Requires Operator or Admin Role)*
1. Navigate to **Simulation Runs** and click **New Simulation Run**.
2. Enter a descriptive **Run Name** (e.g., `Black Friday Stress Simulation 2026`).
3. Enter optional configuration parameters (JSON configuration) or notes.
4. Click **Create Run**. The run appears in the list with status `created`.

### 6.2 Registering SKUs in the Product Catalog (`/simulation/products`)
1. Navigate to **Product Catalog** and click **Add Product**.
2. Enter a unique **SKU Code** (e.g., `SKU-MED-8801`).
3. Enter the **Product Name** (e.g., `Digital Infrared Thermometer Pro`).
4. Enter an optional **Description**.
5. Click **Save Product**. If the SKU already exists, an inline notification indicates a uniqueness conflict.

### 6.3 Assigning Store Stock & Adjustments (`/simulation/inventory`)
1. Navigate to **Store Inventory** and click **Allocate Stock**.
2. Select the **Store ID** (e.g., Store #1) and the target **Product SKU**.
3. Specify the initial **Physical Quantity** (e.g., `500` units).
4. Click **Allocate**.
5. **Adjusting Stock:**
   - To record damaged items or inventory restocks, click the **Adjust** button on any inventory row.
   - Enter the **Quantity Delta** (positive number to add stock, negative number to deduct).
   - Enter a mandatory **Adjustment Reason** (e.g., `Damaged batch returned to supplier`).
   - Click **Confirm Adjustment**. Physical quantity updates immediately.

### 6.4 Scheduling & Activating a Flash Sale (`/simulation/flash-sales`)
1. Navigate to **Flash Sales** and click **Schedule Flash Sale**.
2. Select the parent **Simulation Run**.
3. Enter a title (e.g., `Midnight 50% Drop`).
4. Set **Start Time** and **End Time**.
5. Click **Create Sale**. The sale is created in `draft` status.
6. **Allocating Sale Quotas:**
   - Click **Add Product Quota** under the draft sale.
   - Select the store inventory item.
   - Set the discounted **Sale Price** (e.g., `$14.99`).
   - Set the **Stock Limit** (e.g., `100` units reserved for this flash sale).
   - Click **Save Quota**. The system increments `reserved_quantity` in physical inventory.
7. **Activating the Sale:**
   - Click **Activate Flash Sale**. The status shifts to `active`. Customers can now purchase from this drop.

### 6.5 Executing Simulated Purchases (`/simulation/transactions`)
1. To test purchase throughput, operators can submit manual purchases or run stress-testing scripts against `POST /api/simulations/flash-sale-products/{id}/purchase`.
2. Each purchase requires:
   - `customer_ref`: Unique customer string (e.g., `CUST-1049`).
   - `idempotency_key`: A UUIDv4 string guaranteeing single execution.
   - `quantity`: Number of units (default `1`).
3. **Interpreting Outcomes:**
   - **Success (Green):** Quota decremented; stock secured.
   - **Duplicate (Blue):** Idempotency key previously processed; original transaction returned without double-charging.
   - **Rejected (Red):** Stock exhausted (`Flash sale stock limit exceeded`) or customer limit reached.

---

## 7. Troubleshooting Common User Issues

| Symptom | Probable Cause | Corrective Action |
| :--- | :--- | :--- |
| **"Session expired or invalid" (HTTP 401)** | Token exceeded 30-minute lifespan or was revoked by admin. | Click Sign Out and log back in to obtain a fresh JWT token. |
| **"Action not permitted" (HTTP 403)** | Current role lacks mutation privileges (e.g., Analyst attempting to create products). | Contact your administrator to request role promotion to `Operator` or `Admin`. |
| **"Flash sale stock limit exceeded"** | All allocated units for the flash sale product have been purchased. | Flash sale is sold out; wait for operator to allocate additional quota. |
| **"System Status: Degraded" indicator** | Database latency spike or temporary cloud socket disconnect. | Telemetry recovers automatically. Refresh page after 15 seconds. |
| **Duplicate purchase error on retry** | Request was submitted twice with mismatched payload details. | Ensure retry requests preserve exact identical customer and quantity parameters. |

---
*End of FLASHCORE End-User Operations Manual.*
