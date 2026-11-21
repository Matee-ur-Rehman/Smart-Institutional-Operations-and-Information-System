"""Helpers shared by the user / people routers: account creation, temp passwords, token revocation."""
import re
import secrets
import string

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, ValidationFailed, field_error
from app.core.security import hash_password
from app.modules.foundation.models import User

LOGIN_RE = re.compile(r"^[A-Za-z0-9._-]{3,50}$")
PHONE_PATTERN = r"^[0-9+\-\s()]{7,20}$"
CNIC_PATTERN = r"^\d{5}-\d{7}-\d$"


def generate_password() -> str:
    """Random 12-char password that always satisfies the policy (letter + digit)."""
    alphabet = string.ascii_letters + string.digits
    core = "".join(secrets.choice(alphabet) for _ in range(10))
    return core + secrets.choice(string.ascii_uppercase) + secrets.choice(string.digits)


def create_user(db: Session, *, role: str, login_id: str, full_name: str, password: str | None, email: str | None = None,
                phone: str | None = None) -> tuple[User, str | None]:
    """Insert a user (flush, no commit). Returns (user, temporary_password or None when the caller chose a password)."""
    login_id = login_id.strip()
    if not LOGIN_RE.match(login_id):
        raise ValidationFailed(errors=[field_error("login_id", "3-50 characters: letters, digits, '.', '_' or '-'")])
    if db.scalar(select(User.id).where(func.lower(User.login_id) == login_id.lower())):
        raise Conflict(f"Login ID '{login_id}' is already taken", code="login_id_taken")
    if email and db.scalar(select(User.id).where(func.lower(User.email) == email.lower())):
        raise Conflict("This email is already used by another account", code="email_taken")
    temp = None
    if not password:
        password = temp = generate_password()
    user = User(login_id=login_id, email=email or None, password_hash=hash_password(password), role=role,
                full_name=full_name.strip(), phone=phone, must_change_password=temp is not None)
    db.add(user)
    db.flush()
    return user, temp
