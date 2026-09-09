"""CYBERPULSE AI — dashboard router (all metrics computed from the DB)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth.security import get_current_user
from ..database import get_db
from ..models import Alert, AlertStatus, ATM, Complaint, Investigation, InvestigationStatus, Prediction, Transaction

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _active(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    active_alerts = db.query(func.count(Alert.id)).filter(
        Alert.status.in_([AlertStatus.NEW, AlertStatus.ACKNOWLEDGED, AlertStatus.INVESTIGATING, AlertStatus.ESCALATED])
    ).scalar()
    critical = db.query(func.count(Alert.id)).filter(
        Alert.risk_score >= 81,
        Alert.status.in_([AlertStatus.NEW, AlertStatus.ACKNOWLEDGED, AlertStatus.INVESTIGATING, AlertStatus.ESCALATED]),
    ).scalar()
    high = db.query(func.count(Alert.id)).filter(
        Alert.risk_score.between(61, 80),
        Alert.status.in_([AlertStatus.NEW, AlertStatus.ACKNOWLEDGED, AlertStatus.INVESTIGATING, AlertStatus.ESCALATED]),
    ).scalar()
    predicted = db.query(func.count(Prediction.id)).filter(Prediction.risk_score >= 61).scalar()
    avg_risk = db.query(func.avg(Prediction.risk_score)).scalar() or 0
    open_cases = db.query(func.count(Investigation.id)).filter(
        Investigation.status.in_([InvestigationStatus.OPEN, InvestigationStatus.IN_PROGRESS, InvestigationStatus.ESCALATED])
    ).scalar()
    complaints_24h = db.query(func.count(Complaint.id)).filter(Complaint.timestamp >= day_ago).scalar()
    tx_24h = db.query(func.count(Transaction.id)).filter(Transaction.timestamp >= day_ago).scalar()
    # response time: avg minutes from alert creation to first status change (acknowledged/after)
    resp = db.query(func.avg(Alert.updated_at - Alert.created_at)).filter(
        Alert.status.in_([AlertStatus.ACKNOWLEDGED, AlertStatus.INVESTIGATING, AlertStatus.ESCALATED, AlertStatus.RESOLVED])
    ).scalar()
    response_min = round(resp.total_seconds() / 60, 1) if resp else None

    return {
        "active_threats": int(active_alerts + open_cases),
        "critical_hotspots": int(critical),
        "high_risk": int(high),
        "predicted_events": int(predicted),
        "active_alerts": int(active_alerts),
        "average_risk": round(float(avg_risk), 1),
        "open_investigations": int(open_cases),
        "complaints_24h": int(complaints_24h),
        "transactions_24h": int(tx_24h),
        "avg_response_minutes": response_min,
        "as_of": now.isoformat(),
    }


@router.get("/summary")
def summary(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return _active(db)


@router.get("/risk-trend")
def risk_trend(days: int = 14, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    """Average predicted risk per day (from persisted predictions)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(
            func.date(Prediction.window_start).label("d"),
            func.avg(Prediction.risk_score).label("avg_risk"),
            func.max(Prediction.risk_score).label("max_risk"),
            func.count(Prediction.id).label("n"),
        )
        .where(Prediction.window_start >= since)
        .group_by("d").order_by("d")
    ).all()
    return [{"date": str(r.d), "avg_risk": round(float(r.avg_risk), 1),
             "max_risk": int(r.max_risk), "predictions": int(r.n)} for r in rows]


@router.get("/complaint-trend")
def complaint_trend(days: int = 30, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(func.date(Complaint.timestamp).label("d"), func.count(Complaint.id))
        .where(Complaint.timestamp >= since).group_by("d").order_by("d")
    ).all()
    return [{"date": str(r.d), "count": int(r[1])} for r in rows]


@router.get("/transaction-activity")
def transaction_activity(days: int = 30, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(func.date(Transaction.timestamp).label("d"),
               func.count(Transaction.id),
               func.sum(Transaction.amount))
        .where(Transaction.timestamp >= since).group_by("d").order_by("d")
    ).all()
    return [{"date": str(r.d), "count": int(r[1]), "amount": round(float(r[2] or 0), 2)} for r in rows]


@router.get("/alert-status")
def alert_status(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    rows = db.execute(select(Alert.status, func.count(Alert.id)).group_by(Alert.status)).all()
    return [{"status": s.value, "count": int(c)} for s, c in rows]


@router.get("/district-risk")
def district_risk(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    """Average risk per district from predictions + complaint counts."""
    rows = db.execute(
        select(Prediction.district, func.avg(Prediction.risk_score), func.max(Prediction.risk_score),
               func.count(Prediction.id))
        .where(Prediction.district.isnot(None))
        .group_by(Prediction.district).order_by(func.avg(Prediction.risk_score).desc())
    ).all()
    out = []
    for d, avg, mx, n in rows:
        c = db.query(func.count(Complaint.id)).filter(Complaint.victim_district == d).scalar()
        out.append({"district": d, "avg_risk": round(float(avg), 1), "max_risk": int(mx),
                    "predictions": int(n), "complaints": int(c)})
    return out


@router.get("/hotspot-evolution")
def hotspot_evolution(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    """Count of high-risk (>=61) predictions per day — shows hotspots emerging."""
    rows = db.execute(
        select(func.date(Prediction.window_start).label("d"), func.count(Prediction.id))
        .where(Prediction.risk_score >= 61)
        .group_by("d").order_by("d")
    ).all()
    return [{"date": str(r.d), "hotspots": int(r[1])} for r in rows]