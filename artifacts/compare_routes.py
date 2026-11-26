import os, sys
sys.path.insert(0, os.path.abspath("backend"))
os.environ["DB_NAME"] = "flashcore_test"

import urllib.request, json
from main import app

# 1. Local OpenAPI & Routes
local_openapi = app.openapi()
local_paths = local_openapi.get("paths", {})
print(f"Local registered OpenAPI paths count: {len(local_paths)}")

# 2. Live Render OpenAPI
RENDER_URL = "https://database-management-system-s1g5.onrender.com"
req = urllib.request.Request(f"{RENDER_URL}/openapi.json", headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        live_openapi = json.loads(resp.read().decode("utf-8"))
        live_paths = live_openapi.get("paths", {})
        print(f"Live Render OpenAPI paths count: {len(live_paths)}")
except Exception as e:
    print(f"Failed to fetch live openapi: {e}")
    live_paths = {}

# 3. Diff
diff_paths = sorted(set(local_paths.keys()) - set(live_paths.keys()))
print(f"\nPaths in local commit 50916f8 but NOT in live Render ({len(diff_paths)}):")
for p in diff_paths:
    methods = list(local_paths[p].keys())
    print(f"  + {p} [{', '.join(m.upper() for m in methods)}]")

diff_reverse = sorted(set(live_paths.keys()) - set(local_paths.keys()))
print(f"\nPaths in live Render but NOT in local ({len(diff_reverse)}):")
for p in diff_reverse:
    print(f"  - {p}")

# 4. Route registration source code inspection
print("\n--- EXACT SOURCE CODE LOCATION OF THE 10 NEW ROUTES ---")
import inspect

for route in app.routes:
    path = getattr(route, "path", None)
    if path in diff_paths:
        methods = getattr(route, "methods", set())
        endpoint = getattr(route, "endpoint", None)
        func_name = endpoint.__name__ if endpoint else "unknown"
        module = inspect.getmodule(endpoint)
        module_file = module.__file__ if module else "unknown"
        # make relative to workspace
        rel_file = os.path.relpath(module_file, os.path.abspath("."))
        line_no = inspect.getsourcelines(endpoint)[1] if endpoint else 0
        print(f"Path: {path}")
        print(f"  Methods: {methods}")
        print(f"  Function: {func_name}")
        print(f"  Source File: {rel_file}:{line_no}")
        print()
