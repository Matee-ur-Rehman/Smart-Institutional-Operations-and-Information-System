import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access import teacher_id_for, teacher_teaches
from app.core.config import settings
from app.core.errors import AppError
from app.modules.homework.models import Assignment
from app.modules.homework.schemas import AssignmentOut
from app.modules.ops_common.core_refs import SchoolClass, Section, Subject, Teacher, User
from app.modules.ops_common.scope import not_found, teacher_for_subject, user_section_ids

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".docx"}
_MAGIC = {
    ".pdf": (b"%PDF",),
    ".png": (b"\x89PNG",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".docx": (b"PK\x03\x04",),
}


def base_query():
    """Assignments joined with the display names the apps need."""
    return (
        select(Assignment, Subject.name, Section.name, SchoolClass.name, User.full_name)
        .join(Subject, Subject.id == Assignment.subject_id)
        .join(Section, Section.id == Assignment.section_id)
        .join(SchoolClass, SchoolClass.id == Section.class_id)
        .join(Teacher, Teacher.id == Assignment.teacher_id)
        .join(User, User.id == Teacher.user_id)
    )


def scope_conditions(user: User, db: Session) -> list:
    """Admin sees everything. Teachers see their sections. Students/parents see only published
    assignments of their own (or their children's) sections."""
    sections = user_section_ids(user, db)
    if sections is None:
        return []
    conditions = [Assignment.section_id.in_(sections)]
    if user.role in ("student", "parent"):
        conditions.append(Assignment.status == "published")
    return conditions


def to_out(row) -> AssignmentOut:
    assignment, subject_name, section_name, class_name, teacher_name = row
    return AssignmentOut(
        id=assignment.id,
        teacher_id=assignment.teacher_id,
        teacher_name=teacher_name,
        section_id=assignment.section_id,
        section_name=f"{class_name}-{section_name}",
        subject_id=assignment.subject_id,
        subject_name=subject_name,
        title=assignment.title,
        description=assignment.description,
        assigned_date=assignment.assigned_date,
        due_date=assignment.due_date,
        max_marks=assignment.max_marks,
        has_attachment=bool(assignment.attachment_path),
        status=assignment.status,
        created_at=assignment.created_at,
    )


def get_visible(db: Session, user: User, assignment_id: uuid.UUID):
    stmt = base_query().where(Assignment.id == assignment_id, *scope_conditions(user, db))
    row = db.execute(stmt).first()
    if row is None:
        raise not_found("Assignment")
    return row


def resolve_teacher_for_create(db: Session, user: User, section_id: uuid.UUID, subject_id: uuid.UUID) -> uuid.UUID:
    if user.role == "teacher":
        teacher_id = teacher_id_for(user, db)
        if not teacher_teaches(db, teacher_id, section_id, subject_id):
            raise AppError(403, "forbidden", "You are not assigned to teach this subject in this section")
        return teacher_id
    teacher_id = teacher_for_subject(db, section_id, subject_id)
    if teacher_id is None:
        raise AppError(400, "bad_request", "No teacher is assigned to this subject in this section")
    return teacher_id


def ensure_can_modify(db: Session, user: User, assignment: Assignment) -> None:
    if user.role == "admin":
        return
    if assignment.teacher_id != teacher_id_for(user, db):
        raise AppError(403, "forbidden", "Only the teacher who created this assignment can change it")


def upload_root() -> Path:
    return Path(settings.upload_dir).resolve()


def save_attachment(assignment: Assignment, file: UploadFile, content: bytes) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise AppError(400, "bad_request", "Allowed file types: PDF, PNG, JPG, DOCX")
    if not any(content.startswith(sig) for sig in _MAGIC[suffix]):
        raise AppError(400, "bad_request", "File content does not match its extension")
    folder = upload_root() / "assignments" / str(assignment.id)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{uuid.uuid4().hex}{suffix}"
    target.write_bytes(content)
    return str(target.relative_to(upload_root()))


def resolve_attachment(assignment: Assignment) -> Path:
    if not assignment.attachment_path:
        raise not_found("Attachment")
    path = (upload_root() / assignment.attachment_path).resolve()
    if upload_root() not in path.parents or not path.is_file():  # also blocks path traversal
        raise not_found("Attachment")
    return path


def delete_attachment_file(assignment: Assignment) -> None:
    if assignment.attachment_path:
        try:
            resolve_attachment(assignment).unlink()
        except AppError:
            pass
