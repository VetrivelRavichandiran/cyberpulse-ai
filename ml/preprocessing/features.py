"""CYBERPULSE AI — preprocessing: load raw CSVs, clean, build the prediction
unit (ATM x 6-hour window) and its point-in-time features.

Prediction unit
---------------
Each row = (atm_id, window_start) where window_start is on a 6-hour grid
(00:00, 06:00, 12:00, 18:00).

Target
------
y = 1 if the ATM has >= 3 withdrawals in the 6-hour window starting at
window_start (a "suspicious withdrawal cluster").

Leakage control
---------------
Every feature is computed from data with timestamp < window_start only.
The label uses data in [window_start, window_start + 6h).

`FeatureContext` is the single source of truth for feature math — it is used
by BOTH the training pipeline and the live backend inference, guaranteeing
no train/serve feature mismatch.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

WINDOW_HOURS = 6
LABEL_THRESHOLD = 3  # >=3 withdrawals in the window => positive
GRID_HOURS = (0, 6, 12, 18)

FEATURES = [
    # temporal
    "hour_of_day", "day_of_week", "is_weekend",
    "complaints_last_24h", "complaints_last_72h",
    "complaints_last_7d", "complaint_accel",
    "tx_last_24h", "tx_last_72h", "tx_last_7d",
    "tx_accel",
    "hist_hourly_tx", "hist_hourly_complaints",
    # spatial
    "complaint_density_10km", "tx_density_10km",
    "nearby_atms_5km", "dist_km_last_complaint",
    "hotspot_freq_30d",
    # financial
    "avg_tx_amount_7d", "tx_amount_std_7d", "unique_accounts_7d",
    "suspicious_ratio_7d", "mule_inflow_72h",
    # network
    "entity_degree", "connected_accounts", "suspicious_neighbors",
]


def load_raw(data_dir: str) -> dict[str, pd.DataFrame]:
    out = {}
    for name in ("complaints", "accounts", "transactions", "atms", "entities", "relationships"):
        p = os.path.join(data_dir, f"{name}.csv")
        df = pd.read_csv(p)
        out[name] = df
    meta = {}
    mp = os.path.join(data_dir, "meta.json")
    if os.path.exists(mp):
        with open(mp) as f:
            meta = json.load(f)
    out["meta"] = meta
    return out


def _haversine_vec(lat1, lon1, lat2, lon2) -> np.ndarray:
    lat1 = np.asarray(lat1, dtype=float)
    lon1 = np.asarray(lon1, dtype=float)
    lat2 = np.asarray(lat2, dtype=float)
    lon2 = np.asarray(lon2, dtype=float)
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = np.radians(lat2 - lat1)
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


class FeatureContext:
    """Precomputed arrays + maps for fast point-in-time feature computation.

    Build once from the raw data (or from DB-backed DataFrames with the same
    columns), then call `compute(atm_id, window_start)` for any (ATM, window).
    """

    def __init__(self, complaints: pd.DataFrame, transactions: pd.DataFrame,
                 atms: pd.DataFrame, accounts: pd.DataFrame,
                 entities: pd.DataFrame, relationships: pd.DataFrame,
                 origin: pd.Timestamp, days: int):
        complaints = pd.DataFrame(complaints)
        transactions = pd.DataFrame(transactions)
        atms = pd.DataFrame(atms)
        accounts = pd.DataFrame(accounts)
        entities = pd.DataFrame(entities)
        relationships = pd.DataFrame(relationships)

        complaints["timestamp"] = pd.to_datetime(complaints["timestamp"], utc=True).dt.tz_localize(None)
        transactions["timestamp"] = pd.to_datetime(transactions["timestamp"], utc=True).dt.tz_localize(None)
        complaints = complaints.sort_values("timestamp")
        transactions = transactions.sort_values("timestamp")

        if origin.tzinfo is not None:
            origin = origin.tz_convert("UTC").tz_localize(None)
        self.origin = origin
        self.end = origin + pd.Timedelta(days=days)

        # withdrawals (the activity we predict)
        w = transactions[transactions.transaction_type == "ATM_WITHDRAWAL"].copy()
        w = w[w.atm_id.notna() & (w.atm_id.astype(str) != "")]
        w = w[w.status == "SUCCESS"]
        self.withdrawals = w

        # mule / suspicious accounts
        mule_set = set(accounts[accounts.risk_indicator == "HIGH"].account_id)
        inflow = transactions[transactions.transaction_type == "UPI_TRANSFER"].groupby(
            "beneficiary_account_id").size()
        self.suspicious_acc = set(mule_set) | set(inflow[inflow >= 12].index)
        self.mule_set = mule_set

        # graph degrees
        rels = relationships
        deg_src = rels.groupby("source_entity").size()
        deg_tgt = rels.groupby("target_entity").size()
        self.ent_degree = pd.concat([deg_src, deg_tgt]).groupby(level=0).sum()
        ent_atm = entities[entities.entity_type == "ATM"]
        self.atm_ent_map = dict(zip(ent_atm.masked_identifier, ent_atm.entity_id))

        # arrays
        self.comp_t = complaints.timestamp.to_numpy()
        self.comp_lat = complaints.latitude.to_numpy()
        self.comp_lon = complaints.longitude.to_numpy()
        self.tx_t = w.timestamp.to_numpy()
        self.tx_atm = w.atm_id.to_numpy()
        self.tx_lat = w.latitude.to_numpy()
        self.tx_lon = w.longitude.to_numpy()
        self.tx_amt = w.amount.to_numpy()
        self.tx_acc = w.account_id.to_numpy()
        self.atm_t = atms.atm_id.to_numpy()
        self.atm_lat = atms.latitude.to_numpy()
        self.atm_lon = atms.longitude.to_numpy()
        self._atm_coord = {a: (float(la), float(lo)) for a, la, lo in zip(self.atm_t, self.atm_lat, self.atm_lon)}

        # per-ATM daily withdrawal counts (hotspot frequency)
        wd = w.copy()
        wd["day"] = wd.timestamp.dt.floor("D")
        wd["atm_day"] = wd.atm_id + wd.day.astype(str)
        self.atm_day_counts = wd.groupby("atm_day").size().to_dict()
        # per-ATM hourly history
        wd["hour"] = wd.timestamp.dt.hour
        self.hourly_hist = wd.groupby(["atm_id", "hour"]).size().to_dict()

        # per-ATM index of withdrawal rows (fast slicing)
        self._atm_rows: dict[str, np.ndarray] = {}
        for a in np.unique(self.tx_atm):
            self._atm_rows[a] = np.flatnonzero(self.tx_atm == a)

        # timedelta constants
        self.T24 = np.timedelta64(86400, "s")
        self.T72 = np.timedelta64(259200, "s")
        self.T7D = np.timedelta64(604800, "s")

    def atm_ids(self) -> list[str]:
        return list(self.atm_t)

    def windows(self) -> list[pd.Timestamp]:
        idx = pd.date_range(self.origin, self.end, freq="6h")
        return [t for t in idx if t.hour in GRID_HOURS]

    def compute(self, atm_id: str, window_start) -> dict:
        """Point-in-time feature vector for (atm_id, window_start). No leakage."""
        window_start = pd.Timestamp(window_start)
        if window_start.tzinfo is not None:
            window_start = window_start.tz_convert("UTC").tz_localize(None)
        ws = window_start.to_numpy()
        T24, T72, T7D = self.T24, self.T72, self.T7D
        a = str(atm_id)
        alat, alon = self._atm_coord.get(a, (0.0, 0.0))

        idx = self._atm_rows.get(a, np.array([], dtype=int))
        a_t = self.tx_t[idx]
        a_amt = self.tx_amt[idx]
        a_acc = self.tx_acc[idx]

        hour = int(window_start.hour)
        dow = int(window_start.dayofweek)
        weekend = 1 if dow >= 5 else 0

        # temporal
        c24 = int(((self.comp_t >= ws - T24) & (self.comp_t < ws)).sum())
        c72 = int(((self.comp_t >= ws - T72) & (self.comp_t < ws)).sum())
        c7d = int(((self.comp_t >= ws - T7D) & (self.comp_t < ws)).sum())
        c_prev24 = int(((self.comp_t >= ws - 2 * T24) & (self.comp_t < ws - T24)).sum())
        t24 = int(((a_t >= ws - T24) & (a_t < ws)).sum())
        t72 = int(((a_t >= ws - T72) & (a_t < ws)).sum())
        t7d = int(((a_t >= ws - T7D) & (a_t < ws)).sum())
        t_prev24 = int(((a_t >= ws - 2 * T24) & (a_t < ws - T24)).sum())

        # spatial
        dcomp = _haversine_vec(alat, alon, self.comp_lat, self.comp_lon)
        c10 = int(((dcomp <= 10) & (self.comp_t >= ws - T72) & (self.comp_t < ws)).sum())
        dtx = _haversine_vec(alat, alon, self.tx_lat, self.tx_lon)
        t10 = int(((dtx <= 10) & (self.tx_t >= ws - T72) & (self.tx_t < ws)).sum())
        datm = _haversine_vec(alat, alon, self.atm_lat, self.atm_lon)
        n_atm = int((datm <= 5).sum()) - 1
        before_idx = np.flatnonzero(self.comp_t < ws)
        if len(before_idx) > 0:
            bi = int(before_idx[-1])
            dist_last = float(_haversine_vec(alat, alon, self.comp_lat[bi:bi + 1], self.comp_lon[bi:bi + 1])[0])
        else:
            dist_last = 25.0
        hf = 0
        for d in range(30):
            day_key = pd.Timestamp(ws) - pd.Timedelta(days=d)
            hf += self.atm_day_counts.get(f"{a}{day_key}", 0)

        # financial
        f7 = (a_t >= ws - T7D) & (a_t < ws)
        if f7.sum() > 0:
            avg_amt = float(a_amt[f7].mean())
            amt_std = float(a_amt[f7].std(ddof=0))
            uniq_acc = int(len(np.unique(a_acc[f7])))
            susp_ratio = float(np.isin(a_acc[f7], list(self.suspicious_acc)).mean())
        else:
            avg_amt, amt_std, uniq_acc, susp_ratio = 0.0, 0.0, 0, 0.0
        m72 = (self.tx_t >= ws - T72) & (self.tx_t < ws)
        mule_inflow = int((np.isin(self.tx_acc[m72], list(self.mule_set)) & (dtx[m72] <= 10)).sum())

        # network
        degree = int(self.ent_degree.get(self.atm_ent_map.get(a, a), 0))
        f30 = (a_t >= ws - T7D * 4) & (a_t < ws)
        conn_acc = int(len(np.unique(a_acc[f30]))) if f30.any() else 0
        if f30.any():
            susp_mask = np.isin(a_acc[f30], list(self.suspicious_acc))
            susp_neigh = int(len(np.unique(a_acc[f30][susp_mask])))
        else:
            susp_neigh = 0

        return {
            "atm_id": a,
            "window_start": window_start,
            "window_end": window_start + pd.Timedelta(hours=WINDOW_HOURS),
            "hour_of_day": hour,
            "day_of_week": dow,
            "is_weekend": weekend,
            "complaints_last_24h": c24,
            "complaints_last_72h": c72,
            "complaints_last_7d": c7d,
            "complaint_accel": c24 - c_prev24,
            "tx_last_24h": t24,
            "tx_last_72h": t72,
            "tx_last_7d": t7d,
            "tx_accel": t24 - t_prev24,
            "hist_hourly_tx": float(self.hourly_hist.get((a, hour), 0)),
            "hist_hourly_complaints": float(c7d),
            "complaint_density_10km": c10,
            "tx_density_10km": t10,
            "nearby_atms_5km": n_atm,
            "dist_km_last_complaint": dist_last,
            "hotspot_freq_30d": hf,
            "avg_tx_amount_7d": avg_amt,
            "tx_amount_std_7d": amt_std,
            "unique_accounts_7d": uniq_acc,
            "suspicious_ratio_7d": susp_ratio,
            "mule_inflow_72h": mule_inflow,
            "entity_degree": degree,
            "connected_accounts": conn_acc,
            "suspicious_neighbors": susp_neigh,
        }

    def label(self, atm_id: str, window_start) -> int:
        """Ground-truth label (used only for evaluation, never as a feature)."""
        window_start = pd.Timestamp(window_start)
        if window_start.tzinfo is not None:
            window_start = window_start.tz_convert("UTC").tz_localize(None)
        ws = window_start.to_numpy()
        we = window_start.to_numpy() + np.timedelta64(WINDOW_HOURS, "h")
        idx = self._atm_rows.get(str(atm_id), np.array([], dtype=int))
        a_t = self.tx_t[idx]
        return int(((a_t >= ws) & (a_t < we)).sum() >= LABEL_THRESHOLD)


def build_prediction_units(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Build the (ATM, 6h window) prediction unit with point-in-time features."""
    origin = pd.Timestamp(data["meta"]["origin"])
    days = int(data["meta"]["days"])
    ctx = FeatureContext(
        data["complaints"], data["transactions"], data["atms"],
        data["accounts"], data["entities"], data["relationships"],
        origin, days,
    )
    rows = []
    for a in ctx.atm_ids():
        for ws in ctx.windows():
            row = ctx.compute(a, ws)
            row["y"] = ctx.label(a, ws)
            rows.append(row)
    units = pd.DataFrame(rows)
    return units


def split_units(units: pd.DataFrame, train_frac=0.6, val_frac=0.2) -> dict[str, pd.DataFrame]:
    """Time-based split (no shuffling — preserves temporal order)."""
    units = units.sort_values("window_start").reset_index(drop=True)
    n = len(units)
    t_end = int(n * train_frac)
    v_end = int(n * (train_frac + val_frac))
    return {
        "train": units.iloc[:t_end],
        "val": units.iloc[t_end:v_end],
        "test": units.iloc[v_end:],
    }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw")
    ap.add_argument("--out", default="data/processed/prediction_units.csv")
    args = ap.parse_args()
    data = load_raw(args.data)
    units = build_prediction_units(data)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    units.to_csv(args.out, index=False)
    print(f"Built {len(units)} prediction units; positive rate = {units.y.mean():.3f}")