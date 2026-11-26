# FLASHCORE — Architectural & Flow Diagrams Repository
## High-Resolution Raster (PNG), Vector (SVG) & Editable Source (Mermaid) Catalog

> **Student:** Manas Aggarwal (Roll No. 2501730302)  
> **Course / Programme:** B.Tech CSE (AI/ML), 3rd Semester, Section A  
> **Supervisor:** Ms. Mansi Kajal, Assistant Professor, SOET, K.R. Mangalam University  

---

## Directory Organization

- **`mermaid/`**: Complete editable source code (`.mmd`) for all 19 system diagrams.
- **`png/`**: High-resolution raster images (rendered at 2x scale with white background) for formal reports and slide decks.
- **`svg/`**: Scalable vector graphics versions for loss-free zoom and high-fidelity printing.

---

## Complete Diagram Inventory

| Fig # | Diagram Title | Source (.mmd) | Raster (.png) | Vector (.svg) | Purpose & Description |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **01** | System Architecture | [`fig_01...mmd`](mermaid/fig_01_system_architecture.mmd) | [`fig_01...png`](png/fig_01_system_architecture.png) | [`fig_01...svg`](svg/fig_01_system_architecture.svg) | 3-tier system architecture: Client, FastAPI ASGI, PostgreSQL. |
| **02** | Component Architecture | [`fig_02...mmd`](mermaid/fig_02_component_architecture.mmd) | [`fig_02...png`](png/fig_02_component_architecture.png) | [`fig_02...svg`](svg/fig_02_component_architecture.svg) | Internal module interactions between frontend and backend services. |
| **03** | DFD Level 0 (Context) | [`fig_03...mmd`](mermaid/fig_03_dfd_level_0.mmd) | [`fig_03...png`](png/fig_03_dfd_level_0.png) | [`fig_03...svg`](svg/fig_03_dfd_level_0.svg) | High-level data flow diagram showing external entities and data stores. |
| **04** | DFD Level 1 (Functional) | [`fig_04...mmd`](mermaid/fig_04_dfd_level_1.mmd) | [`fig_04...png`](png/fig_04_dfd_level_1.png) | [`fig_04...svg`](svg/fig_04_dfd_level_1.svg) | Decomposition into 6 core functional processes. |
| **05** | DFD Level 2 (Transactions) | [`fig_05...mmd`](mermaid/fig_05_dfd_level_2.mmd) | [`fig_05...png`](png/fig_05_dfd_level_2.png) | [`fig_05...svg`](svg/fig_05_dfd_level_2.svg) | Low-level process flow of purchase transactions and lock acquisition. |
| **06** | Database ER Diagram | [`fig_06...mmd`](mermaid/fig_06_database_er_diagram.mmd) | [`fig_06...png`](png/fig_06_database_er_diagram.png) | [`fig_06...svg`](svg/fig_06_database_er_diagram.svg) | Entity-Relationship diagram for all 14 relational database tables. |
| **07** | Authentication Flow | [`fig_07...mmd`](mermaid/fig_07_auth_flow.mmd) | [`fig_07...png`](png/fig_07_auth_flow.png) | [`fig_07...svg`](svg/fig_07_auth_flow.svg) | Sequence diagram of Argon2id validation and RFC 7519 JWT lifecycle. |
| **08** | RBAC Architecture | [`fig_08...mmd`](mermaid/fig_08_rbac_architecture.mmd) | [`fig_08...png`](png/fig_08_rbac_architecture.png) | [`fig_08...svg`](svg/fig_08_rbac_architecture.svg) | Role-Based Access Control matrix mapping roles to system capabilities. |
| **09** | API Architecture | [`fig_09...mmd`](mermaid/fig_09_api_architecture.mmd) | [`fig_09...png`](png/fig_09_api_architecture.png) | [`fig_09...svg`](svg/fig_09_api_architecture.svg) | Request middleware pipeline: CORS, Logging, Auth Guard, Validation. |
| **10** | Data Import Workflow | [`fig_10...mmd`](mermaid/fig_10_data_import_workflow.mmd) | [`fig_10...png`](png/fig_10_data_import_workflow.png) | [`fig_10...svg`](svg/fig_10_data_import_workflow.svg) | Rossmann retail CSV batch ingestion and validation pipeline. |
| **11** | Inventory Lifecycle | [`fig_11...mmd`](mermaid/fig_11_inventory_transaction_lifecycle.mmd) | [`fig_11...png`](png/fig_11_inventory_transaction_lifecycle.png) | [`fig_11...svg`](svg/fig_11_inventory_transaction_lifecycle.svg) | State transitions of inventory units under row-level locks. |
| **12** | Purchase Lifecycle | [`fig_12...mmd`](mermaid/fig_12_purchase_lifecycle.mmd) | [`fig_12...png`](png/fig_12_purchase_lifecycle.png) | [`fig_12...svg`](svg/fig_12_purchase_lifecycle.svg) | Sequence diagram of order placement, inventory check, and ledger commit. |
| **13** | Flash-Sale Concurrency | [`fig_13...mmd`](mermaid/fig_13_flash_sale_concurrency_workflow.mmd) | [`fig_13...png`](png/fig_13_flash_sale_concurrency_workflow.png) | [`fig_13...svg`](svg/fig_13_flash_sale_concurrency_workflow.svg) | Burst concurrency workflow modeling 500 parallel checkout workers. |
| **14** | Idempotency Handling | [`fig_14...mmd`](mermaid/fig_14_idempotency_handling.mmd) | [`fig_14...png`](png/fig_14_idempotency_handling.png) | [`fig_14...svg`](svg/fig_14_idempotency_handling.svg) | Deterministic replay of duplicate requests using Idempotency-Key. |
| **15** | Overselling Prevention | [`fig_15...mmd`](mermaid/fig_15_overselling_prevention.mmd) | [`fig_15...png`](png/fig_15_overselling_prevention.png) | [`fig_15...svg`](svg/fig_15_overselling_prevention.svg) | Three-layer defense architecture preventing negative inventory. |
| **16** | Audit Logging | [`fig_16...mmd`](mermaid/fig_16_audit_logging.mmd) | [`fig_16...png`](png/fig_16_audit_logging.png) | [`fig_16...svg`](svg/fig_16_audit_logging.svg) | Event interception and immutable audit trail persistence. |
| **17** | Backup & Recovery | [`fig_17...mmd`](mermaid/fig_17_backup_recovery.mmd) | [`fig_17...png`](png/fig_17_backup_recovery.png) | [`fig_17...svg`](svg/fig_17_backup_recovery.svg) | Disaster recovery, WAL archiving, and point-in-time recovery workflow. |
| **18** | Deployment Architecture | [`fig_18...mmd`](mermaid/fig_18_deployment_architecture.mmd) | [`fig_18...png`](png/fig_18_deployment_architecture.png) | [`fig_18...svg`](svg/fig_18_deployment_architecture.svg) | Cloud production architecture across Vercel, Render, and Neon DB. |
| **19** | Testing Architecture | [`fig_19...mmd`](mermaid/fig_19_testing_architecture.mmd) | [`fig_19...png`](png/fig_19_testing_architecture.png) | [`fig_19...svg`](svg/fig_19_testing_architecture.svg) | Quality assurance pyramid: 144 backend tests + 124 frontend tests. |

---

## Re-rendering Instructions

To re-render all diagrams to PNG and SVG:

```bash
# Render a single diagram to PNG
npx @mermaid-js/mermaid-cli -i mermaid/fig_01_system_architecture.mmd -o png/fig_01_system_architecture.png -b white -s 2

# Render a single diagram to SVG
npx @mermaid-js/mermaid-cli -i mermaid/fig_01_system_architecture.mmd -o svg/fig_01_system_architecture.svg
```
