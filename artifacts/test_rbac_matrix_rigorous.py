import os
import sys

os.environ["DB_NAME"] = "flashcore_test"
sys.path.insert(0, "backend")

from fastapi.testclient import TestClient
from main import app
from app.core.database import engine
from sqlalchemy import text
from app.core.security import create_access_token
import uuid
from datetime import datetime, timedelta, timezone

client = TestClient(app)

# Clean DB and set up fixtures
with engine.begin() as conn:
    conn.execute(text("TRUNCATE TABLE auth_sessions, users RESTART IDENTITY CASCADE"))
    admin_id = conn.execute(text("""
        INSERT INTO users (email, password_hash, role, status)
        VALUES ('admin@flashcore.test', '$2b$12$dummyhashforsecuritytestingonly1234567890123456', 'admin', 'active')
        RETURNING id
    """)).scalar_one()

    analyst_id = conn.execute(text("""
        INSERT INTO users (email, password_hash, role, status)
        VALUES ('analyst@flashcore.test', '$2b$12$dummyhashforsecuritytestingonly1234567890123456', 'analyst', 'active')
        RETURNING id
    """)).scalar_one()

    operator_id = conn.execute(text("""
        INSERT INTO users (email, password_hash, role, status)
        VALUES ('operator@flashcore.test', '$2b$12$dummyhashforsecuritytestingonly1234567890123456', 'operator', 'active')
        RETURNING id
    """)).scalar_one()

    disabled_id = conn.execute(text("""
        INSERT INTO users (email, password_hash, role, status)
        VALUES ('disabled@flashcore.test', '$2b$12$dummyhashforsecuritytestingonly1234567890123456', 'analyst', 'disabled')
        RETURNING id
    """)).scalar_one()

def make_token(user_id: int):
    jti = uuid.uuid4()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=1)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO auth_sessions (jti, user_id, expires_at)
            VALUES (:jti, :user_id, :exp)
        """), {"jti": jti, "user_id": user_id, "exp": exp})
    token, _ = create_access_token(user_id, jti)
    return token

admin_token = make_token(admin_id)
analyst_token = make_token(analyst_id)
operator_token = make_token(operator_id)
disabled_token = make_token(disabled_id)

openapi = app.openapi()
paths = openapi["paths"]

results = []

path_items = []
for p, p_item in sorted(paths.items()):
    for m, op in p_item.items():
        if m.lower() in ("get", "post", "patch", "delete", "put"):
            path_items.append((p, m.upper()))

# Sort so logout is last
path_items.sort(key=lambda x: (1 if "logout" in x[0] else 0, x[0]))

for path, method in path_items:
    test_path = (path
        .replace("{store_id}", "1")
        .replace("{user_id}", str(analyst_id))
        .replace("{run_id}", "1")
        .replace("{product_id}", "1")
        .replace("{inventory_id}", "1")
        .replace("{sale_id}", "1")
        .replace("{sale_product_id}", "1")
        .replace("{attempt_id}", "1")
        .replace("{import_id}", "1")
    )
    
    # Check responses
    r_anon = client.request(method, test_path)
    r_analyst = client.request(method, test_path, headers={"Authorization": f"Bearer {analyst_token}"})
    r_operator = client.request(method, test_path, headers={"Authorization": f"Bearer {operator_token}"})
    r_admin = client.request(method, test_path, headers={"Authorization": f"Bearer {admin_token}"})
    r_disabled = client.request(method, test_path, headers={"Authorization": f"Bearer {disabled_token}"})
    
    results.append({
        "path": path,
        "method": method,
        "anon": r_anon.status_code,
        "analyst": r_analyst.status_code,
        "operator": r_operator.status_code,
        "admin": r_admin.status_code,
        "disabled": r_disabled.status_code,
    })

print(f"{'Method':<6} {'Path':<48} {'Anon':<6} {'Analyst':<8} {'Operator':<9} {'Admin':<7} {'Disabled':<9}")
print("=" * 96)
for r in results:
    print(f"{r['method']:<6} {r['path']:<48} {r['anon']:<6} {r['analyst']:<8} {r['operator']:<9} {r['admin']:<7} {r['disabled']:<9}")
