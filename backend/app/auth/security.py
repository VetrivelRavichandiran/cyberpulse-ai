"""CYBERPULSE AI — JWT authentication, password hashing, RBAC."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

import bcrypt

from ..config import get_settings
from ..database import get_db
from ..models import User, Role

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(subject: str, role: str, expires_minutes: int | None = None) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or s.jwt_expire_minutes
    )
    payload = {"sub": subject, "role": role, "exp": exp, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_token(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e.__class__.__name__}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(creds.credentials)
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_roles(*roles: Role):
    """Server-side RBAC dependency factory."""
    allowed = set(roles)

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.role.value}' is not authorized for this action",
            )
        return user

    return checker


# convenience role groups
ADMIN_ONLY = require_roles(Role.ADMIN)
ANALYST_ROLES = require_roles(
    Role.ADMIN, Role.I4C_ANALYST, Role.STATE_OFFICER, Role.DISTRICT_OFFICER, Role.INVESTIGATOR
)
OFFICER_ROLES = require_roles(Role.ADMIN, Role.I4C_ANALYST, Role.STATE_OFFICER, Role.DISTRICT_OFFICER)
BANK_ROLES = require_roles(Role.ADMIN, Role.BANK_USER)