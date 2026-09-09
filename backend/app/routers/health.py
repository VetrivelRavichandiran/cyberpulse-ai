"""CYBERPULSE AI — health & system status router."""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import engine, get_db
from ml.inference.service import get_service
from ..realtime.hub import hub

router = APIRouter(tags=["health"])

VERSION = "1.0.0"


def _check_db(db: Session) -> dict:
    t0 = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        ms = (time.perf_counter() - t0) * 1000
        return {"status": "up", "latency_ms": round(ms, 1)}
    except Exception as e:
        return {"status": "down", "error": e.__class__.__name__}


def _check_postgis(db: Session) -> dict:
    url = get_settings().database_url_resolved
    if not url.startswith("postgresql"):
        return {"status": "not_configured",
                "note": "SQLite demo mode — spatial ops via haversine; PostGIS active on PostgreSQL"}
    try:
        db.execute(text("SELECT postgis_version()"))
        return {"status": "up"}
    except Exception:
        return {"status": "down"}


def _check_neo4j() -> dict:
    s = get_settings()
    if not s.neo4j_uri:
        return {"status": "not_configured", "note": "PostgreSQL graph fallback active"}
    try:
        from ..graph.neo4j_adapter import try_connect
        svc = try_connect(s.neo4j_uri, s.neo4j_username, s.neo4j_password)
        if svc:
            svc.close()
            return {"status": "up"}
        return {"status": "down", "note": "PostgreSQL graph fallback active"}
    except Exception as e:
        return {"status": "down", "note": f"{e.__class__.__name__} — PostgreSQL graph fallback active"}


def _check_redis() -> dict:
    s = get_settings()
    if not s.redis_url:
        return {"status": "not_configured", "note": "in-process realtime hub active"}
    try:
        import redis  # type: ignore
        r = redis.from_url(s.redis_url, socket_connect_timeout=1)
        r.ping()
        return {"status": "up"}
    except Exception:
        return {"status": "down", "note": "in-process realtime hub active"}


def _check_model() -> dict:
    svc = get_service()
    if not svc.loaded:
        return {"status": "down", "note": "model artifact missing — run scripts/train_model.py"}
    reg = svc.load_registry()
    return {"status": "up",
            "version": reg["active"]["version"] if reg else "unknown",
            "algorithm": reg["active"]["algorithm"] if reg else "XGBoost"}


@router.get("/health")
def health(db: Session = Depends(get_db)):
    svc = get_service()
    return {
        "status": "ok",
        "version": VERSION,
        "time": datetime.now(timezone.utc).isoformat(),
        "model_loaded": svc.loaded,
        "realtime_clients": hub.client_count,
        "dependencies": {
            "api": {"status": "up"},
            "database": _check_db(db),
            "postgis": _check_postgis(db),
            "neo4j": _check_neo4j(),
            "redis": _check_redis(),
            "ml_model": _check_model(),
            "realtime": {"status": "up", "connected_clients": hub.client_count},
        },
    }


@router.get("/health/dependencies")
def health_deps(db: Session = Depends(get_db)):
    return health(db)["dependencies"]