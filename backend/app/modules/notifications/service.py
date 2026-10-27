"""Notification workflow. This is the cross-module API that Member 1 calls (docs/API_CONTRACT.md
section 5): notify_users(...) and notify_section(...).

These functions only INSERT rows in the caller's transaction. They never commit and never raise
because of push problems. The in-app inbox always works; push is optional (see push.py).
"""
import uuid
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.notifications.models import Notification
from app.modules.ops_common.core_refs import Parent, Section, Student, StudentParent, User


def notify_users(
    db: Session,
    user_ids: Iterable[uuid.UUID],
    title: str,
    body: str,
    type: str,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
) -> int:
    """Create one notification per distinct recipient. Returns how many were created."""
    unique_ids = {uid for uid in user_ids if uid is not None}
    if not unique_ids:
        return 0
    push_status = "queued" if settings.fcm_enabled else "disabled"
    db.add_all(
        Notification(
            user_id=uid,
            title=title[:200],
            body=body,
            type=type,
            reference_type=reference_type,
            reference_id=reference_id,
            push_status=push_status,
        )
        for uid in unique_ids
    )
    db.flush()
    return len(unique_ids)


def parent_user_ids(db: Session, student_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
    ids = list(student_ids)
    if not ids:
        return set()
    stmt = (
        select(Parent.user_id)
        .join(StudentParent, StudentParent.parent_id == Parent.id)
        .where(StudentParent.student_id.in_(ids))
    )
    return set(db.scalars(stmt))


def _student_rows(db: Session, section_id: uuid.UUID | None = None, class_id: uuid.UUID | None = None):
    stmt = (
        select(Student.id, Student.user_id)
        .join(Section, Section.id == Student.section_id)
        .where(Student.is_active.is_(True))
    )
    if section_id is not None:
        stmt = stmt.where(Student.section_id == section_id)
    elif class_id is not None:
        stmt = stmt.where(Section.class_id == class_id)
    return db.execute(stmt).all()


def section_recipient_ids(
    db: Session,
    section_id: uuid.UUID | None = None,
    class_id: uuid.UUID | None = None,
    include_students: bool = True,
    include_parents: bool = True,
) -> set[uuid.UUID]:
    rows = _student_rows(db, section_id, class_id)
    recipients: set[uuid.UUID] = set()
    if include_students:
        recipients |= {user_id for _, user_id in rows if user_id is not None}
    if include_parents:
        recipients |= parent_user_ids(db, [student_id for student_id, _ in rows])
    return recipients


def notify_section(
    db: Session,
    section_id: uuid.UUID,
    title: str,
    body: str,
    type: str,
    include_parents: bool = True,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
) -> int:
    recipients = section_recipient_ids(db, section_id=section_id, include_parents=include_parents)
    return notify_users(db, recipients, title, body, type, reference_type, reference_id)


def users_for_audience(
    db: Session,
    audience: str,
    class_id: uuid.UUID | None = None,
    section_id: uuid.UUID | None = None,
) -> set[uuid.UUID]:
    """Resolve an announcement/event audience (all, teachers, students, parents, class) to user ids."""
    if audience == "class":
        return section_recipient_ids(db, section_id=section_id, class_id=class_id)
    stmt = select(User.id).where(User.is_active.is_(True))
    role = {"teachers": "teacher", "students": "student", "parents": "parent"}.get(audience)
    if role is not None:
        stmt = stmt.where(User.role == role)
    return set(db.scalars(stmt))


def admin_user_ids(db: Session) -> set[uuid.UUID]:
    return set(db.scalars(select(User.id).where(User.role == "admin", User.is_active.is_(True))))
