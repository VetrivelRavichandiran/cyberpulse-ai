"""CYBERPULSE AI — what-if simulation router.

Takes user-adjusted activity parameters, recomputes the feature vector for a
chosen (ATM, window) with those multipliers applied, and runs the SAME model
to produce a simulated risk. Clearly labeled as simulation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.security import get_current_user
from ..database import get_db
from ..services.anomaly import get_detector
from ml.inference.service import get_service
from ..models import ATM, User
from ..schemas import WhatIfRequest, WhatIfResponse
from ..services.audit import audit
from ..services.prediction_service import PredictionService, _recommended_action, risk_band

router = APIRouter(prefix="/simulation", tags=["simulation"])


def _next_window(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    h = (now.hour // 6) * 6
    ws = now.replace(hour=h, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    if ws <= now:
        ws += timedelta(hours=6)
    return ws


def _scores_from_features(feat: dict) -> tuple[float, float, float]:
    conn = max(feat.get("connected_accounts", 0), 1)
    susp_ratio = feat.get("suspicious_neighbors", 0) / conn
    mule = min(feat.get("mule_inflow_72h", 0) / 5.0, 1.0)
    degree = min(feat.get("entity_degree", 0) / 20.0, 1.0)
    graph = float(min(0.5 * susp_ratio + 0.3 * mule + 0.2 * degree, 1.0))
    accel = min(max(feat.get("complaint_accel", 0), 0) / 8.0, 1.0)
    vol = min(feat.get("complaints_last_24h", 0) / 10.0, 1.0)
    temporal = float(min(0.6 * accel + 0.4 * vol, 1.0))
    hist = min(feat.get("hotspot_freq_30d", 0) / 40.0, 1.0)
    return graph, temporal, hist


@router.post("/what-if", response_model=WhatIfResponse)
def what_if(req: WhatIfRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    atm = db.execute(select(ATM).where(ATM.atm_id == req.atm_id)).scalar_one_or_none()
    if atm is None:
        raise HTTPException(404, "ATM not found")
    ws = req.window_start or _next_window()
    ws = ws.replace(tzinfo=timezone.utc) if ws.tzinfo is None else ws

    ps = PredictionService(db)
    svc = ps.svc
    if not svc.loaded:
        raise HTTPException(503, "Model not loaded")
    detector = get_detector()
    ctx = ps.build_context()
    base = ctx.compute(atm.atm_id, ws)

    # current
    g, t, h = _scores_from_features(base)
    a = detector.score(base) if detector.fitted else 0.0
    cur = svc.predict(base, anomaly_score=a, graph_score=g, temporal_score=t, history_score=h)

    # simulated: apply multipliers to activity features
    sim = dict(base)
    for k in ("complaints_last_24h", "complaints_last_72h", "complaints_last_7d"):
        sim[k] = base[k] * req.complaint_volume
    sim["complaint_accel"] = max(sim["complaints_last_24h"] - base["complaints_last_24h"], 0)
    for k in ("tx_last_24h", "tx_last_72h", "tx_last_7d"):
        sim[k] = base[k] * req.transaction_intensity
    sim["tx_accel"] = max(sim["tx_last_24h"] - base["tx_last_24h"], 0)
    # radius affects density features (scale by radius ratio vs 10km baseline)
    radius_scale = (req.geographic_radius_km / 10.0) ** 2
    sim["complaint_density_10km"] = base["complaint_density_10km"] * radius_scale
    sim["tx_density_10km"] = base["tx_density_10km"] * radius_scale
    # time window: longer window accumulates more activity
    tw_scale = req.time_window_hours / 6.0
    sim["tx_last_24h"] = sim["tx_last_24h"] * tw_scale
    sim["complaints_last_24h"] = sim["complaints_last_24h"] * tw_scale

    g2, t2, h2 = _scores_from_features(sim)
    a2 = detector.score(sim) if detector.fitted else 0.0
    simres = svc.predict(sim, anomaly_score=a2, graph_score=g2, temporal_score=t2, history_score=h2)

    audit(db, user.username, "SIMULATION_RUN", resource=req.atm_id,
          detail=f"complaint_vol={req.complaint_volume} tx_int={req.transaction_intensity} "
                 f"radius={req.geographic_radius_km} tw={req.time_window_hours}")
    return WhatIfResponse(
        atm_id=req.atm_id,
        window_start=ws,
        current_risk=cur.risk_score,
        simulated_risk=simres.risk_score,
        difference=simres.risk_score - cur.risk_score,
        current_probability=round(cur.probability, 4),
        simulated_probability=round(simres.probability, 4),
        current_factors=cur.factors,
        simulated_factors=simres.factors,
        label="Simulation",
    )


@router.get("/atms")
def list_atms_for_sim(limit: int = 100, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    rows = db.execute(select(ATM).where(ATM.active.is_(True)).limit(limit)).scalars().all()
    return [{"atm_id": a.atm_id, "district": a.district, "bank_id": a.bank_id} for a in rows]