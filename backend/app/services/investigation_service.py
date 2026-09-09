"""CYBERPULSE AI — investigation workflow service.

Creates cases, manages status transitions, notes, timeline events,
interventions, and outcomes. Everything is database-backed.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import (
    Alert,
    AlertStatus,
    Investigation,
    InvestigationNote,
    InvestigationStatus,
    Intervention,
    Prediction,
    TimelineEvent,
)
from ..alerts.service import transition as alert_transition
from ..services.audit import audit

logger = logging.getLogger("cyberpulse.investigation")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_case_id() -> str:
    return f"CASE-{uuid.uuid4().hex[:10].upper()}"


def create_investigation(db: Session, *, title: str, username: str,
                         alert_id: str | None = None,
                         prediction_id: str | None = None,
                         assigned_to: str | None = None,
                         priority: str = "MEDIUM",
                         district: str | None = None,
                         summary: str | None = None) -> Investigation:
    inv = Investigation(
        case_id=_new_case_id(),
        title=title,
        status=InvestigationStatus.OPEN,
        priority=priority,
        assigned_to=assigned_to or username,
        created_by=username,
        alert_id=alert_id,
        prediction_id=prediction_id,
        district=district,
        summary=summary,
    )
    db.add(inv)
    db.flush()
    _add_timeline(db, inv.case_id, "CASE_CREATED", "Investigation opened",
                  f"Case {inv.case_id} created by {username}.")

    # if linked to an alert, move it to INVESTIGATING
    if alert_id:
        alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
        if alert and alert.status == AlertStatus.ACKNOWLEDGED:
            alert_transition(db, alert, AlertStatus.INVESTIGATING, username,
                             assigned_to=assigned_to or username)
    db.commit()
    db.refresh(inv)
    audit(db, username, "INVESTIGATION_CREATED", resource=inv.case_id,
          detail=f"alert={alert_id} prediction={prediction_id}")
    logger.info("Investigation created: %s", inv.case_id)
    return inv


def _add_timeline(db: Session, case_id: str, event_type: str, title: str,
                  detail: str | None = None, metadata: dict | None = None,
                  occurred_at: datetime | None = None) -> TimelineEvent:
    ev = TimelineEvent(
        case_id=case_id,
        event_type=event_type,
        title=title,
        detail=detail,
        occurred_at=occurred_at or _now(),
        metadata_json=json.dumps(metadata) if metadata else None,
    )
    db.add(ev)
    return ev


def add_note(db: Session, inv: Investigation, author: str, note: str) -> InvestigationNote:
    n = InvestigationNote(case_id=inv.case_id, author=author, note=note)
    db.add(n)
    _add_timeline(db, inv.case_id, "NOTE_ADDED", "Note added", f"By {author}")
    db.commit()
    audit(db, author, "INVESTIGATION_NOTE", resource=inv.case_id)
    return n


def add_intervention(db: Session, inv: Investigation, *, action_type: str,
                     description: str, performed_by: str,
                     outcome: str | None = None) -> Intervention:
    itv = Intervention(
        case_id=inv.case_id,
        action_type=action_type,
        description=description,
        performed_by=performed_by,
        outcome=outcome,
    )
    db.add(itv)
    _add_timeline(db, inv.case_id, "INTERVENTION", f"Intervention: {action_type}",
                  description, metadata={"action_type": action_type})
    db.commit()
    audit(db, performed_by, "INTERVENTION_RECORDED", resource=inv.case_id, detail=action_type)
    return itv


def set_status(db: Session, inv: Investigation, new_status: InvestigationStatus,
               username: str, outcome: str | None = None) -> Investigation:
    inv.status = new_status
    if new_status in (InvestigationStatus.RESOLVED, InvestigationStatus.CLOSED):
        inv.resolved_at = _now()
        if outcome:
            inv.outcome = outcome
        _add_timeline(db, inv.case_id, "CASE_RESOLVED", "Case resolved", outcome)
    elif new_status == InvestigationStatus.ESCALATED:
        _add_timeline(db, inv.case_id, "CASE_ESCALATED", "Case escalated")
    else:
        _add_timeline(db, inv.case_id, "CASE_STATUS", f"Status → {new_status.value}")
    db.commit()
    db.refresh(inv)
    audit(db, username, f"INVESTIGATION_{new_status.value}", resource=inv.case_id)
    return inv


def acknowledge_alert_and_open(db: Session, alert: Alert, username: str,
                               assigned_to: str | None = None) -> Investigation:
    """Acknowledge an alert and open an investigation in one step (demo flow)."""
    alert_transition(db, alert, AlertStatus.ACKNOWLEDGED, username,
                     assigned_to=assigned_to or username)
    pred = None
    if alert.prediction_id:
        pred = db.query(Prediction).filter(Prediction.prediction_id == alert.prediction_id).first()
    title = f"Investigation: {alert.title}"
    inv = create_investigation(
        db, title=title, username=username, alert_id=alert.alert_id,
        prediction_id=alert.prediction_id, assigned_to=assigned_to or username,
        priority="HIGH" if alert.risk_score >= 61 else "MEDIUM",
        district=alert.district,
        summary=alert.detail,
    )
    if alert.status == AlertStatus.ACKNOWLEDGED:
        alert_transition(db, alert, AlertStatus.INVESTIGATING, username,
                         assigned_to=assigned_to or username)
    return inv


def build_timeline(inv: Investigation) -> list[dict]:
    """Assemble the full investigation timeline (DB-backed)."""
    events = sorted(inv.timeline, key=lambda e: e.occurred_at)
    out = []
    for e in events:
        out.append({
            "event_type": e.event_type,
            "title": e.title,
            "detail": e.detail,
            "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
            "metadata": json.loads(e.metadata_json) if e.metadata_json else None,
        })
    return out