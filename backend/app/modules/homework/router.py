import uuid
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access import can_access_student
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import get_current_user, require_roles
from app.modules.homework import service
from app.modules.homework.models import Assignment
from app.modules.homework.schemas import AssignmentCreate, AssignmentOut, AssignmentUpdate
from app.modules.notifications.push import dispatch_queued_pushes
from app.modules.notifications.service import notify_section
from app.modules.ops_common.base import utcnow
from app.modules.ops_common.core_refs import User
from app.modules.ops_common.pagination import Page, PageParams, page_of, paginate
from app.modules.ops_common.scope import not_found, student_section_id

router = APIRouter(prefix="/assignments", tags=["Homework & Assignments"])


def _announce(db: Session, assignment: Assignment, subject_name: str) -> None:
    notify_section(
        db,
        assignment.section_id,
        title=f"New homework: {assignment.title}",
        body=f"{subject_name} homework is due on {assignment.due_date.isoformat()}.",
        type="homework",
        reference_type="assignment",
        reference_id=assignment.id,
    )


@router.post("", response_model=AssignmentOut, status_code=201)
def create_assignment(
    payload: AssignmentCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    teacher_id = service.resolve_teacher_for_create(db, user, payload.section_id, payload.subject_id)
    assignment = Assignment(
        teacher_id=teacher_id,
        section_id=payload.section_id,
        subject_id=payload.subject_id,
        title=payload.title,
        description=payload.description,
        assigned_date=date.today(),
        due_date=payload.due_date,
        max_marks=payload.max_marks,
        status=payload.status,
    )
    db.add(assignment)
    db.flush()
    row = service.get_visible(db, user, assignment.id)
    if assignment.status == "published":
        _announce(db, assignment, row[1])
    db.commit()
    if settings.fcm_enabled:
        background.add_task(dispatch_queued_pushes)
    return service.to_out(row)


@router.get("", response_model=Page[AssignmentOut])
def list_assignments(
    section_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
    status: str | None = Query(None, pattern="^(draft|published|closed)$"),
    due_from: date | None = None,
    due_to: date | None = None,
    student_id: uuid.UUID | None = Query(None, description="Parents: show one child's homework"),
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = service.base_query().where(*service.scope_conditions(user, db))
    if student_id is not None:
        if not can_access_student(user, student_id, db):
            raise not_found("Student")
        stmt = stmt.where(Assignment.section_id == student_section_id(db, student_id))
    if section_id is not None:
        stmt = stmt.where(Assignment.section_id == section_id)
    if subject_id is not None:
        stmt = stmt.where(Assignment.subject_id == subject_id)
    if status is not None:
        stmt = stmt.where(Assignment.status == status)
    if due_from is not None:
        stmt = stmt.where(Assignment.due_date >= due_from)
    if due_to is not None:
        stmt = stmt.where(Assignment.due_date <= due_to)
    rows, total = paginate(db, stmt.order_by(Assignment.due_date.desc(), Assignment.created_at.desc()), params, scalars=False)
    return page_of([service.to_out(r) for r in rows], total, params)


@router.get("/{assignment_id}", response_model=AssignmentOut)
def get_assignment(assignment_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.to_out(service.get_visible(db, user, assignment_id))


@router.patch("/{assignment_id}", response_model=AssignmentOut)
def update_assignment(
    assignment_id: uuid.UUID,
    payload: AssignmentUpdate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    row = service.get_visible(db, user, assignment_id)
    assignment: Assignment = row[0]
    service.ensure_can_modify(db, user, assignment)
    changes = payload.model_dump(exclude_unset=True)
    if "due_date" in changes and changes["due_date"] is not None and changes["due_date"] < assignment.assigned_date:
        raise AppError(422, "validation_error", "due_date cannot be before the assigned date")
    was_published = assignment.status == "published"
    for field, value in changes.items():
        if value is None and field in ("title", "due_date", "status"):
            raise AppError(422, "validation_error", f"{field} cannot be empty")
        setattr(assignment, field, value)
    db.flush()
    if not was_published and assignment.status == "published":
        _announce(db, assignment, row[1])
    db.commit()
    if settings.fcm_enabled:
        background.add_task(dispatch_queued_pushes)
    return service.to_out(service.get_visible(db, user, assignment_id))


@router.delete("/{assignment_id}", status_code=204)
def delete_assignment(
    assignment_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    assignment: Assignment = service.get_visible(db, user, assignment_id)[0]
    service.ensure_can_modify(db, user, assignment)
    service.delete_attachment_file(assignment)
    db.delete(assignment)
    db.commit()


@router.post("/{assignment_id}/attachment", response_model=AssignmentOut)
async def upload_attachment(
    assignment_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    assignment: Assignment = service.get_visible(db, user, assignment_id)[0]
    service.ensure_can_modify(db, user, assignment)
    limit = settings.max_upload_mb * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise AppError(413, "payload_too_large", f"File is larger than {settings.max_upload_mb} MB")
    if not content:
        raise AppError(400, "bad_request", "File is empty")
    new_path = service.save_attachment(assignment, file, content)
    service.delete_attachment_file(assignment)
    assignment.attachment_path = new_path
    db.commit()
    return service.to_out(service.get_visible(db, user, assignment_id))


@router.get("/{assignment_id}/attachment")
def download_attachment(assignment_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assignment: Assignment = service.get_visible(db, user, assignment_id)[0]
    path = service.resolve_attachment(assignment)
    return FileResponse(path, filename=f"homework-{assignment.id.hex[:8]}{path.suffix}")
