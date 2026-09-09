"""CYBERPULSE AI — data routers (complaints / transactions / atms)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.security import get_current_user
from ..database import get_db
from ..models import ATM, Complaint, Transaction
from ..schemas import ATMOut, ComplaintOut, TransactionOut

router = APIRouter(tags=["data"])


@router.get("/complaints", response_model=list[ComplaintOut])
def list_complaints(
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    district: str | None = None,
    days: int = Query(30, le=90),
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = select(Complaint).where(Complaint.timestamp >= since).order_by(Complaint.timestamp.desc())
    if district:
        q = q.where(Complaint.victim_district == district)
    rows = db.execute(q.limit(limit).offset(offset)).scalars().all()
    return rows


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    account_id: str | None = None,
    atm_id: str | None = None,
    ttype: str | None = None,
    days: int = Query(14, le=90),
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = select(Transaction).where(Transaction.timestamp >= since).order_by(Transaction.timestamp.desc())
    if account_id:
        q = q.where(Transaction.account_id == account_id)
    if atm_id:
        q = q.where(Transaction.atm_id == atm_id)
    if ttype:
        q = q.where(Transaction.transaction_type == ttype)
    rows = db.execute(q.limit(limit).offset(offset)).scalars().all()
    return rows


@router.get("/atms", response_model=list[ATMOut])
def list_atms(
    district: str | None = None,
    limit: int = Query(300, le=1000),
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    q = select(ATM).where(ATM.active.is_(True))
    if district:
        q = q.where(ATM.district == district)
    rows = db.execute(q.limit(limit)).scalars().all()
    return rows


@router.get("/districts")
def districts(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    rows = db.execute(select(ATM.district).distinct()).scalars().all()
    return sorted(rows)