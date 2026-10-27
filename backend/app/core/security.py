"""Password hashing, JWT and the auth dependencies (docs/API_CONTRACT.md section 2).

TEMPORARY STUB written by Member 2. Owner: Member 1 (Faizan). The public names that Member 2's
code imports are: get_current_user, require_roles, create_access_token, create_refresh_token,
hash_password, verify_password.
"""
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.stub_models import User

ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _create_token(user_id: uuid.UUID, role: str, token_type: str, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=ALGORITHM)


def create_access_token(user_id: uuid.UUID, role: str, minutes: int | None = None) -> str:
    return _create_token(user_id, role, "access", timedelta(minutes=minutes or settings.jwt_access_minutes))


def create_refresh_token(user_id: uuid.UUID, role: str) -> str:
    return _create_token(user_id, role, "refresh", timedelta(days=settings.jwt_refresh_days))


def decode_token(token: str, expected_type: str = "access") -> dict:
    try:
        claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise AppError(401, "token_expired", "Token has expired")
    except JWTError:
        raise AppError(401, "not_authenticated", "Invalid token")
    if claims.get("type") != expected_type:
        raise AppError(401, "not_authenticated", "Wrong token type")
    return claims


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise AppError(401, "not_authenticated", "Authentication required")
    claims = decode_token(creds.credentials)
    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError):
        raise AppError(401, "not_authenticated", "Invalid token")
    user = db.get(User, user_id)
    # The role is re-read from the database: a deactivated user, or one whose role changed, is
    # rejected even though the token itself is still valid.
    if user is None or not user.is_active or user.role != claims.get("role"):
        raise AppError(401, "not_authenticated", "Account is not active")
    return user


def require_roles(*roles: str):
    def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AppError(403, "forbidden", "You do not have permission to do this")
        return user

    return _dependency
