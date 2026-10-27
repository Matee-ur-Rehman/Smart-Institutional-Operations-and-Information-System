import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.access import can_access_student
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import require_roles
from app.modules.complaints.models import Complaint, ComplaintComment
from app.modules.notifications.push import dispatch_queued_pushes
from app.modules.notifications.service import admin_user_ids, notify_users
from app.modules.ops_common.core_refs import Student, User
from app.modules.ops_common.pagination import Page, PageParams, page_of, paginate
from app.modules.ops_common.scope import not_found

router = APIRouter(prefix="/complaints", tags=["Complaints & Feedback"])
ADMIN = Depends(require_roles("admin"))
ADMIN_OR_PARENT = Depends(require_roles("admin", "parent"))

Category = Literal["academic", "fee", "teacher", "facility", "transport", "other"]
Kind = Literal["complaint", "feedback", "suggestion"]
Status = Literal["open", "in_review", "resolved", "closed"]
Priority = Literal["low", "normal", "high"]


class ComplaintCreate(BaseModel):
    student_id: uuid.UUID | None = None
    category: Category
    kind: Kind = "complaint"
    subject: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=5000)


class ComplaintUpdate(BaseModel):
    status: Status | None = None
    priority: Priority | None = None
    assigned_to: uuid.UUID | None = None


class CommentCreate(BaseModel):
    message: str = Field(min_length=1, max_length=3000)
    is_internal: bool = False


class CommentOut(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID
    author_name: str | None
    author_role: str | None
    message: str
    is_internal: bool
    created_at: datetime


class ComplaintOut(BaseModel):
    id: uuid.UUID
    ticket_no: str
    submitted_by: uuid.UUID
    submitter_name: str | None
    student_id: uuid.UUID | None
    student_name: str | None
    category: str
    kind: str
    subject: str
    description: str
    status: str
    priority: str
    assigned_to: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ComplaintDetailOut(ComplaintOut):
    comments: list[CommentOut]


def _out(db: Session, complaint: Complaint) -> ComplaintOut:
    submitter = db.get(User, complaint.submitted_by)
    student = db.get(Student, complaint.student_id) if complaint.student_id else None
    return ComplaintOut(
        id=complaint.id, ticket_no=complaint.ticket_no, submitted_by=complaint.submitted_by,
        submitter_name=submitter.full_name if submitter else None, student_id=complaint.student_id,
        student_name=student.full_name if student else None, category=complaint.category, kind=complaint.kind,
        subject=complaint.subject, description=complaint.description, status=complaint.status,
        priority=complaint.priority, assigned_to=complaint.assigned_to, created_at=complaint.created_at,
        updated_at=complaint.updated_at,
    )


def _detail(db: Session, complaint: Complaint, viewer: User) -> ComplaintDetailOut:
    stmt = (
        select(ComplaintComment, User.full_name, User.role)
        .join(User, User.id == ComplaintComment.author_id)
        .where(ComplaintComment.complaint_id == complaint.id)
        .order_by(ComplaintComment.created_at)
    )
    if viewer.role != "admin":
        stmt = stmt.where(ComplaintComment.is_internal.is_(False))  # parents never see internal notes
    comments = [
        CommentOut(id=c.id, author_id=c.author_id, author_name=name, author_role=role, message=c.message,
                   is_internal=c.is_internal, created_at=c.created_at)
        for c, name, role in db.execute(stmt).all()
    ]
    return ComplaintDetailOut(**_out(db, complaint).model_dump(), comments=comments)


def _get_for(db: Session, user: User, complaint_id: uuid.UUID) -> Complaint:
    complaint = db.get(Complaint, complaint_id)
    if complaint is None or (user.role == "parent" and complaint.submitted_by != user.id):
        raise not_found("Ticket")  # another family's ticket looks like it does not exist
    return complaint


@router.post("", response_model=ComplaintDetailOut, status_code=201)
def create_complaint(
    payload: ComplaintCreate, background: BackgroundTasks, db: Session = Depends(get_db),
    user: User = Depends(require_roles("parent")),
):
    if payload.student_id is not None and not can_access_student(user, payload.student_id, db):
        raise not_found("Student")
    complaint = Complaint(
        ticket_no=f"TKT-{date.today():%Y%m}-{uuid.uuid4().hex[:6].upper()}", submitted_by=user.id,
        student_id=payload.student_id, category=payload.category, kind=payload.kind,
        subject=payload.subject.strip(), description=payload.description.strip(),
    )
    db.add(complaint)
    db.flush()
    notify_users(
        db, admin_user_ids(db), title=f"New {complaint.kind}: {complaint.subject}",
        body=f"Ticket {complaint.ticket_no} ({complaint.category}) was submitted.", type="complaint",
        reference_type="complaint", reference_id=complaint.id,
    )
    db.commit()
    if settings.fcm_enabled:
        background.add_task(dispatch_queued_pushes)
    return _detail(db, complaint, user)


@router.get("", response_model=Page[ComplaintOut])
def list_complaints(
    status: Status | None = None,
    category: Category | None = None,
    kind: Kind | None = None,
    assigned_to: uuid.UUID | None = None,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: User = ADMIN_OR_PARENT,
):
    stmt = select(Complaint)
    if user.role == "parent":
        stmt = stmt.where(Complaint.submitted_by == user.id)
    if status:
        stmt = stmt.where(Complaint.status == status)
    if category:
        stmt = stmt.where(Complaint.category == category)
    if kind:
        stmt = stmt.where(Complaint.kind == kind)
    if assigned_to:
        stmt = stmt.where(Complaint.assigned_to == assigned_to)
    rows, total = paginate(db, stmt.order_by(Complaint.created_at.desc()), params)
    return page_of([_out(db, c) for c in rows], total, params)


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = ADMIN):
    def counts(column):
        return {key: n for key, n in db.execute(select(column, func.count(Complaint.id)).group_by(column)).all()}

    return {
        "total": db.scalar(select(func.count(Complaint.id))) or 0,
        "by_status": counts(Complaint.status),
        "by_category": counts(Complaint.category),
        "by_kind": counts(Complaint.kind),
    }


@router.get("/{complaint_id}", response_model=ComplaintDetailOut)
def get_complaint(complaint_id: uuid.UUID, db: Session = Depends(get_db), user: User = ADMIN_OR_PARENT):
    return _detail(db, _get_for(db, user, complaint_id), user)


@router.patch("/{complaint_id}", response_model=ComplaintDetailOut)
def update_complaint(
    complaint_id: uuid.UUID, payload: ComplaintUpdate, background: BackgroundTasks,
    db: Session = Depends(get_db), user: User = ADMIN,
):
    complaint = _get_for(db, user, complaint_id)
    changes = payload.model_dump(exclude_unset=True)
    old_status = complaint.status
    if "assigned_to" in changes and changes["assigned_to"] is not None:
        assignee = db.get(User, changes["assigned_to"])
        if assignee is None or assignee.role != "admin" or not assignee.is_active:
            raise AppError(400, "bad_request", "Tickets can only be assigned to an active admin")
    for field in ("status", "priority"):
        if field in changes and changes[field] is None:
            raise AppError(422, "validation_error", f"{field} cannot be empty")
    for field, value in changes.items():
        setattr(complaint, field, value)
    if complaint.status != old_status:
        notify_users(
            db, [complaint.submitted_by], title=f"Ticket {complaint.ticket_no} is now {complaint.status.replace('_', ' ')}",
            body=complaint.subject, type="complaint", reference_type="complaint", reference_id=complaint.id,
        )
    db.commit()
    if settings.fcm_enabled:
        background.add_task(dispatch_queued_pushes)
    return _detail(db, complaint, user)


@router.post("/{complaint_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(
    complaint_id: uuid.UUID, payload: CommentCreate, background: BackgroundTasks,
    db: Session = Depends(get_db), user: User = ADMIN_OR_PARENT,
):
    complaint = _get_for(db, user, complaint_id)
    if user.role == "parent":
        if complaint.status == "closed":
            raise AppError(409, "conflict", "This ticket is closed")
        if payload.is_internal:
            raise AppError(403, "forbidden", "Only staff can write internal notes")
    comment = ComplaintComment(complaint_id=complaint.id, author_id=user.id, message=payload.message.strip(), is_internal=payload.is_internal)
    db.add(comment)
    db.flush()
    if user.role == "admin" and not comment.is_internal:
        notify_users(
            db, [complaint.submitted_by], title=f"New reply on ticket {complaint.ticket_no}", body=comment.message[:200],
            type="complaint", reference_type="complaint", reference_id=complaint.id,
        )
    elif user.role == "parent" and complaint.assigned_to is not None:
        notify_users(
            db, [complaint.assigned_to], title=f"Parent replied on ticket {complaint.ticket_no}", body=comment.message[:200],
            type="complaint", reference_type="complaint", reference_id=complaint.id,
        )
    db.commit()
    if settings.fcm_enabled:
        background.add_task(dispatch_queued_pushes)
    return CommentOut(
        id=comment.id, author_id=user.id, author_name=user.full_name, author_role=user.role, message=comment.message,
        is_internal=comment.is_internal, created_at=comment.created_at,
    )
