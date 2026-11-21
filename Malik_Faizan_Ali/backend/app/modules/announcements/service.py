"""Announcement audience resolution, visibility and notification fan-out."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.common.audience import audience_user_ids as resolve_audience, audience_visibility_clause
from app.common.scope import section_labels, user_names
from app.core.errors import ValidationFailed, field_error
from app.modules.announcements.models import Announcement
from app.modules.announcements.schemas import AnnouncementOut
from app.modules.foundation.models import SchoolClass, Section, User
from app.modules.notifications.service import notify_users


def now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ validation / targets
def normalise_target(db: Session, audience: str, class_id, section_id) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """For audience=class make class_id/section_id consistent; for others clear both."""
    if audience != "class":
        return None, None
    if section_id:
        sec = db.get(Section, section_id)
        if sec is None:
            raise ValidationFailed(errors=[field_error("section_id", "Section does not exist")])
        return sec.class_id, section_id
    if db.get(SchoolClass, class_id) is None:
        raise ValidationFailed(errors=[field_error("class_id", "Class does not exist")])
    return class_id, None


# ------------------------------------------------------------------ visibility
def visibility_clause(user: User, db: Session):
    """SQL condition: announcements whose audience includes `user` (non-admin)."""
    return audience_visibility_clause(Announcement, user, db)


def live_clause():
    t = now()
    return and_(Announcement.status == "published", Announcement.publish_at <= t,
                or_(Announcement.expires_at.is_(None), Announcement.expires_at > t))


# ------------------------------------------------------------------ fan-out
def audience_user_ids(db: Session, ann: Announcement) -> list[uuid.UUID]:
    return resolve_audience(db, ann.audience, ann.class_id, ann.section_id)


def dispatch_announcement(db: Session, ann: Announcement) -> int:
    """Notify the audience exactly once (claims `notified_at` atomically). Caller commits."""
    claimed = db.execute(
        update(Announcement)
        .where(Announcement.id == ann.id, Announcement.notified_at.is_(None),
               Announcement.status == "published", Announcement.publish_at <= now())
        .values(notified_at=now())
    ).rowcount
    if not claimed:
        return 0
    prefix = "URGENT: " if ann.priority == "urgent" else ""
    body = ann.body if len(ann.body) <= 200 else ann.body[:197] + "..."
    return notify_users(db, audience_user_ids(db, ann), prefix + ann.title, body, "announcement",
                        "announcement", ann.id)


def dispatch_due_announcements(db: Session) -> int:
    """Scheduled-publish support without a scheduler: runs when inboxes/feeds are read."""
    due = db.scalars(select(Announcement).where(
        Announcement.status == "published", Announcement.notified_at.is_(None),
        Announcement.publish_at <= now())).all()
    total = sum(dispatch_announcement(db, a) for a in due)
    if due:
        db.commit()
    return total


# ------------------------------------------------------------------ output
def to_out(db: Session, rows: list[Announcement]) -> list[AnnouncementOut]:
    sec_ids = {a.section_id for a in rows if a.section_id}
    labels = section_labels(db, sec_ids)
    cls = {c.id: c.name for c in db.scalars(select(SchoolClass).where(SchoolClass.id.in_({a.class_id for a in rows if a.class_id})))} \
        if any(a.class_id for a in rows) else {}
    names = user_names(db, {a.created_by for a in rows})
    t = now()
    out = []
    for a in rows:
        if a.audience == "class":
            target = labels.get(a.section_id) if a.section_id else cls.get(a.class_id, "Class")
        else:
            target = {"all": "Everyone", "teachers": "Teachers", "students": "Students", "parents": "Parents"}[a.audience]
        out.append(AnnouncementOut(
            id=a.id, title=a.title, body=a.body, audience=a.audience, class_id=a.class_id, section_id=a.section_id,
            target_label=target or "", priority=a.priority, publish_at=a.publish_at, expires_at=a.expires_at,
            status=a.status, is_expired=bool(a.expires_at and a.expires_at <= t), created_by=a.created_by,
            created_by_name=names.get(a.created_by), created_at=a.created_at))
    return out
