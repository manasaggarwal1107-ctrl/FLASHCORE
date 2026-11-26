import urllib.request, urllib.error, json

RENDER_URL = "https://database-management-system-s1g5.onrender.com"
VERCEL_URL = "https://flashcore-psi.vercel.app"

results = []

def test_endpoint(method, url, headers=None, data=None):
    if headers is None:
        headers = {}
    if 'User-Agent' not in headers:
        headers['User-Agent'] = 'FLASHCORE-Production-SmokeTest/1.0'
    
    req = urllib.request.Request(url, headers=headers, method=method)
    if data:
        req.data = json.dumps(data).encode('utf-8')
        req.headers['Content-Type'] = 'application/json'
        
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode('utf-8')
            resp_headers = dict(resp.headers)
            return {
                "status": resp.status,
                "headers": resp_headers,
                "body": body[:500]
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8') if e.fp else ""
        return {
            "status": e.code,
            "headers": dict(e.headers),
            "body": body[:500]
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e)
        }

print("=== FLASHCORE PRODUCTION SMOKE TESTS ===")

# 1. Render Health
r1 = test_endpoint("GET", f"{RENDER_URL}/health")
print(f"1. Render /health: {r1['status']} -> {r1.get('body')}")

# 2. Render Database Health
r2 = test_endpoint("GET", f"{RENDER_URL}/health/database")
print(f"2. Render /health/database: {r2['status']} -> {r2.get('body')}")

# 3. CORS Preflight Check from Vercel Origin
r3 = test_endpoint("OPTIONS", f"{RENDER_URL}/api/rossmann/sales", headers={
    "Origin": VERCEL_URL,
    "Access-Control-Request-Method": "GET",
    "Access-Control-Request-Headers": "authorization"
})
print(f"3. CORS Preflight: status={r3['status']}")
print(f"   Access-Control-Allow-Origin: {r3.get('headers', {}).get('access-control-allow-origin')}")
print(f"   Access-Control-Allow-Credentials: {r3.get('headers', {}).get('access-control-allow-credentials')}")

# 4. Anonymous Protected Route Access (RBAC)
r4 = test_endpoint("GET", f"{RENDER_URL}/api/rossmann/sales/summary")
print(f"4. Anonymous GET /api/rossmann/sales/summary: {r4['status']} -> {r4.get('body')}")

# 5. Invalid Auth Credentials
r5 = test_endpoint("POST", f"{RENDER_URL}/api/auth/login", data={"username": "nonexistent_probe_user", "password": "wrong_password"})
print(f"5. Invalid Auth POST /api/auth/login: {r5['status']} -> {r5.get('body')}")

# 6. Public Root
r6 = test_endpoint("GET", f"{RENDER_URL}/")
print(f"6. Render Root /: {r6['status']} -> {r6.get('body')}")

# 7. New Route Check (/api/imports)
r7 = test_endpoint("GET", f"{RENDER_URL}/api/imports")
print(f"7. Check New Route /api/imports: {r7['status']} -> {r7.get('body')}")

# 8. Vercel Frontend Availability
r8 = test_endpoint("GET", VERCEL_URL)
print(f"8. Vercel Frontend {VERCEL_URL}: {r8['status']}, length={len(r8.get('body', ''))}")

# 9. Vercel Security Headers
v_headers = r8.get('headers', {})
print(f"   Vercel Server: {v_headers.get('server')}")
print(f"   Vercel Strict-Transport-Security: {v_headers.get('strict-transport-security')}")
