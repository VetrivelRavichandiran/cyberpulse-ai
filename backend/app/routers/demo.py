"""CYBERPULSE AI — demo router: reset + scripted live-demo scenario.

POST /demo/reset  → restore a clean demo state (re-seed DB, clear derived state)
POST /demo/run    → run the staged live-demo scenario end-to-end:
    normal activity → complaint surge → transaction surge → risk increase →
    hotspot prediction → alert → (investigation/alerts handled via API by the UI)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.security import get_current_user
from ..config import get_settings
from ..database import get_db
from ..models import (
    Alert,
    AuditLog,
    Complaint,
    ComplaintStatus,
    Entity,
    EntityRelationship,
    Investigation,
    Notification,
    Prediction,
    PredictionFactor,
    Transaction,
    User,
)
from ..realtime.hub import hub

logger = logging.getLogger("cyberpulse.demo")
router = APIRouter(prefix="/demo", tags=["demo"])


def _broadcast(msg: dict):
    try:
        hub.broadcast_sync(msg)
    except Exception:
        pass


@router.post("/reset")
def demo_reset(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    """Reset derived state (predictions, alerts, investigations, audit, notifications).

    Re-runs the prediction pipeline for the current window so the map shows a
    fresh, model-generated baseline.
    """
    from ..services.audit import audit
    from ..models import TimelineEvent, InvestigationNote, Intervention
    # delete children before parents (FK order)
    for model in (TimelineEvent, InvestigationNote, Intervention, Investigation,
                  Alert, PredictionFactor, Prediction, Notification, AuditLog):
        db.query(model).delete()
    db.commit()

    # regenerate baseline predictions for the next window (real model)
    from ..routers.predictions import _next_window
    from ..services.prediction_service import PredictionService
    from ..alerts.service import create_alert_from_prediction
    ws = _next_window()
    svc = PredictionService(db)
    preds = svc.predict_all(ws, persist=True, min_risk=0)
    n_alerts = sum(1 for p in preds if create_alert_from_prediction(db, p) is not None)
    audit(db, _user.username, "DEMO_RESET", detail=f"preds={len(preds)} alerts={n_alerts}")
    _broadcast({"type": "demo_reset", "payload": {"predictions": len(preds), "alerts": n_alerts}})
    return {
        "status": "ok",
        "counts": {
            "predictions": len(preds),
            "alerts": n_alerts,
            "complaints": db.query(Complaint).count(),
            "transactions": db.query(Transaction).count(),
        },
    }


@router.post("/run")
def demo_run(
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Kick off the staged live-demo scenario (runs in background, streams events)."""
    background.add_task(_run_demo_scenario, user.username)
    return {"status": "started", "message": "Demo scenario running — watch the event stream"}


def _run_demo_scenario(username: str):
    """Staged scenario: complaint surge → tx surge → risk up → hotspot → alert.

    Uses a real FeatureContext + the real model. Injects synthetic-but-real
    rows into the DB (marked ring_id='DEMO') so the model sees genuine signal.
    """
    from ..database import SessionLocal
    from ..models import ATM
    from ..services.prediction_service import PredictionService
    from ..alerts.service import create_alert_from_prediction
    from ..services.audit import audit

    db = SessionLocal()
    try:
        s = get_settings()
        now = datetime.now(timezone.utc)
        ws = (now + timedelta(hours=6)).replace(minute=0, second=0, microsecond=0)
        # pick a target ATM in a busy district
        atm = db.execute(select(ATM).where(ATM.active.is_(True)).limit(300)).scalars().all()
        # choose the ATM with the most recent withdrawals (a plausible hotspot)
        from sqlalchemy import func
        target = db.execute(
            select(ATM.atm_id).select_from(Transaction)
            .where(Transaction.atm_id.isnot(None))
            .group_by(ATM.atm_id).order_by(func.count(Transaction.id).desc()).limit(1)
        ).scalar_one()
        atm_obj = db.execute(select(ATM).where(ATM.atm_id == target)).scalar_one()
        ring = "DEMO"

        def stage(name: str, detail: str):
            _broadcast({"type": "demo_stage", "payload": {"stage": name, "detail": detail}})

        stage("normal", "Baseline activity — system monitoring")

        # Stage 2: complaint surge near the target ATM
        stage("complaint_surge", "New cybercrime complaints entering the system")
        n_comp = 0
        for i in range(14):
            c = Complaint(
                complaint_id=f"CMP-DEMO{uuid.uuid4().hex[:6].upper()}",
                timestamp=now - timedelta(hours=2 - i * 0.1),
                crime_category="UPI_FRAUD" if i % 2 == 0 else "BANKING_FRAUD",
                subcategory="synthetic-demo",
                victim_state=atm_obj.state,
                victim_district=atm_obj.district,
                latitude=atm_obj.latitude + (i % 5) * 0.004 - 0.008,
                longitude=atm_obj.longitude + (i % 3) * 0.005 - 0.005,
                reported_amount=15000 + i * 2500,
                phone_hash=f"ENT-DEMO{i:03d}",
                status=ComplaintStatus.NEW,
                ring_id=ring,
            )
            db.add(c)
            n_comp += 1
        db.commit()
        _broadcast({"type": "complaints_added", "payload": {"count": n_comp, "district": atm_obj.district}})

        # Stage 3: related transactions (UPI inflow + recon withdrawals)
        stage("transaction_surge", "Related transactions detected — funds aggregation")
        n_tx = 0
        for i in range(22):
            t = Transaction(
                transaction_id=f"TXN-DEMO{uuid.uuid4().hex[:8].upper()}",
                timestamp=now - timedelta(hours=1.5 - i * 0.05),
                account_id=f"ACC-DEMO{i % 6:04d}",
                beneficiary_account_id=f"ACC-MULE{i % 4:04d}" if i < 12 else None,
                amount=8000 + (i % 10) * 3000,
                transaction_type="ATM_WITHDRAWAL" if i >= 12 else "UPI_TRANSFER",
                latitude=atm_obj.latitude,
                longitude=atm_obj.longitude,
                atm_id=atm_obj.atm_id if i >= 12 else None,
                status="SUCCESS",
                ring_id=ring,
            )
            db.add(t)
            n_tx += 1
        db.commit()
        _broadcast({"type": "transactions_added", "payload": {"count": n_tx, "atm_id": atm_obj.atm_id}})

        # Stage 4: graph relationships increase
        stage("graph_increase", "Graph relationships forming between entities")
        _broadcast({"type": "graph_updated", "payload": {"atm_id": atm_obj.atm_id, "new_edges": n_tx}})

        # Stage 5: run the real model for the next window
        stage("risk_increasing", "AI detecting increasing risk — running prediction pipeline")
        svc = PredictionService(db)
        preds = svc.predict_all(ws, persist=True, min_risk=0)
        top = sorted(preds, key=lambda p: -p.risk_score)[:5]
        _broadcast({"type": "predictions_generated", "payload": {
            "window_start": ws.isoformat(), "n_predictions": len(preds),
            "top": [{"prediction_id": p.prediction_id, "atm_id": p.atm_id,
                     "risk_score": p.risk_score, "district": p.district} for p in top],
        }})

        # Stage 6: hotspot appears
        hotspot = next((p for p in top if p.atm_id == atm_obj.atm_id), top[0] if top else None)
        if hotspot:
            stage("hotspot", f"Predicted hotspot: {hotspot.atm_id} risk={hotspot.risk_score}")
            _broadcast({"type": "hotspot", "payload": {
                "prediction_id": hotspot.prediction_id, "atm_id": hotspot.atm_id,
                "risk_score": hotspot.risk_score, "probability": round(hotspot.probability, 3),
                "district": hotspot.district, "window_start": ws.isoformat(),
            }})

            # Stage 7: alert
            alert = create_alert_from_prediction(db, hotspot)
            if alert:
                stage("alert", f"Critical alert {alert.alert_id} issued")
                _broadcast({"type": "alert_created", "payload": {
                    "alert_id": alert.alert_id, "severity": alert.severity.value,
                    "risk_score": alert.risk_score, "atm_id": alert.atm_id,
                }})
        audit(db, username, "DEMO_RUN", detail=f"atm={atm_obj.atm_id} comps={n_comp} txs={n_tx}")
        stage("complete", "Demo scenario complete — acknowledge the alert to open an investigation")
    except Exception as e:
        logger.exception("demo scenario failed")
        _broadcast({"type": "demo_error", "payload": {"error": str(e)}})
    finally:
        db.close()