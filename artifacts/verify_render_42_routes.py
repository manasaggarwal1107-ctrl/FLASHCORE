import urllib.request, urllib.error, json

RENDER_URL = "https://database-management-system-s1g5.onrender.com"
VERCEL_URL = "https://flashcore-psi.vercel.app"

def request_endpoint(method, path, headers=None, body=None):
    req_headers = {"User-Agent": "Mozilla/5.0"}
    if headers:
        req_headers.update(headers)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{RENDER_URL}{path}", data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8")
            return {
                "status": resp.status,
                "headers": dict(resp.headers),
                "body": content
            }
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        return {
            "status": e.code,
            "headers": dict(e.headers),
            "body": err_body
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "headers": {},
            "body": str(e)
        }

print("=== STEP 4: VERIFY ACTIVE RELEASE ===")
r_health = request_endpoint("GET", "/health")
print(f"1. GET /health: HTTP {r_health['status']} -> {r_health['body']}")

r_db = request_endpoint("GET", "/health/database")
print(f"2. GET /health/database: HTTP {r_db['status']} -> {r_db['body']}")

r_openapi = request_endpoint("GET", "/openapi.json")
openapi_data = json.loads(r_openapi["body"])
paths = openapi_data.get("paths", {})
print(f"3. GET /openapi.json: HTTP {r_openapi['status']}, Total Paths: {len(paths)}")

print("\n=== STEP 5: VERIFY THE TEN NEW ROUTES ===")
ten_routes = [
    ("1. Audit Logs", "GET", "/api/admin/audit-logs"),
    ("2. Strategies", "GET", "/api/simulations/strategies"),
    ("3. Purchase Outcomes", "GET", "/api/simulations/analytics/purchase-outcomes"),
    ("4. Inventory Allocation", "GET", "/api/simulations/analytics/inventory-allocation"),
    ("5. Flash Sales Overview", "GET", "/api/simulations/analytics/flash-sales-overview"),
    ("6. Analytics Activity", "GET", "/api/simulations/analytics/activity"),
    ("7. Imports List", "GET", "/api/imports"),
    ("8. Import Detail", "GET", "/api/imports/1"),
    ("9. API System Health", "GET", "/api/health"),
    ("10. API DB Health", "GET", "/api/health/database")
]

ten_results = []
for label, method, path in ten_routes:
    res = request_endpoint(method, path)
    print(f"{label} ({method} {path}): HTTP {res['status']}")
    print(f"   Body snippet: {res['body'][:150]}")
    ten_results.append({
        "label": label,
        "method": method,
        "path": path,
        "status": res["status"],
        "body": res["body"][:250]
    })

print("\n=== STEP 6 & 7: CORS & INTEGRATION VERIFICATION ===")
r_cors = request_endpoint("OPTIONS", "/api/simulations/strategies", headers={
    "Origin": VERCEL_URL,
    "Access-Control-Request-Method": "GET",
    "Access-Control-Request-Headers": "authorization"
})
print(f"CORS Preflight on new route /api/simulations/strategies: HTTP {r_cors['status']}")
print(f"   Access-Control-Allow-Origin: {r_cors['headers'].get('access-control-allow-origin')}")

# Save full results
full_report = {
    "health": r_health,
    "database_health": r_db,
    "openapi_path_count": len(paths),
    "all_registered_paths": sorted(list(paths.keys())),
    "ten_routes_verified": ten_results,
    "cors": {
        "status": r_cors["status"],
        "allow_origin": r_cors["headers"].get("access-control-allow-origin")
    }
}

with open("artifacts/render_42_routes_verification.json", "w", encoding="utf-8") as f:
    json.dump(full_report, f, indent=2)

print("\nResults saved to artifacts/render_42_routes_verification.json")
