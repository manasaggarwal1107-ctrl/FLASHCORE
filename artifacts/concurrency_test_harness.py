import os
import sys
import uuid
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
print("FLASHCORE STAGE 3 — HIGH-CONCURRENCY & RACE-CONDITION TEST HARNESS")
print("Target Database: flashcore_test (Local Isolated PostgreSQL)")
print("=" * 80)

# 1. Setup operator and seed stores
with engine.begin() as conn:
    conn.execute(text("TRUNCATE TABLE users, auth_sessions, simulation_runs, simulation_products, simulation_inventory, flash_sales, flash_sale_products, purchase_attempts, transactions_log, audit_logs RESTART IDENTITY CASCADE"))
    conn.execute(text("""
        INSERT INTO stores (store_id, store_type, assortment, competition_distance)
        VALUES (101, 'a', 'a', 500), (102, 'b', 'b', 1000)
        ON CONFLICT (store_id) DO NOTHING
    """))
    operator_id = conn.execute(text("""
        INSERT INTO users (email, password_hash, role, status)
        VALUES ('operator_concurrency@flashcore.test', '$2b$12$dummyhashforconcurrencytestingonly1234567890123456', 'operator', 'active')
        RETURNING id
    """)).scalar_one()

jti = uuid.uuid4()
now = datetime.now(timezone.utc)
exp = now + timedelta(hours=2)
with engine.begin() as conn:
    conn.execute(text("""
        INSERT INTO auth_sessions (jti, user_id, expires_at)
        VALUES (:jti, :user_id, :exp)
    """), {"jti": jti, "user_id": operator_id, "exp": exp})

token, _ = create_access_token(operator_id, jti)
headers = {"Authorization": f"Bearer {token}"}
setup_client = TestClient(app, headers=headers)

def setup_flash_sale_via_api(stock_limit=10, initial_qty=100, store_id=101):
    run_resp = setup_client.post("/api/simulations/runs", json={
        "run_name": f"Concurrency Run {uuid.uuid4().hex[:6]}",
        "description": "High concurrency test",
        "configuration": {},
    })
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]

    prod_resp = setup_client.post("/api/simulations/products", json={
        "sku": f"CONCUR-{uuid.uuid4().hex[:8]}",
        "name": "Concurrency Test Product",
    })
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["id"]

    inv_resp = setup_client.post("/api/simulations/inventory", json={
        "store_id": store_id,
        "product_id": prod_id,
        "quantity": initial_qty,
    })
    assert inv_resp.status_code == 201
    inv_id = inv_resp.json()["id"]

    sale_resp = setup_client.post(f"/api/simulations/runs/{run_id}/flash-sales", json={
        "title": "High Load Flash Sale",
        "starts_at": (now - timedelta(hours=1)).isoformat(),
        "ends_at": (now + timedelta(hours=2)).isoformat(),
    })
    assert sale_resp.status_code == 201
    sale_id = sale_resp.json()["id"]

    act_resp = setup_client.post(f"/api/simulations/flash-sales/{sale_id}/activate")
    assert act_resp.status_code == 200

    alloc_resp = setup_client.post(f"/api/simulations/flash-sales/{sale_id}/products", json={
        "inventory_id": inv_id,
        "sale_price": "29.99",
        "stock_limit": stock_limit,
    })
    assert alloc_resp.status_code == 201
    sp_id = alloc_resp.json()["id"]

    return {
        "run_id": run_id,
        "product_id": prod_id,
        "inv_id": inv_id,
        "sale_id": sale_id,
        "sale_product_id": sp_id,
        "stock_limit": stock_limit,
        "initial_qty": initial_qty,
    }

# =========================================================================
# SCENARIO A: 50 Concurrent Purchase Attempts on 10 Units of Stock (Overselling)
# =========================================================================
print("\n--- Running Scenario A: 50 Concurrent Purchase Attempts on 10 Stock Units ---")
setup_a = setup_flash_sale_via_api(stock_limit=10, initial_qty=100)
sp_id_a = setup_a["sale_product_id"]

def attempt_a(idx):
    payload = {
        "customer_ref": f"CUST-A-{idx}",
        "idempotency_key": f"IDEMP-A-{idx}-{uuid.uuid4()}",
        "quantity": 1,
    }
    with TestClient(app, headers=headers) as c:
        return c.post(f"/api/simulations/flash-sale-products/{sp_id_a}/purchase", json=payload).json()

with ThreadPoolExecutor(max_workers=50) as pool:
    responses_a = list(pool.map(attempt_a, range(50)))

success_a = [r for r in responses_a if r.get("success") is True]
rejected_a = [r for r in responses_a if r.get("success") is False]

with engine.begin() as conn:
    inv_a = conn.execute(text("SELECT quantity, reserved_quantity FROM simulation_inventory WHERE id = :id"), {"id": setup_a["inv_id"]}).mappings().one()
    sp_a = conn.execute(text("SELECT sold_quantity, stock_limit FROM flash_sale_products WHERE id = :id"), {"id": sp_id_a}).mappings().one()
    attempts_a = conn.execute(text("SELECT COUNT(*) FROM purchase_attempts WHERE flash_sale_product_id = :id"), {"id": sp_id_a}).scalar_one()

print(f"Total Requests: 50 | Successful: {len(success_a)} | Rejected: {len(rejected_a)}")
print(f"Flash Sale Product Sold: {sp_a['sold_quantity']} / {sp_a['stock_limit']}")
print(f"Inventory Quantity: {inv_a['quantity']} (Expected 90) | Reserved: {inv_a['reserved_quantity']} (Expected 0)")
print(f"Purchase Attempts Recorded: {attempts_a} (Expected 50)")

assert len(success_a) == 10, f"Expected 10 successes, got {len(success_a)}"
assert len(rejected_a) == 40, f"Expected 40 rejections, got {len(rejected_a)}"
assert sp_a["sold_quantity"] == 10, f"Expected sold 10, got {sp_a['sold_quantity']}"
assert inv_a["reserved_quantity"] == 0, f"Expected 0 reserved, got {inv_a['reserved_quantity']}"
assert inv_a["quantity"] == 90, f"Expected 90, got {inv_a['quantity']}"
assert attempts_a == 50, f"Expected 50, got {attempts_a}"
print(">>> SCENARIO A: PASSED — ZERO OVERSELLING OCCURRED <<<")

# =========================================================================
# SCENARIO B: 20 Concurrent Requests with Identical Idempotency Key
# =========================================================================
print("\n--- Running Scenario B: 20 Simultaneous Duplicate Requests with Identical Idempotency Key ---")
setup_b = setup_flash_sale_via_api(stock_limit=10, initial_qty=100)
sp_id_b = setup_b["sale_product_id"]
shared_key = f"SHARED-IDEMP-KEY-{uuid.uuid4()}"
customer_b = "CUSTOMER-SCENARIO-B"

def duplicate_attempt_b(idx):
    payload = {
        "customer_ref": customer_b,
        "idempotency_key": shared_key,
        "quantity": 1,
    }
    with TestClient(app, headers=headers) as c:
        return c.post(f"/api/simulations/flash-sale-products/{sp_id_b}/purchase", json=payload).json()

with ThreadPoolExecutor(max_workers=20) as pool:
    responses_b = list(pool.map(duplicate_attempt_b, range(20)))

first_success_b = [r for r in responses_b if r.get("success") is True and not r.get("duplicate")]
duplicates_b = [r for r in responses_b if r.get("duplicate") is True]

with engine.begin() as conn:
    inv_b = conn.execute(text("SELECT quantity, reserved_quantity FROM simulation_inventory WHERE id = :id"), {"id": setup_b["inv_id"]}).mappings().one()
    sp_b = conn.execute(text("SELECT sold_quantity FROM flash_sale_products WHERE id = :id"), {"id": sp_id_b}).mappings().one()
    attempts_b = conn.execute(text("SELECT id, idempotency_key, status FROM purchase_attempts WHERE flash_sale_product_id = :id"), {"id": sp_id_b}).mappings().all()

print(f"Total Requests: 20 | First Success: {len(first_success_b)} | Duplicates Returned: {len(duplicates_b)}")
print(f"Flash Sale Product Sold: {sp_b['sold_quantity']} (Expected 1)")
print(f"Inventory Quantity: {inv_b['quantity']} (Expected 99) | Reserved: {inv_b['reserved_quantity']} (Expected 9)")
print(f"Purchase Attempts Recorded in DB: {len(attempts_b)} (Expected exactly 1)")

assert len(attempts_b) == 1, f"Expected exactly 1 attempt in DB, found {len(attempts_b)}"
assert sp_b["sold_quantity"] == 1, f"Expected 1 sold, got {sp_b['sold_quantity']}"
assert len(first_success_b) == 1, f"Expected 1 first success, got {len(first_success_b)}"
assert len(duplicates_b) == 19, f"Expected 19 duplicates, got {len(duplicates_b)}"
print(">>> SCENARIO B: PASSED — EXACTLY 1 TRANSACTION RECORDED, 0 DUPLICATE DECREMENTS <<<")

# =========================================================================
# SCENARIO C: 20 Concurrent Stock Adjustments (Atomic Stock Operations)
# =========================================================================
print("\n--- Running Scenario C: 20 Concurrent Stock Adjustments of Delta = -1 ---")
prod_c = setup_client.post("/api/simulations/products", json={
    "sku": f"CONCUR-C-{uuid.uuid4().hex[:8]}",
    "name": "Widget C",
}).json()
inv_c_resp = setup_client.post("/api/simulations/inventory", json={
    "store_id": 101,
    "product_id": prod_c["id"],
    "quantity": 50,
})
assert inv_c_resp.status_code == 201
inv_c_id = inv_c_resp.json()["id"]

def adjust_stock_c(idx):
    payload = {
        "quantity_delta": -1,
        "reason": f"Concurrent adjustment test step {idx}",
    }
    with TestClient(app, headers=headers) as c:
        return c.post(f"/api/simulations/inventory/{inv_c_id}/adjust", json=payload).status_code

with ThreadPoolExecutor(max_workers=20) as pool:
    status_codes_c = list(pool.map(adjust_stock_c, range(20)))

with engine.begin() as conn:
    inv_c = conn.execute(text("SELECT quantity FROM simulation_inventory WHERE id = :id"), {"id": inv_c_id}).scalar_one()

print(f"Total Adjustment Calls: 20 | All Status 200: {all(s == 200 for s in status_codes_c)}")
print(f"Final Inventory Quantity: {inv_c} (Initial 50 - 20 = Expected 30)")

assert all(s == 200 for s in status_codes_c)
assert inv_c == 30, f"Expected 30, got {inv_c}"
print(">>> SCENARIO C: PASSED — ZERO LOST UPDATES, EXACT ATOMIC DECREMENTS <<<")

# =========================================================================
# SCENARIO D: Same Customer Submitting 10 Concurrent Purchases (1 per customer limit)
# =========================================================================
print("\n--- Running Scenario D: Same Customer Submitting 10 Concurrent Purchases ---")
setup_d = setup_flash_sale_via_api(stock_limit=10, initial_qty=100)
sp_id_d = setup_d["sale_product_id"]
single_customer = "EXCLUSIVE-CUSTOMER-SCENARIO-D"

def purchase_attempt_d(idx):
    payload = {
        "customer_ref": single_customer,
        "idempotency_key": f"DIFF-KEY-D-{idx}-{uuid.uuid4()}",
        "quantity": 1,
    }
    with TestClient(app, headers=headers) as c:
        return c.post(f"/api/simulations/flash-sale-products/{sp_id_d}/purchase", json=payload).json()

with ThreadPoolExecutor(max_workers=10) as pool:
    responses_d = list(pool.map(purchase_attempt_d, range(10)))

success_d = [r for r in responses_d if r.get("success") is True]
rejected_d = [r for r in responses_d if r.get("success") is False]

print(f"Total Requests: 10 | Successful: {len(success_d)} | Rejected: {len(rejected_d)}")
print(f"Rejection Sample Message: {rejected_d[0].get('message')}")

assert len(success_d) == 1, f"Expected 1 success, got {len(success_d)}"
assert len(rejected_d) == 9, f"Expected 9 rejections, got {len(rejected_d)}"
print(">>> SCENARIO D: PASSED — EXACTLY 1 PURCHASE ALLOWED PER CUSTOMER <<<")

# =========================================================================
# SCENARIO E: Multi-Product Interleaved Purchases (Deadlock Prevention)
# =========================================================================
print("\n--- Running Scenario E: Multi-Product Interleaved Concurrent Purchases ---")
setup_e = setup_flash_sale_via_api(stock_limit=15, initial_qty=100)
sp_id_e1 = setup_e["sale_product_id"]

prod_e2 = setup_client.post("/api/simulations/products", json={
    "sku": f"CONCUR-E2-{uuid.uuid4().hex[:8]}",
    "name": "Widget E2",
}).json()
inv_e2 = setup_client.post("/api/simulations/inventory", json={
    "store_id": 102,
    "product_id": prod_e2["id"],
    "quantity": 100,
}).json()
sp_id_e2 = setup_client.post(f"/api/simulations/flash-sales/{setup_e['sale_id']}/products", json={
    "inventory_id": inv_e2["id"],
    "sale_price": "39.99",
    "stock_limit": 15,
}).json()["id"]

def purchase_interleaved_e(idx):
    target_sp = sp_id_e1 if (idx % 2 == 0) else sp_id_e2
    payload = {
        "customer_ref": f"CUST-INTERLEAVED-{idx}",
        "idempotency_key": f"IDEMP-E-{idx}-{uuid.uuid4()}",
        "quantity": 1,
    }
    with TestClient(app, headers=headers) as c:
        return c.post(f"/api/simulations/flash-sale-products/{target_sp}/purchase", json=payload).json()

with ThreadPoolExecutor(max_workers=30) as pool:
    responses_e = list(pool.map(purchase_interleaved_e, range(30)))

success_e = [r for r in responses_e if r.get("success") is True]
print(f"Total Interleaved Requests: 30 | Successful Purchases: {len(success_e)}")

with engine.begin() as conn:
    sp1_sold = conn.execute(text("SELECT sold_quantity FROM flash_sale_products WHERE id = :id"), {"id": sp_id_e1}).scalar_one()
    sp2_sold = conn.execute(text("SELECT sold_quantity FROM flash_sale_products WHERE id = :id"), {"id": sp_id_e2}).scalar_one()

print(f"Product 1 Sold: {sp1_sold} (Expected 15) | Product 2 Sold: {sp2_sold} (Expected 15)")
assert sp1_sold == 15
assert sp2_sold == 15
assert len(success_e) == 30
print(">>> SCENARIO E: PASSED — ZERO DEADLOCKS, CLEAN TRANSACTION RESOLUTION <<<")

print("\n" + "=" * 80)
print("ALL 5 HIGH-CONCURRENCY SCENARIOS PASSED WITH ZERO FAILURES!")
print("=" * 80)
