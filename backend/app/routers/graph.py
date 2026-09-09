"""CYBERPULSE AI — graph intelligence router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth.security import get_current_user
from ..config import get_settings
from ..database import get_db
from ..graph.service import GraphService

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/entity/{entity_id}")
def get_entity(entity_id: str, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    gs = GraphService(db)
    e = gs.get_entity(entity_id)
    if e is None:
        raise HTTPException(404, "Entity not found")
    return e


@router.get("/relationships/{entity_id}")
def relationships(entity_id: str, limit: int = Query(100, le=500),
                  db: Session = Depends(get_db), _user=Depends(get_current_user)):
    gs = GraphService(db)
    return gs.relationships(entity_id, limit=limit)


@router.get("/cluster/{entity_id}")
def cluster(entity_id: str, hops: int = Query(2, ge=1, le=3),
            db: Session = Depends(get_db), _user=Depends(get_current_user)):
    gs = GraphService(db)
    return gs.cluster(entity_id, hops=hops)


@router.get("/patterns/suspicious-chains")
def suspicious_chains(since_hours: int = Query(720, le=24 * 30),
                      db: Session = Depends(get_db), _user=Depends(get_current_user)):
    gs = GraphService(db)
    return gs.suspicious_chains(since_hours=since_hours)


@router.get("/patterns/shared-phone")
def shared_phone(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    gs = GraphService(db)
    return gs.shared_phone_accounts()


@router.get("/stats")
def stats(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    from sqlalchemy import func
    from ..models import Entity, EntityRelationship
    n_ent = db.execute(select_count(Entity)).scalar_one()
    n_rel = db.execute(select_count(EntityRelationship)).scalar_one()
    by_type = db.execute(
        __import__("sqlalchemy").select(Entity.entity_type, func.count(Entity.id))
        .group_by(Entity.entity_type)
    ).all()
    return {
        "n_entities": n_ent,
        "n_relationships": n_rel,
        "by_type": {t: int(c) for t, c in by_type},
        "backend": "postgresql" if not _neo4j_available() else "neo4j",
    }


def select_count(model):
    from sqlalchemy import func, select
    return select(func.count()).select_from(model)


def _neo4j_available() -> bool:
    s = get_settings()
    if not s.neo4j_uri:
        return False
    try:
        from ..graph.neo4j_adapter import try_connect
        svc = try_connect(s.neo4j_uri, s.neo4j_username, s.neo4j_password)
        if svc:
            svc.close()
            return True
    except Exception:
        pass
    return False