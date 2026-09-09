#!/usr/bin/env python3
"""CYBERPULSE AI — standalone demo simulation (CLI).

Streams the staged live-demo scenario over the API (requires the backend
running). The same scenario is available in-app via POST /api/v1/demo/run.

Usage:
  python scripts/demo_simulation.py            # run against http://localhost:8000
  python scripts/demo_simulation.py --reset    # reset demo state first
"""
from __future__ import annotations

import argparse
import json
import time

import httpx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    # login
    r = httpx.post(f"{base}/api/v1/auth/login",
                   json={"username": "admin", "password": "Admin@123"}, timeout=30)
    r.raise_for_status()
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    print(f"[demo] logged in as admin")

    if args.reset:
        r = httpx.post(f"{base}/api/v1/demo/reset", headers=h, timeout=120)
        print(f"[demo] reset: {r.json()}")

    # open websocket to watch events while the scenario runs
    import websocket  # type: ignore  # pip install websocket-client
    ws = websocket.create_connection(f"{base.replace('http', 'ws')}/ws/events")

    def listen():
        while True:
            try:
                msg = json.loads(ws.recv())
                t = msg.get("type")
                p = msg.get("payload", {})
                if t == "demo_stage":
                    print(f"  ▶ STAGE: {p.get('stage')} — {p.get('detail')}")
                elif t == "complaints_added":
                    print(f"  + {p.get('count')} complaints in {p.get('district')}")
                elif t == "transactions_added":
                    print(f"  + {p.get('count')} transactions at {p.get('atm_id')}")
                elif t == "predictions_generated":
                    print(f"  = {p.get('n_predictions')} predictions; top: "
                          f"{[x['atm_id'] + ':' + str(x['risk_score']) for x in p.get('top', [])]}")
                elif t == "hotspot":
                    print(f"  🔴 HOTSPOT {p.get('atm_id')} risk={p.get('risk_score')} "
                          f"prob={p.get('probability')}")
                elif t == "alert_created":
                    print(f"  🚨 ALERT {p.get('alert_id')} severity={p.get('severity')}")
                elif t == "demo_error":
                    print(f"  ✖ ERROR: {p.get('error')}")
            except Exception:
                break

    import threading
    th = threading.Thread(target=listen, daemon=True)
    th.start()
    time.sleep(0.5)

    r = httpx.post(f"{base}/api/v1/demo/run", headers=h, timeout=30)
    print(f"[demo] scenario started: {r.json()}")

    # wait for completion (max 120s)
    deadline = time.time() + 120
    while time.time() < deadline:
        time.sleep(1)
        try:
            # if the listener thread got the complete stage, break on silence
            pass
        except Exception:
            break
    # simple: wait 30s for the stream to finish
    time.sleep(30)
    ws.close()
    print("[demo] done")


if __name__ == "__main__":
    main()