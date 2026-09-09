"""CYBERPULSE AI — synthetic dataset generator.

Generates a realistic, interconnected synthetic dataset with controlled
fraud-ring patterns (learnable signal):

  1. Complaint surge in a victim district
  2. UPI inflow into mule accounts (funds aggregation)
  3. Small "recon" withdrawals at target ATMs (ATM testing)
  4. Structured cash-out burst at target ATMs

All entities are synthetic. See `world.py` for the region definition.

Output (CSV, in data/raw/):
  complaints.csv, accounts.csv, transactions.csv, atms.csv,
  entities.csv, relationships.csv, meta.json
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from .world import (
    BANKS,
    CRIME_CATEGORIES,
    STATE,
    TX_TYPES,
    FraudRing,
    build_districts,
    haversine_km,
)

# ── timeline ────────────────────────────────────────────────────────────────
DAYS = 45


def _origin() -> pd.Timestamp:
    """Anchor the synthetic timeline to 'now' so the demo data is always fresh."""
    return pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=DAYS)


def _hour_weight(rng: np.random.Generator) -> int:
    """Diurnal activity curve: peaks 11-13h and 19-21h."""
    hours = np.arange(24)
    w = (
        0.35
        + 0.65 * np.exp(-((hours - 12) ** 2) / 18.0)
        + 0.85 * np.exp(-((hours - 20) ** 2) / 10.0)
    )
    w = w / w.sum()
    return int(rng.choice(hours, p=w))


def _pick_category(rng: np.random.Generator) -> str:
    names = [c[0] for c in CRIME_CATEGORIES]
    probs = np.array([c[1] for c in CRIME_CATEGORIES])
    return str(rng.choice(names, p=probs))


def _ring_definitions(rng: np.random.Generator, atms_by_district: dict[str, list[str]]) -> list[FraudRing]:
    """Six controlled fraud rings across the 45-day window."""
    spec = [
        # (start_day, dur, complaint_district, cashout_district, n_mules, n_atms, cross, emerging, scale)
        (5, 5, "Chikkaballapura", "Bengaluru Urban", 10, 4, True, False, 1.0),
        (12, 5, "Mandya", "Ramanagara", 9, 3, True, False, 0.9),
        (19, 5, "Bengaluru Rural", "Bengaluru Urban", 12, 5, True, False, 1.2),
        (26, 5, "Mysuru", "Mysuru", 8, 3, False, False, 0.8),
        (33, 5, "Chikkaballapura", "Mandya", 10, 4, True, False, 1.0),
        (39, 6, "Bengaluru Rural", "Ramanagara", 7, 3, True, True, 0.7),
    ]
    rings = []
    for i, (s, d, cd, kd, nm, na, cross, emerging, scale) in enumerate(spec):
        pool = atms_by_district[kd]
        target_atms = list(rng.choice(pool, size=min(na, len(pool)), replace=False))
        mules = [f"ACC-M{i:02d}{j:02d}" for j in range(nm)]
        rings.append(
            FraudRing(
                ring_id=f"RING-{i+1:02d}",
                complaint_district=cd,
                cashout_district=kd,
                mule_accounts=mules,
                target_atms=[str(a) for a in target_atms],
                active_days=(s, s + d),
                peak_hours=(10, 14),
                cross_district=cross,
                emerging=emerging,
                scale=scale,
            )
        )
    # Cross-ring shared mule phone (R3 and R5 share one SIM) — network signal.
    return rings


@dataclass
class Dataset:
    complaints: pd.DataFrame
    accounts: pd.DataFrame
    transactions: pd.DataFrame
    atms: pd.DataFrame
    entities: pd.DataFrame
    relationships: pd.DataFrame
    meta: dict


def generate_dataset(seed: int = 42, out_dir: str | None = None) -> Dataset:
    rng = np.random.default_rng(seed)
    ORIGIN = _origin()
    districts = build_districts()
    dmap = {d.name: d for d in districts}

    # ── ATMs ──────────────────────────────────────────────────────────────
    atm_rows, atms_by_district = [], {}
    weights = [0.34, 0.14, 0.16, 0.12, 0.14, 0.10]  # Bengaluru Urban heaviest
    total_atms = 260
    n_per = (np.array(weights) * total_atms).astype(int)
    atm_id = 0
    for dist, n in zip(districts, n_per):
        ids = []
        for _ in range(int(n)):
            atm_id += 1
            lat, lon = dist.point(rng)
            bank = str(rng.choice(BANKS, size=1)[0])
            aid = f"ATM-{atm_id:04d}"
            atm_rows.append(
                {
                    "atm_id": aid,
                    "bank_id": bank,
                    "latitude": lat,
                    "longitude": lon,
                    "district": dist.name,
                    "state": STATE,
                    "active": True,
                }
            )
            ids.append(aid)
        atms_by_district[dist.name] = ids
    atms = pd.DataFrame(atm_rows)
    atm_loc = {r["atm_id"]: (r["latitude"], r["longitude"]) for _, r in atms.iterrows()}

    # ── Accounts ──────────────────────────────────────────────────────────
    rings = _ring_definitions(rng, atms_by_district)
    n_normal = 900
    acc_rows = []
    for i in range(n_normal):
        dist = districts[int(rng.choice(len(districts), p=weights))]
        created = ORIGIN - pd.Timedelta(days=int(rng.integers(30, 900)))
        acc_rows.append(
            {
                "account_id": f"ACC-N{i:04d}",
                "bank_id": str(rng.choice(BANKS, size=1)[0]),
                "risk_indicator": "NORMAL",
                "created_at": created.isoformat(),
                "state": STATE,
                "district": dist.name,
            }
        )
    mule_created: dict[str, pd.Timestamp] = {}
    for ring in rings:
        for m in ring.mule_accounts:
            # Mule accounts are fresh (created just before the ring activates)
            created = ORIGIN + pd.Timedelta(days=ring.active_days[0] - int(rng.integers(1, 6)))
            mule_created[m] = created
            acc_rows.append(
                {
                    "account_id": m,
                    "bank_id": str(rng.choice(BANKS, size=1)[0]),
                    "risk_indicator": "HIGH",
                    "created_at": created.isoformat(),
                    "state": STATE,
                    "district": dmap[ring.cashout_district].name,
                }
            )
    accounts = pd.DataFrame(acc_rows)
    normal_accs = [f"ACC-N{i:04d}" for i in range(n_normal)]

    # ── Entities ──────────────────────────────────────────────────────────
    entities: list[dict] = []
    ent_id = 0

    def ent(kind: str, masked: str) -> str:
        nonlocal ent_id
        ent_id += 1
        eid = f"ENT-{ent_id:05d}"
        entities.append({"entity_id": eid, "entity_type": kind, "masked_identifier": masked})
        return eid

    # Phones: one per victim (created with complaint), one per mule (shared per ring)
    mule_phone: dict[str, str] = {}  # account -> entity id
    for ring in rings:
        ph = ent("PHONE", f"PH-{rng.integers(10**8, 10**9 - 1)}")
        for m in ring.mule_accounts:
            mule_phone[m] = ph
    # Cross-ring shared SIM: R3 and R5 share the first mule phone of R3
    if len(rings) >= 5:
        shared = mule_phone[rings[2].mule_accounts[0]]
        mule_phone[rings[4].mule_accounts[0]] = shared

    # ── Complaints ────────────────────────────────────────────────────────
    comp_rows = []
    comp_id = 0
    victim_phone: dict[str, str] = {}  # complaint_id -> entity id

    def add_complaint(ts: pd.Timestamp, district: str, amount: float, cat: str | None = None) -> str:
        nonlocal comp_id
        comp_id += 1
        cid = f"CMP-{comp_id:05d}"
        d = dmap[district]
        lat, lon = d.point(rng)
        comp_rows.append(
            {
                "complaint_id": cid,
                "timestamp": ts.isoformat(),
                "crime_category": cat or _pick_category(rng),
                "subcategory": "synthetic",
                "victim_state": STATE,
                "victim_district": district,
                "latitude": lat,
                "longitude": lon,
                "reported_amount": round(float(amount), 2),
                "phone_hash": "",  # filled below
                "account_hash": "",
                "status": str(rng.choice(["NEW", "INVESTIGATING", "RESOLVED"], p=[0.5, 0.3, 0.2])),
            }
        )
        ph = ent("PHONE", f"PH-{rng.integers(10**8, 10**9 - 1)}")
        victim_phone[cid] = ph
        comp_rows[-1]["phone_hash"] = ph
        return cid

    # Baseline complaints: ~1.2/day
    for day in range(DAYS):
        n = int(rng.poisson(1.2))
        for _ in range(n):
            d = districts[int(rng.choice(len(districts), p=weights))]
            ts = ORIGIN + pd.Timedelta(days=day, hours=_hour_weight(rng), minutes=int(rng.integers(0, 60)))
            amount = float(np.exp(rng.normal(9.6, 0.7)))  # median ~15k
            add_complaint(ts, d.name, amount)

    # Ring complaint surges (front-loaded)
    ring_complaints: dict[str, list[str]] = {}
    for ring in rings:
        s, e = ring.active_days
        cids = []
        for day in range(s, min(e, DAYS)):
            rate = 3.5 * ring.scale if day < s + 2 else 1.5 * ring.scale
            n = int(rng.poisson(rate))
            for _ in range(n):
                ts = ORIGIN + pd.Timedelta(days=day, hours=_hour_weight(rng), minutes=int(rng.integers(0, 60)))
                amount = float(np.exp(rng.normal(10.3, 0.8)))  # median ~30k
                cat = "UPI_FRAUD" if rng.random() < 0.55 else None
                cids.append(add_complaint(ts, ring.complaint_district, amount, cat))
        ring_complaints[ring.ring_id] = cids

    complaints = pd.DataFrame(comp_rows)

    # ── Transactions ──────────────────────────────────────────────────────
    tx_rows = []
    tx_id = 0
    rel_rows = []  # (source, target, type, ts)

    def add_tx(ts, account, amount, ttype, atm_id_: str | None, beneficiary: str | None = None,
               ring_id: str | None = None):
        nonlocal tx_id
        tx_id += 1
        tid = f"TXN-{tx_id:06d}"
        lat = lon = None
        if atm_id_ is not None:
            lat, lon = atm_loc[atm_id_]
        tx_rows.append(
            {
                "transaction_id": tid,
                "timestamp": ts.isoformat(),
                "account_id": account,
                "beneficiary_account_id": beneficiary or "",
                "amount": round(float(amount), 2),
                "transaction_type": ttype,
                "latitude": lat,
                "longitude": lon,
                "atm_id": atm_id_ or "",
                "status": "SUCCESS",
                "ring_id": ring_id or "",  # ground truth (used for evaluation only)
            }
        )
        return tid

    # Baseline transactions: each normal account ~2/week, mostly local
    acc_home_atm: dict[str, str] = {}
    for a in normal_accs:
        d = accounts.loc[accounts.account_id == a, "district"].iloc[0]
        pool = atms_by_district[d]
        acc_home_atm[a] = str(rng.choice(pool))
    for a in normal_accs:
        n = int(rng.poisson(2.0 * DAYS / 7.0))
        for _ in range(n):
            day = int(rng.integers(0, DAYS))
            ts = ORIGIN + pd.Timedelta(days=day, hours=_hour_weight(rng), minutes=int(rng.integers(0, 60)))
            r = rng.random()
            if r < 0.45:
                atm = acc_home_atm[a]
                amount = float(np.exp(rng.normal(8.0, 0.5)))  # median ~3k
                add_tx(ts, a, amount, "ATM_WITHDRAWAL", atm)
            elif r < 0.80:
                b = str(rng.choice(normal_accs))
                amount = float(np.exp(rng.normal(7.5, 1.0)))
                add_tx(ts, a, amount, "UPI_TRANSFER", None, beneficiary=b)
            else:
                ttype = str(rng.choice(["NEFT", "IMPS", "CARD_PAYMENT"]))
                amount = float(np.exp(rng.normal(8.5, 1.2)))
                atm = acc_home_atm[a] if ttype == "CARD_PAYMENT" else None
                add_tx(ts, a, amount, ttype, atm)

    # High-traffic hotspot ATMs: a few ATMs with heavy normal usage (these
# produce the positive windows the model learns "busy ATM" patterns from,
# and fraud rings amplify them further).
    hotspot_atms = list(rng.choice([r["atm_id"] for r in atm_rows], size=30, replace=False))
    for a in hotspot_atms:
        n = int(rng.poisson(6.5 * DAYS / 1.0))  # ~6.5 withdrawals/day, diurnal-peaked
        for _ in range(n):
            day = int(rng.integers(0, DAYS))
            ts = ORIGIN + pd.Timedelta(days=day, hours=_hour_weight(rng), minutes=int(rng.integers(0, 60)))
            amount = float(np.exp(rng.normal(8.2, 0.6)))
            add_tx(ts, str(rng.choice(normal_accs)), amount, "ATM_WITHDRAWAL", a)

    # Ring lifecycle
    # Ring target ATMs also carry elevated baseline traffic (busy cash hubs)
    for ring in rings:
        for atm in ring.target_atms:
            n = int(rng.poisson(1.6 * DAYS))
            for _ in range(n):
                day = int(rng.integers(0, DAYS))
                ts = ORIGIN + pd.Timedelta(days=day, hours=_hour_weight(rng), minutes=int(rng.integers(0, 60)))
                amount = float(np.exp(rng.normal(8.2, 0.6)))
                add_tx(ts, str(rng.choice(normal_accs)), amount, "ATM_WITHDRAWAL", atm)
    ring_ground_truth = []
    for ring in rings:
        s, e = ring.active_days
        cids = ring_complaints[ring.ring_id]
        victims = [f"ACC-N{int(c.split('-')[1]) % n_normal:04d}" for c in cids]  # map complaint->victim account
        # (1) UPI inflow into mules: days s+1..s+3
        for day in range(s + 1, min(s + 4, e, DAYS)):
            for m in ring.mule_accounts:
                k = int(rng.poisson(1.6 * ring.scale))
                for _ in range(k):
                    v = str(rng.choice(victims)) if victims else str(rng.choice(normal_accs))
                    ts = ORIGIN + pd.Timedelta(days=day, hours=int(rng.integers(9, 22)), minutes=int(rng.integers(0, 60)))
                    amount = float(np.exp(rng.normal(9.8, 0.9)))  # median ~18k
                    add_tx(ts, v, amount, "UPI_TRANSFER", None, beneficiary=m, ring_id=ring.ring_id)
                    rel_rows.append((v, m, "TRANSFERRED_TO", ts))
        # (2) Recon withdrawals: days s+2..s+3, small amounts at target ATMs
        for day in range(s + 2, min(s + 4, e, DAYS)):
            for atm in ring.target_atms:
                m = str(rng.choice(ring.mule_accounts))
                k = int(rng.poisson(3.0 * ring.scale))
                for _ in range(k):
                    ts = ORIGIN + pd.Timedelta(days=day, hours=int(rng.integers(9, 16)), minutes=int(rng.integers(0, 60)))
                    amount = float(rng.uniform(500, 2500))
                    add_tx(ts, m, amount, "ATM_WITHDRAWAL", atm, ring_id=ring.ring_id)
                    rel_rows.append((m, atm, "WITHDREW_AT", ts))
        # (3) Cash-out burst: days s+3..s+5, peak hours
        for day in range(s + 3, min(s + 6, e, DAYS)):
            for atm in ring.target_atms:
                k = int(rng.poisson(8.0 * ring.scale))
                for _ in range(k):
                    m = str(rng.choice(ring.mule_accounts))
                    h = int(rng.integers(ring.peak_hours[0], ring.peak_hours[1]))
                    ts = ORIGIN + pd.Timedelta(days=day, hours=h, minutes=int(rng.integers(0, 60)))
                    amount = float(np.exp(rng.normal(10.2, 0.45)))  # median ~27k
                    add_tx(ts, m, amount, "ATM_WITHDRAWAL", atm, ring_id=ring.ring_id)
                    rel_rows.append((m, atm, "WITHDREW_AT", ts))
        ring_ground_truth.append(
            {
                "ring_id": ring.ring_id,
                "complaint_district": ring.complaint_district,
                "cashout_district": ring.cashout_district,
                "target_atms": ring.target_atms,
                "active_days": list(ring.active_days),
                "cashout_days": [s + 3, s + 4],
                "cross_district": ring.cross_district,
                "emerging": ring.emerging,
            }
        )

    transactions = pd.DataFrame(tx_rows)

    # ── Entities: accounts & ATMs ─────────────────────────────────────────
    acc_ent = {a: ent("ACCOUNT", f"ACC-{a.split('-')[1]}") for a in accounts.account_id}
    atm_ent = {a: ent("ATM", a) for a in atm_loc}
    for d in districts:
        ent("DISTRICT", d.name)
    for b, _ in BANKS:
        ent("BANK", b)

    # ── Relationships ─────────────────────────────────────────────────────
    # complaint -> victim phone, complaint -> victim account
    for c in comp_rows:
        rel_rows.append((acc_ent.get(f"ACC-N{int(c['complaint_id'].split('-')[1]) % n_normal:04d}", "UNKNOWN"),
                         victim_phone[c["complaint_id"]], "REPORTED_ON", pd.Timestamp(c["timestamp"])))
    # mule account -> mule phone
    for m, ph in mule_phone.items():
        rel_rows.append((acc_ent[m], ph, "REGISTERED_PHONE", ORIGIN + pd.Timedelta(days=1)))
    # account -> home ATM (first observed)
    for a, atm in acc_home_atm.items():
        first = transactions[(transactions.account_id == a)].timestamp.min()
        rel_rows.append((acc_ent[a], atm_ent[atm], "FREQ_ATM", pd.Timestamp(first)))

    # dedupe relationships, keep first
    rel_df = pd.DataFrame(rel_rows, columns=["source_entity", "target_entity", "relationship_type", "timestamp"])
    rel_df["timestamp"] = rel_df["timestamp"].astype(str)
    rel_df = rel_df.drop_duplicates(subset=["source_entity", "target_entity", "relationship_type"]).reset_index(drop=True)
    rel_df = rel_df[rel_df.source_entity != "UNKNOWN"]

    entities_df = pd.DataFrame(entities)
    meta = {
        "dataset_version": "synthetic-v1",
        "seed": seed,
        "origin": ORIGIN.isoformat(),
        "days": DAYS,
        "state": STATE,
        "n_districts": len(districts),
        "n_atms": len(atms),
        "n_accounts": len(accounts),
        "n_complaints": len(complaints),
        "n_transactions": len(transactions),
        "n_entities": len(entities_df),
        "n_relationships": len(rel_df),
        "fraud_rings": ring_ground_truth,
        "disclaimer": "Synthetic data — prototype evaluation only. No real persons, banks or institutions.",
    }

    ds = Dataset(complaints, accounts, transactions, atms, entities_df, rel_df, meta)

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        complaints.to_csv(os.path.join(out_dir, "complaints.csv"), index=False)
        accounts.to_csv(os.path.join(out_dir, "accounts.csv"), index=False)
        transactions.to_csv(os.path.join(out_dir, "transactions.csv"), index=False)
        atms.to_csv(os.path.join(out_dir, "atms.csv"), index=False)
        entities_df.to_csv(os.path.join(out_dir, "entities.csv"), index=False)
        rel_df.to_csv(os.path.join(out_dir, "relationships.csv"), index=False)
        with open(os.path.join(out_dir, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)
    return ds


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    ds = generate_dataset(seed=args.seed, out_dir=args.out)
    print(f"Generated: {len(ds.complaints)} complaints, {len(ds.transactions)} transactions, "
          f"{len(ds.atms)} ATMs, {len(ds.accounts)} accounts, {len(ds.entities)} entities, "
          f"{len(ds.relationships)} relationships")