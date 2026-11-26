# FLASHCORE — Live Demonstration Script & Capstone Defense Walkthrough
## 15-Minute Timed Demonstration Guide for University Faculty & External Examiners

> **Project:** FLASHCORE — Retail Intelligence & High-Concurrency Simulation Platform  
> **Presenter:** Manas Aggarwal (1107-CS-CAPSTONE)  
> **Course:** B.Tech Capstone Project in Computer Science & Engineering  
> **Target Production URL:** [https://flashcore-psi.vercel.app](https://flashcore-psi.vercel.app)  
> **API Base:** [https://database-management-system-s1g5.onrender.com/api](https://database-management-system-s1g5.onrender.com/api)  
> **Local Fallback:** Frontend `http://localhost:5173` | Backend `http://localhost:8000`  
> **Total Duration:** 15 Minutes (12 Minutes Walkthrough + 3 Minutes Q&A)  

---

## 1. PRE-DEMONSTRATION PREPARATION & ENVIRONMENT CHECKLIST (T - 10 Minutes)

Prior to the examiners arriving or joining the call, complete this verification checklist:

1. **Production Connectivity Check:**
   - Open browser and navigate to `https://database-management-system-s1g5.onrender.com/health`.
   - Verify response is `{"status": "healthy"}` (HTTP 200).
   - If Render container is asleep (free-tier spin-up), ping it 5 minutes early to warm the container.
2. **Frontend Liveness Check:**
   - Navigate to `https://flashcore-psi.vercel.app`. Confirm homepage renders cleanly.
3. **Local Fallback Ready:**
   - In terminal 1: Ensure backend virtual environment is ready (`backend\.venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000`).
   - In terminal 2: Ensure frontend dev server is standby (`npm run dev`).
4. **Browser Tabs Prepared in Advance:**
   - **Tab 1:** FLASHCORE Production App: `https://flashcore-psi.vercel.app`
   - **Tab 2:** Live Interactive OpenAPI Documentation: `https://database-management-system-s1g5.onrender.com/docs`
   - **Tab 3:** System Health JSON: `https://database-management-system-s1g5.onrender.com/api/health`
   - **Tab 4:** GitHub Repository: `https://github.com/manasaggarwal1107-ctrl/DATABASE-MANAGEMENT-SYSTEM`
5. **Terminal Window Ready for Concurrency Script:**
   - Open terminal in repository root, ready to run `python artifacts/concurrency_test_harness.py`.

---

## 2. TIMED DEMONSTRATION SCRIPT (15 MINUTES)

### PHASE 1: Introduction, Architecture & System Health (0:00 – 2:00)

- **Demonstrator Action:**
  - Share screen showing Tab 1 (`https://flashcore-psi.vercel.app`).
  - Highlight the green **System Status: Healthy** indicator in the top navbar.
  - Click on the **System Health** navigation link on the sidebar.
- **Examiner Talking Points:**
  - *"Good morning, respected examiners. Today I am demonstrating FLASHCORE, a full-stack platform addressing two critical challenges in modern retail: high-concurrency transactional integrity and deep exploratory sales analytics."*
  - *"Notice that our frontend is live on Vercel's global edge network, and our backend is running in a Docker container on Render PaaS."*
  - *"On this System Health dashboard, you can see real-time component telemetry: our FastAPI container is operational, and our managed PostgreSQL database is connected with sub-50ms ping times."*
  - *"Next, I will demonstrate our Role-Based Access Control and authentication architecture."*

---

### PHASE 2: Authentication, Session Management & RBAC Governance (2:00 – 4:30)

- **Demonstrator Action:**
  - Click **Sign Out** to show the login screen.
  - Show the self-service **Sign Up** tab: enter a test email `analyst_demo@retail.com` and password `Password123!`.
  - Log in as **Analyst**. Point out that the sidebar restricts access (Administration is hidden; Simulation write actions are disabled).
  - Log out and log in with the **Administrator** identity: `admin@flashcore.test` / `[ADMIN_PASSWORD]`.
  - Navigate to **Administration -> User Management**.
  - Show the user table: point out that password hashes are strictly omitted.
  - Click on the role dropdown for a user and demonstrate role promotion from `analyst` to `operator`.
  - Navigate to **Administration -> Audit Logs**.
  - Show the immutable audit trail: show that the role promotion event was logged with timestamp and user ID, and demonstrate that sensitive metadata is automatically sanitized to `[REDACTED]`.
- **Examiner Talking Points:**
  - *"Passwords are encrypted using Argon2id, providing memory-hard protection against GPU-accelerated cracking."*
  - *"Notice our RBAC matrix: Analysts have read-only access to historical analytics, Operators manage flash sales, and Administrators govern the platform."*
  - *"In the Audit Logs table, notice that every critical action is logged immutably. Furthermore, our automated secret scrubbing engine recursively strips passwords and tokens before writing to disk."*
  - *"When an administrator changes a user's role or status, our backend automatically revokes all active session tokens in `auth_sessions`, instantly terminating access across all user devices."*

---

### PHASE 3: Rossmann Historical Retail Analytics & Promotional Lift (4:30 – 7:30)

- **Demonstrator Action:**
  - Click on **Rossmann Stores** under the Analytics sidebar menu.
  - Filter stores by **Store Type: 'b'** (Extra assortment) and **Assortment: 'c'** (Extended).
  - Click on Store row #85 to open the detailed drawer: point out Competition Distance (meters) and Promo2 configuration.
  - Click on **Sales Explorer**.
  - Select Date Range: `2015-01-01` to `2015-06-30`. Select Store #1.
  - Show the KPI summary cards: Total Sales, Total Customers, Average Basket Size.
  - Hover over the daily revenue trend line chart, showing daily peaks and weekly seasonality.
  - Click on **Promotions Analysis**.
  - Point out the comparative bar chart: **Promo Days vs. Regular Days**.
  - Highlight the calculated metric: **Promotional Sales Lift (%)** and **Customer Footfall Lift (%)**.
- **Examiner Talking Points:**
  - *"FLASHCORE ingests and aggregates historical retail records across 1,115 pharmacy stores."*
  - *"In this view, the user can filter stores by physical assortment and competition proximity."*
  - *"In the Sales Explorer, notice the sub-70 millisecond query execution time. This is achieved through composite B-tree indexes on `(store_id, date)` in PostgreSQL, avoiding sequential table scans."*
  - *"Our Promotions Analysis calculates promotional lift on the fly, allowing category managers to immediately quantify whether a promotional campaign generated genuine incremental volume."*

---

### PHASE 4: Retail Simulation Provisioning & Flash Sale Scheduling (7:30 – 10:30)

- **Demonstrator Action:**
  - Navigate to **Simulation -> Simulation Runs**.
  - Click **New Simulation Run**. Enter Name: `Examiner Evaluation Drop 2026`. Click **Create**.
  - Navigate to **Simulation -> Product Catalog**.
  - Click **Add Product**. Enter SKU: `SKU-VIVA-101`, Name: `Advanced Pulse Oximeter Pro`. Click **Save Product**.
  - Navigate to **Simulation -> Store Inventory**.
  - Click **Allocate Stock**. Select Store: `1`, Product: `SKU-VIVA-101`, Physical Quantity: `100`. Click **Allocate**.
  - Demonstrate a stock adjustment: click **Adjust**, enter `quantity_delta = -5`, reason: `Quality control sample test`. Show physical stock decrementing from 100 to 95.
  - Navigate to **Simulation -> Flash Sales**.
  - Click **Schedule Flash Sale**. Title: `Exclusive 10-Unit Drop`. Select the simulation run.
  - Click **Add Product Quota**: select Store #1 inventory, set discounted Sale Price: `$19.99`, Stock Limit: `10` units.
  - Click **Activate Flash Sale**. Point out status badge changes from yellow `Draft` to green `Active`.
- **Examiner Talking Points:**
  - *"Now we enter our transactional simulation engine."*
  - *"Notice the separation between physical inventory and flash sale quotas. In `inventory`, physical quantity is 95, but we have reserved exactly 10 units for this flash sale drop."*
  - *"Our database check constraint `CHECK (physical_quantity >= reserved_quantity)` ensures physical stock cannot drop below reserved quota."*
  - *"Now we have an active flash sale offering exactly 10 units of SKU-VIVA-101."*

---

### PHASE 5: High-Concurrency Flash Sale Execution & Idempotency Proof (10:30 – 13:30)

- **Demonstrator Action:**
  - Switch to the open terminal window.
  - Execute the live high-concurrency test harness:
    ```bash
    python artifacts/concurrency_test_harness.py
    ```
  - Direct examiners' attention to the terminal output:
    - **Scenario A Output:** 50 concurrent requests competing for 10 units. Show that **exactly 10 succeeded** and **exactly 40 rejected**.
    - **Scenario B Output:** 20 duplicate requests with identical idempotency key. Show that **exactly 1 succeeded**, 19 returned duplicate, and stock decremented **exactly once**.
  - Switch back to the browser: navigate to **Simulation -> Transactions**.
  - Point out the real-time transaction feed showing green `success` badges and red `rejected` badges with reason `"Flash sale stock limit exceeded"`.
  - Point out that the product's sold count is exactly `10 / 10` (Sold Out).
- **Examiner Talking Points:**
  - *"Respected examiners, this is the core technical contribution of FLASHCORE."*
  - *"In Scenario A, we launched 50 concurrent threads simultaneously targeting 10 units. Under standard relational systems, overselling occurs because threads read stock before others commit."*
  - *"In FLASHCORE, our `SELECT ... FOR UPDATE` row lock queues incoming requests at the PostgreSQL kernel level. Exactly 10 requests acquired the lock, purchased stock, and committed. The remaining 40 read the updated counter and were rejected cleanly. Overselling was exactly zero."*
  - *"In Scenario B, 20 threads submitted the identical idempotency key simultaneously. Our savepoint rollback mechanism caught the racing insert at the unique constraint level, rolled back cleanly, and returned the winning attempt without double-charging or crashing with HTTP 500."*

---

### PHASE 6: Disaster Recovery, Summary & Q&A Transition (13:30 – 15:00)

- **Demonstrator Action:**
  - Open Tab 2 showing interactive OpenAPI documentation (`/docs`), demonstrating 42 registered paths.
  - Display the Disaster Recovery verification metrics:
    - RTO: **0.225 seconds** (< 2.0s target).
    - RPO: **0.266 seconds** snapshot capability.
    - Record Parity: **100% across all 14 tables**.
  - Conclude demonstration and open floor for viva questions.
- **Examiner Talking Points:**
  - *"To summarize, FLASHCORE provides: mathematical concurrency safety with zero overselling, unified retail analytics over 1,115 stores, 100% test coverage across 144 backend and 124 frontend tests, and sub-second disaster recovery."*
  - *"Thank you for your attention. I am now delighted to take your questions and defend the project."*

---

## 3. CONTINGENCY & FALLBACK RUNBOOKS

### Contingency 1: Render Cold Start / Latency Spike
- **Symptom:** API requests take > 5 seconds on initial load due to container spin-up.
- **Action:** Explain immediately to examiners: *"Render free-tier instances sleep after 15 minutes of inactivity; the container is currently spinning up."* If it takes longer than 15 seconds, switch browser to the local frontend (`http://localhost:5173`) running against the local backend (`http://localhost:8000`).

### Contingency 2: Internet / WiFi Connection Drop
- **Action:** Transition seamlessly to the pre-started local environment:
  - Open browser tab: `http://localhost:5173`.
  - Show that the entire platform runs locally with complete parity against local PostgreSQL database `flashcore_test`.

### Contingency 3: Database Contention / Lock Wait During Live Demo
- **Action:** Show the audit log table (`/api/admin/audit-logs`) to demonstrate that the transaction engine handled the event gracefully without unhandled exceptions.

---
*End of FLASHCORE Live Demonstration Script.*
