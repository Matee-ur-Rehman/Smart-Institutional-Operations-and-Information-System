"""Audience helpers shared by announcements and calendar events (audience: all|teachers|students|parents|class)."""
import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.common.scope import audience_user_ids_for_section, section_class_ids, visible_section_ids
from app.modules.foundation.models import Section, User

_NONE = [uuid.UUID(int=0)]


def audience_visibility_clause(model, user: User, db: Session):
    """SQL condition: rows of `model` (needs .audience, .section_id, optional .class_id) meant for `user`."""
    role_audience = {"teacher": "teachers", "student": "students", "parent": "parents"}.get(user.role)
    sections = visible_section_ids(user, db) or set()
    class_ids = set(section_class_ids(db, sections).values())
    by_section = and_(model.section_id.is_not(None), model.section_id.in_(list(sections) or _NONE))
    if hasattr(model, "class_id"):
        by_class = and_(model.section_id.is_(None), model.class_id.in_(list(class_ids) or _NONE))
        class_match = and_(model.audience == "class", or_(by_section, by_class))
    else:
        class_match = and_(model.audience == "class", by_section)
    return or_(model.audience == "all", model.audience == role_audience, class_match)


def audience_user_ids(db: Session, audience: str, class_id: uuid.UUID | None, section_id: uuid.UUID | None) -> list[uuid.UUID]:
    if audience == "all":
        return list(db.scalars(select(User.id).where(User.role.in_(("teacher", "student", "parent")), User.is_active)))
    if audience in ("teachers", "students", "parents"):
        return list(db.scalars(select(User.id).where(User.role == audience[:-1], User.is_active)))
    section_ids = [section_id] if section_id else list(db.scalars(select(Section.id).where(Section.class_id == class_id)))
    ids: set[uuid.UUID] = set()
    for sid in section_ids:
        ids.update(audience_user_ids_for_section(db, sid, include_teachers=True))
    return list(ids)
