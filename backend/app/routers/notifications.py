"""CYBERPULSE AI — notifications & audit routers."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.security import get_current_user
from ..database import get_db
from ..models import AuditLog, Notification, User
from ..schemas import NotificationOut

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    limit: int = Query(50, le=200),
    unread_only: bool = False,
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    q = select(Notification).order_by(Notification.created_at.desc())
    if unread_only:
        q = q.where(Notification.read.is_(False))
    rows = db.execute(q.limit(limit)).scalars().all()
    return rows


@router.post("/notifications/{nid}/read")
def mark_read(nid: int, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    n = db.get(Notification, nid)
    if n is None:
        return {"ok": False}
    n.read = True
    db.commit()
    return {"ok": True}


arouter = APIRouter(prefix="/audit", tags=["audit"])


@arouter.get("")
def list_audit(
    limit: int = Query(100, le=500),
    username: str | None = None,
    action: str | None = None,
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    q = select(AuditLog).order_by(AuditLog.timestamp.desc())
    if username:
        q = q.where(AuditLog.username == username)
    if action:
        q = q.where(AuditLog.action == action)
    rows = db.execute(q.limit(limit)).scalars().all()
    return [
        {"id": a.id, "timestamp": a.timestamp.isoformat(), "username": a.username,
         "action": a.action, "resource": a.resource, "result": a.result, "detail": a.detail}
        for a in rows
    ]