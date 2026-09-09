"""CYBERPULSE AI — alerts router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.security import ANALYST_ROLES, get_current_user
from ..database import get_db
from ..models import Alert, AlertStatus, User
from ..schemas import AlertActionRequest, AlertOut
from ..alerts.service import transition

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _get(db: Session, alert_id: str) -> Alert:
    a = db.execute(select(Alert).where(Alert.alert_id == alert_id)).scalar_one_or_none()
    if a is None:
        raise HTTPException(404, "Alert not found")
    return a


@router.get("", response_model=list[AlertOut])
def list_alerts(
    status: str | None = None,
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    q = select(Alert).order_by(Alert.created_at.desc())
    if status:
        try:
            q = q.where(Alert.status == AlertStatus(status))
        except ValueError:
            raise HTTPException(400, f"Invalid status '{status}'")
    rows = db.execute(q.limit(limit).offset(offset)).scalars().all()
    return rows


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: str, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return _get(db, alert_id)


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge(alert_id: str, req: AlertActionRequest | None = None,
                db: Session = Depends(get_db), user: User = Depends(ANALYST_ROLES)):
    a = _get(db, alert_id)
    if a.status not in (AlertStatus.NEW,):
        raise HTTPException(409, f"Alert is {a.status.value}; only NEW alerts can be acknowledged")
    return transition(db, a, AlertStatus.ACKNOWLEDGED, user.username,
                      assigned_to=(req.assigned_to if req else None) or user.username)


@router.post("/{alert_id}/escalate", response_model=AlertOut)
def escalate(alert_id: str, req: AlertActionRequest | None = None,
             db: Session = Depends(get_db), user: User = Depends(ANALYST_ROLES)):
    a = _get(db, alert_id)
    if a.status == AlertStatus.RESOLVED:
        raise HTTPException(409, "Resolved alerts cannot be escalated")
    return transition(db, a, AlertStatus.ESCALATED, user.username,
                      assigned_to=(req.assigned_to if req else None) or user.username)


@router.post("/{alert_id}/resolve", response_model=AlertOut)
def resolve(alert_id: str, req: AlertActionRequest | None = None,
            db: Session = Depends(get_db), user: User = Depends(ANALYST_ROLES)):
    a = _get(db, alert_id)
    return transition(db, a, AlertStatus.RESOLVED, user.username,
                      assigned_to=(req.assigned_to if req else None) or user.username)