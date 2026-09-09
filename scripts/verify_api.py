#!/usr/bin/env python3
"""CYBERPULSE AI — backend smoke test.

Expects the API to be running on :8000 (make run-backend) and logs in as the
demo admin. Exercises the main read endpoints and prints a pass/fail summary.

Usage:
  python scripts/verify_api.py            # against http://localhost:8000
  BASE_URL=http://127.0.0.1:8000 python scripts/verify_api.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE = os.environ.get("BASE_URL", "http://localhost:8000")
API = f"{BASE}/api/v1"


def call(method: str, path: str, token: str | None = None, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return r.status, (json.loads(raw) if raw else None)


def main() -> int:
    checks = []

    def check(name: str, ok: bool, detail: str = ""):
        checks.append((name, ok, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    print(f"Verifying CYBERPULSE AI backend at {API}\n")

    # health (no auth)
    try:
        st, h = call("GET", "/health")
        check("health", st == 200 and h.get("status") == "ok",
              f"model_loaded={h.get('model_loaded')}")
    except Exception as e:
        check("health", False, str(e))
        print("\nBackend not reachable — is it running on :8000?")
        return 1

    # login
    try:
        st, tok = call("POST", "/auth/login",
                       body={"username": "admin", "password": "Admin@123"})
        token = tok["access_token"]
        check("login (admin)", st == 200 and bool(token))
    except Exception as e:
        check("login (admin)", False, str(e))
        print("\nLogin failed — run `make demo` to seed the database.")
        return 1

    # authenticated reads
    endpoints = [
        ("/auth/me", "auth/me"),
        ("/dashboard/summary", "dashboard summary"),
        ("/dashboard/risk-trend", "risk trend"),
        ("/dashboard/complaint-trend", "complaint trend"),
        ("/dashboard/district-risk", "district risk"),
        ("/dashboard/alert-status", "alert status"),
        ("/predictions/hotspots", "hotspots"),
        ("/alerts", "alerts"),
        ("/investigations", "investigations"),
        ("/map/hotspots", "map hotspots"),
        ("/map/atms", "map ATMs"),
        ("/graph/stats", "graph stats"),
        ("/model/info", "model info"),
        ("/model/feature-importance", "feature importance"),
        ("/notifications", "notifications"),
        ("/audit", "audit"),
    ]
    for path, name in endpoints:
        try:
            st, _ = call("GET", path, token)
            check(name, st == 200)
        except Exception as e:
            check(name, False, str(e))

    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)
    print(f"\n{passed}/{total} checks passed.")
    return 0 if passed == total else 2


if __name__ == "__main__":
    sys.exit(main())