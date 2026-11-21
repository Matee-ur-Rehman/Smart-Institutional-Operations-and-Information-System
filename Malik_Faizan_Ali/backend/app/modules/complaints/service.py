import uuid

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.common.scope import student_labels, user_names
from app.common.timeutil import school_today
from app.modules.complaints.models import Complaint, ComplaintComment
from app.modules.complaints.schemas import CommentOut, ComplaintOut
from app.modules.foundation.models import User

STATUS_LABEL = {"open": "Open", "in_review": "In review", "resolved": "Resolved", "closed": "Closed"}


def next_ticket(db: Session) -> str:
    n = db.scalar(text("SELECT nextval('ticket_no_seq')"))
    return f"CMP-{school_today().year}-{n:05d}"


def to_out(db: Session, rows: list[Complaint], viewer: User, detail: bool = False) -> list[ComplaintOut]:
    if not rows:
        return []
    ids = [r.id for r in rows]
    names = user_names(db, {r.submitted_by for r in rows} | {r.assigned_to for r in rows if r.assigned_to})
    studs = student_labels(db, {r.student_id for r in rows if r.student_id})
    comment_stmt = select(ComplaintComment).where(ComplaintComment.complaint_id.in_(ids))
    if viewer.role != "admin":
        comment_stmt = comment_stmt.where(ComplaintComment.is_internal.is_(False))
    comments = list(db.scalars(comment_stmt.order_by(ComplaintComment.created_at, ComplaintComment.id)))
    counts: dict[uuid.UUID, int] = {}
    by: dict[uuid.UUID, list[ComplaintComment]] = {}
    for c in comments:
        counts[c.complaint_id] = counts.get(c.complaint_id, 0) + 1
        by.setdefault(c.complaint_id, []).append(c)
    authors = {}
    if detail and comments:
        authors = {u.id: u for u in db.scalars(select(User).where(User.id.in_({c.author_id for c in comments})))}
    out = []
    for r in rows:
        s = studs.get(r.student_id, {}) if r.student_id else {}
        out.append(ComplaintOut(
            id=r.id, ticket_no=r.ticket_no, submitted_by=r.submitted_by, submitted_by_name=names.get(r.submitted_by),
            student_id=r.student_id, student_name=s.get("full_name"), student_section=s.get("section_label"),
            category=r.category, kind=r.kind, subject=r.subject, description=r.description, status=r.status,
            priority=r.priority, assigned_to=r.assigned_to, assigned_to_name=names.get(r.assigned_to),
            comment_count=counts.get(r.id, 0), created_at=r.created_at, updated_at=r.updated_at,
            comments=[CommentOut(id=c.id, author_id=c.author_id, author_name=authors[c.author_id].full_name,
                                 author_role=authors[c.author_id].role, message=c.message, is_internal=c.is_internal,
                                 created_at=c.created_at) for c in by.get(r.id, [])] if detail else None))
    return out
