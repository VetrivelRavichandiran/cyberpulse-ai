"""CYBERPULSE AI — predictions router."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.security import ANALYST_ROLES, get_current_user
from ..database import get_db
from ..models import ATM, Prediction, User
from ..schemas import GenerateRequest, PredictionOut
from ..services.audit import audit
from ..services.prediction_service import PredictionService

logger = logging.getLogger("cyberpulse.predictions")
router = APIRouter(prefix="/predictions", tags=["predictions"])


def _next_window(now: datetime | None = None) -> datetime:
    """Next 6h grid window start (00/06/12/18)."""
    now = now or datetime.now(timezone.utc)
    h = (now.hour // 6) * 6
    ws = now.replace(hour=h, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    if ws <= now:
        ws += timedelta(hours=6)
    return ws


@router.get("", response_model=list[PredictionOut])
def list_predictions(
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    min_risk: int = Query(0, ge=0, le=100),
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    rows = db.execute(
        select(Prediction).where(Prediction.risk_score >= min_risk)
        .order_by(Prediction.risk_score.desc(), Prediction.created_at.desc())
        .limit(limit).offset(offset)
    ).scalars().all()
    return rows


@router.get("/hotspots", response_model=list[PredictionOut])
def hotspots(
    limit: int = Query(20, le=100),
    min_risk: int = Query(61, ge=0, le=100),
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    rows = db.execute(
        select(Prediction).where(Prediction.risk_score >= min_risk)
        .order_by(Prediction.risk_score.desc()).limit(limit)
    ).scalars().all()
    # dedupe per ATM (keep max)
    best: dict[str, Prediction] = {}
    for p in rows:
        if p.atm_id not in best or p.risk_score > best[p.atm_id].risk_score:
            best[p.atm_id] = p
    return sorted(best.values(), key=lambda p: -p.risk_score)


@router.get("/{prediction_id}", response_model=PredictionOut)
def get_prediction(prediction_id: str, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    p = db.execute(select(Prediction).where(Prediction.prediction_id == prediction_id)).scalar_one_or_none()
    if p is None:
        raise HTTPException(404, "Prediction not found")
    audit(db, _user.username, "PREDICTION_VIEWED", resource=prediction_id)
    return p


def _run_generation(username: str, ws: datetime):
    """Background worker: score all ATMs, persist, auto-alert, broadcast."""
    from ..database import SessionLocal
    from ..alerts.service import create_alert_from_prediction

    db = SessionLocal()
    try:
        svc = PredictionService(db)
        if not svc.svc.loaded:
            try:
                from ..realtime.hub import hub
                hub.broadcast_sync({"type": "predictions_error",
                                    "payload": {"error": "Model not loaded"}})
            except Exception:
                pass
            return
        preds = svc.predict_all(ws, persist=True, min_risk=0)
        alerts_created = 0
        for p in preds:
            if create_alert_from_prediction(db, p) is not None:
                alerts_created += 1
        audit(db, username, "PREDICTIONS_GENERATED",
              resource=f"window={ws.isoformat()}", detail=f"n={len(preds)} alerts={alerts_created}")
        try:
            from ..realtime.hub import hub
            hub.broadcast_sync({
                "type": "predictions_generated",
                "payload": {
                    "window_start": ws.isoformat(),
                    "n_predictions": len(preds),
                    "alerts_created": alerts_created,
                    "top": [
                        {"prediction_id": p.prediction_id, "atm_id": p.atm_id,
                         "risk_score": p.risk_score, "district": p.district}
                        for p in sorted(preds, key=lambda x: -x.risk_score)[:5]
                    ],
                },
            })
        except Exception:
            pass
    except Exception as e:
        logger.exception("prediction generation failed")
        try:
            from ..realtime.hub import hub
            hub.broadcast_sync({"type": "predictions_error", "payload": {"error": str(e)}})
        except Exception:
            pass
    finally:
        db.close()


@router.post("/generate")
def generate(req: GenerateRequest, background: BackgroundTasks,
             db: Session = Depends(get_db), user: User = Depends(ANALYST_ROLES)):
    """Kick off the live prediction pipeline for all active ATMs at a window.

    Runs in the background (scoring 250+ ATMs + SHAP + persistence takes a
    while) and streams the result over the realtime WebSocket as a
    `predictions_generated` event. This is the real model — not canned data.
    """
    from ml.inference.service import get_service
    if not get_service().loaded:
        raise HTTPException(503, "Prediction service unavailable: model not loaded")

    ws = req.window_start or _next_window()
    ws = ws.replace(tzinfo=timezone.utc) if ws.tzinfo is None else ws
    background.add_task(_run_generation, user.username, ws)
    return {"status": "started", "window_start": ws.isoformat(),
            "message": "Prediction pipeline running — watch the event stream"}