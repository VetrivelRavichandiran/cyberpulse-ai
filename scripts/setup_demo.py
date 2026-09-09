#!/usr/bin/env python3
"""CYBERPULSE AI — full reproducible demo setup.

Steps:
  1. Generate synthetic dataset      (data/raw)
  2. Preprocess + build features     (data/processed/prediction_units.csv)
  3. Train + evaluate models         (ml/artifacts/*)
  4. Create DB schema + seed         (data/demo/cyberpulse.db)
  5. Create demo users
  6. Verify model + health
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


def run(step: str, cmd: list[str]):
    print(f"\n{'='*60}\n[setup] {step}\n{'='*60}")
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        print(f"[setup] FAILED at step: {step}")
        sys.exit(r.returncode)


def main():
    run("1/6 Generate synthetic dataset",
        [PY, "scripts/generate_dataset.py"])
    run("2/6 Train + evaluate models (features built internally)",
        [PY, "scripts/train_model.py"])
    run("3/6 Seed database + users",
        [PY, "scripts/seed_database.py", "--reset"])

    # 4/6 verify model artifact
    art = os.path.join(ROOT, "ml", "artifacts", "model_v1.joblib")
    assert os.path.exists(art), "model artifact missing"
    print(f"\n[setup] 4/6 model artifact present: {art}")

    # 5/6 verify DB
    import sqlite3
    dbpath = os.path.join(ROOT, "data", "demo", "cyberpulse.db")
    assert os.path.exists(dbpath), "database missing"
    con = sqlite3.connect(dbpath)
    n_atm = con.execute("SELECT COUNT(*) FROM atms").fetchone()[0]
    n_comp = con.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    n_user = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    con.close()
    print(f"[setup] 5/6 database verified: atms={n_atm} complaints={n_comp} users={n_user}")

    # 6/6 verify app imports + model loads
    sys.path.insert(0, os.path.join(ROOT, "backend"))
    os.chdir(os.path.join(ROOT, "backend"))
    from ml.inference.service import get_service  # noqa: E402
    svc = get_service()
    assert svc.loaded, "model failed to load"
    print(f"[setup] 6/6 model loads OK (threshold={svc.threshold})")

    print("\n" + "=" * 60)
    print("[setup] ✅ Demo environment ready.")
    print("  Backend : cd backend && python -m uvicorn app.main:app --port 8000")
    print("  Frontend: cd frontend && npm run dev")
    print("  Login   : admin / Admin@123")
    print("=" * 60)


if __name__ == "__main__":
    main()