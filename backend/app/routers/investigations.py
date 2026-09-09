"""CYBERPULSE AI — investigations router (workflow + timeline + report)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.security import ANALYST_ROLES, get_current_user
from ..database import get_db
from ..models import (
    Alert,
    AuditLog,
    Investigation,
    InvestigationStatus,
    Prediction,
    User,
)
from ..schemas import (
    AcknowledgeAndOpen,
    InvestigationCreate,
    InvestigationOut,
    InterventionCreate,
    NoteCreate,
    StatusUpdate,
)
from ..services import investigation_service as inv_svc
from ..services.audit import audit
from ..services.report_service import generate_investigation_pdf
from ..graph.service import GraphService

router = APIRouter(prefix="/investigations", tags=["investigations"])


def _get(db: Session, case_id: str) -> Investigation:
    inv = db.execute(select(Investigation).where(Investigation.case_id == case_id)).scalar_one_or_none()
    if inv is None:
        raise HTTPException(404, "Investigation not found")
    return inv


def _to_out(inv: Investigation) -> dict:
    return {
        "case_id": inv.case_id,
        "title": inv.title,
        "status": inv.status.value,
        "priority": inv.priority,
        "assigned_to": inv.assigned_to,
        "created_by": inv.created_by,
        "alert_id": inv.alert_id,
        "prediction_id": inv.prediction_id,
        "district": inv.district,
        "summary": inv.summary,
        "outcome": inv.outcome,
        "created_at": inv.created_at,
        "updated_at": inv.updated_at,
        "resolved_at": inv.resolved_at,
        "notes": [
            {"id": n.id, "author": n.author, "note": n.note,
             "created_at": n.created_at.isoformat()}
            for n in inv.notes
        ],
        "timeline": inv_svc.build_timeline(inv),
        "interventions": [
            {"id": i.id, "action_type": i.action_type, "description": i.description,
             "performed_by": i.performed_by, "outcome": i.outcome,
             "created_at": i.created_at.isoformat()}
            for i in inv.interventions
        ],
    }


@router.get("", response_model=list[InvestigationOut])
def list_investigations(
    status: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    q = select(Investigation).order_by(Investigation.created_at.desc())
    if status:
        try:
            q = q.where(Investigation.status == InvestigationStatus(status))
        except ValueError:
            raise HTTPException(400, f"Invalid status '{status}'")
    rows = db.execute(q.limit(limit).offset(offset)).scalars().all()
    return [_to_out(i) for i in rows]


@router.post("", response_model=InvestigationOut)
def create(req: InvestigationCreate, db: Session = Depends(get_db),
           user: User = Depends(ANALYST_ROLES)):
    inv = inv_svc.create_investigation(
        db, title=req.title, username=user.username, alert_id=req.alert_id,
        prediction_id=req.prediction_id, assigned_to=req.assigned_to,
        priority=req.priority, district=req.district, summary=req.summary,
    )
    return _to_out(inv)


@router.post("/from-alert/{alert_id}", response_model=InvestigationOut)
def from_alert(alert_id: str, req: AcknowledgeAndOpen | None = None,
               db: Session = Depends(get_db), user: User = Depends(ANALYST_ROLES)):
    """Acknowledge an alert and open an investigation in one step."""
    alert = db.execute(select(Alert).where(Alert.alert_id == alert_id)).scalar_one_or_none()
    if alert is None:
        raise HTTPException(404, "Alert not found")
    inv = inv_svc.acknowledge_alert_and_open(db, alert, user.username,
                                             assigned_to=req.assigned_to if req else None)
    return _to_out(inv)


@router.get("/{case_id}", response_model=InvestigationOut)
def get(case_id: str, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    inv = _get(db, case_id)
    audit(db, _user.username, "INVESTIGATION_VIEWED", resource=case_id)
    return _to_out(inv)


@router.post("/{case_id}/notes", response_model=InvestigationOut)
def add_note(case_id: str, req: NoteCreate, db: Session = Depends(get_db),
             user: User = Depends(ANALYST_ROLES)):
    inv = _get(db, case_id)
    inv_svc.add_note(db, inv, user.username, req.note)
    db.refresh(inv)
    return _to_out(inv)


@router.post("/{case_id}/interventions", response_model=InvestigationOut)
def add_intervention(case_id: str, req: InterventionCreate,
                     db: Session = Depends(get_db), user: User = Depends(ANALYST_ROLES)):
    inv = _get(db, case_id)
    inv_svc.add_intervention(db, inv, action_type=req.action_type,
                             description=req.description, performed_by=user.username,
                             outcome=req.outcome)
    db.refresh(inv)
    return _to_out(inv)


@router.post("/{case_id}/status", response_model=InvestigationOut)
def update_status(case_id: str, req: StatusUpdate, db: Session = Depends(get_db),
                  user: User = Depends(ANALYST_ROLES)):
    inv = _get(db, case_id)
    try:
        new_status = InvestigationStatus(req.status)
    except ValueError:
        raise HTTPException(400, f"Invalid status '{req.status}'")
    inv_svc.set_status(db, inv, new_status, user.username, outcome=req.outcome)
    db.refresh(inv)
    return _to_out(inv)


@router.get("/{case_id}/graph")
def case_graph(case_id: str, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    """Graph context for the case: entities linked via its prediction's ATM."""
    inv = _get(db, case_id)
    gs = GraphService(db)
    pred = None
    if inv.prediction_id:
        pred = db.execute(select(Prediction).where(Prediction.prediction_id == inv.prediction_id)).scalar_one_or_none()
    # find the ATM entity for the predicted ATM
    from ..models import ATM, Entity
    center = None
    if pred:
        atm = db.execute(select(ATM).where(ATM.atm_id == pred.atm_id)).scalar_one_or_none()
        if atm:
            ent = db.execute(select(Entity).where(Entity.entity_type == "ATM",
                                                  Entity.masked_identifier == atm.atm_id)).scalar_one_or_none()
            if ent:
                center = ent.entity_id
    if center is None:
        return {"center": None, "nodes": [], "edges": [], "n_nodes": 0, "n_edges": 0,
                "hops": 2, "backend": "postgresql", "note": "No linked ATM entity"}
    return gs.cluster(center, hops=2)


@router.get("/{case_id}/report")
def report(case_id: str, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    """Generate the investigation PDF report."""
    inv = _get(db, case_id)
    pred_dict = None
    factors = []
    if inv.prediction_id:
        p = db.execute(select(Prediction).where(Prediction.prediction_id == inv.prediction_id)).scalar_one_or_none()
        if p:
            pred_dict = {
                "prediction_id": p.prediction_id, "atm_id": p.atm_id,
                "window_start": p.window_start.isoformat(), "window_end": p.window_end.isoformat(),
                "risk_score": p.risk_score, "probability": p.probability,
                "confidence": p.confidence, "model_version": p.model_version,
                "recommended_action": p.recommended_action,
            }
            factors = [
                {"feature": f.feature, "label": f.label, "impact": f.impact,
                 "direction": f.direction}
                for f in sorted(p.factors, key=lambda x: x.rank)
            ]
    graph = None
    # build graph directly
    from ..models import ATM, Entity
    from ..graph.service import GraphService
    gs = GraphService(db)
    if inv.prediction_id:
        p = db.execute(select(Prediction).where(Prediction.prediction_id == inv.prediction_id)).scalar_one_or_none()
        if p:
            atm = db.execute(select(ATM).where(ATM.atm_id == p.atm_id)).scalar_one_or_none()
            if atm:
                ent = db.execute(select(Entity).where(Entity.entity_type == "ATM",
                                                      Entity.masked_identifier == atm.atm_id)).scalar_one_or_none()
                if ent:
                    graph = gs.cluster(ent.entity_id, hops=2)
    audit_rows = [
        {"timestamp": a.timestamp.isoformat(), "username": a.username, "action": a.action,
         "resource": a.resource, "result": a.result}
        for a in db.execute(select(AuditLog).where(AuditLog.resource == case_id)
                            .order_by(AuditLog.timestamp).limit(20)).scalars().all()
    ]
    pdf = generate_investigation_pdf(inv, pred_dict, factors, graph, inv.interventions, audit_rows)
    audit(db, _user.username, "REPORT_GENERATED", resource=case_id)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{inv.case_id}_report.pdf"'},
    )