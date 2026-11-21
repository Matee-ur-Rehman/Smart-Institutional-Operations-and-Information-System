"""
Notification service — the cross-module contract (API_CONTRACT.md section 5).
  notify_users(...)  / notify_section(...)
Only inserts rows inside the caller's transaction: never commits, never raises because of push.
"""
import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.scope import audience_user_ids_for_section
from app.modules.foundation.models import User
from app.modules.notifications.models import Notification
from app.modules.notifications.push import initial_push_status


def notify_users(db: Session, user_ids: Iterable[uuid.UUID], title: str, body: str, type: str,
                 reference_type: str | None = None, reference_id: uuid.UUID | None = None) -> int:
    ids = {u for u in user_ids if u is not None}
    if not ids:
        return 0
    active = set(db.scalars(select(User.id).where(User.id.in_(ids), User.is_active)))
    if not active:
        return 0
    status = initial_push_status()
    rows = [Notification(user_id=u, title=title[:200], body=body, type=type, reference_type=reference_type,
                         reference_id=reference_id, push_status=status) for u in active]
    db.add_all(rows)
    db.flush()
    if status == "queued":
        db.info.setdefault("pending_push", []).extend(r.id for r in rows)
    return len(rows)


def notify_section(db: Session, section_id: uuid.UUID, title: str, body: str, type: str,
                   include_parents: bool = True, reference_type: str | None = None,
                   reference_id: uuid.UUID | None = None, include_students: bool = True,
                   include_teachers: bool = False) -> int:
    ids = audience_user_ids_for_section(db, section_id, include_parents=include_parents,
                                        include_students=include_students, include_teachers=include_teachers)
    return notify_users(db, ids, title, body, type, reference_type, reference_id)
