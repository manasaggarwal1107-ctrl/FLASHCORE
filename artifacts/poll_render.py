import json
import time
import urllib.request
import urllib.error

url_base = "https://database-management-system-s1g5.onrender.com"

print("Checking live Render deployment status...")

for attempt in range(1, 13):
    print(f"\n--- Check Attempt {attempt} ({time.strftime('%H:%M:%S')}) ---")
    
    # 1. Root health
    try:
        with urllib.request.urlopen(f"{url_base}/health", timeout=15) as res:
            print(f"/health: {res.status} {res.read().decode('utf-8')}")
    except Exception as e:
        print(f"/health: ERROR {e}")

    # 2. Database health
    try:
        with urllib.request.urlopen(f"{url_base}/health/database", timeout=15) as res:
            print(f"/health/database: {res.status} {res.read().decode('utf-8')}")
    except Exception as e:
        print(f"/health/database: ERROR {e}")

    # 3. New /api/health
    api_health_ok = False
    try:
        with urllib.request.urlopen(f"{url_base}/api/health", timeout=15) as res:
            body = res.read().decode("utf-8")
            print(f"/api/health: {res.status} {body}")
            api_health_ok = (res.status == 200)
    except urllib.error.HTTPError as e:
        print(f"/api/health: HTTP {e.code} (Previous baseline if 404)")
    except Exception as e:
        print(f"/api/health: ERROR {e}")

    # 4. OpenAPI route count
    new_routes_deployed = False
    try:
        with urllib.request.urlopen(f"{url_base}/openapi.json", timeout=15) as res:
            spec = json.loads(res.read().decode("utf-8"))
            paths = list(spec.get("paths", {}).keys())
            count = len(paths)
            print(f"/openapi.json: {count} paths registered.")
            has_imports = "/api/imports" in paths
            has_audit = "/api/admin/audit-logs" in paths
            has_strategies = "/api/simulations/strategies" in paths
            print(f"  has /api/imports: {has_imports}")
            print(f"  has /api/admin/audit-logs: {has_audit}")
            print(f"  has /api/simulations/strategies: {has_strategies}")
            if count >= 42 and has_imports and has_audit and has_strategies:
                new_routes_deployed = True
    except Exception as e:
        print(f"/openapi.json: ERROR {e}")

    if new_routes_deployed and api_health_ok:
        print("\nSUCCESS: Render deployment is LIVE with all 42 expected routes!")
        break

    if attempt < 12:
        print("Waiting 15 seconds for Render build/deploy to finish...")
        time.sleep(15)
