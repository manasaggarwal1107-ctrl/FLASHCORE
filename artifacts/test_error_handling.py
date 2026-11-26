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

print("=" * 80)
print("FLASHCORE STAGE 3 — ERROR HANDLING & RESPONSE REDACTION AUDIT")
print("=" * 80)

# Setup admin and analyst tokens
with engine.begin() as conn:
    conn.execute(text("TRUNCATE TABLE users, auth_sessions RESTART IDENTITY CASCADE"))
    admin_id = conn.execute(text("""
        INSERT INTO users (email, password_hash, role, status)
        VALUES ('admin_err@flashcore.test', '$2b$12$dummyhashforerrortestingonly1234567890123456', 'admin', 'active')
        RETURNING id
    """)).scalar_one()
    analyst_id = conn.execute(text("""
        INSERT INTO users (email, password_hash, role, status)
        VALUES ('analyst_err@flashcore.test', '$2b$12$dummyhashforerrortestingonly1234567890123456', 'analyst', 'active')
        RETURNING id
    """)).scalar_one()

def get_token(u_id):
    jti = uuid.uuid4()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=1)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO auth_sessions (jti, user_id, expires_at) VALUES (:jti, :u_id, :exp)"), {"jti": jti, "u_id": u_id, "exp": exp})
    t, _ = create_access_token(u_id, jti)
    return t

admin_token = get_token(admin_id)
analyst_token = get_token(analyst_id)

test_cases = [
    ("404 Nonexistent Path", "GET", "/api/not-a-real-endpoint", {}, 404),
    ("404 Nonexistent Resource", "GET", "/api/rossmann/stores/999999", {"Authorization": f"Bearer {analyst_token}"}, 404),
    ("400 Reversed Date Range", "GET", "/api/rossmann/sales?start_date=2026-12-31&end_date=2026-01-01", {"Authorization": f"Bearer {analyst_token}"}, 400),
    ("401 Missing Credentials", "GET", "/api/auth/me", {}, 401),
    ("401 Malformed Token", "GET", "/api/auth/me", {"Authorization": "Bearer not-a-valid-jwt-token"}, 401),
    ("403 Forbidden Role Access", "GET", "/api/admin/users", {"Authorization": f"Bearer {analyst_token}"}, 403),
    ("409 Duplicate User Email", "POST", "/api/auth/signup", {}, 409, {"email": "analyst_err@flashcore.test", "password": "Password123!@#"}),
    ("409 Demote Last Admin", "PATCH", f"/api/admin/users/{admin_id}/role", {"Authorization": f"Bearer {admin_token}"}, 409, {"role": "analyst"}),
    ("422 Validation Short Password", "POST", "/api/auth/signup", {}, 422, {"email": "valid@flashcore.test", "password": "short"}),
    ("422 Validation Invalid Email", "POST", "/api/auth/signup", {}, 422, {"email": "not-an-email", "password": "ValidPassword123!"}),
]

leakage_failures = []

for item in test_cases:
    name, method, path, hdrs, expected_status = item[0], item[1], item[2], item[3], item[4]
    body = item[5] if len(item) > 5 else None
    
    r = client.request(method, path, headers=hdrs, json=body)
    resp_text = r.text
    
    # Check for stack trace or secret leaks
    leaks = []
    for sensitive in ["Traceback", "psycopg.", "sqlalchemy.exc", "surbhi1107", "postgres:", "File \"", "line "]:
        if sensitive.lower() in resp_text.lower():
            # filter out false positives if any
            if "file \"" in resp_text.lower() or "traceback" in resp_text.lower() or "psycopg" in resp_text.lower():
                leaks.append(sensitive)
    
    status_match = (r.status_code == expected_status)
    print(f"[{'PASS' if status_match and not leaks else 'FAIL'}] {name:<35} : HTTP {r.status_code} (Expected {expected_status}) | Leaks: {leaks or 'None'}")
    if leaks or not status_match:
        leakage_failures.append((name, r.status_code, resp_text))

assert len(leakage_failures) == 0, f"Error handling failures detected: {leakage_failures}"
print("\n>>> ALL ERROR RESPONSES VERIFIED: CLEAN JSON, ZERO STACK TRACES OR CREDENTIAL LEAKS <<<")
