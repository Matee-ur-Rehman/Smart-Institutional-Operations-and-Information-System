"""User accounts (admin only): list, create admin accounts, edit, (de)activate, reset password, unlock."""
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams, page_params, paginate
from app.core.database import get_db
from app.core.errors import BadRequest, Conflict, NotFound
from app.core.security import hash_password, require_roles
from app.modules.foundation.accounts import CNIC_PATTERN, PHONE_PATTERN, create_user, generate_password  # noqa: F401
from app.modules.foundation.auth_router import check_password_strength, revoke_all_tokens
from app.modules.foundation.models import Parent, Student, Teacher, User

router = APIRouter(prefix="/users", tags=["Users"])
admin_only = Depends(require_roles("admin"))


class UserOut(BaseModel):
    id: uuid.UUID
    login_id: str
    email: str | None = None
    role: str
    full_name: str
    phone: str | None = None
    is_active: bool
    is_locked: bool = False
    must_change_password: bool = False
    last_login_at: datetime | None = None
    profile_id: uuid.UUID | None = None


class AdminCreate(BaseModel):
    login_id: str = Field(min_length=3, max_length=50)
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(None, pattern=PHONE_PATTERN)
    password: str | None = Field(None, min_length=8, max_length=128)
    role: Literal["admin"] = "admin"
    _strong = field_validator("password")(lambda v: check_password_strength(v) if v else v)


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(None, pattern=PHONE_PATTERN)
    is_active: bool | None = None


class ResetBody(BaseModel):
    new_password: str | None = Field(None, min_length=8, max_length=128)
    _strong = field_validator("new_password")(lambda v: check_password_strength(v) if v else v)


def _profile_map(db: Session, users: list[User]) -> dict[uuid.UUID, uuid.UUID]:
    ids = [u.id for u in users]
    out: dict[uuid.UUID, uuid.UUID] = {}
    for model in (Teacher, Student, Parent):
        for pid, uid in db.execute(select(model.id, model.user_id).where(model.user_id.in_(ids))):
            out[uid] = pid
    return out


def user_out(db: Session, users: list[User]) -> list[UserOut]:
    prof = _profile_map(db, users)
    now = datetime.now().astimezone()
    return [UserOut(id=u.id, login_id=u.login_id, email=u.email, role=u.role, full_name=u.full_name, phone=u.phone,
                    is_active=u.is_active, is_locked=bool(u.locked_until and u.locked_until > now),
                    must_change_password=u.must_change_password, last_login_at=u.last_login_at,
                    profile_id=prof.get(u.id)) for u in users]


def sync_profile_active(db: Session, user: User) -> None:
    """Teacher/Student profiles carry their own is_active flag that the ops modules check."""
    db.execute(update(Teacher).where(Teacher.user_id == user.id).values(is_active=user.is_active))
    db.execute(update(Student).where(Student.user_id == user.id).values(is_active=user.is_active))


def _get(db: Session, user_id: uuid.UUID) -> User:
    u = db.get(User, user_id)
    if u is None:
        raise NotFound("User not found")
    return u


@router.get("", response_model=Page[UserOut])
def list_users(role: Literal["admin", "teacher", "student", "parent"] | None = None, q: str | None = Query(None, max_length=100),
               is_active: bool | None = None, params: PageParams = Depends(page_params), _: User = admin_only,
               db: Session = Depends(get_db)):
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.full_name.ilike(like), User.login_id.ilike(like), User.email.ilike(like)))
    rows, total = paginate(db, stmt.order_by(User.full_name, User.login_id), params)
    return Page(items=user_out(db, [r[0] for r in rows]), total=total, page=params.page, page_size=params.page_size)


@router.post("", status_code=201)
def create_admin(body: AdminCreate, _: User = admin_only, db: Session = Depends(get_db)):
    """Teachers, students and parents are created through /teachers, /students and /parents (they need a profile)."""
    user, temp = create_user(db, role="admin", login_id=body.login_id, full_name=body.full_name, password=body.password,
                             email=body.email, phone=body.phone)
    db.commit()
    return {"user": user_out(db, [user])[0], "temporary_password": temp}


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: uuid.UUID, _: User = admin_only, db: Session = Depends(get_db)):
    return user_out(db, [_get(db, user_id)])[0]


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, body: UserUpdate, me: User = admin_only, db: Session = Depends(get_db)):
    u = _get(db, user_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("email"):
        if db.scalar(select(User.id).where(func.lower(User.email) == data["email"].lower(), User.id != u.id)):
            raise Conflict("This email is already used by another account", code="email_taken")
    if data.get("is_active") is False and u.is_active:
        if u.id == me.id:
            raise BadRequest("You cannot deactivate your own account", code="self_deactivate")
        if u.role == "admin" and (db.scalar(select(func.count()).select_from(User).where(User.role == "admin", User.is_active)) or 0) <= 1:
            raise BadRequest("The last active administrator cannot be deactivated", code="last_admin")
    for k, v in data.items():
        setattr(u, k, v)
    if "full_name" in data:
        db.execute(update(Student).where(Student.user_id == u.id).values(full_name=u.full_name))
    if "is_active" in data:
        sync_profile_active(db, u)
        if not u.is_active:
            revoke_all_tokens(db, u.id)
    db.commit()
    return user_out(db, [u])[0]


@router.post("/{user_id}/reset-password")
def reset_password(user_id: uuid.UUID, body: ResetBody | None = None, _: User = admin_only, db: Session = Depends(get_db)):
    """Sets a new password (or generates a temporary one, returned once). The user must change it at next login."""
    u = _get(db, user_id)
    pwd = body.new_password if body and body.new_password else None
    temp = None if pwd else generate_password()
    u.password_hash = hash_password(pwd or temp)
    u.must_change_password, u.failed_login_count, u.locked_until = True, 0, None
    revoke_all_tokens(db, u.id)
    db.commit()
    return {"temporary_password": temp}


@router.post("/{user_id}/unlock", status_code=204)
def unlock(user_id: uuid.UUID, _: User = admin_only, db: Session = Depends(get_db)):
    u = _get(db, user_id)
    u.failed_login_count, u.locked_until = 0, None
    db.commit()
