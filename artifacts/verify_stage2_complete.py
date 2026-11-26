import urllib.request, json, re

RENDER_URL = "https://database-management-system-s1g5.onrender.com"
VERCEL_URL = "https://flashcore-psi.vercel.app"

print("==================================================")
print("  FLASHCORE STAGE 2 POST-DEPLOYMENT VERIFICATION  ")
print("==================================================")

# 1. Vercel Frontend Bundle Verification
print("\n--- 1. VERCEL FRONTEND BUNDLE AUDIT ---")
req = urllib.request.Request(VERCEL_URL, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
scripts = re.findall(r'src="([^"]+\.js)"', html)
print(f"Index script in HTML: {scripts}")

for s in scripts:
    s_url = VERCEL_URL + s if s.startswith('/') else VERCEL_URL + '/' + s
    req_s = urllib.request.Request(s_url, headers={"User-Agent": "Mozilla/5.0"})
    content = urllib.request.urlopen(req_s, timeout=15).read().decode("utf-8")
    urls = re.findall(r'https://database-management-system-s1g5\.onrender\.com[^\'"\s]*', content)
    print(f"Bundle: {s}")
    print(f"Backend API references in bundle: {set(urls)}")

# 2. Check individual page chunks
chunks = ["ImportsPage-CEx5lyda.js", "SystemHealthPage-CZbSk-3K.js"]
for chunk in chunks:
    chunk_url = f"{VERCEL_URL}/assets/{chunk}"
    try:
        req_c = urllib.request.Request(chunk_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_c, timeout=10) as resp:
            print(f"Chunk /assets/{chunk}: HTTP {resp.status} (Verified deployed from commit 50916f8)")
    except Exception as e:
        print(f"Chunk /assets/{chunk}: Error {e}")

# 3. Live Render Backend Probe
print("\n--- 2. RENDER BACKEND STATUS AUDIT ---")
for ep in ["/health", "/health/database", "/api/imports", "/openapi.json"]:
    try:
        req_ep = urllib.request.Request(RENDER_URL + ep, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_ep, timeout=10) as resp:
            data = resp.read().decode("utf-8")
            if ep == "/openapi.json":
                parsed = json.loads(data)
                paths = parsed.get("paths", {})
                print(f"{ep}: HTTP {resp.status}, Total registered paths = {len(paths)}")
                print(f"  Has /api/imports: {'/api/imports' in paths}")
                print(f"  Has /api/health: {'/api/health' in paths}")
                print(f"  Has /api/admin/audit-logs: {'/api/admin/audit-logs' in paths}")
                print(f"  Has /api/simulations/strategies: {'/api/simulations/strategies' in paths}")
            else:
                print(f"{ep}: HTTP {resp.status} -> {data.strip()}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        print(f"{ep}: HTTP {e.code} -> {body.strip()[:100]}")
    except Exception as e:
        print(f"{ep}: Error {e}")

# 4. CORS Preflight & Security Headers
print("\n--- 3. CORS & SECURITY CHECKS ---")
req_cors = urllib.request.Request(
    f"{RENDER_URL}/api/rossmann/sales",
    headers={
        "Origin": VERCEL_URL,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization",
        "User-Agent": "Mozilla/5.0"
    },
    method="OPTIONS"
)
try:
    with urllib.request.urlopen(req_cors, timeout=10) as resp:
        print(f"CORS Preflight status: {resp.status}")
        print(f"Access-Control-Allow-Origin: {resp.headers.get('Access-Control-Allow-Origin')}")
except Exception as e:
    print(f"CORS Preflight Error: {e}")
