import urllib.request, json, time, sys

RENDER_URL = "https://database-management-system-s1g5.onrender.com"
VERCEL_URL = "https://flashcore-psi.vercel.app"

print("Starting Render deployment listener...")
print("Polling https://database-management-system-s1g5.onrender.com/openapi.json every 10 seconds...")

max_checks = 60  # 10 minutes max
for attempt in range(1, max_checks + 1):
    try:
        req = urllib.request.Request(f"{RENDER_URL}/openapi.json", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            paths = data.get("paths", {})
            count = len(paths)
            has_imports = "/api/imports" in paths
            if has_imports and count >= 40:
                print(f"\n[SUCCESS] New deployment detected on attempt {attempt}!")
                print(f"Total routes registered: {count}")
                print(f"Has /api/imports: {has_imports}")
                sys.exit(0)
            else:
                print(f"Attempt {attempt}/{max_checks}: Still serving baseline ({count} routes). Waiting 10s...", flush=True)
    except Exception as e:
        print(f"Attempt {attempt}/{max_checks}: Probe error ({e}). Waiting 10s...", flush=True)
    time.sleep(10)

print("\nListener timed out after 10 minutes without detecting container swap.")
sys.exit(1)
