import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams, page_params, paginate
from app.common.scope import (
    admin_user_ids, audience_user_ids_for_section, linked_child, parent_user_ids_of_student, section_labels,
    teacher_section_ids, user_names,
)
from app.common.timeutil import school_now, school_today
from app.core.access import parent_child_ids, teacher_id_for
from app.core.database import get_db
from app.core.errors import Conflict, NotFound, ValidationFailed, field_error
from app.core.security import require_roles
from app.modules.attendance.models import Attendance
from app.modules.foundation.models import Student, User
from app.modules.leave.models import LeaveRequest
from app.modules.leave.schemas import DecisionBody, LeaveCreate, LeaveOut, LStatus
from app.modules.notifications.service import notify_users

router = APIRouter(prefix="/leave-requests", tags=["Leave Requests"])
parent_only = Depends(require_roles("parent"))
staff = Depends(require_roles("admin", "teacher"))
any_leave_role = Depends(require_roles("admin", "teacher", "parent"))
MAX_DAYS = 30
BACKDATE_DAYS = 7


def _out(db: Session, rows: list[LeaveRequest]) -> list[LeaveOut]:
    studs = {s.id: s for s in db.scalars(select(Student).where(Student.id.in_({r.student_id for r in rows})))}
    labels = section_labels(db, {s.section_id for s in studs.values()})
    names = user_names(db, {r.applied_by for r in rows} | {r.decided_by for r in rows if r.decided_by})
    return [LeaveOut(
        id=r.id, student_id=r.student_id, student_name=studs[r.student_id].full_name, roll_no=studs[r.student_id].roll_no,
        section_id=studs[r.student_id].section_id, section_label=labels.get(studs[r.student_id].section_id),
        applied_by_name=names.get(r.applied_by), from_date=r.from_date, to_date=r.to_date,
        days=(r.to_date - r.from_date).days + 1, leave_type=r.leave_type, reason=r.reason, status=r.status,
        decided_by_name=names.get(r.decided_by) if r.decided_by else None, decided_at=r.decided_at,
        decision_note=r.decision_note, created_at=r.created_at) for r in rows]


def _scoped(user: User, db: Session):
    stmt = select(LeaveRequest)
    if user.role == "admin":
        return stmt
    if user.role == "parent":
        kids = parent_child_ids(user, db)
        return stmt.where(LeaveRequest.student_id.in_(kids)) if kids else stmt.where(False)
    secs = teacher_section_ids(db, teacher_id_for(user, db))
    return stmt.where(LeaveRequest.student_id.in_(select(Student.id).where(Student.section_id.in_(secs)))) if secs else stmt.where(False)


def _get(db: Session, user: User, leave_id: uuid.UUID) -> LeaveRequest:
    lr = db.scalar(_scoped(user, db).where(LeaveRequest.id == leave_id))
    if lr is None:
        raise NotFound("Leave request not found")
    return lr


@router.post("", response_model=LeaveOut, status_code=201)
def apply_for_leave(body: LeaveCreate, user: User = parent_only, db: Session = Depends(get_db)):
    st = linked_child(user, db, body.student_id)
    today = school_today()
    errors = []
    if body.from_date < today - timedelta(days=BACKDATE_DAYS):
        errors.append(field_error("from_date", f"Leave cannot start more than {BACKDATE_DAYS} days in the past"))
    if (body.to_date - body.from_date).days + 1 > MAX_DAYS:
        errors.append(field_error("to_date", f"A single request can cover at most {MAX_DAYS} days"))
    if errors:
        raise ValidationFailed(errors=errors)
    clash = db.scalar(select(LeaveRequest.id).where(
        LeaveRequest.student_id == st.id, LeaveRequest.status.in_(("pending", "approved")),
        LeaveRequest.from_date <= body.to_date, LeaveRequest.to_date >= body.from_date).limit(1))
    if clash:
        raise Conflict("This child already has a pending or approved leave overlapping these dates", code="leave_overlap")
    lr = LeaveRequest(student_id=st.id, applied_by=user.id, from_date=body.from_date, to_date=body.to_date,
                      leave_type=body.leave_type, reason=body.reason.strip())
    db.add(lr)
    db.flush()
    audience = set(admin_user_ids(db)) | set(audience_user_ids_for_section(
        db, st.section_id, include_parents=False, include_students=False, include_teachers=True))
    notify_users(db, audience, "New leave request",
                 f"{st.full_name}: {lr.from_date:%d %b} to {lr.to_date:%d %b %Y} ({lr.leave_type})", "leave", "leave", lr.id)
    db.commit()
    return _out(db, [lr])[0]


@router.get("", response_model=Page[LeaveOut])
def list_leave(status: LStatus | None = None, student_id: uuid.UUID | None = None, section_id: uuid.UUID | None = None,
               from_date: date | None = None, to_date: date | None = None, params: PageParams = Depends(page_params),
               user: User = any_leave_role, db: Session = Depends(get_db)):
    stmt = _scoped(user, db)
    if student_id:
        stmt = stmt.where(LeaveRequest.student_id == student_id)
    if section_id:
        stmt = stmt.where(LeaveRequest.student_id.in_(select(Student.id).where(Student.section_id == section_id)))
    if status:
        stmt = stmt.where(LeaveRequest.status == status)
    if from_date:
        stmt = stmt.where(LeaveRequest.to_date >= from_date)
    if to_date:
        stmt = stmt.where(LeaveRequest.from_date <= to_date)
    rows, total = paginate(db, stmt.order_by(LeaveRequest.created_at.desc()), params)
    return Page(items=_out(db, [r[0] for r in rows]), total=total, page=params.page, page_size=params.page_size)


@router.get("/{leave_id}", response_model=LeaveOut)
def get_leave(leave_id: uuid.UUID, user: User = any_leave_role, db: Session = Depends(get_db)):
    return _out(db, [_get(db, user, leave_id)])[0]


def _decide(db: Session, user: User, leave_id: uuid.UUID, status: str, note: str | None) -> LeaveRequest:
    lr = _get(db, user, leave_id)
    if lr.status != "pending":
        raise Conflict(f"This request is already {lr.status}", code="already_decided")
    lr.status, lr.decided_by, lr.decided_at, lr.decision_note = status, user.id, school_now(), note
    return lr


@router.post("/{leave_id}/approve", response_model=LeaveOut)
def approve(leave_id: uuid.UUID, body: DecisionBody | None = None, user: User = staff, db: Session = Depends(get_db)):
    lr = _decide(db, user, leave_id, "approved", body.note if body else None)
    # days already marked absent inside the approved range become approved-leave days
    db.execute(update(Attendance).where(
        Attendance.student_id == lr.student_id, Attendance.status == "absent",
        Attendance.attendance_date.between(lr.from_date, min(lr.to_date, school_today()))).values(status="leave"))
    _notify_parents(db, lr, "approved")
    db.commit()
    return _out(db, [lr])[0]


@router.post("/{leave_id}/reject", response_model=LeaveOut)
def reject(leave_id: uuid.UUID, body: DecisionBody, user: User = staff, db: Session = Depends(get_db)):
    if not body.note or len(body.note.strip()) < 3:
        raise ValidationFailed(errors=[field_error("note", "Please give a short reason for rejecting")])
    lr = _decide(db, user, leave_id, "rejected", body.note.strip())
    _notify_parents(db, lr, "rejected")
    db.commit()
    return _out(db, [lr])[0]


@router.post("/{leave_id}/cancel", response_model=LeaveOut)
def cancel(leave_id: uuid.UUID, user: User = parent_only, db: Session = Depends(get_db)):
    lr = _get(db, user, leave_id)
    if lr.status != "pending":
        raise Conflict("Only a pending request can be cancelled", code="not_pending")
    lr.status = "cancelled"
    db.commit()
    return _out(db, [lr])[0]


def _notify_parents(db: Session, lr: LeaveRequest, verdict: str) -> None:
    st = db.get(Student, lr.student_id)
    notify_users(db, parent_user_ids_of_student(db, lr.student_id), f"Leave request {verdict}",
                 f"Leave for {st.full_name} ({lr.from_date:%d %b} to {lr.to_date:%d %b %Y}) was {verdict}."
                 + (f" Note: {lr.decision_note}" if lr.decision_note else ""), "leave", "leave", lr.id)
