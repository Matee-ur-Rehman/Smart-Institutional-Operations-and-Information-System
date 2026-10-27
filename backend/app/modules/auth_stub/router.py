"""TEMPORARY login endpoint so Member 2's modules can be used before Faizan's /auth is merged.
Owner: Member 1 (Faizan). Delete this folder and its include_router line in app/main.py when his
auth module lands. Paths and the platform rule follow docs/API_CONTRACT.md section 2.
"""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import create_access_token, create_refresh_token, get_current_user, verify_password
from app.core.stub_models import User

router = APIRouter(prefix="/auth", tags=["Auth (temporary stub)"])

ALLOWED_PLATFORMS = {
    "admin": {"web"},
    "teacher": {"web", "mobile"},
    "student": {"mobile"},
    "parent": {"mobile"},
}


class LoginIn(BaseModel):
    login_id: str
    password: str


def _user_dict(user: User) -> dict:
    return {"id": str(user.id), "login_id": user.login_id, "full_name": user.full_name, "role": user.role}


@router.post("/login")
def login(
    payload: LoginIn,
    x_client_platform: Literal["web", "mobile"] = Header(),
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.login_id == payload.login_id))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise AppError(401, "not_authenticated", "Invalid login ID or password")
    if x_client_platform not in ALLOWED_PLATFORMS.get(user.role, set()):
        raise AppError(403, "forbidden", f"{user.role} accounts cannot sign in from the {x_client_platform} app")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "access_token": create_access_token(user.id, user.role),
        "refresh_token": create_refresh_token(user.id, user.role),
        "token_type": "bearer",
        "user": _user_dict(user),
    }


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return _user_dict(user)
