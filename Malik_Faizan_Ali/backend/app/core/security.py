"""
JWT + password hashing + auth dependencies (Member 1's contract: API_CONTRACT.md section 2).
get_current_user() and require_roles() are the two names Member 2 imports.
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import Forbidden, NotAuthenticated
from app.modules.foundation.models import User  # TEMP STUB import (see foundation/models.py)

_bearer = HTTPBearer(auto_error=False)


def token_digest(token: str) -> str:
    """sha256 hex of a token: what is stored in refresh_tokens (the raw token is never stored)."""
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode()[:72], hashed.encode())
    except ValueError:
        return False


def _make_token(user_id: uuid.UUID, role: str, kind: str, delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    claims = {"sub": str(user_id), "role": role, "type": kind, "iat": int(now.timestamp()),
              "exp": int((now + delta).timestamp()), "jti": uuid.uuid4().hex}
    return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    return _make_token(user_id, role, "access", timedelta(minutes=settings.JWT_ACCESS_MINUTES))


def create_refresh_token(user_id: uuid.UUID, role: str) -> str:
    return _make_token(user_id, role, "refresh", timedelta(days=settings.JWT_REFRESH_DAYS))


def decode_token(token: str, expected_type: str) -> dict:
    try:
        claims = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except ExpiredSignatureError:
        raise NotAuthenticated("Token has expired", code="token_expired")
    except JWTError:
        raise NotAuthenticated("Invalid authentication token")
    if claims.get("type") != expected_type:
        raise NotAuthenticated("Invalid token type")
    return claims


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None:
        raise NotAuthenticated("Authentication required")
    claims = decode_token(creds.credentials, "access")
    try:
        uid = uuid.UUID(claims["sub"])
    except (KeyError, ValueError):
        raise NotAuthenticated("Invalid authentication token")
    user = db.get(User, uid)
    # Role is re-checked against the database: deactivated users / changed roles are rejected.
    if user is None or not user.is_active or user.role != claims.get("role"):
        raise NotAuthenticated("Account is not active")
    return user


def require_roles(*roles: str):
    """Dependency factory: `Depends(require_roles("admin", "teacher"))` -> User or 403."""

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise Forbidden("You do not have permission to perform this action")
        return user

    return _dep
