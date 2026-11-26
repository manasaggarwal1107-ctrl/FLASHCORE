import urllib.request
import json
import time

BASE_URL = "https://database-management-system-s1g5.onrender.com"
OUTPUT_FILE = "artifacts/database-verification/production_readonly_results.json"

endpoints = [
    ("/", "Root"),
    ("/health", "Health Check"),
    ("/health/database", "Database Health"),
    ("/openapi.json", "OpenAPI Contract"),
    ("/docs", "Swagger UI"),
    ("/api/health", "API Health"),
    ("/api/health/database", "API Database Health"),
    ("/api/imports", "Dataset Imports (Auth Protected)"),
    ("/api/admin/audit-logs", "Admin Audit Logs (Auth Protected)"),
    ("/api/rossmann/sales/summary", "Rossmann Sales Summary (Auth Protected)"),
    ("/api/simulations/analytics/purchase-outcomes", "Purchase Outcomes (Auth Protected)"),
    ("/api/simulations/products", "Simulation Products (Auth Protected)"),
    ("/api/simulations/inventory", "Simulation Inventory (Auth Protected)"),
    ("/api/simulations/transactions", "Simulation Transactions (Auth Protected)"),
    ("/api/simulations/strategies", "Simulation Concurrency Strategies")
]

results = []

print(f"Executing read-only probe against {BASE_URL}...")

for path, desc in endpoints:
    url = BASE_URL + path
    start_t = time.time()
    entry = {
        "path": path,
        "description": desc,
        "url": url,
        "status_code": None,
        "response_time_ms": None,
        "content_type": None,
        "body_preview": None,
        "error": None
    }
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FLASHCORE-MasterAudit/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            elapsed = (time.time() - start_t) * 1000
            entry["status_code"] = resp.status
            entry["response_time_ms"] = round(elapsed, 2)
            entry["content_type"] = resp.headers.get("Content-Type")
            data = resp.read().decode("utf-8", errors="replace")
            entry["body_preview"] = data[:300]
            print(f"[OK] {path:<35} : HTTP {resp.status} ({entry['response_time_ms']}ms)")
    except urllib.error.HTTPError as e:
        elapsed = (time.time() - start_t) * 1000
        entry["status_code"] = e.code
        entry["response_time_ms"] = round(elapsed, 2)
        entry["content_type"] = e.headers.get("Content-Type")
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        entry["body_preview"] = body[:300]
        print(f"[HTTP {e.code}] {path:<35} : ({entry['response_time_ms']}ms) -> {body[:80]}")
    except Exception as e:
        elapsed = (time.time() - start_t) * 1000
        entry["response_time_ms"] = round(elapsed, 2)
        entry["error"] = f"{type(e).__name__}: {str(e)}"
        print(f"[ERR] {path:<35} : {entry['error']}")
    
    results.append(entry)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print(f"\nResults successfully saved to {OUTPUT_FILE}")
