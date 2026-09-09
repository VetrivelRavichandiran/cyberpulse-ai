"""CYBERPULSE AI — auth router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth.security import (
    create_access_token,
    get_current_user,
    verify_password,
)
from ..database import get_db
from ..models import User
from ..schemas import LoginRequest, TokenResponse, UserOut
from ..services.audit import audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if user is None or not verify_password(req.password, user.password_hash):
        audit(db, req.username, "LOGIN_FAILED", result="FAILURE")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    from datetime import datetime, timezone
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    token = create_access_token(user.username, user.role.value)
    audit(db, user.username, "LOGIN", result="SUCCESS")
    return TokenResponse(
        access_token=token,
        username=user.username,
        role=user.role.value,
        full_name=user.full_name,
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user