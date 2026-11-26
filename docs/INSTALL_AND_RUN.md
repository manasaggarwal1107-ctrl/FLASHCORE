# FLASHCORE — Installation, Execution & Evaluation Guide
## Step-by-Step Developer Setup, Database Initialization & Automated Verification

> **Student:** Manas Aggarwal (Roll No. 2501730302)  
> **Course / Programme:** B.Tech CSE (AI/ML), 3rd Semester, Section A  
> **Supervisor:** Ms. Mansi Kajal, Assistant Professor, SOET, K.R. Mangalam University  
> **Target OS:** Windows 10/11 / Ubuntu Linux 22.04+ / macOS Sequoia  

---

## 1. System Prerequisites

Before starting, verify the host machine meets the minimum system dependencies:

| Tool / Runtime | Minimum Version | Verified Version | Purpose |
| :--- | :---: | :---: | :--- |
| **Python** | 3.11+ | 3.13.0 | FastAPI ASGI Backend, SQLAlchemy ORM, Pytest |
| **Node.js** | 18.0+ | 20.18.0 / 22.x | Vite 5, React 18, Vitest, Tailwind CSS |
| **npm** | 9.0+ | 10.8.2 | Package Management |
| **PostgreSQL** | 15.0+ | 16.3 / Neon Serverless | Relational Database with ACID Isolation |
| **Git** | 2.30+ | 2.45+ | Version Control |

---

## 2. Repository Cloning & Structure

```bash
git clone https://github.com/manasaggarwal1107-ctrl/DATABASE-MANAGEMENT-SYSTEM.git
cd DATABASE-MANAGEMENT-SYSTEM/CAPSTONE/FLASHCORE-FRESH
```

### Directory Layout
```text
FLASHCORE-FRESH/
├── backend/                  # FastAPI Application Root
│   ├── app/                  # Application modules (routes, models, core, schemas)
│   ├── tests/                # 144 pytest unit & integration tests
│   ├── .env                  # Backend environment secrets (DB, JWT)
│   └── requirements.txt      # Pinned Python dependencies
├── frontend/                 # React 18 / Vite 5 Application Root
│   ├── src/                  # React components, pages, hooks, state
│   ├── dist/                 # Prebuilt production assets
│   ├── package.json          # Frontend dependencies & test scripts
│   └── vite.config.ts        # Bundler configuration
├── database/                 # DDL, Migrations & Schema SQL files
├── docs/                     # Full Technical Documentation Portfolio
└── artifacts/                # Benchmark outputs, audit reports & verification results
```

---

## 3. Backend Setup & Local Server Execution

### Step 3.1: Virtual Environment Configuration
```bash
cd backend
python -m venv .venv

# On Windows:
.venv\Scripts\activate

# On Linux/macOS:
source .venv/bin/activate
```

### Step 3.2: Dependency Installation
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3.3: Environment Configuration (`backend/.env`)
Create or verify `backend/.env` containing your database connection string and JWT secret:
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=flashcore_db
DB_USER=postgres
DB_PASSWORD=your_secure_password
JWT_SECRET_KEY=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
JWT_ACCESS_TOKEN_MINUTES=120
```

### Step 3.4: Database Schema Initialization & Seeding
```bash
# Execute DDL schema against your database
python -c "
import asyncio
from app.core.database import engine, Base
import app.models
async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
asyncio.run(init())
print('Database tables created successfully.')
"
```

### Step 3.5: Run the Backend ASGI Server
```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
- API Root: `http://127.0.0.1:8000`
- Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`
- Redoc Documentation: `http://127.0.0.1:8000/redoc`

---

## 4. Frontend Setup & Execution

### Step 4.1: Install Dependencies
Open a second terminal window:
```bash
cd frontend
npm install
```

### Step 4.2: Development Server Execution
```bash
npm run dev
```
Opens: `http://localhost:5173`.

### Step 4.3: Production Build & Preview
```bash
npm run build
npm run preview
```

---

## 5. Automated Verification & Test Execution

### 5.1 Run Backend Pytest Suite (144 Tests)
```bash
cd backend
pytest tests/ -v
```
Expected output: `144 passed in ~4.5s`.

### 5.2 Run Frontend Vitest Suite (124 Tests)
```bash
cd frontend
npm run test
```
Expected output: `124 passed in ~3.8s`.

### 5.3 Run Concurrency Simulation Stress Test
```bash
python artifacts/concurrency_test_harness.py
```
Validates zero overselling under 100 concurrent checkout threads.
