import urllib.request, json, re

RENDER_URL = "https://database-management-system-s1g5.onrender.com"
VERCEL_URL = "https://flashcore-psi.vercel.app"

print("--- 1. VERIFY FRONTEND BUNDLE TARGET URL ---")
req = urllib.request.Request(VERCEL_URL, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
scripts = re.findall(r'src="([^"]+\.js)"', html)
print(f"Index scripts referenced in HTML: {scripts}")

for s in scripts:
    s_url = VERCEL_URL + s if s.startswith('/') else VERCEL_URL + '/' + s
    req_s = urllib.request.Request(s_url, headers={"User-Agent": "Mozilla/5.0"})
    content = urllib.request.urlopen(req_s, timeout=15).read().decode("utf-8")
    urls = re.findall(r'https://database-management-system-s1g5\.onrender\.com[^\'"\s]*', content)
    print(f"Script: {s}")
    print(f"Target API URLs found: {set(urls)}")

print("\n--- 2. VERIFY RENDER BACKEND ENDPOINTS ---")
endpoints = ["/health", "/health/database", "/api/imports", "/openapi.json"]
for ep in endpoints:
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
            else:
                print(f"{ep}: HTTP {resp.status} -> {data.strip()}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        print(f"{ep}: HTTP {e.code} -> {body.strip()}")
    except Exception as e:
        print(f"{ep}: Error {e}")
