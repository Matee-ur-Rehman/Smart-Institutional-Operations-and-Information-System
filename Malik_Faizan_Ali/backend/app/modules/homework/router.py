import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import and_, or_, select, tuple_
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams, page_params, paginate
from app.common.scope import (
    child_section_ids, current_year_id, linked_child, own_student, section_of_student, teacher_pairs,
)
from app.common.timeutil import school_today
from app.core.access import can_access_student, teacher_id_for, teacher_teaches
from app.core.database import get_db
from app.core.errors import BadRequest, Forbidden, NotFound, ValidationFailed, field_error
from app.core.security import get_current_user, require_roles
from app.modules.foundation.models import Section, Subject, Teacher, TeacherAssignment, User
from app.modules.homework import service
from app.modules.homework.models import Assignment
from app.modules.homework.schemas import AssignmentCreate, AssignmentOut, AssignmentUpdate
from app.modules.notifications.service import notify_section

router = APIRouter(prefix="/assignments", tags=["Homework & Assignments"])
staff = Depends(require_roles("admin", "teacher"))


def _notify_published(db: Session, a: Assignment) -> None:
    subj = service.subject_names(db, [a.subject_id]).get(a.subject_id, "Homework")
    notify_section(db, a.section_id, f"New homework: {subj}", f"{a.title} — due {a.due_date.strftime('%d %b %Y')}",
                   "homework", reference_type="assignment", reference_id=a.id)


@router.post("", response_model=AssignmentOut, status_code=201)
def create_assignment(body: AssignmentCreate, user: User = staff, db: Session = Depends(get_db)):
    errors = []
    if body.due_date < school_today():
        errors.append(field_error("due_date", "Due date cannot be in the past"))
    if db.get(Section, body.section_id) is None:
        errors.append(field_error("section_id", "Section does not exist"))
    if db.get(Subject, body.subject_id) is None:
        errors.append(field_error("subject_id", "Subject does not exist"))
    if errors:
        raise ValidationFailed(errors=errors)

    if user.role == "teacher":
        teacher_id = teacher_id_for(user, db)
        if not teacher_teaches(db, teacher_id, body.section_id, body.subject_id):
            raise Forbidden("You do not teach this subject in this section")
    else:  # admin: the owner is the teacher assigned to that section+subject
        teacher_id = db.scalar(select(TeacherAssignment.teacher_id).where(
            TeacherAssignment.section_id == body.section_id, TeacherAssignment.subject_id == body.subject_id,
            TeacherAssignment.academic_year_id == current_year_id(db)))
        if teacher_id is None:
            raise BadRequest("No teacher is assigned to this subject in this section", code="no_teacher_assigned")

    a = Assignment(teacher_id=teacher_id, section_id=body.section_id, subject_id=body.subject_id,
                   title=body.title.strip(), description=body.description, due_date=body.due_date,
                   assigned_date=school_today(), max_marks=body.max_marks, status=body.status)
    db.add(a)
    db.flush()
    if a.status == "published":
        _notify_published(db, a)
    db.commit()
    return service.to_out(db, [a])[0]


def _scoped(user: User, db: Session):
    """Base statement restricted (in SQL) to what the caller may see."""
    stmt = select(Assignment)
    if user.role == "admin":
        return stmt
    if user.role == "teacher":
        tid = db.scalar(select(Teacher.id).where(Teacher.user_id == user.id, Teacher.is_active))
        pairs = teacher_pairs(db, tid) if tid else set()
        cond = [tuple_(Assignment.section_id, Assignment.subject_id).in_(list(pairs))] if pairs else []
        if tid:
            cond.append(Assignment.teacher_id == tid)
        return stmt.where(or_(*cond)) if cond else stmt.where(False)
    stmt = stmt.where(Assignment.status.in_(("published", "closed")))
    if user.role == "student":
        st = own_student(user, db)
        return stmt.where(Assignment.section_id == st.section_id) if st else stmt.where(False)
    secs = child_section_ids(user, db)
    return stmt.where(Assignment.section_id.in_(list(secs))) if secs else stmt.where(False)


@router.get("", response_model=Page[AssignmentOut])
def list_assignments(
    section_id: uuid.UUID | None = None, subject_id: uuid.UUID | None = None,
    status: Literal["draft", "published", "closed"] | None = None, due_from: date | None = None,
    due_to: date | None = None, student_id: uuid.UUID | None = None,
    sort: Literal["due_asc", "due_desc"] = "due_desc",
    params: PageParams = Depends(page_params), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    stmt = _scoped(user, db)
    if student_id:
        if user.role == "parent":
            linked_child(user, db, student_id)
        elif not can_access_student(user, student_id, db):
            raise NotFound("Student not found")
        stmt = stmt.where(Assignment.section_id == section_of_student(db, student_id))
    if section_id:
        stmt = stmt.where(Assignment.section_id == section_id)
    if subject_id:
        stmt = stmt.where(Assignment.subject_id == subject_id)
    if status:
        stmt = stmt.where(Assignment.status == status)
    if due_from:
        stmt = stmt.where(Assignment.due_date >= due_from)
    if due_to:
        stmt = stmt.where(Assignment.due_date <= due_to)
    order = Assignment.due_date.asc() if sort == "due_asc" else Assignment.due_date.desc()
    rows, total = paginate(db, stmt.order_by(order, Assignment.created_at.desc(), Assignment.id), params)
    return Page(items=service.to_out(db, [r[0] for r in rows]), total=total, page=params.page, page_size=params.page_size)


def _visible(db: Session, user: User, assignment_id: uuid.UUID) -> Assignment:
    a = db.scalar(_scoped(user, db).where(Assignment.id == assignment_id))
    if a is None:
        raise NotFound("Assignment not found")
    return a


def _writable(db: Session, user: User, assignment_id: uuid.UUID) -> Assignment:
    a = _visible(db, user, assignment_id)
    if user.role == "teacher" and a.teacher_id != teacher_id_for(user, db):
        raise Forbidden("You can only change your own assignments")
    return a


@router.get("/{assignment_id}", response_model=AssignmentOut)
def get_assignment(assignment_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.to_out(db, [_visible(db, user, assignment_id)])[0]


@router.patch("/{assignment_id}", response_model=AssignmentOut)
def update_assignment(assignment_id: uuid.UUID, body: AssignmentUpdate, user: User = staff, db: Session = Depends(get_db)):
    a = _writable(db, user, assignment_id)
    data = body.model_dump(exclude_unset=True)
    was_published = a.status == "published"
    if "due_date" in data and data["due_date"] is not None and data["due_date"] != a.due_date:
        if data["due_date"] < school_today():
            raise ValidationFailed(errors=[field_error("due_date", "Due date cannot be in the past")])
        if data["due_date"] < a.assigned_date:
            raise ValidationFailed(errors=[field_error("due_date", "Due date cannot be before the assigned date")])
    for k, v in data.items():
        if v is None and k in ("title", "due_date", "status"):
            continue
        setattr(a, k, v.strip() if k == "title" else v)
    db.flush()
    if a.status == "published" and not was_published:
        _notify_published(db, a)
    db.commit()
    return service.to_out(db, [a])[0]


@router.delete("/{assignment_id}", status_code=204)
def delete_assignment(assignment_id: uuid.UUID, user: User = staff, db: Session = Depends(get_db)):
    a = _writable(db, user, assignment_id)
    db.delete(a)
    db.commit()
    service.remove_attachment_dir(assignment_id)


@router.post("/{assignment_id}/attachment", response_model=AssignmentOut)
async def upload_attachment(assignment_id: uuid.UUID, file: UploadFile = File(...), user: User = staff,
                            db: Session = Depends(get_db)):
    a = _writable(db, user, assignment_id)
    content = await file.read(service.settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    ext = service.validate_upload(file.filename or "", content)
    a.attachment_path = service.store_attachment(a.id, ext, content, a.attachment_path)
    db.commit()
    return service.to_out(db, [a])[0]


@router.get("/{assignment_id}/attachment")
def download_attachment(assignment_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = _visible(db, user, assignment_id)
    if not a.attachment_path:
        raise NotFound("This assignment has no attachment")
    path = service.attachment_abs_path(a.attachment_path)
    if not path.is_file():
        raise NotFound("Attachment file is missing")
    ext = path.suffix.lower()
    return FileResponse(path, media_type=service.ALLOWED_EXT.get(ext, "application/octet-stream"),
                        filename=service.download_name(a.title, ext))
