import os
import sys

os.environ["DB_NAME"] = "flashcore_test"
sys.path.insert(0, "backend")

from fastapi.testclient import TestClient
from main import app
from app.core.database import engine
from sqlalchemy import text

client = TestClient(app)

openapi = app.openapi()
paths = openapi["paths"]
print(f"Total OpenAPI paths: {len(paths)}")

# Prepare test users: admin, analyst, operator, disabled
with engine.begin() as conn:
    conn.execute(text("TRUNCATE TABLE users, auth_sessions RESTART IDENTITY CASCADE"))
    # Insert users
    # We will use signup / login endpoint to create real sessions
    pass

# Test signup for 3 roles:
# Signup creates analyst by default.
def get_user_token(email, password, role="analyst", status="active"):
    # Create via /api/auth/signup
    res = client.post("/api/auth/signup", json={"email": email, "password": password})
    if res.status_code != 201:
        # maybe login
        res = client.post("/api/auth/login", json={"email": email, "password": password})
    data = res.json()
    token = data["access_token"]
    user_id = data["user"]["id"]
    
    # Update role and status directly in DB
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET role = :role, status = :status WHERE id = :id"),
            {"role": role, "status": status, "id": user_id}
        )
    return token, user_id

admin_token, admin_id = get_user_token("admin@flashcore.test", "AdminPassword123!", role="admin")
analyst_token, analyst_id = get_user_token("analyst@flashcore.test", "AnalystPassword123!", role="analyst")
operator_token, operator_id = get_user_token("operator@flashcore.test", "OperatorPassword123!", role="operator")
disabled_token, disabled_id = get_user_token("disabled@flashcore.test", "DisabledPassword123!", role="analyst", status="disabled")

print("Tokens generated successfully.")

matrix_results = []

for path, path_item in sorted(paths.items()):
    for method, op in path_item.items():
        if method.lower() not in ("get", "post", "patch", "delete", "put"):
            continue
        op_id = op.get("operationId", "")
        summary = op.get("summary", "")
        
        # Test path by substituting {id} with 1 or dummy
        test_path = path.replace("{store_id}", "1").replace("{user_id}", "1").replace("{run_id}", "1").replace("{product_id}", "1").replace("{inventory_id}", "1").replace("{sale_id}", "1").replace("{sale_product_id}", "1").replace("{attempt_id}", "1").replace("{import_id}", "1")
        
        # 1. Anonymous test
        r_anon = client.request(method, test_path)
        anon_status = r_anon.status_code
        
        # 2. Analyst test
        r_analyst = client.request(method, test_path, headers={"Authorization": f"Bearer {analyst_token}"})
        analyst_status = r_analyst.status_code
        
        # 3. Operator test
        r_operator = client.request(method, test_path, headers={"Authorization": f"Bearer {operator_token}"})
        operator_status = r_operator.status_code
        
        # 4. Admin test
        r_admin = client.request(method, test_path, headers={"Authorization": f"Bearer {admin_token}"})
        admin_status = r_admin.status_code
        
        # 5. Disabled test
        r_disabled = client.request(method, test_path, headers={"Authorization": f"Bearer {disabled_token}"})
        disabled_status = r_disabled.status_code
        
        matrix_results.append({
            "path": path,
            "method": method.upper(),
            "anon": anon_status,
            "analyst": analyst_status,
            "operator": operator_status,
            "admin": admin_status,
            "disabled": disabled_status,
        })

print(f"{'Method':<7} {'Path':<50} {'Anon':<6} {'Analyst':<8} {'Operator':<9} {'Admin':<7} {'Disabled':<9}")
print("-" * 100)
for r in matrix_results:
    print(f"{r['method']:<7} {r['path']:<50} {r['anon']:<6} {r['analyst']:<8} {r['operator']:<9} {r['admin']:<7} {r['disabled']:<9}")
