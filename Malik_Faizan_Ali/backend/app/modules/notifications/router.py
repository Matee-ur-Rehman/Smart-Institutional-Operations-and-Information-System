from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams, page_params, paginate
from app.core.database import get_db
from app.core.errors import NotFound
from app.core.security import get_current_user
from app.modules.announcements.service import dispatch_due_announcements
from app.modules.foundation.models import User
from app.modules.notifications.models import DeviceToken, Notification
from app.modules.notifications.schemas import DeviceRegister, NotificationOut, UnreadCount

router = APIRouter(tags=["Notifications"])


@router.get("/notifications", response_model=Page[NotificationOut])
def list_notifications(is_read: bool | None = None, type: str | None = Query(None, max_length=30),
                       params: PageParams = Depends(page_params), user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    dispatch_due_announcements(db)
    stmt = select(Notification).where(Notification.user_id == user.id)
    if is_read is not None:
        stmt = stmt.where(Notification.is_read == is_read)
    if type:
        stmt = stmt.where(Notification.type == type)
    rows, total = paginate(db, stmt.order_by(Notification.created_at.desc(), Notification.id), params)
    return Page(items=[NotificationOut.model_validate(r[0]) for r in rows], total=total,
                page=params.page, page_size=params.page_size)


@router.get("/notifications/unread-count", response_model=UnreadCount)
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dispatch_due_announcements(db)
    n = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id, Notification.is_read.is_(False)))
    return UnreadCount(count=n or 0)


@router.post("/notifications/read-all")
def read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    res = db.execute(update(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False))
                     .values(is_read=True, read_at=datetime.now(timezone.utc)))
    db.commit()
    return {"updated": res.rowcount}


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        import uuid
        nid = uuid.UUID(notification_id)
    except ValueError:
        raise NotFound("Notification not found")
    n = db.get(Notification, nid)
    if n is None or n.user_id != user.id:
        raise NotFound("Notification not found")
    if not n.is_read:
        n.is_read, n.read_at = True, datetime.now(timezone.utc)
        db.commit()
    return NotificationOut.model_validate(n)


@router.post("/devices/register", status_code=201)
def register_device(body: DeviceRegister, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dev = db.scalar(select(DeviceToken).where(DeviceToken.token == body.token))
    if dev is None:
        dev = DeviceToken(user_id=user.id, token=body.token, platform=body.platform)
        db.add(dev)
    else:  # same physical device, new login
        dev.user_id, dev.platform, dev.last_seen_at = user.id, body.platform, datetime.now(timezone.utc)
    db.commit()
    return {"registered": True}


@router.delete("/devices/{token:path}", status_code=204)
def unregister_device(token: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dev = db.scalar(select(DeviceToken).where(DeviceToken.token == token, DeviceToken.user_id == user.id))
    if dev is None:
        raise NotFound("Device not found")
    db.delete(dev)
    db.commit()
    return Response(status_code=204)
