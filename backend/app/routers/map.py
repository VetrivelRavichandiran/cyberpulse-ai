"""CYBERPULSE AI — GIS / map router (GeoJSON APIs).

Spatial filtering uses haversine on (lat, lon) so the demo runs on SQLite;
the same endpoints serve ST_DWithin/ST_MakePoint queries on PostgreSQL
PostGIS (see docs/database.md).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.security import get_current_user
from ..database import get_db
from ..models import ATM, Complaint, Prediction, Transaction

router = APIRouter(prefix="/map", tags=["map"])


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _geojson(points: list[dict], props_key: str) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [p["longitude"], p["latitude"]]},
             "properties": p[props_key]}
            for p in points
        ],
    }


@router.get("/complaints")
def complaints_geo(
    days: int = Query(30, le=90),
    lat: float | None = None, lon: float | None = None,
    radius_km: float | None = Query(None, le=100),
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(select(Complaint).where(Complaint.timestamp >= since)).scalars().all()
    pts = []
    for c in rows:
        if lat is not None and lon is not None and radius_km:
            if _haversine_km(lat, lon, c.latitude, c.longitude) > radius_km:
                continue
        pts.append({"latitude": c.latitude, "longitude": c.longitude, "p": {
            "complaint_id": c.complaint_id, "timestamp": c.timestamp.isoformat(),
            "crime_category": c.crime_category, "victim_district": c.victim_district,
            "reported_amount": c.reported_amount, "status": c.status.value,
        }})
    return _geojson(pts, "p")


@router.get("/atms")
def atms_geo(
    district: str | None = None,
    lat: float | None = None, lon: float | None = None,
    radius_km: float | None = Query(None, le=100),
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    q = select(ATM).where(ATM.active.is_(True))
    if district:
        q = q.where(ATM.district == district)
    rows = db.execute(q).scalars().all()
    pts = []
    for a in rows:
        if lat is not None and lon is not None and radius_km:
            if _haversine_km(lat, lon, a.latitude, a.longitude) > radius_km:
                continue
        pts.append({"latitude": a.latitude, "longitude": a.longitude, "p": {
            "atm_id": a.atm_id, "bank_id": a.bank_id, "district": a.district,
        }})
    return _geojson(pts, "p")


@router.get("/hotspots")
def hotspots_geo(
    min_risk: int = Query(61, ge=0, le=100),
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    """Top predicted hotspots (deduped per ATM, max risk)."""
    rows = db.execute(
        select(Prediction).where(Prediction.risk_score >= min_risk)
        .order_by(Prediction.risk_score.desc()).limit(200)
    ).scalars().all()
    best: dict[str, Prediction] = {}
    for p in rows:
        if p.atm_id not in best or p.risk_score > best[p.atm_id].risk_score:
            best[p.atm_id] = p
    pts = []
    for p in best.values():
        pts.append({"latitude": p.latitude, "longitude": p.longitude, "p": {
            "prediction_id": p.prediction_id, "atm_id": p.atm_id,
            "risk_score": p.risk_score, "probability": round(p.probability, 3),
            "confidence": round(p.confidence, 2), "district": p.district,
            "window_start": p.window_start.isoformat(), "window_end": p.window_end.isoformat(),
        }})
    return _geojson(pts, "p")


@router.get("/risk-zones")
def risk_zones(
    min_risk: int = Query(61, ge=0, le=100),
    radius_km: float = Query(2.5, le=20),
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    """Circles around high-risk hotspots (radius search visualization)."""
    rows = db.execute(
        select(Prediction).where(Prediction.risk_score >= min_risk).limit(200)
    ).scalars().all()
    best: dict[str, Prediction] = {}
    for p in rows:
        if p.atm_id not in best or p.risk_score > best[p.atm_id].risk_score:
            best[p.atm_id] = p
    features = []
    for p in best.values():
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [p.longitude, p.latitude]},
            "properties": {
                "atm_id": p.atm_id, "risk_score": p.risk_score,
                "radius_km": radius_km, "district": p.district,
            },
        })
    return {"type": "FeatureCollection", "features": features}


@router.get("/withdrawals")
def withdrawals_geo(
    days: int = Query(7, le=60),
    lat: float | None = None, lon: float | None = None,
    radius_km: float | None = Query(None, le=100),
    limit: int = Query(2000, le=10000),
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = (select(Transaction)
         .where(Transaction.transaction_type == "ATM_WITHDRAWAL",
                Transaction.timestamp >= since, Transaction.atm_id.isnot(None))
         .order_by(Transaction.timestamp.desc()).limit(limit))
    rows = db.execute(q).scalars().all()
    pts = []
    for t in rows:
        if t.latitude is None or t.longitude is None:
            continue
        if lat is not None and lon is not None and radius_km:
            if _haversine_km(lat, lon, t.latitude, t.longitude) > radius_km:
                continue
        pts.append({"latitude": t.latitude, "longitude": t.longitude, "p": {
            "transaction_id": t.transaction_id, "timestamp": t.timestamp.isoformat(),
            "amount": t.amount, "atm_id": t.atm_id,
        }})
    return _geojson(pts, "p")


@router.get("/nearby")
def nearby(
    lat: float, lon: float,
    radius_km: float = Query(10, le=100),
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    """Radius search: complaints, ATMs, withdrawals within radius."""
    def in_r(c_lat, c_lon):
        return c_lat is not None and c_lon is not None and _haversine_km(lat, lon, c_lat, c_lon) <= radius_km

    comps = db.execute(select(Complaint)).scalars().all()
    atms = db.execute(select(ATM)).scalars().all()
    txs = db.execute(select(Transaction).where(Transaction.transaction_type == "ATM_WITHDRAWAL")).scalars().all()
    return {
        "center": {"lat": lat, "lon": lon},
        "radius_km": radius_km,
        "complaints": [
            {"complaint_id": c.complaint_id, "timestamp": c.timestamp.isoformat(),
             "crime_category": c.crime_category, "distance_km": round(_haversine_km(lat, lon, c.latitude, c.longitude), 2)}
            for c in comps if in_r(c.latitude, c.longitude)
        ],
        "atms": [
            {"atm_id": a.atm_id, "distance_km": round(_haversine_km(lat, lon, a.latitude, a.longitude), 2)}
            for a in atms if in_r(a.latitude, a.longitude)
        ],
        "withdrawals": [
            {"transaction_id": t.transaction_id, "amount": t.amount, "atm_id": t.atm_id,
             "timestamp": t.timestamp.isoformat(),
             "distance_km": round(_haversine_km(lat, lon, t.latitude, t.longitude), 2)}
            for t in txs if in_r(t.latitude, t.longitude)
        ],
    }