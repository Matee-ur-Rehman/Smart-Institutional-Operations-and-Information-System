import re
import shutil
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.scope import section_labels, subject_names, teacher_names
from app.common.timeutil import school_today
from app.core.config import settings
from app.core.errors import BadRequest, PayloadTooLarge
from app.modules.homework.models import Assignment
from app.modules.homework.schemas import AssignmentOut

ALLOWED_EXT = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def _magic_ok(ext: str, head: bytes) -> bool:
    if ext == ".pdf":
        return head.startswith(b"%PDF")
    if ext == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in (".jpg", ".jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == ".docx":
        return head.startswith(b"PK\x03\x04")
    return False


def validate_upload(filename: str, content: bytes) -> str:
    """Returns the safe extension, or raises BadRequest/PayloadTooLarge."""
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise BadRequest("Only PDF, PNG, JPG and DOCX files are allowed", code="unsupported_file_type")
    if len(content) == 0:
        raise BadRequest("The uploaded file is empty")
    if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise PayloadTooLarge(f"File is larger than {settings.MAX_UPLOAD_MB} MB")
    if not _magic_ok(ext, content[:16]):
        raise BadRequest("File content does not match its extension", code="unsupported_file_type")
    return ext


def attachment_abs_path(rel: str) -> Path:
    base = settings.upload_path.resolve()
    p = (base / rel).resolve()
    if base not in p.parents:  # path traversal guard
        raise BadRequest("Invalid attachment path")
    return p


def store_attachment(assignment_id: uuid.UUID, ext: str, content: bytes, old_rel: str | None) -> str:
    rel = f"assignments/{assignment_id}/{uuid.uuid4().hex}{ext}"
    dest = attachment_abs_path(rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    if old_rel:
        try:
            attachment_abs_path(old_rel).unlink(missing_ok=True)
        except BadRequest:
            pass
    return rel


def remove_attachment_dir(assignment_id: uuid.UUID) -> None:
    shutil.rmtree(attachment_abs_path(f"assignments/{assignment_id}"), ignore_errors=True)


def download_name(title: str, ext: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_")[:60] or "attachment"
    return f"{slug}{ext}"


def to_out(db: Session, rows: list[Assignment]) -> list[AssignmentOut]:
    sec = section_labels(db, {a.section_id for a in rows})
    sub = subject_names(db, {a.subject_id for a in rows})
    tea = teacher_names(db, {a.teacher_id for a in rows})
    today = school_today()
    out = []
    for a in rows:
        days_left = (a.due_date - today).days
        out.append(AssignmentOut(
            id=a.id, teacher_id=a.teacher_id, teacher_name=tea.get(a.teacher_id), section_id=a.section_id,
            section_label=sec.get(a.section_id), subject_id=a.subject_id, subject_name=sub.get(a.subject_id),
            title=a.title, description=a.description, assigned_date=a.assigned_date, due_date=a.due_date,
            max_marks=a.max_marks, has_attachment=bool(a.attachment_path), status=a.status,
            is_overdue=a.status == "published" and days_left < 0, days_left=days_left, created_at=a.created_at))
    return out


def get_assignments_for_section(db: Session, section_id: uuid.UUID, due_from: date | None = None) -> list[Assignment]:
    stmt = select(Assignment).where(Assignment.section_id == section_id, Assignment.status != "draft")
    if due_from:
        stmt = stmt.where(Assignment.due_date >= due_from)
    return list(db.scalars(stmt.order_by(Assignment.due_date)))
