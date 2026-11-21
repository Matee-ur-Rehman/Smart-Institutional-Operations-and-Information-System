"""
Authentication (API_CONTRACT.md section 2).

* Login: bcrypt check, platform rule (web/mobile), lock-out after LOGIN_MAX_ATTEMPTS failures.
* Refresh tokens are stored as sha256 hashes: refresh ROTATES the token, logout deletes it, and presenting an already
  used refresh token (replay) revokes every session of that user.
* Changing or resetting a password revokes all refresh tokens.
Honest limitation: access tokens stay valid until they expire (<= JWT_ACCESS_MINUTES) after logout; deactivating a
user is effective immediately because the user row is checked on every request.
"""
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import BadRequest, Conflict, Forbidden, NotAuthenticated, TooManyRequests, ValidationFailed, field_error
from app.core.security import (
    create_access_token, create_refresh_token, decode_token, get_current_user, hash_password, token_digest,
    verify_password,
)
from app.modules.foundation.models import RefreshToken, User

router = APIRouter(prefix="/auth", tags=["Auth"])
PLATFORM_ROLES = {"web": {"admin", "teacher"}, "mobile": {"teacher", "student", "parent"}}


def check_password_strength(v: str) -> str:
    if len(v) < 8 or not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValueError("Password must be at least 8 characters and contain a letter and a digit")
    return v


class LoginBody(BaseModel):
    login_id: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class RefreshBody(BaseModel):
    refresh_token: str


class LogoutBody(BaseModel):
    refresh_token: str | None = None


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
    _strong = field_validator("new_password")(check_password_strength)


class ProfileUpdate(BaseModel):
    phone: str | None = Field(None, max_length=20, pattern=r"^[0-9+\-\s()]{7,20}$")
    email: EmailStr | None = None


def user_dict(u: User) -> dict:
    return {"id": str(u.id), "login_id": u.login_id, "email": u.email, "role": u.role, "full_name": u.full_name,
            "phone": u.phone, "must_change_password": u.must_change_password}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def issue_tokens(db: Session, user: User) -> dict:
    refresh = create_refresh_token(user.id, user.role)
    db.add(RefreshToken(user_id=user.id, token_hash=token_digest(refresh),
                        expires_at=_now() + timedelta(days=settings.JWT_REFRESH_DAYS)))
    return {"access_token": create_access_token(user.id, user.role), "refresh_token": refresh,
            "token_type": "bearer", "user": user_dict(user)}


def revoke_all_tokens(db: Session, user_id: uuid.UUID) -> None:
    """End every session of the user (rows are deleted: a deleted token is simply unknown, not a 'replay')."""
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))


@router.post("/login")
def login(body: LoginBody, x_client_platform: Literal["web", "mobile"] | None = Header(None),
          db: Session = Depends(get_db)):
    if x_client_platform is None:
        raise ValidationFailed(errors=[field_error("X-Client-Platform", "Header must be 'web' or 'mobile'")])
    user = db.scalar(select(User).where(func.lower(User.login_id) == body.login_id.strip().lower()))
    now = _now()
    if user is not None and user.locked_until and user.locked_until > now:
        mins = int((user.locked_until - now).total_seconds() // 60) + 1
        raise TooManyRequests(f"Too many failed attempts. Try again in {mins} minute(s).")
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        if user is not None and user.is_active:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.LOGIN_MAX_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
                user.failed_login_count = 0
            db.commit()
        raise NotAuthenticated("Invalid login ID or password", code="invalid_credentials")
    if user.role not in PLATFORM_ROLES[x_client_platform]:
        where = "the mobile app" if x_client_platform == "web" else "the web dashboard"
        raise Forbidden(f"{user.role.capitalize()} accounts must use {where}")
    user.failed_login_count, user.locked_until, user.last_login_at = 0, None, now
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.expires_at < now))  # housekeeping
    out = issue_tokens(db, user)
    db.commit()
    return out


@router.post("/refresh")
def refresh(body: RefreshBody, db: Session = Depends(get_db)):
    claims = decode_token(body.refresh_token, "refresh")
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_digest(body.refresh_token)).with_for_update())
    if row is None:
        raise NotAuthenticated("Invalid authentication token")
    if row.revoked_at is not None:  # replay of an already-rotated token: assume theft, end every session of the user
        revoke_all_tokens(db, row.user_id)
        db.commit()
        raise NotAuthenticated("Refresh token was already used; please sign in again", code="token_reused")
    user = db.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active or user.role != claims.get("role"):
        raise NotAuthenticated("Account is not active")
    row.revoked_at = _now()
    out = issue_tokens(db, user)
    db.commit()
    return out


@router.post("/logout", status_code=204)
def logout(body: LogoutBody | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """With a refresh_token: ends that session. Without: ends all of the caller's sessions."""
    if body and body.refresh_token:
        db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id,
                                              RefreshToken.token_hash == token_digest(body.refresh_token)))
    else:
        revoke_all_tokens(db, user.id)
    db.commit()


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_dict(user)


@router.patch("/me")
def update_me(body: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    if "email" in data and data["email"]:
        taken = db.scalar(select(User.id).where(func.lower(User.email) == data["email"].lower(), User.id != user.id))
        if taken:
            raise Conflict("This email is already used by another account")
    for k, v in data.items():
        setattr(user, k, v)
    db.commit()
    return user_dict(user)


@router.post("/change-password", status_code=204)
def change_password(body: ChangePasswordBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise BadRequest("Current password is incorrect", code="wrong_password")
    if body.current_password == body.new_password:
        raise BadRequest("The new password must differ from the current one", code="same_password")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    revoke_all_tokens(db, user.id)
    db.commit()
