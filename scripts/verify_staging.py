#!/usr/bin/env python3
"""Verify FLASHCORE staging deployment health, readiness, SPA routing, and optional auth flow.

Usage:
    python scripts/verify_staging.py --frontend-url https://flashcore-staging.vercel.app
    python scripts/verify_staging.py \\
        --frontend-url https://flashcore-staging.vercel.app \\
        --backend-url https://flashcore-api-staging.onrender.com

Optional environment variables for authenticated API checks (never logged or echoed):
    STAGING_TEST_EMAIL
    STAGING_TEST_PASSWORD
    STAGING_ORGANISATION_ID (optional override; defaults to active org / first org)
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any
from urllib.parse import urlparse

import httpx

LEGACY_PROTECTED_HOSTS = {
    "flashcore-psi.vercel.app",
    "database-management-system-s1g5.onrender.com",
}


def _assert_not_legacy(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    if host in LEGACY_PROTECTED_HOSTS:
        raise RuntimeError(
            f"Refusing to run staging checks against protected legacy production host: {host}"
        )


def _check_json_get(client: httpx.Client, url: str, expected_status: int = 200) -> dict[str, Any]:
    response = client.get(url)
    if response.status_code != expected_status:
        raise AssertionError(f"GET {url} returned HTTP {response.status_code} (expected {expected_status})")
    data = response.json()
    if not isinstance(data, dict):
        raise AssertionError(f"GET {url} did not return a JSON object")
    return data


def verify_frontend(frontend_url: str, timeout_s: float) -> None:
    _assert_not_legacy(frontend_url)
    base = frontend_url.rstrip("/")
    spa_routes = ["/", "/login", "/signup", "/overview", "/refunds", "/payment-links", "/settlements", "/reconciliation", "/orders/test-spa-route"]
    with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
        for route in spa_routes:
            url = f"{base}{route}"
            resp = client.get(url)
            if resp.status_code != 200:
                raise AssertionError(f"Frontend route {url} returned HTTP {resp.status_code}")
            body_lower = resp.text.lower()
            if "<!doctype html" not in body_lower or "flashcore" not in body_lower:
                raise AssertionError(f"Frontend route {url} did not return FLASHCORE HTML shell")
            print(f"[PASS] Frontend SPA route HTTP 200: {route}")


def verify_backend(backend_url: str, timeout_s: float) -> None:
    _assert_not_legacy(backend_url)
    base = backend_url.rstrip("/")
    with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
        root = _check_json_get(client, f"{base}/")
        if "flashcore_postgres_temp" in str(root):
            raise RuntimeError("Staging backend reported legacy database flashcore_postgres_temp!")
        if root.get("project") != "FLASHCORE" or root.get("status") != "running":
            raise AssertionError(f"Unexpected root payload: {root}")
        print("[PASS] Backend /")

        health = _check_json_get(client, f"{base}/health")
        if health.get("status") != "healthy":
            raise AssertionError(f"Unexpected /health payload: {health}")
        print("[PASS] Backend /health")

        db_health = _check_json_get(client, f"{base}/health/database")
        if db_health.get("status") != "connected":
            raise AssertionError(f"Unexpected /health/database payload: {db_health}")
        print("[PASS] Backend /health/database")

        ready = _check_json_get(client, f"{base}/ready")
        if ready.get("status") != "ready" or ready.get("migrations") != "ready":
            raise AssertionError(f"Backend /ready check failed: {ready}")
        print(
            "[PASS] Backend /ready "
            f"(env={ready.get('environment')}, rev={ready.get('alembic_revision')}, sha={ready.get('commit_sha')})"
        )

        email = os.getenv("STAGING_TEST_EMAIL", "").strip()
        password = os.getenv("STAGING_TEST_PASSWORD", "").strip()
        if email and password:
            login_resp = client.post(
                f"{base}/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            if login_resp.status_code != 200:
                raise AssertionError(f"Staging login failed with HTTP {login_resp.status_code}")
            token = login_resp.json().get("access_token")
            if not token:
                raise AssertionError("Staging login response missing access_token")
            auth_headers = {"Authorization": f"Bearer {token}"}

            me_resp = client.get(f"{base}/api/v1/auth/me", headers=auth_headers)
            if me_resp.status_code != 200:
                raise AssertionError(f"GET /api/v1/auth/me failed with HTTP {me_resp.status_code}")
            me_data = me_resp.json()
            org_id = os.getenv("STAGING_ORGANISATION_ID") or me_data.get("active_organisation_id")
            if not org_id:
                orgs_resp = client.get(f"{base}/api/v1/organisations", headers=auth_headers)
                if orgs_resp.status_code == 200 and orgs_resp.json():
                    org_id = orgs_resp.json()[0].get("id")
            if org_id:
                auth_headers["X-Organisation-Id"] = str(org_id)

            for path in (
                "/api/v1/orders",
                "/api/v1/refunds",
                "/api/v1/payment-links",
                "/api/v1/settlements",
                "/api/v1/reconciliation/runs",
            ):
                check = client.get(f"{base}{path}", headers=auth_headers)
                if check.status_code != 200:
                    raise AssertionError(f"Authenticated GET {path} returned HTTP {check.status_code}")
            print("[PASS] Authenticated Stage 3/4 tenant-scoped read smoke checks")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify FLASHCORE staging infrastructure.")
    parser.add_argument("--frontend-url", help="Staging Vercel URL")
    parser.add_argument("--backend-url", help="Staging Render backend URL")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout in seconds")
    args = parser.parse_args()

    if not args.frontend_url and not args.backend_url:
        parser.error("Provide at least one of --frontend-url or --backend-url")

    try:
        if args.frontend_url:
            verify_frontend(args.frontend_url, args.timeout)
        if args.backend_url:
            verify_backend(args.backend_url, args.timeout)
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    print("[OK] All requested staging checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
