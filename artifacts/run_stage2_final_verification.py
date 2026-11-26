import urllib.request, urllib.error, json

RENDER_URL = "https://database-management-system-s1g5.onrender.com"
VERCEL_URL = "https://flashcore-psi.vercel.app"

def run_test(name, method, url, headers=None, body=None):
    req_headers = {"User-Agent": "Mozilla/5.0"}
    if headers:
        req_headers.update(headers)
    
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
        
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8")
            return {
                "test": name,
                "method": method,
                "url": url,
                "actual_status": resp.status,
                "headers": dict(resp.headers),
                "full_body": content,
                "body_snippet": content[:300],
                "error": None
            }
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        return {
            "test": name,
            "method": method,
            "url": url,
            "actual_status": e.code,
            "headers": dict(e.headers),
            "full_body": err_body,
            "body_snippet": err_body[:300],
            "error": str(e)
        }
    except Exception as e:
        return {
            "test": name,
            "method": method,
            "url": url,
            "actual_status": "TIMEOUT/ERROR",
            "headers": {},
            "full_body": "",
            "body_snippet": "",
            "error": str(e)
        }

print("Running Stage 2 Full Live Verification Suite...")

# 1. Health
t1 = run_test("Backend Application Health", "GET", f"{RENDER_URL}/health")
print("t1:", t1["actual_status"])

# 2. Database Health
t2 = run_test("Backend Database Health", "GET", f"{RENDER_URL}/health/database")
print("t2:", t2["actual_status"], t2["body_snippet"])

# 3. OpenAPI paths
t3 = run_test("Backend OpenAPI Specification", "GET", f"{RENDER_URL}/openapi.json")
paths_count = len(json.loads(t3["full_body"]).get("paths", {})) if t3["actual_status"] == 200 else 0
print("t3 paths count:", paths_count)

# 4. 10 routes checks
routes_10 = [
    ("/api/admin/audit-logs", "GET", "Audit logs endpoint"),
    ("/api/simulations/strategies", "GET", "Simulation strategies endpoint"),
    ("/api/simulations/analytics/purchase-outcomes", "GET", "Simulation purchase outcomes"),
    ("/api/simulations/analytics/inventory-allocation", "GET", "Simulation inventory allocation"),
    ("/api/simulations/analytics/flash-sales-overview", "GET", "Simulation flash sales overview"),
    ("/api/simulations/analytics/activity", "GET", "Simulation activity feed"),
    ("/api/imports", "GET", "Dataset imports history"),
    ("/api/imports/1", "GET", "Dataset import detail (id 1)"),
    ("/api/health", "GET", "System health duplicate endpoint"),
    ("/api/health/database", "GET", "Database health duplicate endpoint")
]

t_routes = []
for path, meth, desc in routes_10:
    res = run_test(f"Route {path}", meth, f"{RENDER_URL}{path}")
    print(f"Route {path}: {res['actual_status']}")
    t_routes.append({"path": path, "desc": desc, "status": res["actual_status"], "body": res["body_snippet"]})

# 5. Authentication & RBAC (Anonymous & Invalid Token)
t_auth_anon = run_test("Anonymous access to protected /api/rossmann/sales/summary", "GET", f"{RENDER_URL}/api/rossmann/sales/summary")
t_auth_invalid = run_test("Invalid Bearer token access to /api/rossmann/sales/summary", "GET", f"{RENDER_URL}/api/rossmann/sales/summary", headers={"Authorization": "Bearer invalid_tampered_token_xyz"})
t_auth_malformed = run_test("Malformed Authorization header to /api/rossmann/sales/summary", "GET", f"{RENDER_URL}/api/rossmann/sales/summary", headers={"Authorization": "NotBearer xyz"})

# 6. Invalid Payload Validation
t_val_login = run_test("Invalid Login Payload (empty object)", "POST", f"{RENDER_URL}/api/auth/login", body={})
t_val_signup = run_test("Invalid Signup Payload (missing fields)", "POST", f"{RENDER_URL}/api/auth/signup", body={"email": "invalid"})

# 7. CORS Preflight
t_cors = run_test("CORS Preflight from Vercel Origin", "OPTIONS", f"{RENDER_URL}/api/rossmann/sales", headers={
    "Origin": VERCEL_URL,
    "Access-Control-Request-Method": "GET",
    "Access-Control-Request-Headers": "authorization,content-type"
})

# 8. Frontend Production Availability
t_frontend = run_test("Vercel Frontend Root", "GET", VERCEL_URL)

results_summary = {
    "t1": {"status": t1["actual_status"], "body": t1["body_snippet"]},
    "t2": {"status": t2["actual_status"], "body": t2["body_snippet"]},
    "t3_paths_count": paths_count,
    "t_routes": t_routes,
    "t_auth_anon": {"status": t_auth_anon["actual_status"], "body": t_auth_anon["body_snippet"]},
    "t_auth_invalid": {"status": t_auth_invalid["actual_status"], "body": t_auth_invalid["body_snippet"]},
    "t_auth_malformed": {"status": t_auth_malformed["actual_status"], "body": t_auth_malformed["body_snippet"]},
    "t_val_login": {"status": t_val_login["actual_status"], "body": t_val_login["body_snippet"]},
    "t_val_signup": {"status": t_val_signup["actual_status"], "body": t_val_signup["body_snippet"]},
    "t_cors": {
        "status": t_cors["actual_status"],
        "allow_origin": t_cors["headers"].get("access-control-allow-origin"),
        "allow_methods": t_cors["headers"].get("access-control-allow-methods"),
        "allow_headers": t_cors["headers"].get("access-control-allow-headers")
    },
    "t_frontend": {
        "status": t_frontend["actual_status"],
        "body_len": len(t_frontend["body_snippet"])
    }
}

with open("artifacts/stage2_final_verification_results.json", "w", encoding="utf-8") as f:
    json.dump(results_summary, f, indent=2)

print("\nSUCCESS: All tests executed and results saved to artifacts/stage2_final_verification_results.json")
