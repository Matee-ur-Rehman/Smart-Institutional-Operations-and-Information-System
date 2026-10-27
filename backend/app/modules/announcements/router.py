import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import get_current_user, require_roles
from app.modules.announcements.models import Announcement
from app.modules.notifications.push import dispatch_queued_pushes
from app.modules.notifications.service import notify_users, users_for_audience
from app.modules.ops_common.base import utcnow
from app.modules.ops_common.core_refs import SchoolClass, Section, User
from app.modules.ops_common.pagination import Page, PageParams, page_of, paginate
from app.modules.ops_common.scope import audience_condition, get_or_404, not_found

router = APIRouter(prefix="/announcements", tags=["Announcements"])
Audience = Literal["all", "teachers", "students", "parents", "class"]
ADMIN = Depends(require_roles("admin"))


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=3, max_length=10000)
    audience: Audience = "all"
    class_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    priority: Literal["normal", "important", "urgent"] = "normal"
    expires_at: datetime | None = None
    status: Literal["draft", "published"] = "published"

    @model_validator(mode="after")
    def _check(self):
        if self.audience == "class" and self.class_id is None and self.section_id is None:
            raise ValueError("class_id or section_id is required when audience is 'class'")
        if self.audience != "class" and (self.class_id or self.section_id):
            raise ValueError("class_id/section_id are only allowed when audience is 'class'")
        if self.expires_at is not None and _aware(self.expires_at) <= utcnow():
            raise ValueError("expires_at must be in the future")
        return self


class AnnouncementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    body: str | None = Field(default=None, min_length=3, max_length=10000)
    priority: Literal["normal", "important", "urgent"] | None = None
    expires_at: datetime | None = None


class AnnouncementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    body: str
    audience: str
    class_id: uuid.UUID | None
    section_id: uuid.UUID | None
    priority: str
    publish_at: datetime | None
    expires_at: datetime | None
    status: str
    created_at: datetime


def _publish(db: Session, announcement: Announcement) -> None:
    announcement.status = "published"
    announcement.publish_at = utcnow()
    notify_users(
        db, users_for_audience(db, announcement.audience, announcement.class_id, announcement.section_id),
        title=announcement.title, body=announcement.body[:300], type="announcement",
        reference_type="announcement", reference_id=announcement.id,
    )


@router.post("", response_model=AnnouncementOut, status_code=201)
def create_announcement(payload: AnnouncementCreate, background: BackgroundTasks, db: Session = Depends(get_db), user: User = ADMIN):
    if payload.class_id is not None:
        get_or_404(db, SchoolClass, payload.class_id, "Class")
    if payload.section_id is not None:
        get_or_404(db, Section, payload.section_id, "Section")
    announcement = Announcement(
        **payload.model_dump(exclude={"status"}), created_by=user.id, status="draft",
    )
    db.add(announcement)
    db.flush()
    if payload.status == "published":
        _publish(db, announcement)
    db.commit()
    if settings.fcm_enabled:
        background.add_task(dispatch_queued_pushes)
    return announcement


@router.get("", response_model=Page[AnnouncementOut])
def list_announcements(
    status: Literal["draft", "published", "archived"] | None = Query(None, description="Admin only"),
    priority: Literal["normal", "important", "urgent"] | None = None,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Announcement)
    if user.role == "admin":
        if status:
            stmt = stmt.where(Announcement.status == status)
    else:
        now = utcnow()
        stmt = stmt.where(
            Announcement.status == "published",
            Announcement.publish_at <= now,
            or_(Announcement.expires_at.is_(None), Announcement.expires_at > now),
            audience_condition(Announcement, user, db),
        )
    if priority:
        stmt = stmt.where(Announcement.priority == priority)
    rows, total = paginate(db, stmt.order_by(Announcement.publish_at.desc().nulls_last(), Announcement.created_at.desc()), params)
    return page_of(rows, total, params)


def _visible(db: Session, user: User, announcement_id: uuid.UUID) -> Announcement:
    announcement = db.get(Announcement, announcement_id)
    if announcement is None:
        raise not_found("Announcement")
    if user.role == "admin":
        return announcement
    now = utcnow()
    expires = _aware(announcement.expires_at)
    visible = (
        announcement.status == "published"
        and _aware(announcement.publish_at) is not None and _aware(announcement.publish_at) <= now
        and (expires is None or expires > now)
        and db.scalar(
            select(Announcement.id).where(Announcement.id == announcement.id, audience_condition(Announcement, user, db))
        ) is not None
    )
    if not visible:
        raise not_found("Announcement")
    return announcement


@router.get("/{announcement_id}", response_model=AnnouncementOut)
def get_announcement(announcement_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _visible(db, user, announcement_id)


@router.patch("/{announcement_id}", response_model=AnnouncementOut)
def update_announcement(announcement_id: uuid.UUID, payload: AnnouncementUpdate, db: Session = Depends(get_db), user: User = ADMIN):
    announcement = get_or_404(db, Announcement, announcement_id, "Announcement")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None and field in ("title", "body", "priority"):
            raise AppError(422, "validation_error", f"{field} cannot be empty")
        setattr(announcement, field, value)
    db.commit()
    return announcement


@router.post("/{announcement_id}/publish", response_model=AnnouncementOut)
def publish_announcement(announcement_id: uuid.UUID, background: BackgroundTasks, db: Session = Depends(get_db), user: User = ADMIN):
    announcement = get_or_404(db, Announcement, announcement_id, "Announcement")
    if announcement.status != "draft":
        raise AppError(409, "conflict", "Only drafts can be published")
    _publish(db, announcement)
    db.commit()
    if settings.fcm_enabled:
        background.add_task(dispatch_queued_pushes)
    return announcement


@router.post("/{announcement_id}/archive", response_model=AnnouncementOut)
def archive_announcement(announcement_id: uuid.UUID, db: Session = Depends(get_db), user: User = ADMIN):
    announcement = get_or_404(db, Announcement, announcement_id, "Announcement")
    announcement.status = "archived"
    db.commit()
    return announcement


@router.delete("/{announcement_id}", status_code=204)
def delete_announcement(announcement_id: uuid.UUID, db: Session = Depends(get_db), user: User = ADMIN):
    db.delete(get_or_404(db, Announcement, announcement_id, "Announcement"))
    db.commit()
