#!/usr/bin/env python3
"""CYBERPULSE AI — seed the database from data/raw CSVs + create demo users.

Usage:
  python scripts/seed_database.py            # seed (idempotent: skips if loaded)
  python scripts/seed_database.py --reset    # wipe all data first, then seed
  python scripts/seed_database.py --users-only
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import pandas as pd  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    Account,
    ATM,
    Complaint,
    Entity,
    EntityRelationship,
    ModelRun,
    Transaction,
    User,
    Role,
)
from app.auth.security import hash_password  # noqa: E402


DEMO_USERS = [
    ("admin", "CYBERPULSE Admin", "admin@cyberpulse.gov", Role.ADMIN, "Karnataka", None, "Admin@123"),
    ("analyst", "I4C Analyst", "analyst@cyberpulse.gov", Role.I4C_ANALYST, "Karnataka", None, "Analyst@123"),
    ("state_officer", "State Officer", "state@cyberpulse.gov", Role.STATE_OFFICER, "Karnataka", None, "State@123"),
    ("district_officer", "District Officer", "district@cyberpulse.gov", Role.DISTRICT_OFFICER, "Karnataka", "Bengaluru Urban", "District@123"),
    ("investigator", "Field Investigator", "investigator@cyberpulse.gov", Role.INVESTIGATOR, "Karnataka", "Bengaluru Urban", "Invest@123"),
    ("bank_user", "Bank Fraud Cell", "bank@cyberpulse.gov", Role.BANK_USER, "Karnataka", None, "Bank@123"),
]


def _ts(v) -> datetime:
    if isinstance(v, datetime):
        return v
    dt = pd.to_datetime(str(v))
    return dt.to_pydatetime().replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.to_pydatetime()


def wipe(db):
    from app.models import (Alert, AuditLog, Investigation, InvestigationNote,
                            Intervention, Notification, Prediction, PredictionFactor,
                            TimelineEvent)
    for m in (Notification, Intervention, InvestigationNote, TimelineEvent, Investigation,
              Alert, PredictionFactor, Prediction, AuditLog,
              EntityRelationship, Entity, Transaction, Complaint, Account, ATM, ModelRun, User):
        db.query(m).delete()
    db.commit()
    print("[seed] wiped all tables")


def seed_users(db):
    existing = {u.username for u in db.query(User).all()}
    n = 0
    for username, full_name, email, role, state, district, password in DEMO_USERS:
        if username in existing:
            continue
        db.add(User(
            username=username, full_name=full_name, email=email, role=role,
            state=state, district=district, password_hash=hash_password(password),
        ))
        n += 1
    db.commit()
    print(f"[seed] users: {n} created ({len(existing)} existing)")


def seed_data(db, data_dir: str):
    if db.query(ATM).count() > 0:
        print("[seed] data already present — skipping (use --reset to reseed)")
        return

    def load(name):
        return pd.read_csv(os.path.join(data_dir, f"{name}.csv"))

    atms = load("atms")
    accounts = load("accounts")
    complaints = load("complaints")
    transactions = load("transactions")
    entities = load("entities")
    rels = load("relationships")

    print(f"[seed] loading {len(atms)} ATMs, {len(accounts)} accounts, "
          f"{len(complaints)} complaints, {len(transactions)} transactions, "
          f"{len(entities)} entities, {len(rels)} relationships ...")

    for _, r in atms.iterrows():
        db.add(ATM(atm_id=r.atm_id, bank_id=r.bank_id, latitude=float(r.latitude),
                   longitude=float(r.longitude), district=r.district, state=r.state,
                   active=bool(r.active)))
    db.flush()
    for _, r in accounts.iterrows():
        db.add(Account(account_id=r.account_id, bank_id=r.bank_id,
                       risk_indicator=r.risk_indicator, created_at=_ts(r.created_at),
                       state=r.state, district=r.district))
    db.flush()
    for _, r in complaints.iterrows():
        db.add(Complaint(complaint_id=r.complaint_id, timestamp=_ts(r.timestamp),
                         crime_category=r.crime_category, subcategory=r.subcategory,
                         victim_state=r.victim_state, victim_district=r.victim_district,
                         latitude=float(r.latitude), longitude=float(r.longitude),
                         reported_amount=float(r.reported_amount),
                         phone_hash=r.phone_hash if isinstance(r.phone_hash, str) else None,
                         account_hash=r.account_hash if isinstance(r.account_hash, str) else None,
                         status=r.status))
    db.flush()
    for _, r in transactions.iterrows():
        db.add(Transaction(
            transaction_id=r.transaction_id, timestamp=_ts(r.timestamp),
            account_id=r.account_id,
            beneficiary_account_id=r.beneficiary_account_id
            if isinstance(r.beneficiary_account_id, str) and r.beneficiary_account_id else None,
            amount=float(r.amount), transaction_type=r.transaction_type,
            latitude=float(r.latitude) if pd.notna(r.latitude) else None,
            longitude=float(r.longitude) if pd.notna(r.longitude) else None,
            atm_id=r.atm_id if isinstance(r.atm_id, str) and r.atm_id else None,
            status=r.status,
            ring_id=r.ring_id if isinstance(r.ring_id, str) and r.ring_id else None,
        ))
    db.flush()
    for _, r in entities.iterrows():
        db.add(Entity(entity_id=r.entity_id, entity_type=r.entity_type,
                      masked_identifier=r.masked_identifier))
    db.flush()
    for _, r in rels.iterrows():
        db.add(EntityRelationship(source_entity=r.source_entity,
                                  target_entity=r.target_entity,
                                  relationship_type=r.relationship_type,
                                  timestamp=_ts(r.timestamp) if pd.notna(r.timestamp) else None))
    db.commit()
    print("[seed] domain data loaded")


def seed_model_run(db, artifacts_dir: str):
    import json
    p = os.path.join(artifacts_dir, "model_registry.json")
    if not os.path.exists(p) or db.query(ModelRun).count() > 0:
        return
    with open(p) as f:
        reg = json.load(f)
    a = reg["active"]
    db.add(ModelRun(
        version=a["version"], algorithm=a["algorithm"],
        dataset_version=a["dataset_version"],
        trained_at=pd.to_datetime(a["trained_at"]).to_pydatetime(),
        is_active=True,
        metrics_json=json.dumps(a["metrics"]),
        feature_importance_json=json.dumps(a["feature_importance"]),
    ))
    db.commit()
    print("[seed] model run registered")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--users-only", action="store_true")
    ap.add_argument("--data", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--artifacts", default=os.path.join(ROOT, "ml", "artifacts"))
    args = ap.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if args.reset:
            wipe(db)
        seed_users(db)
        if not args.users_only:
            seed_data(db, args.data)
            seed_model_run(db, args.artifacts)
        # summary
        print(f"[seed] done: users={db.query(User).count()} atms={db.query(ATM).count()} "
              f"complaints={db.query(Complaint).count()} txs={db.query(Transaction).count()} "
              f"entities={db.query(Entity).count()} rels={db.query(EntityRelationship).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()