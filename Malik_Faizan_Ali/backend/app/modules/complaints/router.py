import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams, page_params, paginate
from app.common.scope import admin_user_ids, linked_child
from app.core.database import get_db
from app.core.errors import Conflict, NotFound, ValidationFailed, field_error
from app.core.security import require_roles
from app.modules.complaints import service
from app.modules.complaints.models import Complaint, ComplaintComment
from app.modules.complaints.schemas import (
    CommentCreate, ComplaintCreate, ComplaintOut, ComplaintUpdate, Category, CStatus, Kind,
)
from app.modules.foundation.models import User
from app.modules.notifications.service import notify_users

router = APIRouter(prefix="/complaints", tags=["Complaints & Feedback"])
admin_only = Depends(require_roles("admin"))
admin_parent = Depends(require_roles("admin", "parent"))


@router.post("", response_model=ComplaintOut, status_code=201)
def submit_complaint(body: ComplaintCreate, user: User = Depends(require_roles("parent")), db: Session = Depends(get_db)):
    if body.student_id:
        linked_child(user, db, body.student_id)          # 404 for anyone else's child
    c = Complaint(ticket_no=service.next_ticket(db), submitted_by=user.id, student_id=body.student_id,
                  category=body.category, kind=body.kind, subject=body.subject.strip(), description=body.description.strip())
    db.add(c)
    db.flush()
    notify_users(db, admin_user_ids(db), f"New {body.kind}: {c.ticket_no}", f"{user.full_name}: {c.subject}",
                 "complaint", "complaint", c.id)
    db.commit()
    return service.to_out(db, [c], user, detail=True)[0]


@router.get("/summary")
def summary(user: User = admin_only, db: Session = Depends(get_db)):
    def group(col):
        return {k: n for k, n in db.execute(select(col, func.count()).group_by(col)).all()}
    total = db.scalar(select(func.count()).select_from(Complaint)) or 0
    return {"total": total, "by_status": group(Complaint.status), "by_category": group(Complaint.category),
            "by_kind": group(Complaint.kind), "by_priority": group(Complaint.priority),
            "unassigned_open": db.scalar(select(func.count()).select_from(Complaint).where(
                Complaint.assigned_to.is_(None), Complaint.status.in_(("open", "in_review")))) or 0}


def _scoped(user: User):
    stmt = select(Complaint)
    return stmt if user.role == "admin" else stmt.where(Complaint.submitted_by == user.id)


@router.get("", response_model=Page[ComplaintOut])
def list_complaints(status: CStatus | None = None, category: Category | None = None, kind: Kind | None = None,
                    assigned_to: uuid.UUID | None = None, params: PageParams = Depends(page_params),
                    user: User = admin_parent, db: Session = Depends(get_db)):
    stmt = _scoped(user)
    if status:
        stmt = stmt.where(Complaint.status == status)
    if category:
        stmt = stmt.where(Complaint.category == category)
    if kind:
        stmt = stmt.where(Complaint.kind == kind)
    if assigned_to:
        stmt = stmt.where(Complaint.assigned_to == assigned_to)
    rows, total = paginate(db, stmt.order_by(Complaint.created_at.desc(), Complaint.id), params)
    return Page(items=service.to_out(db, [r[0] for r in rows], user), total=total, page=params.page, page_size=params.page_size)


def _get(db: Session, user: User, cid: uuid.UUID) -> Complaint:
    c = db.scalar(_scoped(user).where(Complaint.id == cid))
    if c is None:
        raise NotFound("Ticket not found")
    return c


@router.get("/{complaint_id}", response_model=ComplaintOut)
def get_complaint(complaint_id: uuid.UUID, user: User = admin_parent, db: Session = Depends(get_db)):
    return service.to_out(db, [_get(db, user, complaint_id)], user, detail=True)[0]


@router.patch("/{complaint_id}", response_model=ComplaintOut)
def update_complaint(complaint_id: uuid.UUID, body: ComplaintUpdate, user: User = admin_only, db: Session = Depends(get_db)):
    c = _get(db, user, complaint_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("assigned_to"):
        assignee = db.get(User, data["assigned_to"])
        if assignee is None or not assignee.is_active or assignee.role not in ("admin", "teacher"):
            raise ValidationFailed(errors=[field_error("assigned_to", "Assignee must be an active admin or teacher")])
    status_changed = "status" in data and data["status"] is not None and data["status"] != c.status
    if data.get("status"):
        c.status = data["status"]
    if data.get("priority"):
        c.priority = data["priority"]
    if "assigned_to" in data:
        c.assigned_to = data["assigned_to"]
    db.flush()
    if status_changed:
        notify_users(db, [c.submitted_by], f"Ticket {c.ticket_no}: {service.STATUS_LABEL[c.status]}",
                     f"The status of your {c.kind} \"{c.subject}\" is now {service.STATUS_LABEL[c.status].lower()}.",
                     "complaint", "complaint", c.id)
    db.commit()
    return service.to_out(db, [c], user, detail=True)[0]


@router.post("/{complaint_id}/comments", response_model=ComplaintOut, status_code=201)
def add_comment(complaint_id: uuid.UUID, body: CommentCreate, user: User = admin_parent, db: Session = Depends(get_db)):
    c = _get(db, user, complaint_id)
    if c.status == "closed":
        raise Conflict("This ticket is closed", code="ticket_closed")
    internal = body.is_internal and user.role == "admin"      # parents can never write internal notes
    db.add(ComplaintComment(complaint_id=c.id, author_id=user.id, message=body.message.strip(), is_internal=internal))
    db.flush()
    if user.role == "admin" and not internal:
        notify_users(db, [c.submitted_by], f"Reply on ticket {c.ticket_no}", body.message.strip()[:200],
                     "complaint", "complaint", c.id)
    elif user.role == "parent":
        notify_users(db, [c.assigned_to] if c.assigned_to else admin_user_ids(db), f"New reply on {c.ticket_no}",
                     f"{user.full_name}: {body.message.strip()[:160]}", "complaint", "complaint", c.id)
    db.commit()
    return service.to_out(db, [c], user, detail=True)[0]
