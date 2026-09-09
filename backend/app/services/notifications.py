"""CYBERPULSE AI — notification service (abstraction over channels).

Channels:
  - in_app   : persisted to `notifications` table (always on)
  - websocket: pushed to connected clients via the realtime hub (always on)
  - email    : provider-agnostic stub → logged (integrate real provider later)
  - webhook  : provider-agnostic stub → logged (integrate real provider later)
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..models import Notification

logger = logging.getLogger("cyberpulse.notify")


def notify(db: Session, title: str, body: str | None = None,
           severity: str = "INFO", resource: str | None = None,
           user_id: int | None = None, channels: tuple = ("in_app", "websocket")) -> Notification:
    n = Notification(
        channel="in_app",
        user_id=user_id,
        title=title,
        body=body,
        severity=severity,
    )
    db.add(n)
    db.commit()
    db.refresh(n)

    # websocket fan-out (in-process hub; Redis adapter can replace this).
    # NOTE: must use broadcast_sync — this runs in a sync (DB) context, so the
    # async hub.broadcast() coroutine would never be awaited.
    try:
        from ..realtime.hub import hub
        hub.broadcast_sync({
            "type": "notification",
            "payload": {
                "id": n.id,
                "title": n.title,
                "body": n.body,
                "severity": n.severity,
                "resource": resource,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            },
        })
    except Exception as e:  # realtime must never break the core flow
        logger.debug("websocket notify skipped: %s", e)

    # stub channels (log only; real providers plug in here)
    for ch in channels:
        if ch in ("email", "webhook"):
            logger.info("NOTIFY[%s] %s — %s (simulated)", ch, title, body)
    return n