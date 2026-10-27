from datetime import datetime
from typing import Literal
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import get_current_user
from app.modules.notifications.models import DeviceToken, Notification
from app.modules.ops_common.base import utcnow
from app.modules.ops_common.core_refs import User
from app.modules.ops_common.pagination import Page, PageParams, page_of, paginate
from app.modules.ops_common.scope import not_found

router = APIRouter(tags=["Notifications"])


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    body: str
    type: str
    reference_type: str | None
    reference_id: uuid.UUID | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class DeviceRegisterIn(BaseModel):
    token: str = Field(min_length=10, max_length=500)
    platform: Literal["android", "web"]


@router.get("/notifications", response_model=Page[NotificationOut])
def list_notifications(
    is_read: bool | None = None,
    type_: str | None = Query(None, alias="type"),
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Notification).where(Notification.user_id == user.id)
    if is_read is not None:
        stmt = stmt.where(Notification.is_read.is_(is_read))
    if type_:
        stmt = stmt.where(Notification.type == type_)
    rows, total = paginate(db, stmt.order_by(Notification.created_at.desc()), params)
    return page_of(rows, total, params)


@router.get("/notifications/unread-count")
def unread_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    count = db.scalar(
        select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False))
    )
    return {"count": count or 0}


@router.post("/notifications/read-all")
def read_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=utcnow())
    )
    db.commit()
    return {"updated": result.rowcount}


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    note = db.get(Notification, notification_id)
    if note is None or note.user_id != user.id:  # someone else's notification looks like it doesn't exist
        raise not_found("Notification")
    if not note.is_read:
        note.is_read = True
        note.read_at = utcnow()
        db.commit()
    return note


@router.post("/devices/register", status_code=201)
def register_device(payload: DeviceRegisterIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    existing = db.scalar(select(DeviceToken).where(DeviceToken.token == payload.token))
    if existing is not None:
        # The same physical device may sign in as a different user: the token follows the latest user.
        existing.user_id = user.id
        existing.platform = payload.platform
        existing.last_seen_at = utcnow()
    else:
        db.add(DeviceToken(user_id=user.id, token=payload.token, platform=payload.platform))
    db.commit()
    return {"registered": True}


@router.delete("/devices/{token}", status_code=204)
def unregister_device(token: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.execute(delete(DeviceToken).where(DeviceToken.token == token, DeviceToken.user_id == user.id))
    db.commit()
