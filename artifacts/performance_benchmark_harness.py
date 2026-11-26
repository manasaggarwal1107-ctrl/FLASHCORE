import os
import sys
import time
import uuid
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

os.environ["DB_NAME"] = "flashcore_test"
sys.path.insert(0, "backend")

from fastapi.testclient import TestClient
from main import app
from app.core.database import engine
from sqlalchemy import text
from app.core.security import create_access_token

print("=" * 80)
print("FLASHCORE STAGE 3 — PERFORMANCE & LOAD BENCHMARKING HARNESS")
print("Target Database: flashcore_test (Local Isolated PostgreSQL)")
print("=" * 80)

# 1. Setup Admin and Analyst Users
with engine.begin() as conn:
    conn.execute(text("TRUNCATE TABLE users, auth_sessions, simulation_runs, simulation_products, simulation_inventory, flash_sales, flash_sale_products, purchase_attempts, transactions_log, audit_logs, daily_store_sales, dataset_imports, stores RESTART IDENTITY CASCADE"))
    admin_id = conn.execute(text("""
        INSERT INTO users (email, password_hash, role, status)
        VALUES ('admin_perf@flashcore.test', '$2b$12$dummyhashforperftestingonly1234567890123456', 'admin', 'active')
        RETURNING id
    """)).scalar_one()

    imp_id = conn.execute(text("""
        INSERT INTO dataset_imports (source_name, source_file, source_split, total_rows, successful_rows, rejected_rows, status)
        VALUES ('Rossmann Benchmark Dataset', 'train.csv', 'train', 200, 200, 0, 'completed')
        RETURNING id
    """)).scalar_one()

    # Seed 50 stores and 200 sales records for analytics benchmarks
    for s_id in range(1, 51):
        conn.execute(text("""
            INSERT INTO stores (store_id, store_type, assortment, competition_distance)
            VALUES (:id, 'a', 'b', 750)
        """), {"id": s_id})
        for day in range(1, 5):
            conn.execute(text("""
                INSERT INTO daily_store_sales
                    (store_id, sales_date, day_of_week, sales, customers, is_open, promo, state_holiday, school_holiday, import_id)
                VALUES
                    (:id, :s_date, :dow, :sales, :cust, TRUE, :promo, '0', FALSE, :imp_id)
            """), {
                "id": s_id,
                "s_date": f"2026-01-0{day}",
                "dow": day,
                "sales": 5420.50 + s_id * 10,
                "cust": 550 + s_id * 2,
                "promo": (day % 2 == 0),
                "imp_id": imp_id,
            })

jti = uuid.uuid4()
now = datetime.now(timezone.utc)
exp = now + timedelta(hours=3)
with engine.begin() as conn:
    conn.execute(text("""
        INSERT INTO auth_sessions (jti, user_id, expires_at)
        VALUES (:jti, :user_id, :exp)
    """), {"jti": jti, "user_id": admin_id, "exp": exp})

admin_token, _ = create_access_token(admin_id, jti)
auth_headers = {"Authorization": f"Bearer {admin_token}"}
setup_client = TestClient(app, headers=auth_headers)

# Create a flash sale for purchase benchmark
run_id = setup_client.post("/api/simulations/runs", json={
    "run_name": "Perf Benchmarking Run",
    "description": "Load test simulation",
    "configuration": {},
}).json()["id"]

prod_id = setup_client.post("/api/simulations/products", json={
    "sku": "PERF-PROD-001",
    "name": "Benchmark Widget",
}).json()["id"]

inv_id = setup_client.post("/api/simulations/inventory", json={
    "store_id": 1,
    "product_id": prod_id,
    "quantity": 5000,
}).json()["id"]

sale_id = setup_client.post(f"/api/simulations/runs/{run_id}/flash-sales", json={
    "title": "Perf Sale",
    "starts_at": (now - timedelta(hours=1)).isoformat(),
    "ends_at": (now + timedelta(hours=5)).isoformat(),
}).json()["id"]
setup_client.post(f"/api/simulations/flash-sales/{sale_id}/activate")

alloc_id = setup_client.post(f"/api/simulations/flash-sales/{sale_id}/products", json={
    "inventory_id": inv_id,
    "sale_price": "19.99",
    "stock_limit": 2000,
}).json()["id"]

print("Seeded test dataset: 50 stores, 200 sales records, flash sale product ready.")

def calculate_percentiles(latencies_ms):
    if not latencies_ms:
        return 0, 0, 0, 0, 0, 0
    s = sorted(latencies_ms)
    n = len(s)
    p50 = s[int(n * 0.50)]
    p95 = s[min(int(n * 0.95), n - 1)]
    p99 = s[min(int(n * 0.99), n - 1)]
    mean_val = statistics.mean(s)
    min_val = min(s)
    max_val = max(s)
    return p50, p95, p99, mean_val, min_val, max_val

def run_endpoint_benchmark(name, request_fn, total_requests=100, concurrency=10):
    latencies = []
    status_codes = []

    t_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(lambda i: request_fn(i), range(total_requests)))
    total_time = time.perf_counter() - t_start

    for status, lat in results:
        status_codes.append(status)
        latencies.append(lat)

    rps = total_requests / total_time
    err_count = sum(1 for s in status_codes if s >= 500)
    err_rate = (err_count / total_requests) * 100
    p50, p95, p99, mean_val, min_val, max_val = calculate_percentiles(latencies)

    print(f"\nBenchmark: {name}")
    print(f"Requests: {total_requests} | Concurrency: {concurrency} | Total Time: {total_time:.3f}s | Throughput: {rps:.1f} req/s")
    print(f"Latency (ms): p50={p50:.2f}ms | p95={p95:.2f}ms | p99={p99:.2f}ms | Mean={mean_val:.2f}ms | Max={max_val:.2f}ms")
    print(f"Errors (>=500): {err_count} ({err_rate:.1f}%)")

    return {
        "name": name,
        "requests": total_requests,
        "concurrency": concurrency,
        "rps": round(rps, 1),
        "p50": round(p50, 2),
        "p95": round(p95, 2),
        "p99": round(p99, 2),
        "mean": round(mean_val, 2),
        "max": round(max_val, 2),
        "error_rate": round(err_rate, 2),
    }

benchmarks_data = []

# Benchmark 1: Public Health API (GET /api/health)
def req_health(i):
    t0 = time.perf_counter()
    with TestClient(app) as c:
        resp = c.get("/api/health")
    lat = (time.perf_counter() - t0) * 1000
    return resp.status_code, lat

benchmarks_data.append(run_endpoint_benchmark("GET /api/health (Public Health)", req_health, total_requests=100, concurrency=10))

# Benchmark 2: Public Strategies API (GET /api/simulations/strategies)
def req_strategies(i):
    t0 = time.perf_counter()
    with TestClient(app) as c:
        resp = c.get("/api/simulations/strategies")
    lat = (time.perf_counter() - t0) * 1000
    return resp.status_code, lat

benchmarks_data.append(run_endpoint_benchmark("GET /api/simulations/strategies", req_strategies, total_requests=100, concurrency=10))

# Benchmark 3: Rossmann Sales Summary (GET /api/rossmann/sales/summary) - Complex Aggregation
def req_sales_summary(i):
    t0 = time.perf_counter()
    with TestClient(app, headers=auth_headers) as c:
        resp = c.get("/api/rossmann/sales/summary")
    lat = (time.perf_counter() - t0) * 1000
    return resp.status_code, lat

benchmarks_data.append(run_endpoint_benchmark("GET /api/rossmann/sales/summary (Analytics Aggregation)", req_sales_summary, total_requests=100, concurrency=10))

# Benchmark 4: Rossmann Stores Listing (GET /api/rossmann/stores?limit=50)
def req_stores(i):
    t0 = time.perf_counter()
    with TestClient(app, headers=auth_headers) as c:
        resp = c.get("/api/rossmann/stores?limit=50")
    lat = (time.perf_counter() - t0) * 1000
    return resp.status_code, lat

benchmarks_data.append(run_endpoint_benchmark("GET /api/rossmann/stores?limit=50", req_stores, total_requests=100, concurrency=10))

# Benchmark 5: Flash Sale Purchase with Pessimistic Locking (POST /api/simulations/flash-sale-products/{id}/purchase)
def req_purchase(i):
    payload = {
        "customer_ref": f"PERF-CUST-{i}",
        "idempotency_key": f"PERF-KEY-{i}-{uuid.uuid4()}",
        "quantity": 1,
    }
    t0 = time.perf_counter()
    with TestClient(app, headers=auth_headers) as c:
        resp = c.post(f"/api/simulations/flash-sale-products/{alloc_id}/purchase", json=payload)
    lat = (time.perf_counter() - t0) * 1000
    return resp.status_code, lat

benchmarks_data.append(run_endpoint_benchmark("POST .../purchase (Transactional Row-Locking)", req_purchase, total_requests=100, concurrency=20))

# Benchmark 6: High Contention Purchase Burst (Tier 3: 50 concurrent threads)
benchmarks_data.append(run_endpoint_benchmark("POST .../purchase (Elevated Contention: 50 Threads)", req_purchase, total_requests=150, concurrency=50))

print("\n" + "=" * 80)
print(f"{'Endpoint / Workload':<48} {'Conc':<6} {'RPS':<8} {'p50(ms)':<9} {'p95(ms)':<9} {'p99(ms)':<9} {'Err%':<6}")
print("=" * 80)
for b in benchmarks_data:
    print(f"{b['name']:<48} {b['concurrency']:<6} {b['rps']:<8} {b['p50']:<9} {b['p95']:<9} {b['p99']:<9} {b['error_rate']:<6}")
print("=" * 80)
