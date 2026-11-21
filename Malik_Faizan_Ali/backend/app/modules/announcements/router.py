import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams, page_params, paginate
from app.core.database import get_db
from app.core.errors import Conflict, NotFound, ValidationFailed, field_error
from app.core.security import get_current_user, require_roles
from app.modules.announcements import service
from app.modules.announcements.models import Announcement
from app.modules.announcements.schemas import AnnouncementCreate, AnnouncementOut, AnnouncementUpdate
from app.modules.foundation.models import User

router = APIRouter(prefix="/announcements", tags=["Announcements"])
admin_only = Depends(require_roles("admin"))


@router.post("", response_model=AnnouncementOut, status_code=201)
def create_announcement(body: AnnouncementCreate, user: User = admin_only, db: Session = Depends(get_db)):
    class_id, section_id = service.normalise_target(db, body.audience, body.class_id, body.section_id)
    ann = Announcement(title=body.title.strip(), body=body.body, audience=body.audience, class_id=class_id,
                       section_id=section_id, priority=body.priority, publish_at=body.publish_at or service.now(),
                       expires_at=body.expires_at, status=body.status, created_by=user.id)
    db.add(ann)
    db.flush()
    service.dispatch_announcement(db, ann)
    db.commit()
    return service.to_out(db, [ann])[0]


@router.get("", response_model=Page[AnnouncementOut])
def list_announcements(status: Literal["draft", "published", "archived"] | None = None,
                       audience: str | None = Query(None, max_length=20), priority: str | None = Query(None, max_length=20),
                       params: PageParams = Depends(page_params), user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    service.dispatch_due_announcements(db)
    stmt = select(Announcement)
    if user.role == "admin" and status:
        stmt = stmt.where(Announcement.status == status)            # admin: exact status, any time
    else:
        stmt = stmt.where(service.live_clause())
        if user.role != "admin":
            stmt = stmt.where(service.visibility_clause(user, db))
    if audience:
        stmt = stmt.where(Announcement.audience == audience)
    if priority:
        stmt = stmt.where(Announcement.priority == priority)
    rows, total = paginate(db, stmt.order_by(Announcement.publish_at.desc(), Announcement.id), params)
    return Page(items=service.to_out(db, [r[0] for r in rows]), total=total, page=params.page, page_size=params.page_size)


def _get_visible(db: Session, user: User, ann_id: uuid.UUID) -> Announcement:
    stmt = select(Announcement).where(Announcement.id == ann_id)
    if user.role != "admin":
        stmt = stmt.where(service.live_clause(), service.visibility_clause(user, db))
    ann = db.scalar(stmt)
    if ann is None:
        raise NotFound("Announcement not found")
    return ann


@router.get("/{announcement_id}", response_model=AnnouncementOut)
def get_announcement(announcement_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.to_out(db, [_get_visible(db, user, announcement_id)])[0]


@router.patch("/{announcement_id}", response_model=AnnouncementOut)
def update_announcement(announcement_id: uuid.UUID, body: AnnouncementUpdate, user: User = admin_only,
                        db: Session = Depends(get_db)):
    ann = _get_visible(db, user, announcement_id)
    data = body.model_dump(exclude_unset=True)
    if ann.status == "archived" and data.get("status") is None and data:
        raise Conflict("Archived announcements cannot be edited")
    for k in ("title", "body", "priority", "publish_at", "expires_at", "status"):
        if k in data and data[k] is not None:
            setattr(ann, k, data[k].strip() if k == "title" else data[k])
    if "expires_at" in data and data["expires_at"] is None:
        ann.expires_at = None
    if {"audience", "class_id", "section_id"} & data.keys():
        audience = data.get("audience") or ann.audience
        ann.class_id, ann.section_id = service.normalise_target(
            db, audience, data.get("class_id", ann.class_id), data.get("section_id", ann.section_id))
        ann.audience = audience
        if audience == "class" and not (ann.class_id or ann.section_id):
            raise ValidationFailed(errors=[field_error("class_id", "class_id or section_id is required")])
    if ann.expires_at and ann.expires_at <= ann.publish_at:
        raise ValidationFailed(errors=[field_error("expires_at", "expires_at must be after publish_at")])
    db.flush()
    service.dispatch_announcement(db, ann)
    db.commit()
    return service.to_out(db, [ann])[0]


@router.post("/{announcement_id}/archive", response_model=AnnouncementOut)
def archive_announcement(announcement_id: uuid.UUID, user: User = admin_only, db: Session = Depends(get_db)):
    ann = _get_visible(db, user, announcement_id)
    ann.status = "archived"
    db.commit()
    return service.to_out(db, [ann])[0]


@router.delete("/{announcement_id}", status_code=204)
def delete_announcement(announcement_id: uuid.UUID, user: User = admin_only, db: Session = Depends(get_db)):
    ann = _get_visible(db, user, announcement_id)
    if ann.status == "published":
        raise Conflict("Archive a published announcement instead of deleting it")
    db.delete(ann)
    db.commit()
