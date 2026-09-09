"""CYBERPULSE AI — audit logging service.

Every important action creates an audit record. Never logs credentials.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import AuditLog


def audit(db: Session, username: str, action: str, resource: str | None = None,
          result: str = "SUCCESS", detail: str | None = None) -> AuditLog:
    log = AuditLog(
        username=username or "system",
        action=action,
        resource=resource,
        result=result,
        detail=detail,
    )
    db.add(log)
    db.commit()
    return log


def mask_phone(value: str) -> str:
    """9876543210 -> 98******10"""
    v = str(value)
    if len(v) >= 4:
        return v[:2] + "*" * (len(v) - 4) + v[-2:]
    return "*" * len(v)


def mask_account(value: str) -> str:
    """ACC-1234567890 -> ACC-********90"""
    v = str(value)
    if "-" in v:
        prefix, _, tail = v.rpartition("-")
        if len(tail) >= 2:
            return f"{prefix}-{'*' * max(len(tail) - 2, 1)}{tail[-2:]}"
    if len(v) >= 4:
        return "*" * (len(v) - 2) + v[-2:]
    return "*" * len(v)