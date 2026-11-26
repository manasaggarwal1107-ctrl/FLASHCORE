import os, sys, inspect
sys.path.insert(0, os.path.abspath("backend"))
os.environ["DB_NAME"] = "flashcore_test"

from main import app

diff_paths = [
    "/api/admin/audit-logs",
    "/api/health",
    "/api/health/database",
    "/api/imports",
    "/api/imports/{import_id}",
    "/api/simulations/analytics/activity",
    "/api/simulations/analytics/flash-sales-overview",
    "/api/simulations/analytics/inventory-allocation",
    "/api/simulations/analytics/purchase-outcomes",
    "/api/simulations/strategies"
]

all_routes = []
for r in app.routes:
    if hasattr(r, "original_router"):
        all_routes.extend(r.original_router.routes)
    else:
        all_routes.append(r)

print("=== EXACT SOURCE CODE VERIFICATION OF ALL 10 NEW ROUTES IN COMMIT 50916f8 ===\n")

found_count = 0
for route in all_routes:
    path = getattr(route, "path", None)
    if path in diff_paths:
        found_count += 1
        methods = getattr(route, "methods", set())
        endpoint = getattr(route, "endpoint", None)
        func_name = endpoint.__name__ if endpoint else "unknown"
        module = inspect.getmodule(endpoint)
        module_file = module.__file__ if module else "unknown"
        rel_file = os.path.relpath(module_file, os.path.abspath("."))
        line_no = inspect.getsourcelines(endpoint)[1] if endpoint else 0
        print(f"[{found_count}/10] Route: {path}")
        print(f"       HTTP Methods: {', '.join(sorted(methods))}")
        print(f"       Handler Function: {func_name}()")
        print(f"       Source File: {rel_file} (Line {line_no})")
        print()

print(f"Total verified routes matching diff: {found_count} of 10")
